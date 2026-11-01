
import pytest
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8000"


@pytest.fixture
def browser_page():

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)

        page = browser.new_page()

        page.goto(URL)

        page.wait_for_function("""
            () => document.getElementById("connectionStatus")
                .textContent.includes("Connected")
        """)

        yield page

        browser.close()


def test_canvas_exists(browser_page):

    canvas = browser_page.locator("#gameCanvas")

    assert canvas.count() == 1

    print("[PASS] Canvas element exists")


def test_canvas_dimensions(browser_page):

    dimensions = browser_page.locator(
        "#gameCanvas"
    ).evaluate("""
        canvas => ({
            width: canvas.width,
            height: canvas.height
        })
    """)

    assert dimensions["width"] == 800
    assert dimensions["height"] == 450

    print("[PASS] Canvas dimensions verified")


def test_websocket_connection(browser_page):

    status = browser_page.locator(
        "#connectionStatus"
    ).inner_text()

    assert status == "Connected"

    print("[PASS] WebSocket connected")


def test_balance_display(browser_page):

    balance = browser_page.locator(
        "#balance"
    ).inner_text()

    assert balance == "100"

    print("[PASS] Balance display verified")


def test_sequence_updates(browser_page):

    sequence_element = browser_page.locator("#sequence")

    initial_sequence = int(
        sequence_element.inner_text()
    )

    browser_page.wait_for_function("""
        () => Number(
            document.getElementById("sequence").textContent
        ) > 0
    """)

    updated_sequence = int(
        sequence_element.inner_text()
    )

    assert updated_sequence >= initial_sequence

    print("[PASS] WebSocket sequence updates verified")
