"""The catalogue of editable copy for the site — the source of truth for flask-sitecopy.

Every user-facing string the templates render through ``t('…')`` is declared here once,
with the copy the site ships with as its default. The database (table ``site_texts``)
stores overrides only, so a fresh install renders exactly these defaults — no seeding,
and "restore the original" is a row delete.

Structure: Registry → Group (one admin screen + one preview page) → Section → TextField.

Three conventions worth knowing:

* **Defaults for the topic cards and the rumbos are pulled from the existing content
  modules** (:mod:`app.content.topics`, :mod:`app.content.rumbos`) so there is a single
  source of truth for that copy. Those fields are rendered through *dynamic* keys built
  from a slug in a loop (``t('topic.' ~ slug ~ '.title')``), so they are also listed in
  :data:`DYNAMIC_COPY_KEYS` for ``check_templates``.
* **A few decorated home-page fragments stay hard-coded in the templates** — the intro
  lead (its drop-cap ``.drop`` and script ``.script`` styling cannot be expressed in the
  rich allow-list ``p h2 h3 ul ol li strong b em i a br``). Everything else is editable.
* **A field that never renders as visible text carries ``resizable=False``.** The site
  runs flask-sitecopy with ``text_sizes=True``, and a size reaches the page as a
  ``<span class="sc-s …">`` around the value — which the library only emits in text
  position. A string that lands in an attribute (``aria-label``, ``placeholder``,
  ``og:*``), inside ``<title>`` or inside the JSON-LD block therefore has nowhere to put
  one, so those fields opt out and the admin never sees a *Tamaño* control that would do
  nothing. ``url``/``image``/``video`` fields are excluded by the library itself.
"""

from __future__ import annotations

from datetime import date

from sitecopy import Group, Registry, Section, TextField

from app.content.rumbos import RUMBOS
from app.content.topics import TOPICS, Topic


def _year() -> str:
    return str(date.today().year)


def _years_sailing() -> str:
    return str(date.today().year - 1941)


def _asset(base: str) -> str:
    """The site path of a bundled photo, used as an image field's default.

    Points at the responsive set's fallback JPG. The templates recognise this
    `/static/img/<base>-fallback.jpg` shape and render the full `<picture>` with its
    webp srcset; once an admin pastes a different URL the picture becomes a plain
    `<img>` pointing wherever they said. See ``img_src`` in ``app.factory``.
    """
    return f"/static/img/{base}-fallback.jpg"


# Hint shown under every image field in the admin.
_IMAGE_HINT = (
    "Subí una imagen o pegá un link (https://…) o una ruta del sitio como "
    "/static/img/foto.jpg. La foto que viene por defecto se muestra optimizada en "
    "varios tamaños; una que subas o pegues se muestra tal cual."
)

# Hint shown under every video field in the admin.
_VIDEO_HINT = (
    "Subí un video (mp4 o webm) o pegá un link (https://…) o una ruta del sitio "
    "como /static/video/clip.mp4."
)

# The gallery photos, in order. Defaults for the `home.galeria.imgNN` image fields.
# The owner picked this selection by hand (13/08/2026): the three shots under sail he
# kept from the original twelve, then the two of life aboard he sent to replace the rest.
_GALLERY_BASES: tuple[str, ...] = (
    "hero/under-full-sail",
    "hero/heeling-blue",
    "aerial/wing-on-wing",
    "on-deck/cockpit",
    "interior/cabin",
)

# The gallery captions, in the same order as ``_GALLERY_BASES``.
_GALLERY_CAPTIONS: tuple[str, ...] = (
    "A vela llena, atardecer en el Plata",
    "A toda vela, cielo abierto",
    "A vuelo de pájaro",
    "El cockpit de la Juana María: un espacio para la sociabilidad a bordo",
    "La cabina de la Juana María: un lugar para el encuentro en el Río de la Plata",
)


# --- Global (marca, navegación, redes, pie) -----------------------------------------

