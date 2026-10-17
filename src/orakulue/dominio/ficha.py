"""Entidad Ficha: lo que se sabe de un documento tras leerlo el modelo."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class FichaNoValida(Exception):
    """La respuesta del modelo no tiene la forma de una ficha."""


@dataclass(frozen=True)
class Ficha:
    """Ficha de un contenido, con sus datos de origen.

    Atributos:
        huella: huella del contenido.
        rutas: dónde está en el disco.
        modelo: modelo que la escribió.
        datos: campos devueltos por el modelo, según ``EsquemaFicha``.
        familia: rutas de los demás miembros de su familia de plantilla.
    """

    huella: str
    rutas: tuple[Path, ...]
    modelo: str
    datos: dict[str, Any]
    familia: tuple[Path, ...] = field(default_factory=tuple)

    _CAMPOS = ("titulo", "tipo", "tema", "temas", "nivel", "idioma", "publico", "vigencia",
               "interes", "motivo_interes", "resumen", "teoria", "ejercicios", "ideas_curso",
               "ideas_pildora", "observaciones")

    def __post_init__(self) -> None:
        """Comprueba que no falta ningún campo.

        La salida estructurada ya lo garantiza; se vuelve a comprobar porque una
        ficha incompleta guardada en disco haría creer que el documento ya está
        hecho.

        Raises:
            FichaNoValida: si falta algún campo.
        """
        faltan = [c for c in self._CAMPOS if c not in self.datos]
        if faltan:
            raise FichaNoValida(f"faltan los campos {', '.join(faltan)}")

    @property
    def sin_interes(self) -> bool:
        """Si el modelo juzga que no sirve para formación."""
        return self.datos["interes"] == "ninguno"

    @property
    def titulo(self) -> str:
        """Título, o el nombre del fichero si el modelo no dio ninguno."""
        return self.datos["titulo"].strip() or self.rutas[0].stem
