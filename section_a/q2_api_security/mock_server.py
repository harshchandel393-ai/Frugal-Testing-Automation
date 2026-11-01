
import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse


app = FastAPI(title="Frugal Testing - Q2 Security Mock API")

# Local demonstration key only. Never use this hard-coded key in production.
SECRET_KEY = b"frugal-testing-q2-local-demo-secret"

transactions = {}


def current_timestamp_us():
    """Return current Unix timestamp in microseconds."""
    return time.time_ns() // 1000


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_challenge(transaction_id: str, transaction: dict):
    """Create a signed, short-lived, one-time challenge."""

    challenge_number = len(transaction["challenges"]) + 1

    payload = {
        "transaction_id": transaction_id,
        "nonce": secrets.token_urlsafe(24),
        "server_timestamp_us": current_timestamp_us(),
        "salt_sequence": (
            f"Q2-SALT-{challenge_number}-{secrets.token_hex(6)}"
        ),
        "expires_at_us": current_timestamp_us() + 120_000_000
    }

    encoded_payload = b64url_encode(
        json.dumps(payload, separators=(",", ":")).encode()
    )

    signature = hmac.new(
        SECRET_KEY,
        encoded_payload.encode(),
        hashlib.sha256
    ).hexdigest()

    token = f"{encoded_payload}.{signature}"

    transaction["challenges"][payload["nonce"]] = payload

    return token, payload


def decode_challenge(token: str):
    """Verify and decode the signed challenge token."""

    try:
        encoded_payload, supplied_signature = token.split(".", 1)

        expected_signature = hmac.new(
            SECRET_KEY,
            encoded_payload.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(
            expected_signature, supplied_signature
        ):
            raise ValueError("Invalid challenge signature")

        payload = json.loads(
            b64url_decode(encoded_payload).decode()
        )

        return payload

    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid challenge token: {exc}"
        )


def calculate_mac(
    raw_body: bytes,
    timestamp_us: str,
    salt_sequence: str,
    nonce: str
) -> str:
    """Calculate HMAC-SHA512 over the canonical request data."""

    canonical_message = (
        raw_body
        + b"|"
        + timestamp_us.encode()
        + b"|"
        + salt_sequence.encode()
        + b"|"
        + nonce.encode()
    )

    return hmac.new(
        SECRET_KEY,
        canonical_message,
        hashlib.sha512
    ).hexdigest()


def calculate_chain_hash(
    previous_hash: str,
    raw_body: bytes,
    timestamp_us: str,
    salt_sequence: str,
    nonce: str
) -> str:
    """Create the next SHA-512 link in the transaction hash chain."""

    chain_message = (
        previous_hash.encode()
        + b"|"
        + raw_body
        + b"|"
        + timestamp_us.encode()
        + b"|"
        + salt_sequence.encode()
        + b"|"
        + nonce.encode()
    )

    return hashlib.sha512(chain_message).hexdigest()


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "Q2 Cryptographic Replay Testing API"
    }


@app.post("/transactions", status_code=201)
async def create_transaction(request: Request):
    """Create a transaction and issue its first challenge."""

    raw_body = await request.body()

    try:
        initial_data = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Request body must contain valid JSON"
        )

    transaction_id = str(uuid.uuid4())

    created_at_us = current_timestamp_us()

    genesis_hash = hashlib.sha512(
        f"{transaction_id}:{created_at_us}".encode()
    ).hexdigest()

    transaction = {
        "id": transaction_id,
        "created_at_us": created_at_us,
        "initial_data": initial_data,
        "current_data": initial_data,
        "genesis_hash": genesis_hash,
        "chain": [],
        "challenges": {},
        "used_nonces": set()
    }

    transactions[transaction_id] = transaction

    challenge_token, challenge = create_challenge(
        transaction_id, transaction
    )

    return JSONResponse(
        status_code=201,
        headers={
            "X-Transaction-ID": transaction_id,
            "X-Challenge-Token": challenge_token
        },
        content={
            "message": "Transaction created",
            "transaction_id": transaction_id,
            "challenge": challenge
        }
    )


@app.get("/transactions/{transaction_id}/challenge")
async def get_new_challenge(transaction_id: str):
    """Issue a fresh challenge for the next chained update."""

    transaction = transactions.get(transaction_id)

    if not transaction:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found"
        )

    token, challenge = create_challenge(
        transaction_id, transaction
    )

    return JSONResponse(
        content={
            "message": "New challenge issued",
            "challenge": challenge
        },
        headers={
            "X-Challenge-Token": token
        }
    )


