"""HTTP / integration layer — every endpoint, happy path + error paths.

Uses the `client` fixture (a real Flask test client against the real app on the
test DB). The site is a hub: the home page is the "Sobre la Juana María" topic,
and every other topic is its own page that 404s until published. Visibility is
DB-backed (TopicVisibility) and flipped from the admin panel; these tests cover
the public routes, the topic visibility gate, and the admin auth + toggle flow.
"""

from __future__ import annotations

from typing import Any

from app.repositories.crew_application_repository import CrewApplicationRepository
from app.repositories.topic_visibility_repository import TopicVisibilityRepository

ADMIN_PW = "test-admin-pw"


# ----- GET / (happy path) -----------------------------------------------------

def test_index_returns_200_html(client: Any) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.mimetype == "text/html"


def test_index_renders_hero_and_home_sections(client: Any) -> None:
    body = client.get("/").get_data(as_text=True)
    assert "<h1>Juana María</h1>" in body
    # The dynamic footer year (inject_globals) is rendered server-side.
    assert "Juana María — Argentina" in body
    # Sections that stay on the home ("about") topic.
    for anchor in ('id="historia"', 'id="galeria"', 'id="ficha"'):
        assert anchor in body
    # Seminars moved to its own topic page, and Los Pericos was removed: neither
    # should be a home section anymore.
    assert 'id="seminarios"' not in body
    assert 'id="pericos"' not in body


def test_los_pericos_section_removed(client: Any) -> None:
    body = client.get("/").get_data(as_text=True)
    assert "Los Pericos" not in body
    assert "video-facade" not in body


def test_nav_lists_published_topics_only(client: Any) -> None:
    body = client.get("/").get_data(as_text=True)
    # crew-program is published by default; seminars is not.
    assert "Programa de tripulantes" in body
    assert "Seminarios a bordo" not in body


def test_neutral_names_pass_removed_private_names(client: Any) -> None:
    # Point 4 of the brief: no private captains/owners by name.
    body = client.get("/").get_data(as_text=True)
    for name in ("Wasserman", "Marcelo Blanco", "Mateo Blanco", "Tedín"):
        assert name not in body, f"private name still present: {name}"


# ----- Topic pages (visibility gate) -----------------------------------------

def test_published_topic_page_returns_200(client: Any) -> None:
    resp = client.get("/crew-program")
    assert resp.status_code == 200
    assert "Programa de tripulantes" in resp.get_data(as_text=True)


def test_unpublished_topic_page_returns_404(client: Any) -> None:
    # seminars exists in the registry but is disabled by default.
    assert client.get("/seminars").status_code == 404


def test_enabling_a_topic_makes_its_page_reachable(client: Any, app_instance: Any) -> None:
    assert client.get("/seminars").status_code == 404
    with app_instance.app_context():
        TopicVisibilityRepository.set_enabled("seminars", True)
    resp = client.get("/seminars")
    assert resp.status_code == 200
    assert "Seminarios a bordo" in resp.get_data(as_text=True)
    # And it now appears in the nav on the home page.
    assert "Seminarios a bordo" in client.get("/").get_data(as_text=True)


# ----- Crew-program prominence on the home -----------------------------------

def test_home_shows_crew_cta_band_when_published(client: Any) -> None:
    body = client.get("/").get_data(as_text=True)
    assert 'class="crew-cta"' in body
    # The band's button links to the crew-program page.
    assert "Quiero ser tripulante" in body
    assert 'href="/crew-program"' in body


def test_home_hides_crew_cta_when_unpublished(client: Any, app_instance: Any) -> None:
    with app_instance.app_context():
        TopicVisibilityRepository.set_enabled("crew-program", False)
    body = client.get("/").get_data(as_text=True)
    assert 'class="crew-cta"' not in body


# ----- Crew-program intake form (DB-backed) ----------------------------------

def test_crew_form_renders_on_published_page(client: Any) -> None:
    body = client.get("/crew-program").get_data(as_text=True)
    assert "<form" in body
    assert 'name="full_name"' in body
    assert 'name="email"' in body


