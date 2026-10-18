"""Entidad Propuesta: un curso o una píldora redactados a partir del fondo."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Propuesta:
    """Propuesta redactada, con su origen y su puntuación.

    Atributos:
        tipo: ``curso`` o ``pildora``.
        clave: clave de la candidata de la que sale.
        modelo: modelo que la redactó.
        datos: campos devueltos por el modelo (según su esquema).
        fuentes: huellas de los documentos numerados que se le dieron al
            modelo; ``fuentes[0]`` es la fuente [1].
        puntuacion: puntuación de la candidata.
        desglose: puntos por criterio.
        en_catalogo: relación con el catálogo actual, si la hay.
    """

    tipo: str
    clave: str
    modelo: str
    datos: dict[str, Any]
    fuentes: tuple[str, ...]
    puntuacion: float
    desglose: dict[str, float] = field(default_factory=dict)
    en_catalogo: str = ""

    @property
    def titulo(self) -> str:
        """Título de la propuesta."""
        return self.datos.get("titulo", "").strip() or self.clave