GLOBAL = Group(
    key="global",
    title="Marca y pie de página",
    description="Textos que se repiten en todo el sitio: la marca, la navegación, las redes y el pie.",
    category="Sitio",
    preview_path="/",
    sections=(
        Section(
            key="brand",
            title="Marca",
            note="El nombre se puede escribir en cualquier texto como {brand}.",
            fields=(
                TextField("global.brand", "Nombre de la marca", "Juana María", max_length=60),
                TextField("global.brand_year", "Año junto a la marca", "1941"),
                TextField(
                    "global.tagline",
                    "Texto del pie (junto a la marca)",
                    "Ballenera de doble proa, dibujo de Manuel M. Campos, botada en 1941 "
                    "en el Tigre. Sigue navegando el Río de la Plata.",
                    type="text",
                ),
            ),
        ),
        Section(
            key="nav",
            title="Navegación",
            fields=(
                TextField(
                    "global.nav_brand_aria",
                    "Etiqueta accesible de la marca",
                    "Juana María, inicio",
                    resizable=False,
                ),
                TextField("global.skip_link", "Enlace para saltar al contenido", "Saltar al contenido"),
                TextField(
                    "global.nav_toggle",
                    "Etiqueta del botón de menú",
                    "Abrir menú",
                    resizable=False,
                ),
            ),
        ),
        Section(
            key="social",
            title="Redes",
            fields=(
                TextField("global.social_handle", "Usuario de Instagram (texto)", "@velaclasica"),
                TextField(
                    "global.social_url",
                    "Enlace a Instagram",
                    "https://www.instagram.com/velaclasica/",
                    type="url",
                ),
            ),
        ),
        Section(
            key="footer",
            title="Pie de página",
            fields=(
                TextField("global.footer_waters_heading", "Título de la columna «Aguas»", "Aguas"),
                TextField(
                    "global.footer_waters",
                    "Aguas (uno por línea)",
                    "San Isidro, Buenos Aires\nYacht Club San Isidro\nRío de la Plata",
                    type="lines",
                ),
                TextField("global.footer_nav_heading", "Título de la columna «Navegar»", "Navegar"),
                TextField("global.footer_link_history", "Enlace del pie: Historia", "Historia"),
                TextField("global.footer_link_gallery", "Enlace del pie: Galería", "Galería"),
                TextField("global.footer_link_specs", "Enlace del pie: Ficha técnica", "Ficha técnica"),
                TextField("global.footer_copyright", "Línea de copyright", "© {year} {brand} — Argentina"),
                TextField("global.footer_credit", "Segunda línea del pie", "Ballenera Campos · 1941 — {year}"),
            ),
        ),
    ),
)

# --- Buscadores y redes (SEO / metadatos) -------------------------------------------

SEO = Group(
    key="seo",
    title="Buscadores y redes",
    description="Lo que ve Google y lo que aparece al compartir el link. No se ve en la página.",
    category="Sitio",
    preview_path="/",
    sections=(
        Section(
            key="meta",
            title="Metadatos",
            note="{years} se reemplaza por los años navegando (año actual − 1941).",
            fields=(
                TextField(
                    "seo.title",
                    "Título en Google",
                    "Juana María — Ballenera de 1941 · {years} años navegando el Río de la Plata",
                    resizable=False,
                ),
                TextField(
                    "seo.description",
                    "Descripción en Google",
                    "La Juana María es una ballenera de doble proa dibujada por Manuel M. "
                    "Campos y construida en madera en el Tigre en 1941. {years} años "
                    "navegando el Río de la Plata.",
                    type="text",
                    resizable=False,
                ),
                TextField(
                    "seo.og_title",
                    "Título al compartir",
                    "Juana María — ballenera de 1941",
                    resizable=False,
                ),
                TextField(
                    "seo.og_description",
                    "Descripción al compartir",
                    "Doble proa de madera dibujada por Manuel M. Campos. {years} años "
                    "navegando el Río de la Plata.",
                    type="text",
                    resizable=False,
                ),
                TextField(
                    "seo.og_image_alt",
                    "Texto de la imagen al compartir",
                    "La Juana María navegando a toda vela en el Río de la Plata.",
                    resizable=False,
                ),
            ),
        ),
    ),
)

# --- Inicio -------------------------------------------------------------------------

