from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    slug: str
    nav_label: str
    title: str
    blurb: str
    template: str
    is_home: bool = False
    image: str = ""
    cta_label: str = "Ver más"

    @property
    def endpoint(self) -> str:
        return "index" if self.is_home else f"topic_{self.slug.replace('-', '_')}"

    @property
    def path(self) -> str:
        return "/" if self.is_home else f"/{self.slug}"


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
        slug="crew-program",
        nav_label="Programa de tripulantes",
        title="Programa de tripulantes",
        blurb="Súmate como tripulante a bordo: cómo es y cómo anotarse.",
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

HOME_TOPIC: Topic = next(t for t in TOPICS if t.is_home)
TOGGLEABLE_TOPICS: list[Topic] = [t for t in TOPICS if not t.is_home]

DEFAULT_ENABLED: dict[str, bool] = {t.slug: (t.slug == "crew-program") for t in TOGGLEABLE_TOPICS}


def get_topic(slug: str) -> Topic | None:
    return next((t for t in TOPICS if t.slug == slug), None)
