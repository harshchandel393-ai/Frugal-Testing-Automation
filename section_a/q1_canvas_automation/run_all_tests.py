
import subprocess
import sys
from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parent

TESTS = [
    {
        "name": "WebSocket Fibonacci Jitter Test",
        "command": [sys.executable, "automation.py"],
        "timeout": 120
    },
    {
        "name": "Canvas Coordinate and Mouse Automation",
        "command": [sys.executable, "coordinate_automation.py"],
        "timeout": 60
    },
    {
        "name": "Coordinate Drift Correction",
        "command": [sys.executable, "drift_correction.py"],
        "timeout": 60
    },
    {
        "name": "Circuit Breaker Test",
        "command": [sys.executable, "circuit_breaker.py"],
        "timeout": 60
    },
    {
        "name": "State Validation Test",
        "command": [sys.executable, "state_validation.py"],
        "timeout": 30
    },
    {
        "name": "Canvas Pytest Suite",
        "command": [
            sys.executable,
            "-m",
            "pytest",
            "test_canvas.py",
            "-v",
            "-s"
        ],
        "timeout": 120
    }
]


def run_test(test):

    print("\n" + "=" * 65)
    print("[RUNNING]", test["name"])
    print("=" * 65)

    try:

        result = subprocess.run(
            test["command"],
            cwd=BASE_DIR,
            timeout=test["timeout"],
            check=False
        )

        if result.returncode == 0:

            print("\n[PASS]", test["name"])

            return "PASS"

        else:

            print("\n[FAIL]", test["name"])

            print("[INFO] Exit code:", result.returncode)

            return "FAIL"

    except subprocess.TimeoutExpired:

        print("\n[TIMEOUT]", test["name"])

        return "TIMEOUT"

    except Exception as error:

        print("\n[ERROR]", str(error))

        return "ERROR"


def main():

    print("\n")
    print("=" * 65)
    print("       FRUGAL TESTING - Q1 MASTER TEST RUNNER")
    print("=" * 65)

    print("[INFO] Started:", datetime.now().strftime(
        "%d-%m-%Y %H:%M:%S"
    ))

    print("[INFO] Total test suites:", len(TESTS))

    print("\n[IMPORTANT] Ensure FastAPI server is running.")
    print("[INFO] Server URL: http://127.0.0.1:8000")

    results = []

    for test in TESTS:

        status = run_test(test)

        results.append({
            "name": test["name"],
            "status": status
        })

    # Final report

    passed = sum(
        item["status"] == "PASS"
        for item in results
    )

    failed = sum(
        item["status"] == "FAIL"
        for item in results
    )

    timed_out = sum(
        item["status"] == "TIMEOUT"
        for item in results
    )

    errors = sum(
        item["status"] == "ERROR"
        for item in results
    )

    print("\n\n")
    print("=" * 65)
    print("                 FINAL Q1 TEST REPORT")
    print("=" * 65)

    for index, item in enumerate(results, start=1):

        print(
            f"{index}. {item['name']}: {item['status']}"
        )

    print("-" * 65)

    print("[INFO] Total suites:", len(results))
    print("[INFO] Passed:", passed)
    print("[INFO] Failed:", failed)
    print("[INFO] Timeouts:", timed_out)
    print("[INFO] Errors:", errors)

    print("-" * 65)

    if passed == len(TESTS):

        print("[SUCCESS] ALL TEST SUITES PASSED")

    else:

        print("[WARNING] SOME TEST SUITES NEED ATTENTION")

    print("=" * 65)

    # Save report to file

    report_path = BASE_DIR / "q1_test_report.txt"

    with open(report_path, "w", encoding="utf-8") as file:

        file.write("FRUGAL TESTING - Q1 FINAL TEST REPORT\n")

        file.write("=" * 50 + "\n")

        file.write(
            datetime.now().strftime("%d-%m-%Y %H:%M:%S")
            + "\n\n"
        )

        for item in results:

            file.write(
                f"{item['name']}: {item['status']}\n"
            )

        file.write("\n")

        file.write(f"Total: {len(results)}\n")
        file.write(f"Passed: {passed}\n")
        file.write(f"Failed: {failed}\n")
        file.write(f"Timeouts: {timed_out}\n")
        file.write(f"Errors: {errors}\n")

    print("\n[INFO] Report saved:", report_path.name)


if __name__ == "__main__":

    main()
