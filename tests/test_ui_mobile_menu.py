"""UI / visual-regression for the responsive side menu (the hamburger overlay).

Below 1080px the inline nav collapses into a hamburger that opens a full-screen
overlay menu (`.nav-links.is-open`, see the @media block in styles.css and the
toggle handler in main.js). The responsive layer screenshots the page with the
menu CLOSED, so this file covers the OPEN state at every viewport where the
hamburger exists, and commits a screenshot of each as the baseline.
"""

from __future__ import annotations

import os

import pytest
from playwright.sync_api import Browser, expect

from pages import VIEWPORTS

_SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")

# The hamburger only appears below 1080px (styles.css: @media max-width: 1080px).
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
        expect(toggle).to_be_visible()  # hamburger present at this breakpoint
        toggle.click()

        # Menu slid in: toggle flips to its open state and every link is visible.
        expect(toggle).to_have_attribute("aria-expanded", "true")
        nav_links = page.locator("#navLinks")
        expect(nav_links).to_have_class("nav-links is-open")
        # Nav is driven by the published topics: the home ("about") topic is
        # always present, plus crew-program (the one published by default).
        for label in ("Sobre la Juana María", "Programa de tripulantes"):
            expect(nav_links.get_by_role("link", name=label)).to_be_visible()

        # The overlay covers the full viewport — width AND height. Height matters:
        # a backdrop-filtered nav would clip the fixed overlay to the bar's height
        # (see test_side_menu_covers_page_when_scrolled), letting the page show
        # through; assert both dimensions so that regression can't slip past.
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
    """Regression: opening the menu mid-page must still cover the whole viewport.

    The nav bar uses backdrop-filter (always on the solid-nav topic pages, and on
    the home once scrolled). A backdrop-filtered element becomes the containing
    block for its fixed-position descendants, which used to clip the open overlay
    to the bar's height — so the menu links bled over the page content when opened
    after scrolling. main.js drops the filter (.nav.menu-open) while the menu is
    open; this guards that fix.
    """
    width, height = 390, 844
    context = browser_instance.new_context(
        viewport={"width": width, "height": height}, reduced_motion="reduce"
    )
    page = context.new_page()
    try:
        # A solid-nav topic page (crew-program is published by default) — its nav
        # carries backdrop-filter at all times, the exact trigger for the bug.
        page.goto(f"{live_server}/crew-program", wait_until="networkidle")
        # Scroll past the threshold so .is-scrolled is also active (mid-page).
        page.evaluate("window.scrollTo(0, 600)")
        page.wait_for_function("document.getElementById('nav').classList.contains('is-scrolled')")

        page.locator("#navToggle").click()
        nav_links = page.locator("#navLinks")
        expect(nav_links).to_have_class("nav-links is-open")

        box = nav_links.bounding_box()
        assert box is not None
        # The overlay must fill the viewport in BOTH dimensions; before the fix its
        # height collapsed to the nav bar (~60px) and the page showed through.
        assert abs(box["width"] - width) <= 1, f"menu width {box['width']} != {width}"
        assert box["height"] >= height - 1, f"menu height {box['height']} < {height}"
    finally:
        context.close()
