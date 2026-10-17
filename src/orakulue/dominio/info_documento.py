"""Entidad InfoDocumento: lo que se muestra de un documento en los resultados."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InfoDocumento:
    """Datos de un contenido para presentar un resultado de búsqueda.

    Atributos:
        huella: huella del contenido.
        rutas: dónde está en el disco.
        titulo: título de su ficha o, si no la tiene, nombre del fichero.
        interes: interés formativo según la ficha, o ``""`` si no hay ficha.
        materia: materia del índice, o ``""``.
        ruta_ficha: fichero de su ficha, si la tiene.
        personal: si tiene datos personales. Sus pasajes **nunca** se envían
            a un servicio externo.
    """

    huella: str
    rutas: tuple[Path, ...]
    titulo: str
    interes: str = ""
    materia: str = ""
    ruta_ficha: Path | None = None
    personal: bool = False
