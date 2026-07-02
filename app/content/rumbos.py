from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rumbo:
    key: str
    name: str
    where: str
    body: str


RUMBOS: list[Rumbo] = [
    Rumbo(
        key="southeast",
        name="Rumbo Sudeste",
        where="el horizonte de Buenos Aires",
        body=(
            "Zarpando desde San Isidro, un antiguo puerto colonial al norte de "
            "Buenos Aires, la Juana María suele poner vela hacia el sudeste para "
            "observar el atardecer sobre la ciudad desde el Río de la Plata. El "
            "Puerto Nuevo de Buenos Aires, su frondosa reserva y la boca del "
            "Riachuelo dibujan, desde algunas millas aguas adentro, un perfil "
            "distintivo que recorta el horizonte sobre el cielo de la ciudad. "
            "Saludando el paso de las embarcaciones que conectan al litoral con "
            "el planeta, Buenos Aires se comprende mirándola desde la navegación "
            "apacible de un barco."
        ),
    ),
    Rumbo(
        key="delta",
        name="El ancla arriada",
        where="un respiro en el Delta",
        body=(
            "Si la altura de la marea lo permite, en ocasiones sacamos al barco "
            "de su amarra para fondear el ancla en alguno de los paraísos "
            "escondidos del Delta. Desde la cercanísima boca del río San Antonio "
            "hasta el pasaje El Sueco, el Delta del Paraná es un frondoso "
            "laberinto que arrulla y contiene. A pocos minutos de navegación "
            "desde la amarra, el reparo ofrecido por la entrada al Delta del "
            "Paraná ofrece una utopía demasiado cercana."
        ),
    ),
    Rumbo(
        key="banda-oriental",
        name="La Banda Oriental",
        where="los días navegando",
        body=(
            "Seis horas de navegación, el arribo a un puerto extranjero y el "
            "contacto con las tradiciones coloniales del Río de la Plata. "
            "Uruguay es un destino que abre las puertas a historias impensadas, "
            "paisajes acogedores y amistades de largo plazo. El aroma del "
            "guayabo, los perfumes de la yerba mate y las tardes anaranjadas "
            "ameritan varios días en sus embarcaderos."
        ),
    ),
]

RUMBOS_BY_KEY: dict[str, Rumbo] = {r.key: r for r in RUMBOS}


def get_rumbo(key: str) -> Rumbo | None:
    return RUMBOS_BY_KEY.get(key)
