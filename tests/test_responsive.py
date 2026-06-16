"""Responsive / visual-regression layer: every public page x every viewport.

Two assertions per cell:
  1. No horizontal overflow — scrollWidth must not exceed the viewport width
     (+1px tolerance for sub-pixel rounding).
  2. A full-page screenshot is written to tests/screenshots/, COMMITTED as the
     visual baseline; diffs surface during code review.

The overflow assertion is only trustworthy if test_overflow_detection passes
first (no overflow-x:hidden on html/body) — see that file.
"""

from __future__ import annotations

import os

import pytest
from playwright.sync_api import Browser

from pages import PUBLIC_PAGES, VIEWPORTS, page_slug

_SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
_PAGES = [(page_slug(p), p) for p in PUBLIC_PAGES]


@pytest.mark.parametrize("page_name,path", _PAGES)
@pytest.mark.parametrize("viewport_name,width,height", VIEWPORTS)
def test_page_responsive(
    live_server: str,
    browser_instance: Browser,
    page_name: str,
    path: str,
    viewport_name: str,
    width: int,
    height: int,
) -> None:
    # reduced_motion makes the baseline deterministic: main.js then skips the
    # count-up animation (leaving the literal "85" instead of a frozen mid-count
    # value) and reveals all scroll-in content immediately. Without it, full-page
    # screenshots catch animations mid-flight and diff noisily on every run.
    context = browser_instance.new_context(
        viewport={"width": width, "height": height}, reduced_motion="reduce"
    )
    page = context.new_page()
    try:
        page.goto(f"{live_server}{path}", wait_until="networkidle")

        scroll_width = page.evaluate("document.documentElement.scrollWidth")
        assert scroll_width <= width + 1, (
            f"Horizontal overflow on {path} @ {viewport_name}: "
            f"{scroll_width}px > {width}px"
        )

        # The page lazy-loads images (loading="lazy") and media below the fold;
        # a naive full-page screenshot leaves those cells blank (e.g. the gallery
        # grid). Walk the whole page to trigger every lazy load, return to top,
        # then wait for all images to finish decoding before capturing.
        page.evaluate(
            """async () => {
                const vh = window.innerHeight;
                for (let y = 0; y < document.body.scrollHeight; y += vh) {
                    window.scrollTo(0, y);
                    await new Promise(r => setTimeout(r, 80));
                }
                window.scrollTo(0, 0);
            }"""
        )
        # Only require images that actually have a source to finish — the lightbox
        # placeholder <img id="lbImg" src=""> never decodes and would hang this.
        page.wait_for_function(
            """() => Array.from(document.images)
                .filter(img => img.currentSrc || (img.getAttribute('src') || '').trim())
                .every(img => img.complete && img.naturalWidth > 0)""",
            timeout=15000,
        )
        page.wait_for_load_state("networkidle")

        os.makedirs(_SCREENSHOT_DIR, exist_ok=True)
        page.screenshot(
            path=os.path.join(_SCREENSHOT_DIR, f"{page_name}-{viewport_name}.png"),
            full_page=True,
        )
    finally:
        context.close()
