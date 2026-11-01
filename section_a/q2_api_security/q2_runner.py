
import base64
import hashlib
import hmac
import json
import time
from pathlib import Path

import requests


BASE_URL = "http://127.0.0.1:8001"

# Must match the local mock server's demonstration key.
SECRET_KEY = b"frugal-testing-q2-local-demo-secret"

TIMEOUT = 5
MAX_REPLAY_DELAY_MS = 150

results = []


def log_result(name, passed):
    """Record and display an individual test result."""
    status = "PASS" if passed else "FAIL"

    print(f"[{status}] {name}")
    results.append((name, passed))


def encode_json(data):
    """Serialize JSON into stable raw bytes."""
    return json.dumps(
        data,
        separators=(",", ":"),
        ensure_ascii=False
    ).encode("utf-8")


def decode_base64url(value):
    """Decode URL-safe Base64 data."""
    padding = "=" * (-len(value) % 4)

    return base64.urlsafe_b64decode(
        value + padding
    )


def parse_and_verify_challenge(token):
    """Verify the server signature and extract challenge data."""

    if not token or "." not in token:
        raise ValueError("Invalid challenge token format")

    encoded_payload, supplied_signature = token.split(".", 1)

    expected_signature = hmac.new(
        SECRET_KEY,
        encoded_payload.encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(
        supplied_signature,
        expected_signature
    ):
        raise ValueError("Challenge signature verification failed")

    payload = json.loads(
        decode_base64url(encoded_payload).decode("utf-8")
    )

    required_fields = [
        "transaction_id",
        "nonce",
        "server_timestamp_us",
        "salt_sequence",
        "expires_at_us"
    ]

    for field in required_fields:
        if field not in payload:
            raise ValueError(
                f"Missing challenge field: {field}"
            )

    if not payload["nonce"]:
        raise ValueError("Challenge nonce is empty")

    if not payload["salt_sequence"]:
        raise ValueError("Salt sequence is empty")

    return payload


def build_auth_headers(raw_body, challenge_token, transaction_id):
    """Generate dynamic HMAC-SHA512 authentication."""

    challenge = parse_and_verify_challenge(
        challenge_token
    )

    if challenge["transaction_id"] != transaction_id:
        raise ValueError(
            "Challenge belongs to a different transaction"
        )

    timestamp_us = str(
        challenge["server_timestamp_us"]
    )

    salt_sequence = challenge["salt_sequence"]
    nonce = challenge["nonce"]

    # Sign the exact raw body that will be sent in the PUT request.
    canonical_message = (
        raw_body
        + b"|"
        + timestamp_us.encode()
        + b"|"
        + salt_sequence.encode()
        + b"|"
        + nonce.encode()
    )

    mac = hmac.new(
        SECRET_KEY,
        canonical_message,
        hashlib.sha512
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Challenge-Token": challenge_token,
        "X-Timestamp-Us": timestamp_us,
        "X-Salt-Sequence": salt_sequence,
        "X-Nonce": nonce,
        "X-Frugal-Mac": mac
    }

    return headers, challenge


def write_report():
    """Write the consolidated Q2 execution report."""

    passed = sum(
        1 for _, status in results if status
    )

    failed = len(results) - passed

    report_lines = [
        "FRUGAL TESTING - Q2 CRYPTOGRAPHIC REPLAY REPORT",
        "=" * 55
    ]

    for name, status in results:
        report_lines.append(
            f"[{'PASS' if status else 'FAIL'}] {name}"
        )

    report_lines.extend([
        "",
        f"Total tests: {len(results)}",
        f"Passed: {passed}",
        f"Failed: {failed}",
        "",
        (
            "ALL Q2 TESTS PASSED"
            if failed == 0 and len(results) == 7
            else "Q2 TESTS INCOMPLETE"
        )
    ])

    report_path = Path(__file__).with_name(
        "q2_test_report.txt"
    )

    report_path.write_text(
        "\n".join(report_lines),
        encoding="utf-8"
    )

    print(f"[INFO] Report saved: {report_path.name}")

    return passed, failed


def main():
    session = requests.Session()

    print("\n" + "=" * 65)
    print(" FRUGAL TESTING - Q2 CRYPTOGRAPHIC REPLAY TEST")
    print("=" * 65)

    try:
        # -------------------------------------------------
        # STEP 1: Check local API server
        # -------------------------------------------------

        print("\n[STEP 1] Checking API server health")

        health_response = session.get(
            f"{BASE_URL}/health",
            timeout=TIMEOUT
        )

        health_response.raise_for_status()

        health_data = health_response.json()

        print("[RESPONSE]", health_data)

        log_result(
            "Local API health check",
            health_data.get("status") == "healthy"
        )

        # -------------------------------------------------
        # STEP 2: Create transaction using POST
        # -------------------------------------------------

        print("\n[STEP 2] Creating transaction using POST")

        initial_data = {
            "customer": "Demo Customer",
            "amount": 1250,
            "currency": "INR",
            "description": "Q2 replay protection demonstration"
        }

        initial_body = encode_json(initial_data)

        create_response = session.post(
            f"{BASE_URL}/transactions",
            data=initial_body,
            headers={
                "Content-Type": "application/json"
            },
            timeout=TIMEOUT
        )

        print("[HTTP STATUS]", create_response.status_code)

        assert create_response.status_code == 201, (
            "Transaction creation failed"
        )

        transaction_id = create_response.headers.get(
            "X-Transaction-ID"
        )

        challenge_token = create_response.headers.get(
            "X-Challenge-Token"
        )

        assert transaction_id, (
            "Transaction ID response header missing"
        )

        assert challenge_token, (
            "Challenge token response header missing"
        )

        print("[TRANSACTION ID]", transaction_id)
        print("[CHALLENGE] Received from server response header")

        log_result(
            "POST transaction creation and dynamic ID extraction",
            True
        )

        # -------------------------------------------------
        # STEP 3: Prepare exact PUT body and create HMAC
        # -------------------------------------------------

        print("\n[STEP 3] Verifying challenge and generating HMAC")

        # IMPORTANT:
        # Create the PUT body BEFORE HMAC calculation.
        # The exact same raw bytes must be signed and transmitted.

        update_body = encode_json({
            "status": "APPROVED",
            "amount": 1250,
            "reference": "Q2-UPDATE-001"
        })

        headers, challenge = build_auth_headers(
            update_body,
            challenge_token,
            transaction_id
        )

        print(
            "[SERVER TIMESTAMP - MICROSECONDS]",
            challenge["server_timestamp_us"]
        )

        print("[NONCE]", challenge["nonce"])
        print("[SALT SEQUENCE]", challenge["salt_sequence"])

        print(
            "[HMAC] SHA-512 generated successfully"
        )

        print(
            "[HMAC LENGTH]",
            len(headers["X-Frugal-Mac"]),
            "hex characters"
        )

        assert len(headers["X-Frugal-Mac"]) == 128

        log_result(
            "Challenge verification and HMAC-SHA512 generation",
            True
        )

        # -------------------------------------------------
        # STEP 4: Send authenticated PUT request
        # -------------------------------------------------

        print("\n[STEP 4] Sending authenticated PUT request")

        put_response = session.put(
            f"{BASE_URL}/transactions/{transaction_id}",
            data=update_body,
            headers=headers,
            timeout=TIMEOUT
        )

        # Capture completion immediately after HTTP response.
        put_completed_ns = time.perf_counter_ns()

        print("[HTTP STATUS]", put_response.status_code)

        print(
            "[RESPONSE]",
            json.dumps(put_response.json(), indent=4)
        )

        assert put_response.status_code == 200, (
            "Authenticated PUT request failed"
        )

        log_result(
            "First authenticated PUT request",
            True
        )

        # -------------------------------------------------
        # STEP 5: Send identical replay within 150 ms
        # -------------------------------------------------

        print("\n[STEP 5] Performing immediate replay attack")

        replay_start_ns = time.perf_counter_ns()

        replay_delay_ms = (
            replay_start_ns - put_completed_ns
        ) / 1_000_000

        # Send EXACT same raw body and authentication headers.
        replay_response = session.put(
            f"{BASE_URL}/transactions/{transaction_id}",
            data=update_body,
            headers=headers.copy(),
            timeout=TIMEOUT
        )

        print(
            f"[REPLAY INITIATION DELAY] "
            f"{replay_delay_ms:.3f} ms"
        )

        print(
            "[REPLAY HTTP STATUS]",
            replay_response.status_code
        )

        replay_data = replay_response.json()

        print(
            "[REPLAY RESPONSE]",
            json.dumps(replay_data, indent=4)
        )

        assert replay_delay_ms <= MAX_REPLAY_DELAY_MS, (
            "Replay request initiation exceeded 150 ms"
        )

        assert replay_response.status_code == 409, (
            "Replay vulnerability: duplicate request was accepted"
        )

        assert replay_data.get("error") == "REPLAY_DETECTED", (
            "Expected REPLAY_DETECTED response"
        )

        print(
            "[SECURITY] Duplicate transaction was rejected"
        )

        log_result(
            "Identical replay rejected within 150 ms",
            True
        )

        # -------------------------------------------------
        # STEP 6: Generate another challenge and chained PUT
        # -------------------------------------------------

        print("\n[STEP 6] Creating second chained update")

        challenge_response = session.get(
            f"{BASE_URL}/transactions/{transaction_id}/challenge",
            timeout=TIMEOUT
        )

        challenge_response.raise_for_status()

        second_token = challenge_response.headers.get(
            "X-Challenge-Token"
        )

        assert second_token, (
            "Second challenge token missing"
        )

        second_body = encode_json({
            "status": "SETTLED",
            "confirmation": "Q2-CHAIN-STEP-002"
        })

        second_headers, second_challenge = build_auth_headers(
            second_body,
            second_token,
            transaction_id
        )

        print(
            "[SECOND SERVER TIMESTAMP]",
            second_challenge["server_timestamp_us"]
        )

        second_response = session.put(
            f"{BASE_URL}/transactions/{transaction_id}",
            data=second_body,
            headers=second_headers,
            timeout=TIMEOUT
        )

        print(
            "[HTTP STATUS]",
            second_response.status_code
        )

        print(
            "[RESPONSE]",
            json.dumps(second_response.json(), indent=4)
        )

        assert second_response.status_code == 200, (
            "Second authenticated update failed"
        )

        log_result(
            "Second authenticated chained update",
            True
        )

        # -------------------------------------------------
        # STEP 7: Verify hash-chain integrity
        # -------------------------------------------------

        print("\n[STEP 7] Verifying SHA-512 hash chain")

        verify_response = session.get(
            f"{BASE_URL}/transactions/{transaction_id}/verify-chain",
            timeout=TIMEOUT
        )

        verify_response.raise_for_status()

        chain_result = verify_response.json()

        print(
            "[HASH CHAIN REPORT]",
            json.dumps(chain_result, indent=4)
        )

        assert chain_result.get("valid") is True, (
            "Hash-chain integrity verification failed"
        )

        assert chain_result.get("entries") == 2, (
            "Expected exactly two valid chain entries"
        )

        log_result(
            "SHA-512 hash-chain integrity verification",
            True
        )

    except Exception as error:

        print("\n[ERROR]", type(error).__name__, str(error))

        log_result(
            f"Execution failed: {type(error).__name__}: {error}",
            False
        )

    finally:

        session.close()

        print("\n" + "=" * 65)
        print(" Q2 FINAL TEST REPORT")
        print("=" * 65)

        passed, failed = write_report()

        if failed == 0 and len(results) == 7:
            print("\n[SUCCESS] ALL 7 Q2 TESTS PASSED")
        else:
            print("\n[FAILURE] Q2 TEST SUITE INCOMPLETE")

        print("=" * 65)

    if failed != 0 or len(results) != 7:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
