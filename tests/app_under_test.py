"""app_under_test.py — Flask adapter for the cross-project testing strategy.

The framework-specific glue conftest.py imports:
  build_app, apply_migrations, client, LiveServer, session_cookie.

Adapted to juana-maria-web's factory, which differs from the stock template in
one way:
  - ``create_app()`` takes NO config argument; it reads ``DATABASE_URL`` from the
    environment (defaulting to local SQLite). We point it at the test DB by
    setting that env var before building the app.

The schema is owned by Alembic, so ``apply_migrations`` runs the real
``flask db upgrade`` against the fresh test DB — every run exercises the full
migration chain, exactly as production does on deploy.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from flask import session
from flask.sessions import SecureCookieSessionInterface
from werkzeug.serving import make_server

# app/__init__.py eagerly runs ``app = create_app()`` at import (gunicorn's
# ``run:app`` target needs it), and create_app() calls db.create_all(). Importing
# the factory here would therefore connect to whatever DATABASE_URL the env / .env
# holds (a Postgres that isn't reachable from the host) and fail before
# testcontainers even starts. Pin a throwaway in-memory SQLite for that import-time
# instantiation only; the real test app is built by build_app() against the
# testcontainers Postgres. setdefault so an explicit DATABASE_URL still wins.
os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.factory import create_app

if TYPE_CHECKING:
    # Playwright's cookie TypedDict lives in a private module; referenced only for
    # typing (annotations are strings via `from __future__ import annotations`),
    # so this never imports at runtime and survives version bumps.
    from playwright._impl._api_structures import SetCookieParam


def build_app(database_url: str) -> Any:
    # The factory reads DATABASE_URL from the environment, so aim it at the test
    # container's Postgres before constructing the app.
    os.environ["DATABASE_URL"] = database_url
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    # The factory sets no SECRET_KEY (the site has no sessions today). Provide one
    # so the forged-cookie helper below can sign sessions once auth is added.
    app.config.setdefault("SECRET_KEY", "test-secret-key")
    return app


def apply_migrations(app: Any, database_url: str) -> None:
    # Run the real Alembic migration chain against the fresh test DB, the same
    # way production does (Docker entrypoint -> `flask db upgrade`). This exercises
    # every migration on every test run.
    from flask_migrate import upgrade

    with app.app_context():
        upgrade()


@contextmanager
def client(app: Any) -> Iterator[Any]:
    with app.test_client() as c:
        yield c


class LiveServer:
    """Real WSGI server in a background thread (threaded=True → parallel assets)."""

    def __init__(self, app: Any, host: str, port: int) -> None:
        self._server = make_server(host, port, app, threaded=True)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self.url = f"http://{host}:{port}"

    def stop(self) -> None:
        self._server.shutdown()
        self._thread.join(timeout=2)


def session_cookie(app: Any, base_url: str, **session_data: Any) -> SetCookieParam:
    """Mint a signed Flask session cookie for Playwright's add_cookies().

    Unused today (the site has no auth) but kept wired so the forged-cookie
    contexts in conftest.py work the moment a login flow is added.
    """
    parsed = urlparse(base_url)
    with app.test_request_context():
        for k, v in session_data.items():
            session[k] = v
        sci = SecureCookieSessionInterface()
        serializer = sci.get_signing_serializer(app)
        assert serializer is not None, "app.secret_key must be set to sign sessions"
        value = serializer.dumps(dict(session))
    return {
        "name": app.config.get("SESSION_COOKIE_NAME", "session"),
        "value": value,
        "domain": parsed.hostname,
        "path": "/",
        "httpOnly": True,
        "sameSite": "Lax",
    }