def test_crew_form_valid_submission_persists(client: Any, app_instance: Any) -> None:
    resp = client.post(
        "/crew-program",
        data={
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
            "whatsapp": "+54 11 5555 5555",
            "instagram": "@ada",
            "is_adult": "si",
            "preferred_date": "un sábado de noviembre",
            "preferred_route": "banda-oriental",
            "message": "Quiero navegar.",
        },
    )
    # Post/Redirect/Get to the thank-you state.
    assert resp.status_code == 302
    assert "sent=1" in resp.headers["Location"]
    with app_instance.app_context():
        saved = CrewApplicationRepository.get_all()
    assert len(saved) == 1
    assert saved[0].email == "ada@example.com"
    assert saved[0].whatsapp == "+54 11 5555 5555"
    assert saved[0].instagram == "@ada"
    assert saved[0].is_adult is True
    assert saved[0].preferred_date == "un sábado de noviembre"
    # The rumbo is stored as the enum key from RUMBOS, not free text.
    assert saved[0].preferred_route == "banda-oriental"


def test_crew_form_ignores_unknown_rumbo(client: Any, app_instance: Any) -> None:
    # A preferred_route that isn't a known RUMBOS key is dropped, not stored.
    client.post(
        "/crew-program",
        data={
            "full_name": "Eve",
            "email": "eve@example.com",
            "whatsapp": "123",
            "is_adult": "si",
            "preferred_route": "not-a-rumbo",
        },
    )
    with app_instance.app_context():
        saved = CrewApplicationRepository.get_all()
    assert len(saved) == 1
    assert saved[0].preferred_route is None


