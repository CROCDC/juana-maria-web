from __future__ import annotations

import os

import pytest
from playwright.sync_api import Browser, expect

from pages import VIEWPORTS

_SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")

_MENU_VIEWPORTS = [(n, w, h) for (n, w, h) in VIEWPORTS if w <= 1080]


@pytest.mark.parametrize("viewport_name,width,height", _MENU_VIEWPORTS)
def test_side_menu_opens_full_screen(
    live_server: str,
    browser_instance: Browser,
    viewport_name: str,
    width: int,
    height: int,
) -> None:
    context = browser_instance.new_context(
        viewport={"width": width, "height": height}, reduced_motion="reduce"
    )
    page = context.new_page()
    try:
        page.goto(f"{live_server}/", wait_until="networkidle")

        toggle = page.locator("#navToggle")
        expect(toggle).to_be_visible()
        toggle.click()

        expect(toggle).to_have_attribute("aria-expanded", "true")
        nav_links = page.locator("#navLinks")
        expect(nav_links).to_have_class("nav-links is-open")
        for label in ("Sobre la Juana María", "Programa de tripulantes"):
            expect(nav_links.get_by_role("link", name=label)).to_be_visible()

        box = nav_links.bounding_box()
        assert box is not None
        assert abs(box["width"] - width) <= 1, f"menu width {box['width']} != {width}"
        assert box["height"] >= height - 1, f"menu height {box['height']} < {height}"

        os.makedirs(_SCREENSHOT_DIR, exist_ok=True)
        page.screenshot(path=os.path.join(_SCREENSHOT_DIR, f"menu-open-{viewport_name}.png"))
    finally:
        context.close()


def test_side_menu_covers_page_when_scrolled(
    live_server: str, browser_instance: Browser
) -> None:
    width, height = 390, 844
    context = browser_instance.new_context(
        viewport={"width": width, "height": height}, reduced_motion="reduce"
    )
    page = context.new_page()
    try:
        page.goto(f"{live_server}/crew-program", wait_until="networkidle")
        page.evaluate("window.scrollTo(0, 600)")
        page.wait_for_function("document.getElementById('nav').classList.contains('is-scrolled')")

        page.locator("#navToggle").click()
        nav_links = page.locator("#navLinks")
        expect(nav_links).to_have_class("nav-links is-open")

        box = nav_links.bounding_box()
        assert box is not None
        assert abs(box["width"] - width) <= 1, f"menu width {box['width']} != {width}"
        assert box["height"] >= height - 1, f"menu height {box['height']} < {height}"
    finally:
        context.close()
