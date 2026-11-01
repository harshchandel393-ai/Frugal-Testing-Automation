
import asyncio
import time


class CircuitBreaker:

    def __init__(self, failure_threshold=3, recovery_timeout=5):

        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self.failure_count = 0
        self.state = "CLOSED"
        self.last_failure_time = None

    def record_success(self):

        self.failure_count = 0
        self.state = "CLOSED"

        print("[CIRCUIT] Success recorded")
        print("[CIRCUIT] State: CLOSED")

    def record_failure(self):

        self.failure_count += 1
        self.last_failure_time = time.monotonic()

        print(
            f"[CIRCUIT] Failure count: "
            f"{self.failure_count}/{self.failure_threshold}"
        )

        if self.failure_count >= self.failure_threshold:

            self.state = "OPEN"

            print("[CIRCUIT] State: OPEN")
            print("[CIRCUIT] Further requests blocked")

    def allow_request(self):

        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":

            elapsed = time.monotonic() - self.last_failure_time

            if elapsed >= self.recovery_timeout:

                self.state = "HALF_OPEN"

                print("[CIRCUIT] Recovery timeout completed")
                print("[CIRCUIT] State: HALF_OPEN")

                return True

            print("[CIRCUIT] Request rejected - Circuit OPEN")

            return False

        if self.state == "HALF_OPEN":
            return True

        return False


async def simulate_operation(should_fail):

    await asyncio.sleep(0.5)

    if should_fail:
        raise RuntimeError("Simulated automation failure")

    return "Operation successful"


async def main():

    breaker = CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=5
    )

    print("\n========== CIRCUIT BREAKER TEST ==========\n")

    # Phase 1: Simulate three failures

    for attempt in range(1, 4):

        print(f"\n[ATTEMPT] {attempt}")

        if not breaker.allow_request():
            break

        try:

            await simulate_operation(should_fail=True)

            breaker.record_success()

        except RuntimeError as error:

            print("[ERROR]", error)

            breaker.record_failure()

    # Phase 2: Verify blocked request

    print("\n[PHASE 2] Testing blocked request")

    if not breaker.allow_request():

        print("[PASS] Circuit breaker blocked further requests")

    else:

        print("[FAIL] Circuit breaker did not block request")

    # Phase 3: Wait for recovery

    print("\n[PHASE 3] Waiting for recovery timeout")

    await asyncio.sleep(5.5)

    if breaker.allow_request():

        print("[PASS] Circuit entered HALF_OPEN state")

        try:

            result = await simulate_operation(
                should_fail=False
            )

            print("[RESULT]", result)

            breaker.record_success()

            print("[PASS] Circuit recovered successfully")

        except RuntimeError as error:

            print("[ERROR]", error)

            breaker.record_failure()

    print("\nFinal Circuit State:", breaker.state)

    print("\n========== CIRCUIT BREAKER TEST COMPLETED ==========")


if __name__ == "__main__":

    asyncio.run(main())
