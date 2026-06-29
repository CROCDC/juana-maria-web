"""E2E flows — the load-bearing layer, walked like a manual QA script.

Juana María is a single-page brochure site with no auth, forms or persistence,
so every flow is a read-only browser journey: each test drives a real Chromium
against the live server and asserts on what the USER sees (visible text, URL hash,
DOM state) — exactly the interactions in app/static/js/main.js:

  - in-page anchor navigation (desktop nav)
  - the mobile hamburger menu (open / close)
  - the gallery lightbox (open, keyboard-navigate, close)
  - click-to-load video facades (YouTube / Vimeo)
  - the lazy <video> that loads its source only when scrolled near

There is no repository-level assertion at the end of these journeys because the
site has no side effects to persist — the user-visible outcome IS the assertion.

NEVER time.sleep: every wait is a Playwright auto-retrying expectation or an
explicit wait_for_*.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, expect


@pytest.fixture()
def desktop_context(browser_instance: Browser) -> Iterator[BrowserContext]:
    """A desktop-sized context (the default `page` fixture is mobile, 375px).

    reduced_motion keeps E2E deterministic: scroll-reveal shows immediately and
    the gallery carousel does not autoplay, so a slide stays put to be clicked.
    """
    ctx = browser_instance.new_context(
        viewport={"width": 1280, "height": 800}, reduced_motion="reduce"
    )
    try:
        yield ctx
    finally:
        ctx.close()


# ----- Page load --------------------------------------------------------------

def test_homepage_loads_with_hero_and_all_sections(
    live_server: str, desktop_context: BrowserContext
) -> None:
    page = desktop_context.new_page()
    try:
        page.goto(f"{live_server}/", wait_until="networkidle")

        expect(page).to_have_title(
            "Juana María — Ballenera de 1941 · 85 años navegando el Río de la Plata"
        )
        expect(page.get_by_role("heading", level=1, name="Juana María")).to_be_visible()
        expect(page.get_by_text("Botada en 1941.")).to_be_visible()

        # The home ("about") topic keeps these anchored sections; seminars moved
        # to its own topic page, Los Pericos was removed, and the "Madera, bronce
        # y barniz" (#madera) section is temporarily hidden at the client's request.
        for anchor in ("historia", "diseno", "galeria", "ficha"):
            expect(page.locator(f"section#{anchor}")).to_have_count(1)
    finally:
        page.close()


# ----- In-page navigation (desktop) -------------------------------------------

def test_prologue_link_jumps_to_history_section(
    live_server: str, desktop_context: BrowserContext
) -> None:
    page = desktop_context.new_page()
    try:
        page.goto(f"{live_server}/", wait_until="networkidle")

        page.locator("#prologo").get_by_role("link", name="Conocé su historia").click()

        page.wait_for_url("**/#historia")
        expect(page.get_by_role("heading", name="Una larga línea de agua")).to_be_visible()
    finally:
        page.close()


# ----- Topic navigation (multi-page) ------------------------------------------

def test_desktop_nav_opens_published_topic_page(
    live_server: str, desktop_context: BrowserContext
) -> None:
    page = desktop_context.new_page()
    try:
        page.goto(f"{live_server}/", wait_until="networkidle")

        # crew-program is published by default, so its link is in the nav.
        page.locator("#navLinks").get_by_role("link", name="Programa de tripulantes").click()

        page.wait_for_url("**/crew-program")
        expect(
            page.get_by_role("heading", level=1, name="Programa de tripulantes")
        ).to_be_visible()
    finally:
        page.close()


# ----- Mobile hamburger menu --------------------------------------------------

def test_mobile_menu_opens_and_closes(
    live_server: str, page: Page  # the mobile (375px) `page` fixture from conftest
) -> None:
    page.goto(f"{live_server}/", wait_until="networkidle")

    toggle = page.locator("#navToggle")
    expect(toggle).to_be_visible()  # hamburger only shows on small viewports
    expect(toggle).to_have_attribute("aria-expanded", "false")

    toggle.click()
    expect(toggle).to_have_attribute("aria-expanded", "true")
    expect(page.locator("#navLinks")).to_have_class("nav-links is-open")

    # Escape collapses the overlay (closeMenu in main.js). The open overlay
    # covers the toggle, so it can't be re-clicked to close.
    page.keyboard.press("Escape")
    expect(toggle).to_have_attribute("aria-expanded", "false")


# ----- Gallery lightbox -------------------------------------------------------

def test_gallery_lightbox_opens_navigates_and_closes(
    live_server: str, desktop_context: BrowserContext
) -> None:
    page = desktop_context.new_page()
    try:
        page.goto(f"{live_server}/", wait_until="networkidle")

        lightbox = page.locator("#lightbox")
        caption = page.locator("#lbCaption")
        expect(lightbox).to_be_hidden()

        # Autoplay is off under reduced motion (desktop_context), so the first
        # slide stays in view; clicking it opens the lightbox at that photo.
        page.locator(".carousel__slide").first.click()

        expect(lightbox).to_be_visible()
        expect(caption).to_have_text("A vela llena, atardecer en el Plata")
        expect(page.locator("#lbImg")).not_to_have_attribute("src", "")  # got a real image

        # Arrow keys cycle through the gallery (ArrowRight -> next caption).
        page.keyboard.press("ArrowRight")
        expect(caption).to_have_text("«Juana María» en el casco")

        # Escape closes the dialog and restores the page.
        page.keyboard.press("Escape")
        expect(lightbox).to_be_hidden()
    finally:
        page.close()


# ----- Crew-program intake form -----------------------------------------------

def test_crew_form_submission_shows_thank_you(
    live_server: str, desktop_context: BrowserContext
) -> None:
    page = desktop_context.new_page()
    try:
        page.goto(f"{live_server}/crew-program", wait_until="networkidle")

        page.fill("#email", "grace@example.com")
        page.fill("#full_name", "Grace Hopper")
        page.fill("#whatsapp", "+54 11 5555 1234")
        page.check("input[name='is_adult'][value='si']")
        page.select_option("#preferred_route", "banda-oriental")
        page.fill("#message", "Quiero sumarme a la tripulación.")
        page.get_by_role("button", name="Enviar inscripción").click()

        page.wait_for_url("**/crew-program?sent=1")
        expect(page.get_by_text("Recibimos tu inscripción")).to_be_visible()
    finally:
        page.close()


# ----- Lazy-loaded <video> ----------------------------------------------------

def test_double_proa_video_loads_source_when_scrolled_into_view(
    live_server: str, desktop_context: BrowserContext
) -> None:
    page = desktop_context.new_page()
    try:
        page.goto(f"{live_server}/", wait_until="networkidle")

        video_source = page.locator("section#diseno video[data-lazy-video] source")
        expect(video_source).to_have_count(0)  # nothing fetched above the fold

        page.locator("section#diseno").scroll_into_view_if_needed()

        # whenNear() appends a <source> + calls video.load() as the section nears.
        expect(video_source).to_have_count(1)
        # URL carries a ?v=<mtime> cache-bust (factory's static_url), so match
        # on the filename rather than the full string.
        src = video_source.get_attribute("src") or ""
        assert "double-ender-aerial.mp4" in src, src
    finally:
        page.close()
