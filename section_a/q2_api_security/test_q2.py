
import time
import requests
import pytest

from q2_runner import (
    BASE_URL,
    build_auth_headers,
    encode_json
)


TIMEOUT = 5


@pytest.fixture(scope="module")
def api():
    """Create a reusable HTTP session."""
    session = requests.Session()
    yield session
    session.close()


def create_transaction(api):
    """Create a transaction and extract its response headers."""

    initial_body = encode_json({
        "customer": "Pytest Customer",
        "amount": 2500,
        "currency": "INR"
    })

    response = api.post(
        f"{BASE_URL}/transactions",
        data=initial_body,
        headers={"Content-Type": "application/json"},
        timeout=TIMEOUT
    )

    assert response.status_code == 201

    transaction_id = response.headers.get("X-Transaction-ID")
    challenge_token = response.headers.get("X-Challenge-Token")

    assert transaction_id is not None
    assert challenge_token is not None

    return transaction_id, challenge_token


def test_api_health(api):
    """Test API availability."""

    response = api.get(
        f"{BASE_URL}/health",
        timeout=TIMEOUT
    )

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

    print("[PASS] API health check")


def test_invalid_hmac_is_rejected(api):
    """Verify that an invalid HMAC is rejected."""

    transaction_id, challenge_token = create_transaction(api)

    raw_body = encode_json({
        "status": "APPROVED",
        "amount": 2500
    })

    headers, _ = build_auth_headers(
        raw_body,
        challenge_token,
        transaction_id
    )

    # Deliberately modify the valid HMAC.
    original_mac = headers["X-Frugal-Mac"]

    replacement = "0" if original_mac[-1] != "0" else "1"

    headers["X-Frugal-Mac"] = (
        original_mac[:-1] + replacement
    )

    response = api.put(
        f"{BASE_URL}/transactions/{transaction_id}",
        data=raw_body,
        headers=headers,
        timeout=TIMEOUT
    )

    assert response.status_code == 401

    assert (
        response.json()["detail"]
        == "HMAC authentication failed"
    )

    print("[PASS] Invalid HMAC rejected with HTTP 401")


def test_replay_protection_and_hash_chain(api):
    """Test authentication, replay protection and hash-chain integrity."""

    transaction_id, challenge_token = create_transaction(api)

    # -----------------------------------------
    # First authenticated PUT request
    # -----------------------------------------

    first_body = encode_json({
        "status": "APPROVED",
        "reference": "PYTEST-STEP-001"
    })

    first_headers, _ = build_auth_headers(
        first_body,
        challenge_token,
        transaction_id
    )

    first_response = api.put(
        f"{BASE_URL}/transactions/{transaction_id}",
        data=first_body,
        headers=first_headers,
        timeout=TIMEOUT
    )

    # Capture completion immediately after the response arrives.
    first_completed_ns = time.perf_counter_ns()

    assert first_response.status_code == 200

    print("[PASS] First authenticated PUT")

    # -----------------------------------------
    # Immediate identical replay
    # -----------------------------------------

    # Record the replay initiation immediately before sending it.
    replay_start_ns = time.perf_counter_ns()

    replay_delay_ms = (
        replay_start_ns - first_completed_ns
    ) / 1_000_000

    replay_response = api.put(
        f"{BASE_URL}/transactions/{transaction_id}",
        data=first_body,
        headers=first_headers.copy(),
        timeout=TIMEOUT
    )

    assert replay_delay_ms <= 150, (
        f"Replay initiation exceeded 150 ms: "
        f"{replay_delay_ms:.3f} ms"
    )

    assert replay_response.status_code == 409

    assert (
        replay_response.json()["error"]
        == "REPLAY_DETECTED"
    )

    print(
        f"[PASS] Replay rejected within 150 ms "
        f"({replay_delay_ms:.3f} ms)"
    )

    print("[PASS] Duplicate request rejected with HTTP 409")

    # -----------------------------------------
    # Second chained update
    # -----------------------------------------

    challenge_response = api.get(
        f"{BASE_URL}/transactions/{transaction_id}/challenge",
        timeout=TIMEOUT
    )

    assert challenge_response.status_code == 200

    second_token = challenge_response.headers.get(
        "X-Challenge-Token"
    )

    assert second_token is not None

    second_body = encode_json({
        "status": "SETTLED",
        "reference": "PYTEST-STEP-002"
    })

    second_headers, _ = build_auth_headers(
        second_body,
        second_token,
        transaction_id
    )

    second_response = api.put(
        f"{BASE_URL}/transactions/{transaction_id}",
        data=second_body,
        headers=second_headers,
        timeout=TIMEOUT
    )

    assert second_response.status_code == 200

    print("[PASS] Second chained update")

    # -----------------------------------------
    # Hash-chain integrity verification
    # -----------------------------------------

    verify_response = api.get(
        f"{BASE_URL}/transactions/{transaction_id}/verify-chain",
        timeout=TIMEOUT
    )

    assert verify_response.status_code == 200

    chain_data = verify_response.json()

    assert chain_data["valid"] is True
    assert chain_data["entries"] == 2

    print("[PASS] Hash-chain integrity verified")
    print("[CHAIN ENTRIES]", chain_data["entries"])


if __name__ == "__main__":
    raise SystemExit(
        pytest.main([__file__, "-v", "-s"])
    )
