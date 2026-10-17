"""Interfaz común de los extractores de texto."""

from abc import ABC, abstractmethod
from pathlib import Path


class ErrorExtraccion(Exception):
    """El documento no se ha podido leer. El mensaje va en castellano."""


class ExtractorTexto(ABC):
    """Extrae el texto plano de un documento.

    Cada subclase cubre una familia de formatos y declara sus extensiones.
    """

    #: Extensiones (minúsculas, sin punto) que cubre el extractor.
    extensiones: frozenset[str] = frozenset()

    #: Límite de caracteres que se conservan por documento. Un libro entero
    #: cabe de sobra; una hoja de cálculo con cientos de miles de filas no
    #: aporta nada más allá de este tamaño y llenaría el disco.
    LIMITE_CARACTERES = 3_000_000

    @property
    def nombre(self) -> str:
        """Nombre del extractor, para el registro."""
        return type(self).__name__

    @abstractmethod
    def extraer(self, ruta: Path) -> str:
        """Devuelve el texto del documento.

        Args:
            ruta: fichero que se va a leer.

        Returns:
            Texto plano, posiblemente vacío.

        Raises:
            ErrorExtraccion: si el fichero no se puede leer.
        """

    def _recortar(self, texto: str) -> str:
        """Aplica ``LIMITE_CARACTERES``."""
        return texto[: self.LIMITE_CARACTERES]
