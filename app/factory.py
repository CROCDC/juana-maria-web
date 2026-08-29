import json
import os
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, Response, current_app, redirect, request, url_for
from flask_compress import Compress
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sitecopy import LocalFileStore, SiteCopy
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
sitecopy = SiteCopy()


def _editor_pages() -> list[dict[str, str]]:
    """Pages the visual editor can open in its canvas: home plus every published topic.

    Also the allow-list of pages the editor may START on, so a disabled topic (which
    404s publicly) is never offered as an editing target.
    """
    from app.content.topics import TOGGLEABLE_TOPICS
    from app.repositories.topic_visibility_repository import TopicVisibilityRepository

    pages = [{"path": "/", "label": "Inicio"}]
    try:
        state = TopicVisibilityRepository.get_state_map()
    except Exception:  # noqa: BLE001 — the picker must never 500 the panel
        state = {}
    pages += [
        {"path": topic.path, "label": topic.nav_label}
        for topic in TOGGLEABLE_TOPICS
        if state.get(topic.slug, False)
    ]
    return pages


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
    def inject_image_helpers() -> dict[str, object]:
        """Template helpers for the editable `image` fields (flask-sitecopy 0.3).

        The site ships its photos as responsive `<picture>` sets built from the image
        manifest, but the admin can now paste a different image URL/path per slot. These
        two helpers bridge the two worlds without touching the fast path for the bundled
        photos.
        """
        static_prefix = "/static/img/"
        fallback_suffix = "-fallback.jpg"

        def img_src(value: object) -> dict[str, object]:
            """Decide how a resolved image-field value should render.

            A value that still points at a bundled asset
            (``/static/img/<base>-fallback.jpg``) renders as the full responsive
            ``<picture>`` with its webp srcset; anything an admin pasted (an absolute
            URL, or any other path) renders as a plain ``<img>``. In edit mode ``t()``
            wraps the value in click-to-edit markers, so it stops matching the asset
            pattern and falls to the plain ``<img>`` — which is exactly what the visual
            editor needs to make the picture clickable and open its controls (preview,
            upload, version gallery and alt text) right there on the canvas.
            """
            if (
                isinstance(value, str)
                and value.startswith(static_prefix)
                and value.endswith(fallback_suffix)
            ):
                base = value[len(static_prefix) : -len(fallback_suffix)]
                if base:
                    return {"responsive": True, "base": base, "src": value}
            return {"responsive": False, "base": None, "src": value}

        def share_image_url(value: object) -> str:
            """An absolute URL for a share/JSON-LD image, from an image-field value.

            A bundled ``/static`` path goes through the cache-busting static URL (so the
            default output is byte-for-byte what the site emitted before); an already
            absolute ``http(s)`` URL is used as-is.
            """
            text = value if isinstance(value, str) else ""
            if text.startswith(("http://", "https://")):
                return text
            prefix = "/static/"
            if text.startswith(prefix):
                return static_url("static", filename=text[len(prefix) :], _external=True)
            return canonical_root().rstrip("/") + "/" + text.lstrip("/")

        return {"img_src": img_src, "share_image_url": share_image_url}

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

    # In-place content editor at /admin/content. Wired AFTER Compress (Flask runs
    # after_request hooks in reverse order, and the editor rewrites the HTML — it must
    # see the response before it is gzipped) and AFTER the routes so it reuses the
    # site's own admin session. The site_texts and site_media_versions tables are
    # created by migrations, so ensure_schema() is intentionally not called here.
    #
    # That ordering used to matter only to an admin in `?edit=1`; since text sizes were
    # turned on (below) the rewrite runs on public pages too, so getting it backwards
    # would ship the editor's private-use markers to every visitor as empty boxes.
    # `tests/test_sitecopy_pipeline.py` fails if these two lines ever swap.
    from app.admin_auth import is_logged_in, login_required
    from app.content.copy_registry import REGISTRY

    # Uploads for the image/video fields (flask-sitecopy 0.4): the editor can upload a
    # file straight from the panel instead of only pasting a URL. Files are written under
    # the served static folder (mounted on a persistent volume in docker-compose, so they
    # survive a redeploy) and addressed by content hash. The version history that lets the
    # editor roll a picture/clip back rides the same `db` (table from migration 0004).
    # Since 0.6 all of that — preview, upload, the version gallery and the picture's own
    # alt text — opens on the canvas when the picture is clicked, so nothing about the
    # wiring changes but the owner never has to find the side panel to change a photo.
    uploads_store: LocalFileStore | bool = False
    if app.static_folder:
        uploads_store = LocalFileStore(
            os.path.join(app.static_folder, "sitecopy-uploads"),
            "/static/sitecopy-uploads",
        )

    sitecopy.init_app(
        app,
        registry=REGISTRY,
        db=db,
        login_required=login_required,
        is_logged_in=is_logged_in,
        pages=_editor_pages,
        brand="Juana María",
        site_url=app.config.get("CANONICAL_URL") or "",
        files=uploads_store,
        # Editable text sizes (flask-sitecopy 0.5): every text field grows an A−/A+ pair
        # on the block itself and a "Tamaño" dropdown in the panel. The whole scale is
        # offered — the steps are relative (`em`), so the site's own clamp()-based type
        # scale keeps deciding the absolute size at every breakpoint, and "Normal" is the
        # absence of an override rather than a value. Fields that never reach the page as
        # visible text (a `<title>`, an aria-label, the JSON-LD description) are marked
        # `resizable=False` in the registry so the panel does not offer a size that
        # nothing would render. The CSS goes inline in the `<head>`; the site sends no
        # Content-Security-Policy, so `text_sizes_css="link"` is not needed.
        text_sizes=True,
    )

    return app