HOME = Group(
    key="home",
    title="Inicio",
    description="La portada del sitio.",
    category="Páginas",
    preview_path="/",
    sections=(
        Section(
            key="hero",
            title="Portada",
            note="Lo primero que se ve al entrar. (La bajada con la letra capital queda fija en el diseño.)",
            fields=(
                TextField("home.hero.eyebrow", "Antetítulo", "Ballenera"),
                TextField("home.hero.title", "Título", "Juana María"),
                TextField("home.hero.location", "Lugar y año", "1941 · Buenos Aires"),
                TextField("home.hero.years_label", "Texto bajo el contador de años", "años navegando"),
                TextField(
                    "home.hero.image",
                    "Foto de portada",
                    _asset("hero/under-full-sail"),
                    type="image",
                    hint=_IMAGE_HINT,
                ),
                TextField(
                    "home.hero.image_alt",
                    "Texto de la foto de portada",
                    "La Juana María navegando a vela llena sobre el Río de la Plata al atardecer",
                ),
                TextField("home.hero.scroll_cue", "Texto para bajar", "Bajar"),
            ),
        ),
        Section(
            key="prologo",
            title="Prólogo",
            fields=(
                TextField(
                    "home.prologo.body",
                    "Párrafo de introducción",
                    "<p>La <strong>Juana María</strong> es una <em>ballenera</em>: un tipo "
                    "de embarcación que el arquitecto naval Manuel M. Campos diseñó para un "
                    "río ancho, poco profundo y caprichoso. Casco de viraró, popa en punta "
                    "como su proa, orza rebatible: un velero noble, pensado para cruzar el "
                    "Plata con seguridad y aplomo.</p>",
                    type="rich",
                ),
                TextField("home.prologo.more_link", "Enlace a la historia", "Conoce su historia"),
            ),
        ),
        Section(
            key="historia",
            title="Historia (bitácora)",
            note="La línea de tiempo. Los nombres de barcos pierden su tipografía de detalle al editarse.",
            fields=(
                TextField("home.historia.eyebrow", "Antetítulo", "La bitácora"),
                TextField("home.historia.heading", "Título de la sección", "Una larga línea de agua"),
                TextField("home.historia.t1.year", "Hito 1 · año", "1939"),
                TextField("home.historia.t1.title", "Hito 1 · título", "Nacen las balleneras rioplatenses"),
                TextField(
                    "home.historia.t1.body",
                    "Hito 1 · texto",
                    "<p>Manuel M. Campos (1894–1987) dibuja la <em>Nutria</em>, primera "
                    "ballenera en la región: una doble proa pensada para el Río de la Plata, "
                    "inspirada en los veleros noruegos de doble proa diseñados durante el "
                    "siglo XIX por Colin Archer (1832–1921) para la actividad ballenera y la "
                    "expedición científica.</p>",
                    type="rich",
                ),
                TextField("home.historia.t2.year", "Hito 2 · año", "1941"),
                TextField("home.historia.t2.title", "Hito 2 · título", "Se construye la Juana María"),
                TextField(
                    "home.historia.t2.body",
                    "Hito 2 · texto",
                    "<p>Construida en madera de viraró por el astillero de Agustín Cadenazzi "
                    "en el Tigre, corazón histórico de la construcción náutica regional. Hoy, "
                    "la Juana María es la más antigua de las balleneras navegando el Río de "
                    "la Plata.</p>",
                    type="rich",
                ),
                TextField("home.historia.t3.year", "Hito 3 · año", "1942–43"),
                TextField("home.historia.t3.title", "Hito 3 · título", "El mismo tablero de dibujo"),
                TextField(
                    "home.historia.t3.body",
                    "Hito 3 · texto",
                    "<p>De la mano de Campos sale el <em>LEHG II</em>, con el que Vito Dumas "
                    "da la vuelta al mundo de manera solitaria, conectando los tres grandes "
                    "cabos. La Juana María pertenece a esa estirpe.</p>",
                    type="rich",
                ),
                TextField("home.historia.t4.year", "Hito 4 · año", "Segunda mitad del siglo XX"),
                TextField("home.historia.t4.title", "Hito 4 · título", "Orzando las aguas"),
                TextField(
                    "home.historia.t4.body",
                    "Hito 4 · texto",
                    "<p>La Juana María emprende travesías hacia las profundidades "
                    "septentrionales del Río Paraná, extensas singladuras marítimas, "
                    "embarcaderos orientales y puertos del litoral atlántico. De la mano de "
                    "sus capitanes, la Juana María construyó historias, anécdotas y amistades "
                    "que perviven en el tiempo.</p>",
                    type="rich",
                ),
                TextField("home.historia.t5.year", "Hito 5 · año", "El siglo XXI"),
                TextField("home.historia.t5.title", "Hito 5 · título", "Un símbolo del Río"),
                TextField(
                    "home.historia.t5.body",
                    "Hito 5 · texto",
                    "<p>Parte constitutiva de la cultura náutica, la Juana María encontró "
                    "capitanes que continuaron honrando su historia, garantizando su cuidado "
                    "junto a los más prestigiosos carpinteros de ribera y respetando las "
                    "tradiciones de su mantenimiento con técnicas clásicas y métodos "
                    "rigurosos.</p>",
                    type="rich",
                ),
                TextField("home.historia.t6.year", "Hito 6 · año", "Hoy"),
                TextField("home.historia.t6.title", "Hito 6 · título", "{years} años navegando"),
                TextField(
                    "home.historia.t6.body",
                    "Hito 6 · texto",
                    "<p>A más de ocho décadas de su botadura, la Juana María sigue saliendo "
                    "al Río de la Plata: cuidada, estudiada y bien navegada.</p>",
                    type="rich",
                ),
            ),
        ),
        Section(
            key="diseno",
            title="Diseño (vista aérea)",
            fields=(
                TextField(
                    "home.diseno.video",
                    "Video aéreo",
                    "/static/video/double-ender-aerial.mp4",
                    type="video",
                    hint=_VIDEO_HINT,
                ),
                TextField(
                    "home.diseno.poster",
                    "Imagen de portada del video",
                    "/static/video/double-ender-aerial-poster.webp",
                    type="image",
                    hint=_IMAGE_HINT,
                ),
                TextField("home.diseno.caption", "Epígrafe del video", "Vista cenital — proa y proa"),
                TextField(
                    "home.diseno.source",
                    "Crédito de la imagen",
                    "Fuente: cortesía de Diego Blanco (@chapadiego) & Marcelo Blanco (@marcelobohemio)",
                ),
            ),
        ),
        Section(
            key="ficha",
            title="Ficha técnica",
            fields=(
                TextField("home.ficha.eyebrow", "Antetítulo", "Ficha técnica"),
                TextField("home.ficha.heading", "Título de la sección", "Registro de a bordo"),
                TextField(
                    "home.ficha.lede",
                    "Bajada",
                    "Más de ocho décadas en el mismo tramo del Río de la Plata para el que "
                    "fue dibujada. Pocas embarcaciones de madera en la Argentina pueden "
                    "contar una vida tan larga — y todavía en navegación.",
                    type="text",
                ),
                TextField(
                    "home.ficha.image",
                    "Foto de perfil",
                    _asset("moored/profile-with-name"),
                    type="image",
                    hint=_IMAGE_HINT,
                ),
                TextField(
                    "home.ficha.image_alt",
                    "Texto de la foto de perfil",
                    "La Juana María amarrada, de perfil, con su nombre en el casco",
                ),
            ),
        ),
        Section(
            key="ficha_spec",
            title="Ficha técnica · datos",
            note="Cada dato: etiqueta, valor y una aclaración opcional debajo.",
            fields=(
                TextField("home.spec.type.label", "Tipo · etiqueta", "Tipo"),
                TextField("home.spec.type.value", "Tipo · valor", "Ballenera de doble proa"),
                TextField("home.spec.type.note", "Tipo · aclaración", "Diseño de Manuel M. Campos"),
                TextField("home.spec.launch.label", "Botadura · etiqueta", "Botadura"),
                TextField("home.spec.launch.value", "Botadura · valor", "1941"),
                TextField("home.spec.launch.note", "Botadura · aclaración", "Astillero Agustín Cadenazzi, Tigre"),
                TextField("home.spec.length.label", "Eslora · etiqueta", "Eslora"),
                TextField("home.spec.length.value", "Eslora · valor", "10,65 m"),
                TextField("home.spec.beam.label", "Manga · etiqueta", "Manga"),
                TextField("home.spec.beam.value", "Manga · valor", "2,47 m"),
                TextField("home.spec.draft.label", "Calado · etiqueta", "Calado"),
                TextField("home.spec.draft.value", "Calado · valor", "0,60 m"),
                TextField("home.spec.draft.note", "Calado · aclaración", "Con orza rebatible"),
                TextField("home.spec.hull.label", "Casco · etiqueta", "Casco"),
                TextField("home.spec.hull.value", "Casco · valor", "Madera de viraró"),
                TextField("home.spec.hull.note", "Casco · aclaración", "Quilla, roda y codaste de lapacho"),
                TextField("home.spec.rig.label", "Aparejo · etiqueta", "Aparejo"),
                TextField("home.spec.rig.value", "Aparejo · valor", "Ketch Cutter"),
                TextField("home.spec.flag.label", "Bandera · etiqueta", "Bandera"),
                TextField("home.spec.flag.value", "Bandera · valor", "Argentina"),
                TextField("home.spec.flag.note", "Bandera · aclaración", "Prefectura Naval Argentina"),
                TextField("home.spec.waters.label", "Aguas · etiqueta", "Aguas"),
                TextField("home.spec.waters.value", "Aguas · valor", "Río de la Plata"),
                TextField(
                    "home.spec.waters.note",
                    "Aguas · aclaración",
                    "Base en el Yacht Club San Isidro (YCSI), Buenos Aires",
                ),
            ),
        ),
        Section(
            key="galeria",
            title="Galería",
            note="Cada foto de la galería: la imagen y su epígrafe.",
            fields=(
                TextField("home.galeria.eyebrow", "Antetítulo", "Galería"),
                TextField("home.galeria.heading", "Título de la sección", "{years} años de luz"),
                *(
                    field
                    for n, base in enumerate(_GALLERY_BASES, start=1)
                    for field in (
                        TextField(
                            f"home.galeria.img{n:02d}",
                            f"Foto {n} · imagen",
                            _asset(base),
                            type="image",
                            hint=_IMAGE_HINT,
                        ),
                        TextField(f"home.galeria.cap{n:02d}", f"Foto {n} · epígrafe", _GALLERY_CAPTIONS[n - 1]),
                    )
                ),
            ),
        ),
        Section(
            key="galeria_video",
            title="Galería · video",
            note="El video que cierra la galería, debajo de las fotos.",
            fields=(
                TextField(
                    "home.galeria.video",
                    "Video",
                    "/static/video/under-sail-aerial.mp4",
                    type="video",
                    hint=_VIDEO_HINT,
                ),
                TextField(
                    "home.galeria.video_poster",
                    "Imagen de portada del video",
                    "/static/video/under-sail-aerial-poster.webp",
                    type="image",
                    hint=_IMAGE_HINT,
                ),
                TextField("home.galeria.video_caption", "Epígrafe del video", "En navegación por el Río de la Plata"),
                TextField(
                    "home.galeria.video_source",
                    "Crédito del video",
                    "Fuente: cortesía de Diego Blanco (@chapadiego) & Marcelo Blanco (@marcelobohemio)",
                ),
            ),
        ),
        Section(
            key="crew_cta",
            title="Llamado a tripulantes",
            note="El bloque que invita a sumarse (el título y el botón salen del «Programa de tripulantes»).",
            fields=(
                TextField("home.crew_cta.eyebrow", "Antetítulo", "Súmate a bordo"),
                TextField(
                    "home.crew_cta.lede",
                    "Texto",
                    "La Juana María recibe tripulantes a bordo. Anótate y navega una "
                    "ballenera de madera de 1941 por el mismo Río de la Plata para el que "
                    "fue dibujada.",
                    type="text",
                ),
            ),
        ),
        Section(
            key="hub",
            title="Más de la Juana María",
            fields=(
                TextField("home.hub.eyebrow", "Antetítulo", "A bordo"),
                TextField("home.hub.heading", "Título de la sección", "Más de la Juana María"),
            ),
        ),
    ),
)

