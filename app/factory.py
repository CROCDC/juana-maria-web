import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, Response, current_app, g, redirect, request, session, url_for
from flask.sessions import SecureCookieSessionInterface
from flask_compress import Compress
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sitecopy import FileStore, LocalFileStore, SiteCopy
from werkzeug.wrappers import Response as WerkzeugResponse

from app.cdn import SITE_TAG, invalidate_site_cache

load_dotenv()

try:
    _BA_TZ: ZoneInfo | timezone = ZoneInfo("America/Argentina/Buenos_Aires")
except Exception:  # noqa: BLE001 — missing tzdata must not crash app import
    _BA_TZ = timezone(timedelta(hours=-3))

compress = Compress()


def _load_image_manifest() -> dict[str, dict[str, int]]:
    """Intrinsic sizes and the variant widths the image build actually wrote.

    Kept inside the package rather than next to the images it describes: Vercel
    serves `public/` from its CDN but leaves it out of the function bundle, and a
    manifest the app cannot read silently degrades every `<picture>` to the macro's
    guessed dimensions.
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content", "image_manifest.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _static_version() -> str | None:
    """A per-deploy cache-buster for `/static` URLs, or None to use file mtimes.

    Same reason: on Vercel the asset files are not in the bundle, so the mtime the
    URLs are normally versioned by cannot be read — and with `immutable` caching a
    returning visitor would keep the previous deploy's CSS for a year.
    """
    for name in ("VERCEL_DEPLOYMENT_ID", "VERCEL_GIT_COMMIT_SHA", "VERCEL_URL"):
        value = os.environ.get(name)
        if value:
            return "".join(c for c in value if c.isalnum())[:32]
    return None


class CacheableSessionInterface(SecureCookieSessionInterface):
    """Drops `Vary: Cookie` from responses the app already decided are shareable.

    Flask adds that header whenever anything so much as reads the session, and on a
    public page something always does — flask-sitecopy checks `is_logged_in` on every
    render. Vercel refuses to cache any response whose `Vary` names `Cookie` (it logs
    "Vary key denied"), so the site was 100% cache MISS without this, and every visit
    reached the function and woke Postgres.

    Removing it is only safe because `add_cdn_cache_headers` tags a response solely
    when it is anonymous, outside `/admin`, and free of `?edit=`/`?preview=` — i.e.
    when the bytes genuinely do not depend on the cookie. The tag is that decision,
    which is why it is the signal read here. Flask writes the session cookie in this
    same method, after every `after_request` has run, so this is the first point where
    both facts are known.
    """

    def save_session(self, app: Flask, session: Any, response: Response) -> None:  # type: ignore[override]
        super().save_session(app, session, response)
        if not response.headers.get("Vercel-Cache-Tag"):
            return
        # Rewritten by hand rather than through `response.vary`: that property builds a
        # fresh HeaderSet on every access and only writes back from some of its mutators
        # — `discard()` silently changes nothing at all.
        vary = response.headers.get("Vary")
        if not vary:
            return
        kept = [v.strip() for v in vary.split(",") if v.strip().lower() != "cookie"]
        if kept:
            response.headers["Vary"] = ", ".join(kept)
        else:
            del response.headers["Vary"]


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


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


# Assets live at the repo root, not under the package: Vercel only serves files
# from `public/**` through its CDN, and only files present in the uploaded source
# (a directory generated by the build command is not collected).
_STATIC_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public", "static"
)


def create_app() -> Flask:
    app = Flask(__name__, static_folder=_STATIC_FOLDER)

    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = timedelta(days=365)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///local.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    # Serverless (Vercel) reuses a warm instance whose pooled connections outlive
    # the managed Postgres' idle timeout — a scale-to-zero provider hands back a
    # dead socket otherwise. Harmless on the long-lived gunicorn process.
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    app.config["UMAMI_WEBSITE_ID"] = os.environ.get("UMAMI_WEBSITE_ID")

    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY", "dev-insecure-secret-key-change-me"
    )
    app.config["ADMIN_PASSWORD"] = os.environ.get("ADMIN_PASSWORD")

    app.session_interface = CacheableSessionInterface()

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

    # Public HTML is cached at Vercel's CDN so ordinary traffic — crawlers above all —
    # stops reaching the function, and through it Postgres. What keeps Neon's CU-hour
    # bill down is the length of the idle gaps, not the number of queries per render:
    # a compute only suspends after five idle minutes, and the 2026-09-21 outage was
    # the quota running out. `stale-while-revalidate` means no visitor ever waits for
    # the refresh, so the only cost of a long window is how stale an edit can look.
    cdn_seconds = _int_env("CDN_CACHE_SECONDS", 3600)
    cdn_stale = _int_env("CDN_STALE_SECONDS", 86400)

    @app.after_request
    def add_cdn_cache_headers(response: Response) -> Response:
        if cdn_seconds <= 0 or request.method not in ("GET", "HEAD"):
            return response
        if response.status_code != 200 or response.mimetype != "text/html":
            return response
        if request.path.startswith("/admin"):
            return response
        # Checked before the session is read, because reading it makes Flask attach
        # `Vary: Cookie` — which then has to be stripped again in save_session. A view
        # that set its own Cache-Control has opted out anyway.
        if "Cache-Control" in response.headers or "Set-Cookie" in response.headers:
            return response
        # The editor's canvas and the draft preview. Both render differently for an
        # admin than for anyone else, and Vercel's cache key ignores cookies — a cached
        # anonymous copy under these URLs would hand the admin a page with no editor.
        if "edit" in request.args or "preview" in request.args:
            return response
        if session.get("is_admin"):
            return response
        # Rendered while Postgres was unreachable, so its nav and its very existence
        # are a guess. Caching it would keep the outage on screen after it ended.
        if g.get("visibility_degraded"):
            return response
        shared = f"public, s-maxage={cdn_seconds}, stale-while-revalidate={cdn_stale}"
        # Three headers, because they answer three different caches. Vercel's own
        # examples for caching a function response use the targeted pair, and the
        # single-header form did NOT work here: with `Cache-Control` alone carrying
        # `max-age=0, s-maxage=…`, production stayed `x-vercel-cache: MISS` on every
        # request while static files cached normally. `Vercel-CDN-Cache-Control` takes
        # precedence for Vercel's CDN, so the browser can keep `max-age=0` — revalidate
        # every time — without that zero having any say over the shared copy.
        response.headers["Cache-Control"] = "public, max-age=0, must-revalidate"
        response.headers["CDN-Cache-Control"] = shared
        response.headers["Vercel-CDN-Cache-Control"] = shared
        # NOT `Vary: Cookie`. Vercel refuses to cache any response whose Vary names a
        # high-cardinality header, recording "Vary key denied" — it silently turned
        # every page here into a permanent MISS, so nothing was cached at all between
        # 2026-09-21 and 2026-09-22. Keeping the admin out of the shared cache is the
        # job of the checks above, which is where it belonged anyway.
        response.headers["Vercel-Cache-Tag"] = SITE_TAG
        return response

    @app.after_request
    def purge_cdn_after_admin_write(response: Response) -> Response:
        """Any successful write under /admin drops the CDN's copy of the public site.

        Hung off the request rather than off a save hook because the editor's writes
        belong to flask-sitecopy, which exposes none — and this way a topic toggle, a
        copy edit and an image upload are all covered by one rule.
        """
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return response
        if not request.path.startswith("/admin"):
            return response
        # Signing in and out changes nothing a visitor can see.
        if request.path in ("/admin/login", "/admin/logout"):
            return response
        if response.status_code >= 400:
            return response
        invalidate_site_cache()
        return response

    static_version = _static_version()

    def static_url(endpoint: str, **values: object) -> str:
        if endpoint == "static":
            if static_version:
                values["v"] = static_version
            else:
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

    image_manifest = _load_image_manifest()
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

        from app.repositories.topic_visibility_repository import (
            TopicVisibilityRepository,
        )

        # `published_state` already survives a database outage, and unlike the bare
        # `except` it used to have, it keeps the nav populated instead of emptying it.
        state = TopicVisibilityRepository.published_state().state

        published = [HOME_TOPIC] + [
            t for t in TOGGLEABLE_TOPICS if state.get(t.slug, False)
        ]
        return {"nav_topics": published}

    # Seeding used to run here. It opened a Postgres connection on EVERY cold start,
    # which on a scale-to-zero database means five more minutes of awake compute even
    # for a request that never needed data. It now waits until a read comes back empty
    # (`TopicVisibilityRepository.get_state_map`), which is the only time it does
    # anything — a seeded database never pays for it again.
    with app.app_context():
        from app import models  # noqa: F401
        from app.cache_probe import register_cache_probes
        from app.routes import register_routes

        register_routes(app)
        # Temporary. Remove with app/cache_probe.py once the CDN answer is in.
        register_cache_probes(app)

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
    from app.alerts import install_error_alerts
    from app.content.copy_registry import REGISTRY

    # Uploads for the image/video fields (flask-sitecopy 0.4): the editor can upload a
    # file straight from the panel instead of only pasting a URL. Files are written under
    # the served static folder (mounted on a persistent volume in docker-compose, so they
    # survive a redeploy) and addressed by content hash. The version history that lets the
    # editor roll a picture/clip back rides the same `db` (table from migration 0004).
    # Since 0.6 all of that — preview, upload, the version gallery and the picture's own
    # alt text — opens on the canvas when the picture is clicked, so nothing about the
    # wiring changes but the owner never has to find the side panel to change a photo.
    uploads_store: FileStore | bool = False
    if os.environ.get("BLOB_READ_WRITE_TOKEN"):
        # Vercel: the function's filesystem is read-only and per-deploy, so the
        # bytes go to Vercel Blob and the field stores its CDN URL.
        from app.media_store import VercelBlobFileStore

        uploads_store = VercelBlobFileStore()
    elif app.static_folder:
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

    # Last, so the signal covers every route and extension registered above.
    install_error_alerts(app)

    return app
