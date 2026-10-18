"""Entidad Candidata: un grupo de ideas parecidas que puede ser una propuesta."""

import zlib
from dataclasses import dataclass, field

from orakulue.dominio.idea_formativa import IdeaFormativa


@dataclass
class Candidata:
    """Propuesta candidata, con las ideas que la forman y su puntuación.

    Atributos:
        tipo: ``curso`` o ``pildora``.
        ideas: ideas agrupadas, la más representativa primero.
        puntuacion: puntuación total (mayor es mejor).
        desglose: puntos por criterio, para explicar la posición.
        en_catalogo: relación con el catálogo actual («ya lo ofreces: …» o
            «parecido a: …»), o ``""`` si es nueva.
    """

    tipo: str
    ideas: list[IdeaFormativa] = field(default_factory=list)
    puntuacion: float = 0.0
    desglose: dict[str, float] = field(default_factory=dict)
    en_catalogo: str = ""

    @property
    def titulo(self) -> str:
        """Título de la idea más representativa."""
        return self.ideas[0].titulo if self.ideas else ""

    @property
    def huellas(self) -> list[str]:
        """Documentos distintos que la sugieren, sin repetir y en orden."""
        return list(dict.fromkeys(i.huella for i in self.ideas))

    @property
    def clave(self) -> str:
        """Identificador estable: tipo y documento de la idea principal.

        Sirve para no redactar dos veces la misma candidata y para exportarla
        después por su clave.
        """
        principal = self.ideas[0]
        # CRC32 y no hash(): hash() cambia de una ejecución a otra.
        return f"{self.tipo}-{principal.huella[:10]}-{zlib.crc32(principal.titulo.encode()) % 10_000:04d}"