# --- Rumbos (página) ----------------------------------------------------------------

ROUTES = Group(
    key="routes",
    title="Los rumbos",
    description="La página de rumbos y cada uno de los rumbos.",
    category="Páginas",
    preview_path="/routes",
    sections=(
        Section(
            key="intro",
            title="Encabezado",
            fields=(
                TextField("routes.eyebrow", "Antetítulo", "Adónde apunta la proa"),
                TextField(
                    "routes.lead",
                    "Bajada",
                    "Cada salida elige su rumbo. Estos son los de la Juana María sobre el "
                    "Río de la Plata: del atardecer frente a Buenos Aires al cruce a la "
                    "Banda Oriental.",
                    type="text",
                ),
            ),
        ),
        Section(
            key="rumbos",
            title="Los rumbos",
            note="Cada rumbo: nombre, dónde y el texto.",
            fields=tuple(
                field
                for rumbo in RUMBOS
                for field in (
                    TextField(f"rumbo.{rumbo.key}.name", f"{rumbo.name} · nombre", rumbo.name),
                    TextField(f"rumbo.{rumbo.key}.where", f"{rumbo.name} · dónde", rumbo.where),
                    TextField(
                        f"rumbo.{rumbo.key}.body",
                        f"{rumbo.name} · texto",
                        rumbo.body,
                        type="text",
                        max_length=900,
                    ),
                )
            ),
        ),
    ),
)

