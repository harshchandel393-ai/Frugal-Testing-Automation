
import subprocess
import sys
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent

TEST_SUITES = [
    (
        "Q2 Cryptographic Replay Automation",
        [sys.executable, str(BASE_DIR / "q2_runner.py")]
    ),
    (
        "Q2 Pytest Security Suite",
        [
            sys.executable,
            "-m",
            "pytest",
            str(BASE_DIR / "test_q2.py"),
            "-v",
            "-s"
        ]
    )
]


def main():
    results = []

    print("\n" + "=" * 65)
    print(" FRUGAL TESTING - Q2 MASTER TEST RUNNER")
    print("=" * 65)

    print("[INFO] Started:", datetime.now().strftime("%d-%m-%Y %H:%M:%S"))
    print("[INFO] Total suites:", len(TEST_SUITES))
    print("[INFO] API Server: http://127.0.0.1:8001")

    for suite_name, command in TEST_SUITES:
        print("\n" + "=" * 65)
        print("[RUNNING]", suite_name)
        print("=" * 65)

        try:
            process = subprocess.run(
                command,
                cwd=BASE_DIR,
                check=False
            )

            passed = process.returncode == 0

            results.append((suite_name, passed))

            print(
                f"\n[{'PASS' if passed else 'FAIL'}] {suite_name}"
            )

        except Exception as error:
            results.append((suite_name, False))
            print("[ERROR]", str(error))

    passed_count = sum(
        1 for _, passed in results if passed
    )

    failed_count = len(results) - passed_count

    print("\n" + "=" * 65)
    print(" Q2 FINAL MASTER TEST REPORT")
    print("=" * 65)

    for name, passed in results:
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")

    print("-" * 65)
    print("[INFO] Total suites:", len(results))
    print("[INFO] Passed:", passed_count)
    print("[INFO] Failed:", failed_count)

    if failed_count == 0 and len(results) == 2:
        print("\n[SUCCESS] ALL Q2 TEST SUITES PASSED")
    else:
        print("\n[FAILURE] Q2 TEST EXECUTION INCOMPLETE")

    report = [
        "FRUGAL TESTING - Q2 MASTER TEST REPORT",
        "=" * 50,
        f"Execution time: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}",
        "",
    ]

    for name, passed in results:
        report.append(
            f"[{'PASS' if passed else 'FAIL'}] {name}"
        )

    report.extend([
        "",
        f"Total suites: {len(results)}",
        f"Passed: {passed_count}",
        f"Failed: {failed_count}",
        "",
        (
            "ALL Q2 TEST SUITES PASSED"
            if failed_count == 0 and len(results) == 2
            else "Q2 TEST EXECUTION INCOMPLETE"
        )
    ])

    report_path = BASE_DIR / "q2_master_report.txt"

    report_path.write_text(
        "\n".join(report),
        encoding="utf-8"
    )

    print("[INFO] Report saved:", report_path.name)
    print("=" * 65)

    if failed_count != 0 or len(results) != 2:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
