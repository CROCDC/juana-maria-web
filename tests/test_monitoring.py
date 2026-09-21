"""Health endpoint, CDN cache headers and alert mail.

The scenario every one of these is written against is the 2026-09-21 outage: Neon's
quota suspended the database, every DB-backed page 500'd, `/` kept answering 200, and
nothing told anybody.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app import alerts
from app.repositories import topic_visibility_repository
from app.repositories.topic_visibility_repository import TopicVisibilityRepository

ADMIN_PW = "test-admin-pw"


# ------------------------------------------------------------------------ /healthz


def test_healthz_reports_ok_with_a_working_database(client: Any) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = json.loads(resp.get_data(as_text=True))
    assert body["status"] == "ok"
    assert body["checks"] == {"app": "ok", "db": "ok"}


def test_healthz_reports_503_when_the_database_is_unreachable(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom() -> dict[str, bool]:
        raise RuntimeError("connection to server failed: exceeded the quota")

    monkeypatch.setattr(TopicVisibilityRepository, "get_state_map", staticmethod(boom))

    resp = client.get("/healthz")
    assert resp.status_code == 503
    body = json.loads(resp.get_data(as_text=True))
    assert body["status"] == "error"
    assert "exceeded the quota" in body["checks"]["db"]


def test_healthz_shallow_mode_does_not_touch_the_database(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`?db=0` must stay green while Postgres is down — it is the "is the function
    alive?" probe, and it runs often enough that waking Neon would cost real CU-hours."""

    def boom() -> dict[str, bool]:
        raise RuntimeError("should not be called")

    monkeypatch.setattr(TopicVisibilityRepository, "get_state_map", staticmethod(boom))

    resp = client.get("/healthz?db=0")
    assert resp.status_code == 200
    assert json.loads(resp.get_data(as_text=True))["checks"] == {"app": "ok"}


def test_healthz_is_never_cached(client: Any) -> None:
    assert client.get("/healthz").headers["Cache-Control"] == "no-store"