# --- Seminarios (página) ------------------------------------------------------------

SEMINARS = Group(
    key="seminars",
    title="Seminarios a bordo",
    description="La página de seminarios.",
    category="Páginas",
    preview_path="/seminars",
    sections=(
        Section(
            key="intro",
            title="Encabezado",
            fields=(
                TextField("seminars.eyebrow", "Antetítulo", "El oficio de navegar"),
                TextField(
                    "seminars.lead",
                    "Bajada",
                    "Con especialistas invitados para impartir seminarios a bordo sobre "
                    "aspectos específicos de la navegación a vela, la cubierta de la Juana "
                    "María se vuelve también un aula.",
                    type="text",
                ),
            ),
        ),
        Section(
            key="posicionamiento",
            title="Grupo 1 · Posicionamiento",
            fields=(
                TextField("seminars.g1.title", "Título del grupo", "Seminarios de posicionamiento a bordo"),
                TextField("seminars.estima.title", "Estima · título", "Navegación costera por estima: pínulas y carta náutica"),
                TextField(
                    "seminars.estima.body",
                    "Estima · texto",
                    "Fijar la posición sin electrónica: rumbo, velocidad y tiempo llevados "
                    "sobre la carta náutica, con instrumentos de pínulas para tomar demoras "
                    "y alturas. La navegación de estima, los ojos del navegante cerca de la "
                    "costa.",
                    type="text",
                ),
                TextField("seminars.astronomica.title", "Astronómica · título", "Navegación astronómica: sextante y carta náutica"),
                TextField(
                    "seminars.astronomica.body",
                    "Astronómica · texto",
                    "Hallar la posición con el sol y las estrellas. Sextante, almanaque y "
                    "horizonte — la navegación de altura, como se hacía mucho antes del GPS.",
                    type="text",
                ),
                TextField("seminars.satelital.title", "Satelital · título", "Navegación satelital: sistemas de GPS"),
                TextField(
                    "seminars.satelital.body",
                    "Satelital · texto",
                    "Cómo funciona el posicionamiento por satélite y cómo se integra a la "
                    "carta náutica a bordo: waypoints, rumbos y singladura en la navegación "
                    "de hoy.",
                    type="text",
                ),
            ),
        ),
        Section(
            key="trimado",
            title="Grupo 2 · Trimado y maniobra",
            fields=(
                TextField("seminars.g2.title", "Título del grupo", "Seminarios de trimado y maniobra a bordo"),
                TextField("seminars.mesana.title", "Mesana · título", "Navegación con mesana"),
                TextField(
                    "seminars.mesana.body",
                    "Mesana · texto",
                    "Equilibrar y gobernar el barco con la vela de popa: cómo la mesana ayuda "
                    "a capear, fondear y mantener el rumbo cuando se navega a vela.",
                    type="text",
                ),
                TextField("seminars.trinquetilla.title", "Trinquetilla · título", "Navegación con trinquetilla"),
                TextField(
                    "seminars.trinquetilla.body",
                    "Trinquetilla · texto",
                    "El aparejo de proa en acción: cómo se caza y se ajusta la trinquetilla "
                    "para ganar altura, equilibrar el barco y sostener el rumbo con viento "
                    "cambiante.",
                    type="text",
                ),
                TextField("seminars.orza.title", "Orza · título", "Navegación con orza rebatible"),
                TextField(
                    "seminars.orza.body",
                    "Orza · texto",
                    "La orza que sube y baja según el fondo: cuándo arriarla para agarrar el "
                    "agua y ceñir, y cuándo rebatirla para cruzar los bajíos del Río de la "
                    "Plata.",
                    type="text",
                ),
            ),
        ),
        Section(
            key="historia",
            title="Grupo 3 · Historia náutica",
            fields=(
                TextField("seminars.g3.title", "Título del grupo", "Seminarios de historia náutica en amarra"),
                TextField("seminars.arquitectura.title", "Arquitectura · título", "Evolución de la arquitectura y la cultura naval"),
                TextField(
                    "seminars.arquitectura.body",
                    "Arquitectura · texto",
                    "Del casco de madera a las líneas de la ballenera: cómo cambiaron el "
                    "diseño, los materiales y la cultura marinera que dieron origen a barcos "
                    "como la Juana María.",
                    type="text",
                ),
                TextField("seminars.historia.title", "Historia · título", "Historia de los sistemas y técnicas de navegación occidental"),
                TextField(
                    "seminars.historia.body",
                    "Historia · texto",
                    "Del portulano a la carta náutica moderna: cartas, derroteros e "
                    "instrumentos con los que Occidente aprendió a orientarse en el mar.",
                    type="text",
                ),
                TextField("seminars.preservacion.title", "Preservación · título", "Mantenimiento y preservación de embarcaciones de madera"),
                TextField(
                    "seminars.preservacion.body",
                    "Preservación · texto",
                    "Barniz, calafateo y herrajes de bronce: las técnicas clásicas y los "
                    "métodos rigurosos con los que se cuida y se preserva un casco de madera "
                    "en navegación.",
                    type="text",
                ),
            ),
        ),
    ),
)

