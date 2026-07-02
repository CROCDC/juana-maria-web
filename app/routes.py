import hmac
import json
import re
from collections.abc import Callable
from datetime import date
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
from app.factory import canonical_root
from app.repositories.crew_application_repository import CrewApplicationRepository
from app.repositories.topic_visibility_repository import TopicVisibilityRepository

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
        return render_template("index.html", is_index=True)

    for topic in TOGGLEABLE_TOPICS:
        if topic.slug == CREW_SLUG:
            continue
        app.add_url_rule(topic.path, endpoint=topic.endpoint, view_func=_make_topic_view(topic))

    @app.route("/crew-program", methods=["GET", "POST"], endpoint="topic_crew_program")
    def crew_program() -> Any:
        topic = get_topic(CREW_SLUG)
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
                return redirect(url_for("topic_crew_program", sent=1))

        return render_template(
            topic.template,
            topic=topic,
            errors=errors,
            form=request.form,
            sent=request.args.get("sent"),
        )


    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login() -> Any:
        target = request.args.get("next") or url_for("admin_topics")
        if session.get("is_admin"):
            return redirect(target)

        error = None
        if request.method == "POST":
            password = request.form.get("password", "")
            expected = current_app.config.get("ADMIN_PASSWORD")
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
        applications = CrewApplicationRepository.get_all()
        return render_template("admin/crew.html", applications=applications)


    @app.route("/site.webmanifest")
    def web_manifest() -> Response:
        years = date.today().year - 1941
        manifest = {
            "name": "Juana María",
            "short_name": "Juana María",
            "description": (
                f"Ballenera de doble proa de 1941. {years} años navegando "
                "el Río de la Plata."
            ),
            "lang": "es",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#150e08",
            "theme_color": "#150e08",
            "icons": [
                {"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png"},
                {
                    "src": "/static/apple-touch-icon.png",
                    "sizes": "180x180",
                    "type": "image/png",
                },
            ],
        }
        return Response(
            json.dumps(manifest, ensure_ascii=False),
            mimetype="application/manifest+json",
        )

    @app.route("/robots.txt")
    def robots() -> Response:
        body = f"User-agent: *\nAllow: /\nSitemap: {canonical_root()}sitemap.xml\n"
        return Response(body, mimetype="text/plain")

    @app.route("/sitemap.xml")
    def sitemap() -> Response:
        root = canonical_root()
        state = TopicVisibilityRepository.get_state_map()
        locs = [root]
        locs += [
            f"{root.rstrip('/')}{t.path}"
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
