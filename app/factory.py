import json
import os
from datetime import date, timedelta

from dotenv import load_dotenv
from flask import Flask, Response, request, url_for
from flask_compress import Compress
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

load_dotenv()

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

    db.init_app(app)
    migrate.init_app(app, db)
    compress.init_app(app)

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

    image_manifest = _load_image_manifest(app.static_folder)
    # Responsive image widths produced by scripts/build_images.py (descending).
    image_widths = [1920, 1280, 960, 640, 420]

    @app.context_processor
    def inject_globals() -> dict[str, object]:
        # Global template variables (footer year + responsive-image metadata).
        return {
            "current_year": date.today().year,
            "IMG": image_manifest,
            "IMG_WIDTHS": image_widths,
        }

    with app.app_context():
        # Importing models registers them with SQLAlchemy so Flask-Migrate
        # autogenerate can detect them.
        from app import models  # noqa: F401
        from app.routes import register_routes

        register_routes(app)
        db.create_all()

    return app
