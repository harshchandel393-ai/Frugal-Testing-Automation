
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE_DIR = Path(__file__).resolve().parent

HTML_FILE = BASE_DIR / "shadow_dom_demo.html"
JS_FILE = BASE_DIR / "shadow_dom_pathfinder.js"
REPORT_FILE = BASE_DIR / "q3_test_report.txt"

results = []


def record(name, passed):
    """Record an individual check."""
    results.append((name, passed))

    print(
        f"[{'PASS' if passed else 'FAIL'}] {name}"
    )


def read_ax_properties(node):
    """Read accessibility properties from a CDP AX node."""

    properties = {}

    for prop in node.get("properties", []):

        value = prop.get("value", {})

        if isinstance(value, dict):
            value = value.get("value")

        properties[prop["name"]] = value

    return properties


def verify_hosts(scan):

    required = {
        "OUTER-SHELL",
        "MIDDLE-SHELL",
        "SEALED-PANEL"
    }

    discovered = {
        host["tag"]
        for host in scan.get("hosts", [])
    }

    return required.issubset(discovered)


def main():

    print("\n" + "=" * 65)
    print(" FRUGAL TESTING - Q3 SHADOW DOM PATHFINDER")
    print("=" * 65)

    browser = None
    cdp = None

    try:

        # =============================================
        # STEP 1: Open browser
        # =============================================

        with sync_playwright() as p:

            browser = p.chromium.launch(
                headless=False
            )

            page = browser.new_page()

            print("\n[STEP 1] Opening Shadow DOM application")

            page.goto(HTML_FILE.as_uri())

            page.wait_for_load_state("load")

            print("[PASS] Demo application loaded")

            # =============================================
            # STEP 2: Shadow DOM traversal
            # =============================================

            print("\n[STEP 2] Inspecting nested Shadow DOM")

            pathfinder_code = JS_FILE.read_text(
                encoding="utf-8"
            ).strip()

            # shadow_dom_pathfinder.js is a complete IIFE.
            # Evaluate it directly; do not wrap or invoke it again.

            first_scan = page.evaluate(pathfinder_code)

            if not isinstance(first_scan, dict):
                raise RuntimeError(
                    "Pathfinder did not return a valid result"
                )

            print(
                json.dumps(first_scan, indent=4)
            )

            record(
                "All three Shadow DOM hosts detected",
                verify_hosts(first_scan)
            )

            access_map = {
                item["tag"]: item["rootAccess"]
                for item in first_scan["hosts"]
            }

            boundary_ok = (
                access_map.get("OUTER-SHELL") == "OPEN"
                and access_map.get("MIDDLE-SHELL") == "OPEN"
                and access_map.get("SEALED-PANEL")
                    == "CLOSED_BOUNDARY"
            )

            record(
                "Open and closed boundaries identified",
                boundary_ok
            )

            # =============================================
            # STEP 3: Dynamic classes
            # =============================================

            print("\n[STEP 3] Testing dynamic CSS classes")

            first_classes = {
                item["tag"]: item["dynamicClass"]
                for item in first_scan["hosts"]
            }

            print("[BEFORE RELOAD]", first_classes)

            page.reload()

            page.wait_for_load_state("load")

            second_scan = page.evaluate(pathfinder_code)

            if not isinstance(second_scan, dict):
                raise RuntimeError(
                    "Second scan returned invalid data"
                )

            second_classes = {
                item["tag"]: item["dynamicClass"]
                for item in second_scan["hosts"]
            }

            print("[AFTER RELOAD]", second_classes)

            dynamic_ok = all(
                first_classes.get(tag)
                and second_classes.get(tag)
                and first_classes[tag] != second_classes[tag]
                for tag in [
                    "OUTER-SHELL",
                    "MIDDLE-SHELL",
                    "SEALED-PANEL"
                ]
            )

            record(
                "Dynamic classes regenerated after reload",
                dynamic_ok
            )

            # =============================================
            # STEP 4: Accessibility Tree using Chrome CDP
            # =============================================

            print("\n[STEP 4] Reading Chrome Accessibility Tree")

            cdp = page.context.new_cdp_session(page)

            cdp.send("Accessibility.enable")
            cdp.send("DOM.enable")

            ax_result = cdp.send(
                "Accessibility.getFullAXTree"
            )

            ax_nodes = ax_result.get("nodes", [])

            print(
                "[INFO] Accessibility nodes:",
                len(ax_nodes)
            )

            record(
                "Accessibility Tree retrieved",
                len(ax_nodes) > 0
            )

            # =============================================
            # STEP 5: Semantic button discovery
            # =============================================

            print("\n[STEP 5] Identifying accessible button")

            candidates = []

            for node in ax_nodes:

                if node.get("ignored", False):
                    continue

                role = node.get(
                    "role", {}
                ).get("value")

                properties = read_ax_properties(node)

                disabled = properties.get("disabled")

                backend_node_id = node.get(
                    "backendDOMNodeId"
                )

                # Target identification uses semantic role
                # and enabled state, not CSS or XPath.

                if (
                    role == "button"
                    and disabled is not True
                    and backend_node_id is not None
                ):
                    candidates.append(node)

            print(
                "[INFO] Eligible semantic buttons:",
                len(candidates)
            )

            record(
                "Unique enabled semantic button identified",
                len(candidates) == 1
            )

            if len(candidates) != 1:
                raise RuntimeError(
                    "Could not uniquely identify the accessible button"
                )

            # =============================================
            # STEP 6: Resolve and click through CDP
            # =============================================

            print("\n[STEP 6] Resolving accessibility node")

            button_node = candidates[0]

            backend_node_id = button_node[
                "backendDOMNodeId"
            ]

            resolved = cdp.send(
                "DOM.resolveNode",
                {
                    "backendNodeId": backend_node_id
                }
            )

            object_id = resolved.get(
                "object", {}
            ).get("objectId")

            if not object_id:
                raise RuntimeError(
                    "Could not resolve accessibility node"
                )

            print(
                "[INFO] Semantic button resolved through CDP"
            )

            interaction = cdp.send(
                "Runtime.callFunctionOn",
                {
                    "objectId": object_id,
                    "functionDeclaration": """
                        function() {

                            if (
                                !this ||
                                typeof this.click !== "function" ||
                                this.disabled
                            ) {
                                return false;
                            }

                            this.focus();
                            this.click();

                            return true;
                        }
                    """,
                    "returnByValue": True,
                    "userGesture": True
                }
            )

            clicked = (
                interaction.get(
                    "result", {}
                ).get("value") is True
                and "exceptionDetails" not in interaction
            )

            record(
                "Closed Shadow DOM button interaction",
                clicked
            )

            # =============================================
            # STEP 7: Verify accessible status
            # =============================================

            print("\n[STEP 7] Verifying accessible status")

            page.wait_for_function("""
                () => {
                    const status = document.querySelector(
                        'output[role="status"]'
                    );

                    return status &&
                        status.getAttribute("data-state") === "success";
                }
            """, timeout=5000)

            status_text = page.get_by_role(
                "status"
            ).inner_text()

            print("[STATUS]", status_text)

            status_ok = (
                "Authorization completed successfully."
                in status_text
            )

            record(
                "Accessible status update verified",
                status_ok
            )

            cdp.detach()
            cdp = None

    except Exception as error:

        print(
            "\n[ERROR]",
            type(error).__name__,
            str(error)
        )

        results.append(
            (
                f"Execution error: {type(error).__name__}: {error}",
                False
            )
        )

    finally:

        if cdp is not None:
            try:
                cdp.detach()
            except Exception:
                pass

        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass

    # =============================================
    # FINAL REPORT
    # =============================================

    passed = sum(
        1 for _, status in results if status
    )

    failed = len(results) - passed

    print("\n" + "=" * 65)
    print(" Q3 FINAL TEST REPORT")
    print("=" * 65)

    for name, status in results:
        print(
            f"[{'PASS' if status else 'FAIL'}] {name}"
        )

    print("-" * 65)
    print("[INFO] Total checks:", len(results))
    print("[INFO] Passed:", passed)
    print("[INFO] Failed:", failed)

    success = (
        failed == 0
        and len(results) == 7
    )

    if success:
        print("\n[SUCCESS] ALL Q3 TESTS PASSED")
    else:
        print("\n[FAILURE] Q3 TEST SUITE INCOMPLETE")

    report_lines = [
        "FRUGAL TESTING - Q3 TEST REPORT",
        "=" * 50,
        *[
            f"[{'PASS' if status else 'FAIL'}] {name}"
            for name, status in results
        ],
        "",
        f"Total tests: {len(results)}",
        f"Passed: {passed}",
        f"Failed: {failed}",
        "",
        (
            "ALL Q3 TESTS PASSED"
            if success
            else "Q3 TESTS INCOMPLETE"
        )
    ]

    REPORT_FILE.write_text(
        "\n".join(report_lines),
        encoding="utf-8"
    )

    print("[INFO] Report saved:", REPORT_FILE.name)
    print("=" * 65)

    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
