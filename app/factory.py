import json
import os
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, Response, current_app, redirect, request, url_for
from flask_compress import Compress
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from werkzeug.wrappers import Response as WerkzeugResponse

load_dotenv()

try:
    _BA_TZ: ZoneInfo | timezone = ZoneInfo("America/Argentina/Buenos_Aires")
except Exception:  # noqa: BLE001 — missing tzdata must not crash app import
    _BA_TZ = timezone(timedelta(hours=-3))

compress = Compress()


def _load_image_manifest(static_folder: str | None) -> dict[str, dict[str, int]]:
    if not static_folder:
        return {}
    path = os.path.join(static_folder, "img", "manifest.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}

def canonical_root() -> str:
    base = current_app.config.get("CANONICAL_URL")
    return base.rstrip("/") + "/" if base else request.url_root


db = SQLAlchemy()
migrate = Migrate()


def create_app() -> Flask:
    app = Flask(__name__)

    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = timedelta(days=365)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///local.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["UMAMI_WEBSITE_ID"] = os.environ.get("UMAMI_WEBSITE_ID")

    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY", "dev-insecure-secret-key-change-me"
    )
    app.config["ADMIN_PASSWORD"] = os.environ.get("ADMIN_PASSWORD")

    app.config["CANONICAL_URL"] = os.environ.get("CANONICAL_URL")
    app.config["REDIRECT_HOSTS"] = {
        h.strip().lower()
        for h in os.environ.get("REDIRECT_HOSTS", "").split(",")
        if h.strip()
    }

    db.init_app(app)
    migrate.init_app(app, db)
    compress.init_app(app)

    @app.before_request
    def redirect_to_canonical_host() -> WerkzeugResponse | None:
        base = app.config["CANONICAL_URL"]
        redirect_hosts = app.config["REDIRECT_HOSTS"]
        if not base or not redirect_hosts:
            return None
        if request.host.split(":", 1)[0].lower() not in redirect_hosts:
            return None
        target = base.rstrip("/") + request.path
        if request.query_string:
            target += "?" + request.query_string.decode("latin-1")
        return redirect(target, code=301)

    @app.after_request
    def add_static_cache_headers(response: Response) -> Response:
        if request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    def static_url(endpoint: str, **values: object) -> str:
        if endpoint == "static":
            filename = values.get("filename")
            if filename and app.static_folder:
                fs_path = os.path.join(app.static_folder, str(filename))
                try:
                    values["v"] = int(os.stat(fs_path).st_mtime)
                except OSError:
                    pass
        return url_for(endpoint, **values)

    @app.context_processor
    def override_url_for() -> dict[str, object]:
        return {"url_for": static_url}

    @app.template_filter("localdt")
    def _localdt(value: datetime | None) -> str:
        if value is None:
            return "—"
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(_BA_TZ).strftime("%d/%m/%Y · %H:%M")

    image_manifest = _load_image_manifest(app.static_folder)
    image_widths = [1920, 1280, 960, 640, 420]

    @app.context_processor
    def inject_globals() -> dict[str, object]:
        from app.content.rumbos import RUMBOS, RUMBOS_BY_KEY

        return {
            "current_year": date.today().year,
            "years_sailing": date.today().year - 1941,
            "IMG": image_manifest,
            "IMG_WIDTHS": image_widths,
            "rumbos": RUMBOS,
            "rumbos_by_key": RUMBOS_BY_KEY,
            "canonical_base": canonical_root(),
        }

    @app.context_processor
    def inject_topics() -> dict[str, object]:
        from app.content.topics import HOME_TOPIC, TOGGLEABLE_TOPICS

        try:
            from app.repositories.topic_visibility_repository import (
                TopicVisibilityRepository,
            )

            state = TopicVisibilityRepository.get_state_map()
        except Exception:  # noqa: BLE001 — never let nav rendering 500 the page
            state = {}

        published = [HOME_TOPIC] + [
            t for t in TOGGLEABLE_TOPICS if state.get(t.slug, False)
        ]
        return {"nav_topics": published}

    with app.app_context():
        from sqlalchemy import inspect as sa_inspect

        from app import models  # noqa: F401
        from app.content.topics import DEFAULT_ENABLED
        from app.repositories.topic_visibility_repository import (
            TopicVisibilityRepository,
        )
        from app.routes import register_routes

        register_routes(app)
        if sa_inspect(db.engine).has_table("topic_visibility"):
            TopicVisibilityRepository.ensure_seeded(DEFAULT_ENABLED)

    return app