# --- Navegación histórica (página) --------------------------------------------------

HISTORIC = Group(
    key="historic",
    title="Navegación histórica",
    description="La página de navegaciones históricas.",
    category="Páginas",
    preview_path="/historic-sailings",
    sections=(
        Section(
            key="body",
            title="Contenido",
            fields=(
                TextField("historic.eyebrow", "Antetítulo", "Efemérides a bordo"),
                TextField(
                    "historic.lead",
                    "Bajada",
                    "Todos los meses, la Juana María navega rumbos marcados por efemérides "
                    "con historiadores e historiadoras a bordo.",
                    type="text",
                ),
                TextField(
                    "historic.body",
                    "Texto de la página",
                    "<p>La épica llegada de Juan de Garay en 1580, las arribadas holandesas "
                    "durante 1678, el desembarco de Cevallos en Colonia hacia 1762, las "
                    "hazañas rioplatenses durante la invasión inglesa de 1806, las gloriosas "
                    "batallas navales comandadas por Guillermo Brown entre 1814 y 1827, o el "
                    "regreso triunfal de Vito Dumas en 1943, son sólo algunos de los diversos "
                    "motivos que nos empujan a navegar a lugares precisos y en fechas "
                    "precisas todos los meses.</p>"
                    "<p>Conjugando la navegación clásica con la exploración histórica, el Río "
                    "de la Plata se nos presenta como un vasto campo de agua del que emergen, "
                    "vivas, escenas claves de nuestra historia y de nuestra cultura.</p>"
                    "<p>Las navegaciones históricas se anuncian por las redes con "
                    "anticipación, para que quienes quieran sumarse a la tripulación puedan "
                    "hacerlo.</p>",
                    type="rich",
                ),
            ),
        ),
    ),
)

