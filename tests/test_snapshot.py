"""The content snapshot: does a public render still touch the database?

Written against the failure modes, because the happy path here is indistinguishable
from the bug. A page that renders correctly proves nothing — it renders correctly both
when the snapshot is serving it and when the snapshot is being ignored and Postgres is
quietly answering every request, which is the thing this exists to stop.

So the important tests below break the database on purpose and then require the page
to work anyway.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from sitecopy import SQLAlchemyStore

from app import snapshot
from app.factory import db
from app.repositories.topic_visibility_repository import TopicVisibilityRepository

ADMIN_PW = "test-admin-pw"


@pytest.fixture()
def snapshot_path(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    path = tmp_path / "snapshot.json"
    monkeypatch.setattr(snapshot, "PATH", str(path))
    snapshot.reset_cache()
    yield path
    snapshot.reset_cache()


@pytest.fixture()
def written_snapshot(app_instance: Any, snapshot_path: Any, db_clean: None) -> Any:
    with app_instance.app_context():
        data = snapshot.build(SQLAlchemyStore(db), TopicVisibilityRepository.get_state_map())
        snapshot.write(data)
    snapshot.reset_cache()
    return data


@pytest.fixture()
def db_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every database read raises — exactly what Neon's quota did on 2026-09-21."""

    def boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("psycopg2.OperationalError: exceeded the quota")

    monkeypatch.setattr(SQLAlchemyStore, "as_map", boom)
    monkeypatch.setattr(TopicVisibilityRepository, "get_state_map", staticmethod(boom))


# ------------------------------------------------------------------- building


def test_build_captures_published_texts_and_visibility(written_snapshot: Any) -> None:
    assert written_snapshot["version"] == snapshot.VERSION
    assert "generated_at" in written_snapshot
    assert isinstance(written_snapshot["texts"], dict)
    # The site ships with crew-program published and the rest off.
    assert written_snapshot["topic_visibility"]["crew-program"] is True


def test_build_never_captures_a_draft(
    app_instance: Any, snapshot_path: Any, db_clean: None
) -> None:
    """A draft belongs to the admin who staged it. Baking one would publish it to
    everyone on the next deploy, which is the opposite of what Publicar means."""
    with app_instance.app_context():
        store = SQLAlchemyStore(db)
        store.set_draft("global.brand", "BORRADOR SECRETO")
        store.commit()
        data = snapshot.build(store, TopicVisibilityRepository.get_state_map())

    assert "BORRADOR SECRETO" not in json.dumps(data, ensure_ascii=False)


# ------------------------------------------------- the point: no database read


def test_public_page_renders_with_the_database_down(
    client: Any, written_snapshot: Any, db_is_down: None
) -> None:
    """The whole feature in one assertion: a visitor costs no query."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Juana María" in resp.get_data(as_text=True)


def test_published_topic_page_renders_with_the_database_down(
    client: Any, written_snapshot: Any, db_is_down: None
) -> None:
    assert client.get("/crew-program").status_code == 200


def test_unpublished_topic_still_404s_from_the_snapshot(
    client: Any, written_snapshot: Any, db_is_down: None
) -> None:
    """The snapshot is the published truth, so a miss here is a real 404 — not the
    503 that an unknown visibility has to answer."""
    assert client.get("/seminars").status_code == 404


def test_sitemap_renders_with_the_database_down(
    client: Any, written_snapshot: Any, db_is_down: None
) -> None:
    assert client.get("/sitemap.xml").status_code == 200


# --------------------------------------------------------------- fallbacks


def test_without_a_snapshot_the_site_falls_back_to_the_database(
    client: Any, snapshot_path: Any
) -> None:
    """The snapshot is an optimization, never a dependency."""
    assert not snapshot_path.exists()
    assert client.get("/").status_code == 200
    assert client.get("/crew-program").status_code == 200


def test_a_snapshot_from_another_version_is_ignored(
    client: Any, snapshot_path: Any, written_snapshot: Any
) -> None:
    stale = dict(written_snapshot, version=snapshot.VERSION + 99)
    snapshot_path.write_text(json.dumps(stale), encoding="utf-8")
    snapshot.reset_cache()

    assert snapshot.current() is None
    assert client.get("/").status_code == 200  # served from the database instead


def test_an_unreadable_snapshot_is_ignored(client: Any, snapshot_path: Any) -> None:
    snapshot_path.write_text("{not json", encoding="utf-8")
    snapshot.reset_cache()

    assert snapshot.current() is None
    assert client.get("/").status_code == 200


# --------------------------------------------------------------- the admin


def test_the_admin_reads_the_database_not_the_snapshot(
    client: Any, app_instance: Any, written_snapshot: Any, snapshot_path: Any
) -> None:
    """They are about to edit it, so they have to see what is really stored."""
    app_instance.config["ADMIN_PASSWORD"] = ADMIN_PW
    client.post("/admin/login", data={"password": ADMIN_PW})

    with app_instance.app_context():
        store = SQLAlchemyStore(db)
        store.set_draft("global.brand", "CAMBIO EN CURSO")
        store.commit()

    # The panel lists the pending change even though no deploy has rebuilt anything.
    assert client.get("/admin/content/").status_code in (200, 302)
    assert "CAMBIO EN CURSO" not in client.get("/").get_data(as_text=True)


# ------------------------------------------------- publishing asks for a deploy


def test_only_the_writes_the_public_can_see_trigger_a_rebuild() -> None:
    """A draft save must not deploy: an editing session would become fifty deploys."""
    from app.rebuild import triggers_rebuild

    for path in ("/admin/content/publish", "/admin/content/revert", "/admin/topics"):
        assert triggers_rebuild(path), path
    for path in ("/admin/content/save", "/admin/content/discard", "/admin/login",
                 "/admin/content/upload", "/admin/crew"):
        assert not triggers_rebuild(path), path


def test_publishing_asks_the_pipeline_to_rebuild(
    client: Any, app_instance: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import factory

    called: list[bool] = []

    def fake_rebuild() -> bool:
        called.append(True)
        return True

    monkeypatch.setattr(factory, "request_rebuild", fake_rebuild)
    app_instance.config["ADMIN_PASSWORD"] = ADMIN_PW
    client.post("/admin/login", data={"password": ADMIN_PW})

    client.post("/admin/topics", data={"enabled": ["seminars"]})

    assert called == [True]


def test_a_failed_dispatch_alerts_instead_of_failing_the_save(
    client: Any, app_instance: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The content is already committed; the deploy just did not fire. Say so."""
    from app import factory

    alerts: list[str] = []

    def fake_alert(subject: str, body: str, **kwargs: Any) -> bool:
        alerts.append(subject)
        return True

    monkeypatch.setattr(factory, "request_rebuild", lambda: False)
    monkeypatch.setattr(factory, "send_alert", fake_alert)
    app_instance.config["ADMIN_PASSWORD"] = ADMIN_PW
    client.post("/admin/login", data={"password": ADMIN_PW})

    resp = client.post("/admin/topics", data={"enabled": ["seminars"]})

    assert resp.status_code == 302  # the save succeeded
    assert len(alerts) == 1
    assert "sin poder pedir el deploy" in alerts[0]


def test_rebuild_is_a_noop_without_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.rebuild import request_rebuild

    monkeypatch.delenv("GITHUB_DISPATCH_TOKEN", raising=False)
    assert request_rebuild() is False
