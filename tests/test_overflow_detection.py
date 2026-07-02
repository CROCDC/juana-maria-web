from __future__ import annotations

from typing import Any

from playwright.sync_api import Browser

from pages import PUBLIC_PAGES


def test_no_overflow_hidden_on_html_or_body(
    live_server: str, browser_instance: Browser
) -> None:
    context = browser_instance.new_context(viewport={"width": 375, "height": 667})
    page = context.new_page()
    failures: list[tuple[str, str, str]] = []
    try:
        for path in PUBLIC_PAGES:
            page.goto(f"{live_server}{path}", wait_until="networkidle")
            result: dict[str, Any] = page.evaluate(
                """() => ({
                    html: getComputedStyle(document.documentElement).overflowX,
                    body: getComputedStyle(document.body).overflowX,
                })"""
            )
            if result["html"] == "hidden" or result["body"] == "hidden":
                failures.append((path, result["html"], result["body"]))
    finally:
        context.close()
    assert not failures, (
        f"overflow-x:hidden on html/body hides real horizontal overflow and "
        f"invalidates the responsive layer: {failures}"
    )