@app.put("/transactions/{transaction_id}")
async def update_transaction(
    transaction_id: str,
    request: Request
):
    """Verify HMAC, reject replayed nonces and extend the hash chain."""

    transaction = transactions.get(transaction_id)

    if not transaction:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found"
        )

    raw_body = await request.body()

    try:
        update_data = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Update body must contain valid JSON"
        )

    challenge_token = request.headers.get("X-Challenge-Token")
    timestamp_us = request.headers.get("X-Timestamp-Us")
    salt_sequence = request.headers.get("X-Salt-Sequence")
    nonce = request.headers.get("X-Nonce")
    supplied_mac = request.headers.get("X-Frugal-Mac")

    if not all([
        challenge_token,
        timestamp_us,
        salt_sequence,
        nonce,
        supplied_mac
    ]):
        raise HTTPException(
            status_code=400,
            detail="Required cryptographic headers are missing"
        )

    challenge = decode_challenge(challenge_token)

    if challenge.get("transaction_id") != transaction_id:
        raise HTTPException(
            status_code=401,
            detail="Challenge belongs to another transaction"
        )

    if nonce in transaction["used_nonces"]:
        return JSONResponse(
            status_code=409,
            content={
                "accepted": False,
                "error": "REPLAY_DETECTED",
                "message": "This nonce has already been used."
            }
        )

    stored_challenge = transaction["challenges"].get(nonce)

    if not stored_challenge:
        raise HTTPException(
            status_code=401,
            detail="Unknown challenge nonce"
        )

    if (
        timestamp_us != str(challenge["server_timestamp_us"])
        or salt_sequence != challenge["salt_sequence"]
        or nonce != challenge["nonce"]
    ):
        raise HTTPException(
            status_code=401,
            detail="Challenge headers do not match"
        )

    if current_timestamp_us() > challenge["expires_at_us"]:
        raise HTTPException(
            status_code=401,
            detail="Challenge token has expired"
        )

    expected_mac = calculate_mac(
        raw_body,
        timestamp_us,
        salt_sequence,
        nonce
    )

    if not hmac.compare_digest(expected_mac, supplied_mac):
        raise HTTPException(
            status_code=401,
            detail="HMAC authentication failed"
        )

    # A valid nonce is consumed exactly once.
    transaction["used_nonces"].add(nonce)

    previous_hash = (
        transaction["chain"][-1]["hash"]
        if transaction["chain"]
        else transaction["genesis_hash"]
    )

    new_hash = calculate_chain_hash(
        previous_hash,
        raw_body,
        timestamp_us,
        salt_sequence,
        nonce
    )

    entry = {
        "sequence": len(transaction["chain"]) + 1,
        "raw_body_hex": raw_body.hex(),
        "timestamp_us": timestamp_us,
        "salt_sequence": salt_sequence,
        "nonce": nonce,
        "previous_hash": previous_hash,
        "hash": new_hash
    }

    transaction["chain"].append(entry)
    transaction["current_data"] = update_data

    return JSONResponse(
        status_code=200,
        headers={
            "X-Hash-Chain-Head": new_hash
        },
        content={
            "accepted": True,
            "message": "Transaction updated successfully",
            "transaction_id": transaction_id,
            "chain_sequence": entry["sequence"],
            "hash": new_hash
        }
    )


@app.get("/transactions/{transaction_id}/verify-chain")
async def verify_hash_chain(transaction_id: str):
    """Recalculate every link and verify chain integrity."""

    transaction = transactions.get(transaction_id)

    if not transaction:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found"
        )

    expected_previous_hash = transaction["genesis_hash"]

    for entry in transaction["chain"]:
        if entry["previous_hash"] != expected_previous_hash:
            return {
                "valid": False,
                "message": "Previous hash link mismatch"
            }

        raw_body = bytes.fromhex(entry["raw_body_hex"])

        expected_hash = calculate_chain_hash(
            expected_previous_hash,
            raw_body,
            entry["timestamp_us"],
            entry["salt_sequence"],
            entry["nonce"]
        )

        if not hmac.compare_digest(
            expected_hash, entry["hash"]
        ):
            return {
                "valid": False,
                "message": "Hash-chain integrity check failed"
            }

        expected_previous_hash = expected_hash

    return {
        "valid": True,
        "entries": len(transaction["chain"]),
        "chain_head": expected_previous_hash,
        "message": "Hash-chain integrity verified"
    }
