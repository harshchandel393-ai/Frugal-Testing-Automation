
import asyncio
from playwright.async_api import async_playwright

URL = "http://127.0.0.1:8000"

MAX_RETRIES = 5
DRIFT_THRESHOLD = 5


async def detect_target(page):
    return await page.evaluate("""
        () => new Promise((resolve, reject) => {
            const canvas = document.getElementById("gameCanvas");

            if (!canvas) {
                reject(new Error("Canvas not found"));
                return;
            }

            const ctx = canvas.getContext("2d");
            let frames = 0;

            function scan() {
                frames++;

                const image = ctx.getImageData(
                    0, 0, canvas.width, canvas.height
                );

                const pixels = image.data;

                let minX = canvas.width;
                let minY = canvas.height;
                let maxX = -1;
                let maxY = -1;
                let count = 0;

                for (let y = 0; y < canvas.height; y += 2) {
                    for (let x = 0; x < canvas.width; x += 2) {
                        const i = (y * canvas.width + x) * 4;

                        const r = pixels[i];
                        const g = pixels[i + 1];
                        const b = pixels[i + 2];

                        if (g > 150 && r < 80 && b < 100) {
                            minX = Math.min(minX, x);
                            minY = Math.min(minY, y);
                            maxX = Math.max(maxX, x);
                            maxY = Math.max(maxY, y);

                            count++;
                        }
                    }
                }

                if (count > 500) {
                    resolve({
                        x: minX,
                        y: minY,
                        width: maxX - minX,
                        height: maxY - minY
                    });
                    return;
                }

                if (frames >= 300) {
                    reject(new Error("Target not detected"));
                    return;
                }

                requestAnimationFrame(scan);
            }

            requestAnimationFrame(scan);
        });
    """)


async def main():
    async with async_playwright() as p:

        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            await page.goto(URL)

            await page.wait_for_function("""
                () => {
                    const status =
                        document.getElementById("connectionStatus");

                    return status &&
                        status.textContent.includes("Connected");
                }
            """)

            print("[PASS] Canvas connected")

            canvas = page.locator("#gameCanvas")
            canvas_box = await canvas.bounding_box()

            if not canvas_box:
                raise RuntimeError("Canvas not found")

            scale_x = canvas_box["width"] / 800
            scale_y = canvas_box["height"] / 450

            async def get_screen_center():
                target = await detect_target(page)

                center_x = target["x"] + target["width"] / 2
                center_y = target["y"] + target["height"] / 2

                return (
                    canvas_box["x"] + center_x * scale_x,
                    canvas_box["y"] + center_y * scale_y
                )

            # Initial target detection
            screen_x, screen_y = await get_screen_center()

            print(
                f"[DETECTED] Initial position: "
                f"({screen_x:.1f}, {screen_y:.1f})"
            )

            success = False

            for attempt in range(1, MAX_RETRIES + 1):

                print(f"\n[ATTEMPT] {attempt}")

                # Move pointer to detected target
                await page.mouse.move(screen_x, screen_y)

                # Wait for next WebSocket position update
                await page.wait_for_timeout(1200)

                # Detect target again
                new_x, new_y = await get_screen_center()

                drift_x = new_x - screen_x
                drift_y = new_y - screen_y

                print(
                    f"[DRIFT] X={drift_x:.1f}px, "
                    f"Y={drift_y:.1f}px"
                )

                if (
                    abs(drift_x) > DRIFT_THRESHOLD
                    or abs(drift_y) > DRIFT_THRESHOLD
                ):
                    print("[WARNING] Target position changed")

                    screen_x = new_x
                    screen_y = new_y

                    print("[RECOVERY] Coordinates updated")

                else:
                    print("[INFO] Target position stable")

                    screen_x = new_x
                    screen_y = new_y

                # Perform interaction using latest coordinates
                await page.mouse.move(screen_x, screen_y)
                await page.wait_for_timeout(100)

                await page.mouse.down()

                await page.mouse.move(
                    screen_x + 15 * scale_x,
                    screen_y,
                    steps=3
                )

                await page.mouse.up()

                await page.wait_for_timeout(200)

                final_status = await page.locator(
                    "#status"
                ).inner_text()

                print("[STATUS]", final_status)

                if "SUCCESS" in final_status:
                    print("[PASS] Coordinate drift handled")
                    print("[PASS] Hover, Drag and Click completed")

                    print(
                        "\n========== DRIFT TEST PASSED =========="
                    )

                    success = True
                    break

                print("[WARNING] Interaction unsuccessful")

                # Refresh coordinates before retry
                screen_x, screen_y = await get_screen_center()

                print("[RECOVERY] Target coordinates refreshed")

            if not success:
                print("[FAIL] Maximum retry attempts reached")

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
