from __future__ import annotations

import os
import socket
from collections.abc import Iterator
from typing import Any

import pytest
import sqlalchemy
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
from testcontainers.postgres import PostgresContainer

import app_under_test as adapter

DB_IMAGE = os.environ.get("TEST_DB_IMAGE", "postgres:16")
MIGRATION_TABLE = os.environ.get("TEST_MIGRATION_TABLE", "alembic_version")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def db_container() -> Iterator[PostgresContainer]:
    container = PostgresContainer(image=DB_IMAGE).with_command(
        "postgres -c fsync=off -c synchronous_commit=off -c full_page_writes=off"
    )
    container.start()
    try:
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def database_url(db_container: PostgresContainer) -> str:
    return db_container.get_connection_url()


@pytest.fixture(scope="session")
def app_instance(database_url: str) -> Iterator[Any]:
    app = adapter.build_app(database_url)
    adapter.apply_migrations(app, database_url)
    yield app


@pytest.fixture(scope="session")
def _truncate_engine(database_url: str) -> Iterator[Any]:
    engine = sqlalchemy.create_engine(database_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def db_clean(app_instance: Any, _truncate_engine: Any) -> Iterator[None]:
    yield
    with _truncate_engine.begin() as conn:
        rows = conn.exec_driver_sql(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
        tables = [r[0] for r in rows if r[0] != MIGRATION_TABLE]
        if tables:
            joined = ", ".join(f'"{t}"' for t in tables)
            conn.exec_driver_sql(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE")


@pytest.fixture()
def client(app_instance: Any, db_clean: None) -> Iterator[Any]:
    with adapter.client(app_instance) as c:
        yield c


@pytest.fixture(autouse=True)
def _seed_topic_visibility(app_instance: Any, db_clean: None) -> None:
    from app.content.topics import DEFAULT_ENABLED
    from app.repositories.topic_visibility_repository import TopicVisibilityRepository

    with app_instance.app_context():
        TopicVisibilityRepository.ensure_seeded(DEFAULT_ENABLED)


@pytest.fixture(scope="session")
def live_server(app_instance: Any) -> Iterator[str]:
    server = adapter.LiveServer(app_instance, "127.0.0.1", _free_port())
    try:
        yield server.url
    finally:
        server.stop()


@pytest.fixture(scope="session")
def playwright_session() -> Iterator[Any]:
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def browser_instance(playwright_session: Any) -> Iterator[Browser]:
    browser = playwright_session.chromium.launch(headless=True)
    try:
        yield browser
    finally:
        browser.close()


@pytest.fixture()
def context(browser_instance: Browser, db_clean: None) -> Iterator[BrowserContext]:
    ctx = browser_instance.new_context(viewport={"width": 375, "height": 667})
    try:
        yield ctx
    finally:
        ctx.close()


@pytest.fixture()
def page(context: BrowserContext) -> Iterator[Page]:
    pg = context.new_page()
    try:
        yield pg
    finally:
        pg.close()


@pytest.fixture()
def patron_browser_context(
    browser_instance: Browser, app_instance: Any, live_server: str, db_clean: None
) -> Iterator[BrowserContext]:
    ctx = browser_instance.new_context(viewport={"width": 375, "height": 667})
    ctx.add_cookies([adapter.session_cookie(app_instance, live_server, user_id=1, role="patron")])
    try:
        yield ctx
    finally:
        ctx.close()


@pytest.fixture()
def admin_browser_context(
    browser_instance: Browser, app_instance: Any, live_server: str, db_clean: None
) -> Iterator[BrowserContext]:
    ctx = browser_instance.new_context(viewport={"width": 1280, "height": 720})
    ctx.add_cookies([adapter.session_cookie(app_instance, live_server, user_id=2, role="admin")])
    try:
        yield ctx
    finally:
        ctx.close()
