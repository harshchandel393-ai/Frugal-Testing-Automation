
import asyncio
import time

from playwright.async_api import async_playwright

URL = "http://127.0.0.1:8000"

FIBONACCI = [1, 1, 2, 3, 5, 8]
MAX_FRAMES = 6


def get_jitter_ms(index):
    return min(FIBONACCI[index % len(FIBONACCI)] * 1000, 8000)


async def main():

    async with async_playwright() as p:

        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        message_queue = asyncio.Queue()
        delayed_frames = []

        completion = asyncio.Event()

        async def process_frames(browser_socket):

            index = 0

            while index < MAX_FRAMES:

                message = await message_queue.get()

                try:
                    delay = get_jitter_ms(index)

                    print(
                        f"[INTERCEPTED] Frame {index + 1}: "
                        f"delay={delay}ms"
                    )

                    start = time.monotonic()

                    await asyncio.sleep(delay / 1000)

                    # Synchronous Playwright API
                    browser_socket.send(message)

                    elapsed = (
                        time.monotonic() - start
                    ) * 1000

                    delayed_frames.append({
                        "frame": index + 1,
                        "expected_ms": delay,
                        "actual_ms": round(elapsed, 2)
                    })

                    print(
                        f"[FORWARDED] Frame {index + 1}: "
                        f"actual={elapsed:.2f}ms"
                    )

                    index += 1

                finally:
                    message_queue.task_done()

            completion.set()

        workers = []

        def handle_websocket(browser_socket):

            server_socket = browser_socket.connect_to_server()

            worker = asyncio.create_task(
                process_frames(browser_socket)
            )

            workers.append(worker)

            received_count = 0

            def receive_message(message):
                nonlocal received_count

                if received_count < MAX_FRAMES:
                    received_count += 1
                    message_queue.put_nowait(message)

            server_socket.on_message(receive_message)

            browser_socket.on_message(server_socket.send)

        await page.route_web_socket(
            "ws://127.0.0.1:8000/ws",
            handle_websocket
        )

        print("[INFO] WebSocket interception enabled")

        try:

            await page.goto(URL)

            await asyncio.wait_for(
                completion.wait(),
                timeout=30000
            )

            print("\n===== JITTER REPORT =====")

            for item in delayed_frames:
                print(item)

            assert len(delayed_frames) == MAX_FRAMES

            for index, item in enumerate(delayed_frames):
                assert item["expected_ms"] == get_jitter_ms(index)
                assert item["expected_ms"] <= 8000
                assert item["actual_ms"] >= item["expected_ms"]

            print("\n[PASS] Six frames intercepted")
            print("[PASS] Fibonacci delays verified")
            print("[PASS] Maximum delay cap verified")
            print("\n========== Q1 JITTER TEST PASSED ==========")

        finally:

            for worker in workers:
                worker.cancel()

            if workers:
                await asyncio.gather(
                    *workers,
                    return_exceptions=True
                )

            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
