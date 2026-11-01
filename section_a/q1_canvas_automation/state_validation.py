
import requests
import json

URL = "http://127.0.0.1:8000/validate-state"


def test_balance(name, balance, expected_accepted):

    print(f"\n[TEST] {name}")

    payload = {
        "balance": balance
    }

    try:

        response = requests.post(
            URL,
            json=payload,
            timeout=5
        )

        result = response.json()

        print("[REQUEST]", payload)
        print("[RESPONSE]", json.dumps(result, indent=4))

        actual_accepted = result.get("accepted")

        if actual_accepted == expected_accepted:

            print("[PASS]", name)

            return True

        else:

            print("[FAIL]", name)

            return False

    except requests.RequestException as error:

        print("[ERROR]", error)

        return False


def main():

    print("\n========== STATE VALIDATION TEST ==========\n")

    test_cases = [

        ("Valid integer balance", 100, True),

        ("Invalid string balance", "100", False),

        ("Invalid fractional balance", 100.5, False),

        ("Out of range balance", 2000000, False),

        ("Valid zero balance", 0, True),

        ("Valid negative balance", -100, True)

    ]

    passed = 0

    failed = 0

    for name, balance, expected in test_cases:

        result = test_balance(
            name,
            balance,
            expected
        )

        if result:
            passed += 1
        else:
            failed += 1

    print("\n========== FINAL REPORT ==========")

    print("[INFO] Total tests:", len(test_cases))

    print("[INFO] Passed:", passed)

    print("[INFO] Failed:", failed)

    if failed == 0:

        print("\n[PASS] ALL STATE VALIDATION TESTS PASSED")

    else:

        print("\n[FAIL] SOME TESTS FAILED")


if __name__ == "__main__":

    main()