# --- Programa de tripulantes (página + formulario) ----------------------------------

CREW = Group(
    key="crew",
    title="Programa de tripulantes",
    description="La página del programa de tripulantes y su formulario.",
    category="Páginas",
    preview_path="/crew-program",
    sections=(
        Section(
            key="intro",
            title="Encabezado y texto",
            fields=(
                TextField("crew.eyebrow", "Antetítulo", "Súmate a la tripulación"),
                TextField(
                    "crew.lead",
                    "Bajada",
                    "Súmate a la tripulación por un día y comparte una navegación por el Río "
                    "de la Plata.",
                    type="text",
                ),
                TextField(
                    "crew.body",
                    "Texto de la página",
                    "<p>Un barco es una comunidad navegando. Navegar con tripulantes "
                    "enriquece la experiencia, facilita las maniobras y permite compartir "
                    "conocimientos. La Juana María es una comunidad con historia, y es "
                    "posible sumarse.</p>"
                    "<p>Si quisieras incorporarte a la tripulación durante un día, por favor "
                    "completa este formulario para que podamos contactarte, ofrecerte "
                    "información y coordinar nuestra navegación por el Río de la Plata.</p>"
                    "<p><strong>Es gratis: sólo compartimos los gastos operativos.</strong></p>"
                    "<p>La navegación es gratuita. Sólo existen unos pocos gastos operativos "
                    "de poner en movimiento al barco (derecho de amarra, combustible, "
                    "servicio de marinería, etc.), que nos distribuimos equitativamente entre "
                    "toda la tripulación a bordo. Únicamente te pediremos que participes con "
                    "tu parte en dichos gastos mínimos compartidos.</p>"
                    "<p>Puesto que son montos pequeños pero cambiantes (últimamente rondaba, "
                    "por persona, el precio de una pizza en Buenos Aires), los calcularemos "
                    "para actualizarlos y te los comentaremos al contactarnos contigo para "
                    "conocer tu parecer.</p>"
                    "<p><strong>No es necesario tener experiencia: podrás ganarla a "
                    "bordo.</strong></p>"
                    "<p>No es necesario contar con experiencia náutica para sumarse a una "
                    "navegación durante un día. Y si la tuvieras, ¡bienvenida!: la navegación "
                    "es un aprendizaje constante.</p>",
                    type="rich",
                ),
            ),
        ),
        Section(
            key="form",
            title="Formulario",
            fields=(
                TextField("crew.form.error_summary", "Aviso de errores", "Revisa los campos marcados y vuelve a enviar."),
                TextField("crew.form.email", "Etiqueta · correo", "¿Cuál es tu correo electrónico?"),
                TextField("crew.form.full_name", "Etiqueta · nombre", "¿Cómo te llamas?"),
                TextField("crew.form.whatsapp", "Etiqueta · WhatsApp", "¿Cuál es tu contacto de WhatsApp?"),
                TextField("crew.form.whatsapp_hint", "Ayuda · WhatsApp", "Nos comunicaremos contigo por este medio."),
                TextField("crew.form.instagram", "Etiqueta · Instagram", "¿Cuál es tu cuenta de Instagram?"),
                TextField("crew.form.is_adult", "Etiqueta · mayoría de edad", "¿Eres mayor de 18 años de edad?"),
                TextField("crew.form.adult_yes", "Opción · Sí", "Sí"),
                TextField("crew.form.adult_no", "Opción · No", "No"),
                TextField("crew.form.date", "Etiqueta · fecha", "¿Cuál es la fecha en la que quisieras salir a navegar en el Río de la Plata?"),
                TextField(
                    "crew.form.date_placeholder",
                    "Placeholder · fecha",
                    "Ej.: un fin de semana de noviembre",
                    resizable=False,
                ),
                TextField("crew.form.route", "Etiqueta · rumbo", "¿Tienes algún rumbo de preferencia?"),
                TextField("crew.form.route_none", "Opción · sin preferencia", "Sin preferencia"),
                TextField("crew.form.message", "Etiqueta · comentario", "¿Algún comentario, consulta o inquietud que nos quieras comunicar antes de que nos contactemos contigo?"),
                TextField("crew.form.submit", "Botón de envío", "Enviar inscripción"),
            ),
        ),
        Section(
            key="success",
            title="Mensaje de éxito",
            fields=(
                TextField("crew.success.heading", "Título", "¡Gracias! Recibimos tu inscripción."),
                TextField(
                    "crew.success.body",
                    "Texto",
                    "Nos vamos a comunicar contigo por WhatsApp para coordinar la próxima "
                    "navegación con lugar para tripulantes.",
                    type="text",
                ),
                TextField("crew.success.follow", "Antes del enlace a Instagram", "Mientras tanto, puedes seguirnos en"),
                TextField("crew.success.again", "Enlace para cargar otra", "Cargar otra inscripción"),
            ),
        ),
    ),
)

