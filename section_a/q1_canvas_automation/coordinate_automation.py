
import asyncio

from playwright.async_api import async_playwright

URL = "http://127.0.0.1:8000"


async def detect_canvas_target(page):

    return await page.evaluate("""
        () => new Promise((resolve, reject) => {

            const canvas = document.getElementById("gameCanvas");
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
                        height: maxY - minY,
                        pixels: count
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

        await page.goto(URL)

        await page.wait_for_function("""
            () => document.getElementById("connectionStatus")
                .textContent.includes("Connected")
        """)

        print("[PASS] Canvas application connected")

        # Capture actual browser mouse events
        await page.evaluate("""
            () => {

                window.automationClickEvents = [];

                const canvas =
                    document.getElementById("gameCanvas");

                canvas.addEventListener("pointerdown", () => {
                    window.automationClickEvents.push("pointerdown");
                });

                canvas.addEventListener("pointerup", () => {
                    window.automationClickEvents.push("pointerup");
                });

                canvas.addEventListener("click", () => {
                    window.automationClickEvents.push("click");
                });

            }
        """)

        # Detect target using Canvas pixels
        target = await detect_canvas_target(page)

        print("[PIXEL DETECTION]", target)

        canvas_box = await page.locator(
            "#gameCanvas"
        ).bounding_box()

        if not canvas_box:
            raise RuntimeError("Canvas not found")

        # Calculate target center
        center_x = target["x"] + target["width"] / 2
        center_y = target["y"] + target["height"] / 2

        # Convert Canvas coordinates to browser coordinates
        scale_x = canvas_box["width"] / 800
        scale_y = canvas_box["height"] / 450

        screen_x = canvas_box["x"] + center_x * scale_x
        screen_y = canvas_box["y"] + center_y * scale_y

        # HOVER
        await page.mouse.move(screen_x, screen_y)

        print("[PASS] Hover completed")

        # DRAG
        await page.mouse.down()

        await page.mouse.move(
            screen_x + 15 * scale_x,
            screen_y,
            steps=3
        )

        await page.mouse.up()

        print("[PASS] Drag action performed")

        # Allow browser click event to finish
        await page.wait_for_timeout(300)

        # Read browser-generated events
        events = await page.evaluate(
            "() => window.automationClickEvents"
        )

        # Read final application status
        final_status = await page.locator(
            "#status"
        ).inner_text()

        print("[DEBUG] Browser events:", events)

        print("[DEBUG] Final status:", final_status)

        # Verify chained interaction
        if (
            "click" in events
            and "SUCCESS: Hover, Drag and Click completed" in final_status
        ):

            print("[PASS] Hover completed")
            print("[PASS] Drag completed: 15px X-axis")
            print("[PASS] Click confirmed")

            print(
                "\n========== CHAINED ACTION PASSED =========="
            )

        else:

            print("[FAIL] Chained action unsuccessful")

            print("[INFO] Browser event details:", events)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
