"""Cálculo de la huella SHA-256 del contenido de un fichero.

La huella depende solo de los bytes: dos ficheros con nombres distintos y el
mismo contenido dan la misma huella. Así se detectan los duplicados aunque se
hayan renombrado al descargarlos.
"""

import hashlib
from pathlib import Path


class CalculadorHuellas:
    """Calcula huellas SHA-256 leyendo los ficheros por bloques."""

    ALGORITMO = "sha256"

    def calcular(self, ruta: Path) -> str:
        """Devuelve la huella del contenido de un fichero.

        Se usa ``hashlib.file_digest``, que lee por bloques sin cargar el
        fichero entero en memoria: hay PDF de cientos de megas.

        Args:
            ruta: fichero que se va a leer.

        Returns:
            Huella en hexadecimal (64 caracteres).

        Raises:
            OSError: si el fichero no se puede abrir o leer.
        """
        with ruta.open("rb") as fichero:
            return hashlib.file_digest(fichero, self.ALGORITMO).hexdigest()