# --- Varios (secciones en preparación, error 404) -----------------------------------

MISC = Group(
    key="misc",
    title="Varios",
    description="Textos sueltos: las secciones en preparación y la página de error.",
    category="Sitio",
    preview_path="/",
    sections=(
        Section(
            key="pending",
            title="Secciones en preparación",
            fields=(
                TextField("reading.eyebrow", "Ciclo de lectura · antetítulo", "Leer a bordo"),
                TextField("other.eyebrow", "Otras actividades · antetítulo", "Sobre cubierta"),
                TextField(
                    "misc.pending_note",
                    "Aviso de sección en preparación",
                    "Estamos preparando esta sección. Muy pronto vas a encontrar aquí todo "
                    "el detalle.",
                    type="text",
                ),
            ),
        ),
        Section(
            key="error",
            title="Página no encontrada (404)",
            fields=(
                TextField("error404.eyebrow", "Antetítulo", "Error 404"),
                TextField("error404.title", "Título", "Esta página zarpó sin avisar"),
                TextField(
                    "error404.lead",
                    "Texto",
                    "No encontramos lo que buscabas en estas aguas. Vuelve al puerto y sigue "
                    "navegando.",
                    type="text",
                ),
                TextField("error404.button", "Botón", "Volver al inicio"),
            ),
        ),
    ),
)


# --- Tarjetas y navegación de los tópicos (claves dinámicas por slug) ----------------
#
# Rendered from the Topic objects in a loop, so the keys are built at run time
# (`t('topic.' ~ slug ~ '.title')`). Defaults come straight from app.content.topics, so
# there is one source of truth for this copy. Only the fields each topic actually renders
# are declared, to keep every field live:
#   * the home topic contributes only its nav label (top nav),
#   * crew-program has no blurb card (it is not in the hub grid),
#   * the rest contribute nav label, title, blurb and CTA.

_TOPIC_FIELD_SPECS = {
    "nav": ("nav_label", "Etiqueta en la navegación"),
    "title": ("title", "Título"),
    "blurb": ("blurb", "Descripción (tarjeta)"),
    "cta": ("cta_label", "Texto del botón"),
}


def _topic_fields_for(topic: Topic) -> tuple[str, ...]:
    if topic.is_home:
        return ("nav",)
    if topic.slug == "crew-program":
        return ("nav", "title", "cta")
    return ("nav", "title", "blurb", "cta")


def _build_topic_section() -> Section:
    fields: list[TextField] = []
    for topic in TOPICS:
        for name in _topic_fields_for(topic):
            attr, label = _TOPIC_FIELD_SPECS[name]
            fields.append(
                TextField(
                    f"topic.{topic.slug}.{name}",
                    f"{topic.nav_label} · {label}",
                    getattr(topic, attr),
                )
            )
        # The photo behind the section: its home-page card, its page header, and (for
        # the crew program) the home call-to-action all read this one image field.
        if topic.image:
            fields.append(
                TextField(
                    f"topic.{topic.slug}.image",
                    f"{topic.nav_label} · Imagen",
                    _asset(topic.image),
                    type="image",
                    hint=_IMAGE_HINT,
                )
            )
    return Section(key="topics", title="Secciones", fields=tuple(fields))


NAV_CARDS = Group(
    key="nav_cards",
    title="Navegación y tarjetas",
    description="Los nombres de cada sección en el menú, el pie y las tarjetas de inicio.",
    category="Sitio",
    preview_path="/",
    sections=(_build_topic_section(),),
)


REGISTRY = Registry(
    groups=(GLOBAL, SEO, HOME, NAV_CARDS, ROUTES, SEMINARS, HISTORIC, CREW, MISC),
    tokens=("global.brand",),
    computed_tokens={"year": _year, "years": _years_sailing},
)


# Keys rendered through run-time-built `t('…')` calls, which the literal template scan
# in `check_templates` cannot see, so they are passed as its `dynamic` allow-list to
# keep them from being flagged as unrendered:
#   * the topic cards/nav and the rumbos, built from a slug in a loop, and
#   * every media (`image`/`video`) field — the images are rendered by the
#     `editable_img` macro, which calls `t(copy_key)` on the key it is handed rather than
#     a literal; listing the media fields keeps them off the "declared but unrendered"
#     report regardless of how each one reaches the page.
DYNAMIC_COPY_KEYS: tuple[str, ...] = tuple(
    key
    for key, field in REGISTRY.fields.items()
    if key.startswith("topic.") or key.startswith("rumbo.") or field.type in ("image", "video")
)
