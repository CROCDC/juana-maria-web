"""The seven site topics — single source of truth for structure and routing.

The site is organised as a hub: the home page IS the first topic ("Sobre la
Juana María"), and every other topic is its own page under ``/<slug>``. Which of
the non-home topics are actually published is controlled at runtime from the
admin panel (see ``TopicVisibility`` and the admin routes); this registry only
declares the topics that exist, their URLs, templates and nav/hub copy.

Identifiers are English (slug, endpoint, template) per CONVENTIONS §13; the
user-facing strings (nav label, title, blurb) are the site's Spanish copy.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    slug: str  # URL segment + DB key + endpoint suffix (English, kebab-case)
    nav_label: str  # short label for the top nav
    title: str  # page heading / home band title
    blurb: str  # one-line description for the home band
    template: str  # template rendered for this topic's page
    is_home: bool = False  # the home topic renders at "/" and is always visible
    image: str = ""  # image key for this topic's full-width band on the home page
    cta_label: str = "Ver más"  # button label on that band

    @property
    def endpoint(self) -> str:
        # Flask endpoint name, e.g. "topic_crew_program". The home topic keeps
        # the existing "index" endpoint (registered separately in routes.py).
        return "index" if self.is_home else f"topic_{self.slug.replace('-', '_')}"

    @property
    def path(self) -> str:
        return "/" if self.is_home else f"/{self.slug}"


# Order here is the canonical order in the nav and the hub.
TOPICS: list[Topic] = [
    Topic(
        slug="about",
        nav_label="Sobre la Juana María",
        title="Sobre la Juana María",
        blurb="La historia del barco y de su clase, y sus apariciones en pantalla.",
        template="index.html",
        is_home=True,
    ),
    Topic(
        slug="routes",
        nav_label="Los rumbos",
        title="Los rumbos de la Juana María",
        blurb="Los rumbos que toma el barco al salir al Río de la Plata.",
        template="topics/routes.html",
        image="aerial/sailing-away",
        cta_label="Ver los rumbos",
    ),
    Topic(
        # NOTE: on the home page the crew-program renders as a full-bleed CTA
        # band (index.html "A bordo" zone) whose lede paragraph is hardcoded in
        # the template. Its title/cta_label/image come from here, so if this
        # entry is repurposed, update that hardcoded lede too.
        slug="crew-program",
        nav_label="Programa de tripulantes",
        title="Programa de tripulantes",
        blurb="Sumate como tripulante a bordo: cómo es y cómo anotarse.",
        template="topics/crew-program.html",
        image="on-deck/deck-sunrise",
        cta_label="Quiero ser tripulante",
    ),
    Topic(
        slug="historic-sailings",
        nav_label="Navegación histórica",
        title="Navegación histórica",
        blurb="Réplicas de derroteros históricos, con historiadores a bordo.",
        template="topics/historic-sailings.html",
        image="heritage/teseo",
        cta_label="Ver más",
    ),
    Topic(
        slug="seminars",
        nav_label="Seminarios a bordo",
        title="Seminarios a bordo",
        blurb="Seminarios de náutica a cargo de especialistas, sobre cubierta.",
        template="topics/seminars.html",
        # seminars/* images are only generated up to 960px (and aren't in the
        # manifest), so a full-bleed 100vw band requests a missing 1280 webp and
        # shows no background. Use a fully-sized sailing image for the band; the
        # seminars/* thumbnails are still fine on the detail page at small sizes.
        image="sailing/bsas-skyline",
        cta_label="Ver los seminarios",
    ),
    Topic(
        slug="reading-circle",
        nav_label="Ciclo de lectura",
        title="Ciclo de lectura",
        blurb="Un ciclo de lectura a bordo de la Juana María.",
        template="topics/reading-circle.html",
        image="interior/galley-and-nav",
        cta_label="Ver el ciclo",
    ),
    Topic(
        slug="other-activities",
        nav_label="Otras actividades",
        title="Otras actividades a bordo",
        blurb="Otras propuestas y actividades que ocurren sobre cubierta.",
        template="topics/other-activities.html",
        image="on-deck/foredeck-detail",
        cta_label="Ver más",
    ),
]

# The home topic always renders; only these can be toggled from the admin panel.
HOME_TOPIC: Topic = next(t for t in TOPICS if t.is_home)
TOGGLEABLE_TOPICS: list[Topic] = [t for t in TOPICS if not t.is_home]

# Initial published state when a topic is first seeded into the DB. Per the
# client's example, the site launches with only "Sobre la Juana María" (the
# home, always on) and "Programa de tripulantes" visible; the rest are revealed
# later from the admin panel, closer to when each one actually happens.
DEFAULT_ENABLED: dict[str, bool] = {t.slug: (t.slug == "crew-program") for t in TOGGLEABLE_TOPICS}


def get_topic(slug: str) -> Topic | None:
    return next((t for t in TOPICS if t.slug == slug), None)
