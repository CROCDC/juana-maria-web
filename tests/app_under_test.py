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

os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.factory import create_app

if TYPE_CHECKING:
    from playwright._impl._api_structures import SetCookieParam


def build_app(database_url: str) -> Any:
    os.environ["DATABASE_URL"] = database_url
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config.setdefault("SECRET_KEY", "test-secret-key")
    return app


def apply_migrations(app: Any, database_url: str) -> None:
    from flask_migrate import upgrade

    with app.app_context():
        upgrade()


@contextmanager
def client(app: Any) -> Iterator[Any]:
    with app.test_client() as c:
        yield c


class LiveServer:

    def __init__(self, app: Any, host: str, port: int) -> None:
        self._server = make_server(host, port, app, threaded=True)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self.url = f"http://{host}:{port}"

    def stop(self) -> None:
        self._server.shutdown()
        self._thread.join(timeout=2)


def session_cookie(app: Any, base_url: str, **session_data: Any) -> SetCookieParam:
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