def test_home_page_alone_would_not_have_caught_the_outage(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Why the watchdog cannot just check `/`: its DB reads degrade instead of failing."""

    def boom() -> dict[str, bool]:
        raise RuntimeError("exceeded the quota")

    monkeypatch.setattr(TopicVisibilityRepository, "get_state_map", staticmethod(boom))

    assert client.get("/").status_code == 200
    assert client.get("/healthz").status_code == 503


# ------------------------------------------------------------------- cache headers


def test_public_page_is_cacheable_by_the_cdn(client: Any) -> None:
    headers = client.get("/").headers
    assert "s-maxage=" in headers["Cache-Control"]
    assert "stale-while-revalidate=" in headers["Cache-Control"]
    # Browsers must revalidate, or an edit stays invisible to whoever already visited.
    assert "max-age=0" in headers["Cache-Control"]
    assert "Cookie" in headers["Vary"]


def test_admin_pages_are_not_cacheable(client: Any) -> None:
    assert "s-maxage" not in client.get("/admin/login").headers.get("Cache-Control", "")


def test_logged_in_admin_response_is_not_cacheable(client: Any, app_instance: Any) -> None:
    app_instance.config["ADMIN_PASSWORD"] = ADMIN_PW
    client.post("/admin/login", data={"password": ADMIN_PW})
    assert "s-maxage" not in client.get("/").headers.get("Cache-Control", "")


def test_static_assets_keep_their_immutable_header(client: Any) -> None:
    resp = client.get("/static/css/admin.css")
    assert resp.headers["Cache-Control"] == "public, max-age=31536000, immutable"


# -------------------------------------------------------------------------- alerts


@pytest.fixture()
def resend(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    sent: list[dict[str, Any]] = []

    class _Response:
        status = 200

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

    def fake_urlopen(req: Any, timeout: int = 0) -> _Response:
        sent.append({"url": req.full_url, "body": json.loads(req.data)})
        return _Response()

    monkeypatch.setattr(alerts.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("ALERT_EMAIL_TO", "crocdc1999@gmail.com")
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alertas@velaclasica.ar")
    alerts._last_sent.clear()
    return sent


def test_send_alert_posts_to_resend(resend: list[dict[str, Any]]) -> None:
    assert alerts.send_alert("asunto", "cuerpo") is True
    assert resend[0]["url"] == alerts.RESEND_ENDPOINT
    assert resend[0]["body"]["to"] == ["crocdc1999@gmail.com"]
    assert resend[0]["body"]["subject"] == "asunto"


def test_send_alert_is_a_noop_without_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    assert alerts.send_alert("asunto", "cuerpo") is False


def test_repeated_failures_are_throttled_by_dedup_key(
    resend: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An outage raises the same error on every request; one mail per outage, not per hit."""
    monkeypatch.setenv("ALERT_THROTTLE_SECONDS", "900")
    for _ in range(5):
        alerts.send_alert("asunto", "cuerpo", dedup_key="OperationalError@pool.py:900")
    assert len(resend) == 1


def test_different_failures_are_not_throttled_together(
    resend: list[dict[str, Any]],
) -> None:
    alerts.send_alert("a", "b", dedup_key="OperationalError@pool.py:900")
    alerts.send_alert("c", "d", dedup_key="KeyError@routes.py:42")
    assert len(resend) == 2


def test_unhandled_exception_mails_the_traceback(
    client: Any, app_instance: Any, resend: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reported symptom: the admin panel 500s because the database is gone."""
    app_instance.config["ADMIN_PASSWORD"] = ADMIN_PW
    client.post("/admin/login", data={"password": ADMIN_PW})

    def boom() -> dict[str, bool]:
        raise RuntimeError("exceeded the quota")

    monkeypatch.setattr(TopicVisibilityRepository, "get_state_map", staticmethod(boom))

    with pytest.raises(RuntimeError):
        client.get("/admin/topics")

    assert len(resend) == 1
    assert "RuntimeError" in resend[0]["body"]["subject"]
    assert "/admin/topics" in resend[0]["body"]["subject"]
    assert "exceeded the quota" in resend[0]["body"]["text"]
    assert "Traceback" in resend[0]["body"]["text"]


# --------------------------------------------------- surviving a database outage


@pytest.fixture()
def db_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exactly what Neon's quota did: every read raises at connection time."""

    def boom() -> dict[str, bool]:
        raise RuntimeError("psycopg2.OperationalError: exceeded the quota")

    monkeypatch.setattr(TopicVisibilityRepository, "get_state_map", staticmethod(boom))


def test_topic_page_survives_the_outage_on_the_last_known_state(
    client: Any, db_down: None
) -> None:
    assert client.get("/").status_code == 200  # warms nothing; the read already ran
    assert client.get("/crew-program").status_code == 200
    assert client.get("/sitemap.xml").status_code == 200


def test_nav_stays_populated_during_the_outage(client: Any, db_down: None) -> None:
    assert "Programa de tripulantes" in client.get("/").get_data(as_text=True)


def test_cold_process_during_an_outage_falls_back_to_the_shipped_defaults(
    client: Any, db_down: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(topic_visibility_repository, "_last_known", None)

    body = client.get("/").get_data(as_text=True)
    assert client.get("/crew-program").status_code == 200
    # Still honours what the site ships with, so an unpublished topic stays unpublished.
    assert "Seminarios a bordo" not in body


def test_unknown_visibility_answers_503_not_404(
    client: Any, db_down: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A guess that a page is unpublished must not be served to Google as "gone"."""
    monkeypatch.setattr(topic_visibility_repository, "_last_known", None)

    resp = client.get("/seminars")
    assert resp.status_code == 503
    assert resp.headers["Retry-After"] == "300"
    assert "Volvemos en un momento" in resp.get_data(as_text=True)


def test_an_unpublished_topic_still_404s_when_the_database_answers(client: Any) -> None:
    assert client.get("/seminars").status_code == 404


def test_admin_still_fails_loudly_during_the_outage(
    client: Any, app_instance: Any, db_down: None
) -> None:
    """The panel writes; a stale map there would have somebody toggling the wrong row."""
    app_instance.config["ADMIN_PASSWORD"] = ADMIN_PW
    client.post("/admin/login", data={"password": ADMIN_PW})
    with pytest.raises(RuntimeError):
        client.get("/admin/topics")


def test_a_degraded_page_is_not_handed_to_the_cdn(client: Any, db_down: None) -> None:
    """Caching an outage's output would keep it on screen long after it ended."""
    resp = client.get("/crew-program")
    assert resp.status_code == 200
    assert "s-maxage" not in resp.headers.get("Cache-Control", "")
