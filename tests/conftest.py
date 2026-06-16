"""Shared fixtures: real DB (testcontainers), HTTP client, live server, Playwright.

Framework-agnostic core of the cross-project testing strategy
(docs/testing/TESTING_STRATEGY.md in infra.pantech). The ONLY framework-specific
glue lives in `app_under_test.py` — copy the adapter for your stack (Flask /
FastAPI / Django / other) and leave THIS file verbatim.

The suite runs against the SAME database engine/version as production, started
once per session via testcontainers; real migrations are applied (every run
exercises them); between tests we TRUNCATE (schema/extensions/indexes stay warm)
instead of recreating the DB or rolling back nested transactions.

Import note: assumes pytest's DEFAULT import mode with `tests/` NOT a package
(no `__init__.py`) — sibling modules (`app_under_test`, `pages`) import by bare
name. If you make `tests/` a package, switch those to relative imports.
"""

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

# Same image/version/extensions as production. Override per project (TEST_DB_IMAGE).
# For MySQL, swap PostgresContainer for testcontainers.mysql.MySqlContainer (here
# and in the import) and adjust the TRUNCATE catalog query in db_clean.
DB_IMAGE = os.environ.get("TEST_DB_IMAGE", "postgres:16")
# Migration bookkeeping table to keep when truncating ('django_migrations' on Django).
MIGRATION_TABLE = os.environ.get("TEST_MIGRATION_TABLE", "alembic_version")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# ----- Database (framework-agnostic) ------------------------------------------

@pytest.fixture(scope="session")
def db_container() -> Iterator[PostgresContainer]:
    """Production DB engine, once per session.

    fsync / synchronous_commit / full_page_writes are off: safe in a throwaway
    test container and they shave significant startup + per-commit time.
    """
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
    """SQLAlchemy-style connection URL for the test DB."""
    return db_container.get_connection_url()


@pytest.fixture(scope="session")
def app_instance(database_url: str) -> Iterator[Any]:
    """The app under test, on the test DB, with real migrations applied."""
    app = adapter.build_app(database_url)
    adapter.apply_migrations(app, database_url)
    yield app


@pytest.fixture(scope="session")
def _truncate_engine(database_url: str) -> Iterator[Any]:
    """Raw engine used only to TRUNCATE between tests, independent of the app ORM."""
    engine = sqlalchemy.create_engine(database_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def db_clean(app_instance: Any, _truncate_engine: Any) -> Iterator[None]:
    """TRUNCATE all tables (except the migration bookkeeping table) after each test.

    Faster than recreating the DB and avoids the subtle bugs of rollback-based
    isolation (a test that itself issues ROLLBACK behaves differently in real life).
    """
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
    """HTTP test client for endpoint tests (happy + error paths)."""
    with adapter.client(app_instance) as c:
        yield c


# ----- Live server + Playwright -----------------------------------------------

@pytest.fixture(scope="session")
def live_server(app_instance: Any) -> Iterator[str]:
    """Serve the real app (WSGI or ASGI) on a free port for Playwright.

    A real HTTP server is required: test clients serve no static assets and run no
    JS. Same process, same DB, same app instance.
    """
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
    """One headless Chromium per session."""
    browser = playwright_session.chromium.launch(headless=True)
    try:
        yield browser
    finally:
        browser.close()


@pytest.fixture()
def context(browser_instance: Browser, db_clean: None) -> Iterator[BrowserContext]:
    """One fresh context per test — cheap, full isolation. Viewport = primary form factor."""
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


# ----- Authenticated browser contexts (forged session, no login form) ---------
# One fixture per role. Walking the login form on every E2E test is slow and
# fragile, so we mint the session directly. The login flow that PRODUCES the
# session still gets its own E2E test that walks the real form.
# ADAPT the session payload (id key, role key) to your app's auth.

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
