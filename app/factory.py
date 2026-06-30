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

# The site's audience and admin are in Argentina; crew applications are stored in
# UTC but shown to the admin in local time. Fall back to a fixed UTC-3 offset if
# the zone database is unavailable (e.g. a slim container without tzdata) —
# Argentina has observed no DST since 2009, so the offset is constant.
try:
    _BA_TZ: ZoneInfo | timezone = ZoneInfo("America/Argentina/Buenos_Aires")
except Exception:  # noqa: BLE001 — missing tzdata must not crash app import
    _BA_TZ = timezone(timedelta(hours=-3))

# gzip/brotli for text responses (HTML/CSS/JS/SVG). Render-blocking CSS/HTML
# shrink ~4-5x, cutting time-to-first-render. woff2/images are already
# compressed and are skipped by content type.
compress = Compress()


def _load_image_manifest(static_folder: str | None) -> dict[str, dict[str, int]]:
    """Intrinsic dimensions per image key, written by scripts/build_images.py.

    Templates use these to set width/height (and build srcset) so images never
    cause layout shift. Loaded once at startup.
    """
    if not static_folder:
        return {}
    path = os.path.join(static_folder, "img", "manifest.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}

def canonical_root() -> str:
    """Absolute public origin (with trailing slash) for SEO URLs and host redirects.

    Returns the configured CANONICAL_URL so canonical/OG/sitemap/robots URLs are
    emitted on the primary domain regardless of which host served the request.
    Falls back to the request's own origin in dev/tests, where no public origin
    is configured.
    """
    base = current_app.config.get("CANONICAL_URL")
    return base.rstrip("/") + "/" if base else request.url_root


# Extensions are created at module level so models and repositories can import
# them (e.g. ``from app.factory import db``).
db = SQLAlchemy()
migrate = Migrate()


def create_app() -> Flask:
    app = Flask(__name__)

    # Static asset caching (conventions §7.1): without this Flask serves static
    # files with ``no-cache`` and Lighthouse flags inefficient cache lifetimes.
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = timedelta(days=365)

    # Database configuration. Default to local SQLite for dev; production injects
    # DATABASE_URL (PostgreSQL) via the environment.
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///local.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Umami analytics: the website id is public (it ships in the client HTML), so
    # it's wired through a plain env var, not a secret. Templates guard on it.
    app.config["UMAMI_WEBSITE_ID"] = os.environ.get("UMAMI_WEBSITE_ID")

    # Sessions (admin login). SECRET_KEY signs the session cookie; production
    # injects a real value via the environment. The dev fallback only exists so
    # local runs work out of the box — never use it in production.
    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY", "dev-insecure-secret-key-change-me"
    )
    # Admin panel password (controls topic visibility). If unset, admin login is
    # effectively disabled — no password can match.
    app.config["ADMIN_PASSWORD"] = os.environ.get("ADMIN_PASSWORD")

    # Public canonical origin (e.g. https://velaclasica.ar). When set, alias hosts
    # 301 here and SEO URLs are emitted on this origin regardless of which host
    # served the request. Unset in dev/tests, where the request's own origin is used.
    app.config["CANONICAL_URL"] = os.environ.get("CANONICAL_URL")
    # Hosts that 301 to CANONICAL_URL (the www variant + the internal nexttech
    # subdomain). Comma-separated; matched case-insensitively, port stripped.
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
        # In production the app answers on several hosts (the public apex, its
        # www, and the internal nexttech subdomain) but only one is canonical:
        # alias hosts 301 to CANONICAL_URL so users and crawlers converge on a
        # single origin. No-op in dev/tests (REDIRECT_HOSTS unset).
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
        # Cache-bust static URLs with the file's mtime so a changed file
        # becomes a new URL (safe for the year-long immutable cache above).
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
        # Templates calling url_for('static', filename=...) get ?v=<mtime> automatically.
        return {"url_for": static_url}

    @app.template_filter("localdt")
    def _localdt(value: datetime | None) -> str:
        """Render a stored (UTC) datetime in Buenos Aires local time for the admin."""
        if value is None:
            return "—"
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(_BA_TZ).strftime("%d/%m/%Y · %H:%M")

    image_manifest = _load_image_manifest(app.static_folder)
    # Responsive image widths produced by scripts/build_images.py (descending).
    image_widths = [1920, 1280, 960, 640, 420]

    @app.context_processor
    def inject_globals() -> dict[str, object]:
        # Global template variables (footer year + responsive-image metadata).
        # RUMBOS is the single source of truth shared by the routes page and the
        # crew-program form's "rumbo de preferencia" select (see content/rumbos).
        from app.content.rumbos import RUMBOS, RUMBOS_BY_KEY

        return {
            "current_year": date.today().year,
            "IMG": image_manifest,
            "IMG_WIDTHS": image_widths,
            "rumbos": RUMBOS,
            "rumbos_by_key": RUMBOS_BY_KEY,
            "canonical_base": canonical_root(),
        }

    @app.context_processor
    def inject_topics() -> dict[str, object]:
        # Nav + hub iterate over the currently published topics. The home topic
        # is always present; the rest depend on their admin-controlled state.
        # Guarded so an error page still renders if the DB is unreachable.
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
        # Importing models registers them with SQLAlchemy so Flask-Migrate
        # autogenerate can detect them.
        from sqlalchemy import inspect as sa_inspect

        from app import models  # noqa: F401
        from app.content.topics import DEFAULT_ENABLED
        from app.repositories.topic_visibility_repository import (
            TopicVisibilityRepository,
        )
        from app.routes import register_routes

        register_routes(app)
        # The schema is owned by Alembic (`flask db upgrade`, run from the Docker
        # entrypoint before the server starts), not db.create_all(). Seed the
        # reference rows only once the table exists, so importing the app before
        # the first migration runs (e.g. during `flask db upgrade` itself) never
        # crashes on a missing table.
        if sa_inspect(db.engine).has_table("topic_visibility"):
            TopicVisibilityRepository.ensure_seeded(DEFAULT_ENABLED)

    return app
