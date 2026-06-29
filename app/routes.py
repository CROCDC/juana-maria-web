import hmac
import re
from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import (
    Flask,
    Response,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.wrappers import Response as WerkzeugResponse

from app.content.rumbos import RUMBOS_BY_KEY
from app.content.topics import TOGGLEABLE_TOPICS, Topic, get_topic
from app.repositories.crew_application_repository import CrewApplicationRepository
from app.repositories.topic_visibility_repository import TopicVisibilityRepository

# The crew-program topic has a DB-backed intake form, so it gets a dedicated
# GET/POST handler instead of the generic read-only topic view.
CREW_SLUG = "crew-program"

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_crew_form(data: dict[str, str]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not data["full_name"]:
        errors["full_name"] = "Ingresa tu nombre."
    if not data["email"]:
        errors["email"] = "Ingresa tu email."
    elif not _EMAIL_RE.match(data["email"]):
        errors["email"] = "Revisa el email: no parece válido."
    if not data["whatsapp"]:
        errors["whatsapp"] = "Déjanos un WhatsApp: es por donde te contactamos."
    if data["is_adult"] not in ("si", "no"):
        errors["is_adult"] = "Cuéntanos si eres mayor de 18 años."
    return errors


def _make_topic_view(topic: Topic) -> Callable[[], str]:
    """Build the view for a single topic page.

    Visibility is checked per request (not at registration time) so toggling a
    topic from the admin panel takes effect immediately: a disabled topic 404s.
    """

    def view() -> str:
        if not TopicVisibilityRepository.is_enabled(topic.slug):
            abort(404)
        return render_template(topic.template, topic=topic)

    return view


def _login_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def register_routes(app: Flask) -> None:
    @app.route("/")
    def index() -> str:
        # is_index lets base.html keep bare "#section" anchors here (smooth
        # in-page scroll) while other pages get "/#section" that resolve home.
        return render_template("index.html", is_index=True)

    # One page per toggleable topic, at /<slug>. Registered from the registry so
    # adding a topic is a single entry in app/content/topics.py. crew-program is
    # the exception: it has a form, so it's handled explicitly below.
    for topic in TOGGLEABLE_TOPICS:
        if topic.slug == CREW_SLUG:
            continue
        app.add_url_rule(topic.path, endpoint=topic.endpoint, view_func=_make_topic_view(topic))

    @app.route("/crew-program", methods=["GET", "POST"], endpoint="topic_crew_program")
    def crew_program() -> Any:
        topic = get_topic(CREW_SLUG)
        # Same visibility gate as every other topic: 404 while unpublished.
        if topic is None or not TopicVisibilityRepository.is_enabled(CREW_SLUG):
            abort(404)

        errors: dict[str, str] = {}
        if request.method == "POST":
            data = {
                "full_name": request.form.get("full_name", "").strip(),
                "email": request.form.get("email", "").strip(),
                "whatsapp": request.form.get("whatsapp", "").strip(),
                "instagram": request.form.get("instagram", "").strip(),
                "is_adult": request.form.get("is_adult", "").strip(),
                "preferred_date": request.form.get("preferred_date", "").strip(),
                "preferred_route": request.form.get("preferred_route", "").strip(),
                "message": request.form.get("message", "").strip(),
            }
            errors = _validate_crew_form(data)
            if not errors:
                # Persist the rumbo only if it's a known key (enum from RUMBOS);
                # ignore anything else so the column stays a clean enum value.
                route = data["preferred_route"]
                preferred_route = route if route in RUMBOS_BY_KEY else ""
                CrewApplicationRepository.create(
                    full_name=data["full_name"],
                    email=data["email"],
                    whatsapp=data["whatsapp"],
                    is_adult=data["is_adult"] == "si",
                    instagram=data["instagram"],
                    preferred_date=data["preferred_date"],
                    preferred_route=preferred_route,
                    message=data["message"],
                )
                # Post/Redirect/Get: ?sent=1 shows the thank-you state.
                return redirect(url_for("topic_crew_program", sent=1))

        return render_template(
            topic.template,
            topic=topic,
            errors=errors,
            form=request.form,
            sent=request.args.get("sent"),
        )

    # ----- Admin (topic visibility) ------------------------------------------

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login() -> Any:
        target = request.args.get("next") or url_for("admin_topics")
        if session.get("is_admin"):
            return redirect(target)

        error = None
        if request.method == "POST":
            password = request.form.get("password", "")
            expected = current_app.config.get("ADMIN_PASSWORD")
            # compare_digest guards against timing attacks; an unset password
            # (expected is None) can never match, disabling admin entirely.
            if expected and hmac.compare_digest(password, expected):
                session["is_admin"] = True
                return redirect(request.form.get("next") or target)
            error = "Contraseña incorrecta."

        return render_template("admin/login.html", error=error, next=target)

    @app.route("/admin/logout", methods=["POST"])
    def admin_logout() -> WerkzeugResponse:
        session.pop("is_admin", None)
        return redirect(url_for("admin_login"))

    @app.route("/admin", methods=["GET"])
    @app.route("/admin/topics", methods=["GET", "POST"])
    @_login_required
    def admin_topics() -> Any:
        if request.method == "POST":
            # Checkboxes only submit when checked, so an absent slug means "off".
            checked = set(request.form.getlist("enabled"))
            for topic in TOGGLEABLE_TOPICS:
                TopicVisibilityRepository.set_enabled(topic.slug, topic.slug in checked)
            return redirect(url_for("admin_topics", saved=1))

        state = TopicVisibilityRepository.get_state_map()
        rows = [(topic, state.get(topic.slug, False)) for topic in TOGGLEABLE_TOPICS]
        return render_template(
            "admin/topics.html", rows=rows, saved=request.args.get("saved")
        )

    @app.route("/admin/crew", methods=["GET"])
    @_login_required
    def admin_crew() -> Any:
        # Read-only list of crew-program applications, newest first (the repo
        # already orders by created_at desc). Dates are shown in local time via
        # the `localdt` template filter.
        applications = CrewApplicationRepository.get_all()
        return render_template("admin/crew.html", applications=applications)

    # ----- SEO / infra --------------------------------------------------------

    @app.route("/robots.txt")
    def robots() -> Response:
        body = f"User-agent: *\nAllow: /\nSitemap: {request.url_root}sitemap.xml\n"
        return Response(body, mimetype="text/plain")

    @app.route("/sitemap.xml")
    def sitemap() -> Response:
        # Home plus every currently published topic page.
        state = TopicVisibilityRepository.get_state_map()
        locs = [request.url_root]
        locs += [
            f"{request.url_root.rstrip('/')}{t.path}"
            for t in TOGGLEABLE_TOPICS
            if state.get(t.slug, False)
        ]
        urls = "".join(
            f"  <url><loc>{loc}</loc><changefreq>monthly</changefreq>"
            "<priority>0.8</priority></url>\n"
            for loc in locs
        )
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{urls}"
            "</urlset>\n"
        )
        return Response(body, mimetype="application/xml")

    @app.errorhandler(404)
    def not_found(_error: object) -> tuple[str, int]:
        return render_template("404.html"), 404