def test_crew_form_requires_whatsapp_and_age(client: Any, app_instance: Any) -> None:
    # whatsapp and the age question are both required; missing them blocks the
    # submission even when name + email are valid.
    resp = client.post(
        "/crew-program",
        data={"full_name": "Sin WhatsApp", "email": "ok@example.com"},
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Déjanos un WhatsApp" in body
    assert "si eres mayor de 18" in body
    with app_instance.app_context():
        assert CrewApplicationRepository.get_all() == []


def test_crew_form_thank_you_state_after_redirect(client: Any) -> None:
    body = client.get("/crew-program?sent=1").get_data(as_text=True)
    assert "Recibimos tu inscripción" in body
    assert "<form" not in body  # form is replaced by the success message


def test_crew_form_invalid_shows_errors_and_saves_nothing(
    client: Any, app_instance: Any
) -> None:
    resp = client.post(
        "/crew-program", data={"full_name": "Sin Mail", "email": ""}
    )
    assert resp.status_code == 200
    assert "Ingresa tu email" in resp.get_data(as_text=True)
    with app_instance.app_context():
        assert CrewApplicationRepository.get_all() == []


def test_crew_form_rejects_malformed_email(client: Any, app_instance: Any) -> None:
    resp = client.post(
        "/crew-program", data={"full_name": "Bad Mail", "email": "not-an-email"}
    )
    assert resp.status_code == 200
    assert "no parece válido" in resp.get_data(as_text=True)
    with app_instance.app_context():
        assert CrewApplicationRepository.get_all() == []


def test_crew_form_404_when_topic_unpublished(client: Any, app_instance: Any) -> None:
    with app_instance.app_context():
        TopicVisibilityRepository.set_enabled("crew-program", False)
    assert client.get("/crew-program").status_code == 404
    assert (
        client.post("/crew-program", data={"full_name": "X", "email": "x@y.com"}).status_code
        == 404
    )


# ----- Admin (auth + toggle) -------------------------------------------------

def test_admin_requires_login(client: Any) -> None:
    resp = client.get("/admin/topics")
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["Location"]


def test_admin_login_rejects_bad_password(client: Any, app_instance: Any) -> None:
    app_instance.config["ADMIN_PASSWORD"] = ADMIN_PW
    resp = client.post("/admin/login", data={"password": "wrong"})
    assert resp.status_code == 200
    assert "incorrecta" in resp.get_data(as_text=True)


def test_admin_login_then_toggle_publishes_topic(client: Any, app_instance: Any) -> None:
    app_instance.config["ADMIN_PASSWORD"] = ADMIN_PW
    # Log in.
    login = client.post("/admin/login", data={"password": ADMIN_PW})
    assert login.status_code == 302
    # Publish seminars (and implicitly unpublish crew-program by omission).
    save = client.post("/admin/topics", data={"enabled": ["seminars"]})
    assert save.status_code == 302
    assert client.get("/seminars").status_code == 200
    assert client.get("/crew-program").status_code == 404


def test_admin_logout_clears_session(client: Any, app_instance: Any) -> None:
    app_instance.config["ADMIN_PASSWORD"] = ADMIN_PW
    client.post("/admin/login", data={"password": ADMIN_PW})
    assert client.get("/admin/topics").status_code == 200
    client.post("/admin/logout")
    assert client.get("/admin/topics").status_code == 302


# ----- Admin (crew applications list) ----------------------------------------

def test_admin_crew_requires_login(client: Any) -> None:
    resp = client.get("/admin/crew")
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["Location"]


def test_admin_crew_lists_submitted_applications(client: Any, app_instance: Any) -> None:
    app_instance.config["ADMIN_PASSWORD"] = ADMIN_PW
    with app_instance.app_context():
        CrewApplicationRepository.create(
            full_name="Grace Hopper",
            email="grace@example.com",
            whatsapp="+54 11 5555 1234",
            instagram="@grace",
            is_adult=True,
            preferred_route="southeast",
            message="Quiero sumarme a una salida.",
        )
    client.post("/admin/login", data={"password": ADMIN_PW})
    body = client.get("/admin/crew").get_data(as_text=True)
    assert "Inscripciones de tripulantes" in body
    assert "Grace Hopper" in body
    assert "grace@example.com" in body
    assert "@grace" in body
    # The admin resolves the stored rumbo key ("southeast") to its display name.
    assert "Rumbo Sudeste" in body
    assert "Mayor de 18" in body


def test_admin_crew_shows_empty_state_with_no_applications(
    client: Any, app_instance: Any
) -> None:
    app_instance.config["ADMIN_PASSWORD"] = ADMIN_PW
    client.post("/admin/login", data={"password": ADMIN_PW})
    body = client.get("/admin/crew").get_data(as_text=True)
    assert "Todavía no hay inscripciones" in body


# ----- Error paths ------------------------------------------------------------

def test_unknown_path_returns_404(client: Any) -> None:
    resp = client.get("/no-such-page")
    assert resp.status_code == 404


def test_post_to_index_is_method_not_allowed(client: Any) -> None:
    # The index route only registers GET; POST must be rejected, not 500.
    resp = client.post("/")
    assert resp.status_code == 405


# ----- Sitemap (published topics) --------------------------------------------

def test_sitemap_lists_only_published_topics(client: Any) -> None:
    body = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/crew-program" in body
    assert "/seminars" not in body


# ----- Static asset caching (app/factory.py after_request) --------------------

def test_static_asset_has_immutable_cache_header(client: Any) -> None:
    resp = client.get("/static/css/styles.css")
    assert resp.status_code == 200
    assert resp.headers["Cache-Control"] == "public, max-age=31536000, immutable"


# ----- Compression (flask-compress) -------------------------------------------

def test_html_is_gzip_compressed_when_accepted(client: Any) -> None:
    resp = client.get("/", headers={"Accept-Encoding": "gzip"})
    assert resp.status_code == 200
    assert resp.headers.get("Content-Encoding") == "gzip"


def test_html_is_brotli_compressed_when_accepted(client: Any) -> None:
    resp = client.get("/", headers={"Accept-Encoding": "br"})
    assert resp.status_code == 200
    assert resp.headers.get("Content-Encoding") == "br"
