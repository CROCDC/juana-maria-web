from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, expect

_YEARS_SAILING = date.today().year - 1941


@pytest.fixture()
def desktop_context(browser_instance: Browser) -> Iterator[BrowserContext]:
    ctx = browser_instance.new_context(
        viewport={"width": 1280, "height": 800}, reduced_motion="reduce"
    )
    try:
        yield ctx
    finally:
        ctx.close()


def test_homepage_loads_with_hero_and_all_sections(
    live_server: str, desktop_context: BrowserContext
) -> None:
    page = desktop_context.new_page()
    try:
        page.goto(f"{live_server}/", wait_until="networkidle")

        expect(page).to_have_title(
            f"Juana María — Ballenera de 1941 · {_YEARS_SAILING} años "
            "navegando el Río de la Plata"
        )
        expect(page.get_by_role("heading", level=1, name="Juana María")).to_be_visible()
        expect(page.get_by_text("1941 · Buenos Aires")).to_be_visible()

        for anchor in ("historia", "diseno", "galeria", "ficha"):
            expect(page.locator(f"section#{anchor}")).to_have_count(1)
    finally:
        page.close()


def test_prologue_link_jumps_to_history_section(
    live_server: str, desktop_context: BrowserContext
) -> None:
    page = desktop_context.new_page()
    try:
        page.goto(f"{live_server}/", wait_until="networkidle")

        page.locator("#prologo").get_by_role("link", name="Conoce su historia").click()

        page.wait_for_url("**/#historia")
        expect(page.get_by_role("heading", name="Una larga línea de agua")).to_be_visible()
    finally:
        page.close()


def test_desktop_nav_opens_published_topic_page(
    live_server: str, desktop_context: BrowserContext
) -> None:
    page = desktop_context.new_page()
    try:
        page.goto(f"{live_server}/", wait_until="networkidle")

        page.locator("#navLinks").get_by_role("link", name="Programa de tripulantes").click()

        page.wait_for_url("**/crew-program")
        expect(
            page.get_by_role("heading", level=1, name="Programa de tripulantes")
        ).to_be_visible()
    finally:
        page.close()


def test_mobile_menu_opens_and_closes(
    live_server: str, page: Page
) -> None:
    page.goto(f"{live_server}/", wait_until="networkidle")

    toggle = page.locator("#navToggle")
    expect(toggle).to_be_visible()
    expect(toggle).to_have_attribute("aria-expanded", "false")

    toggle.click()
    expect(toggle).to_have_attribute("aria-expanded", "true")
    expect(page.locator("#navLinks")).to_have_class("nav-links is-open")

    page.keyboard.press("Escape")
    expect(toggle).to_have_attribute("aria-expanded", "false")


def test_gallery_lightbox_opens_navigates_and_closes(
    live_server: str, desktop_context: BrowserContext
) -> None:
    page = desktop_context.new_page()
    try:
        page.goto(f"{live_server}/", wait_until="networkidle")

        lightbox = page.locator("#lightbox")
        caption = page.locator("#lbCaption")
        expect(lightbox).to_be_hidden()

        # Read the captions off the carousel instead of hard-coding them: the owner
        # re-curates the gallery, and that must not turn into a red test.
        slide_captions = page.locator(".carousel__cap").all_inner_texts()
        assert len(slide_captions) >= 2

        page.locator(".carousel__slide").first.click()

        expect(lightbox).to_be_visible()
        expect(caption).to_have_text(slide_captions[0])
        expect(page.locator("#lbImg")).not_to_have_attribute("src", "")

        page.keyboard.press("ArrowRight")
        expect(caption).to_have_text(slide_captions[1])

        page.keyboard.press("Escape")
        expect(lightbox).to_be_hidden()
    finally:
        page.close()


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


def test_double_proa_video_loads_source_when_scrolled_into_view(
    live_server: str, desktop_context: BrowserContext
) -> None:
    page = desktop_context.new_page()
    try:
        page.goto(f"{live_server}/", wait_until="networkidle")

        video_source = page.locator("section#diseno video[data-lazy-video] source")
        expect(video_source).to_have_count(0)

        page.locator("section#diseno").scroll_into_view_if_needed()

        expect(video_source).to_have_count(1)
        src = video_source.get_attribute("src") or ""
        assert "double-ender-aerial.mp4" in src, src
    finally:
        page.close()
