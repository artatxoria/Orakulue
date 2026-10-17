"""Base para los extractores que llaman a un programa del sistema."""

import subprocess
from pathlib import Path

from orakulue.infraestructura.extractores.extractor_texto import ErrorExtraccion, ExtractorTexto


class ExtractorProgramaExterno(ExtractorTexto):
    """Ejecuta un programa que escribe el texto por su salida estándar.

    Las subclases solo dicen qué orden ejecutar para cada fichero.
    """

    #: Segundos máximos por documento. Un PDF dañado puede dejar colgado al
    #: programa; mejor perder ese documento que la pasada entera.
    TIEMPO_MAXIMO = 120

    def orden(self, ruta: Path) -> list[str]:
        """Devuelve la orden que extrae el texto de ``ruta``.

        Args:
            ruta: documento.

        Returns:
            Lista de argumentos para ``subprocess``.
        """
        raise NotImplementedError

    def extraer(self, ruta: Path) -> str:
        """Ejecuta la orden y devuelve su salida como texto.

        Args:
            ruta: documento.

        Returns:
            Texto extraído.

        Raises:
            ErrorExtraccion: si el programa falla, no existe o tarda demasiado.
        """
        orden = self.orden(ruta)
        try:
            resultado = subprocess.run(
                orden, capture_output=True, timeout=self.TIEMPO_MAXIMO, check=False
            )
        except FileNotFoundError as error:
            raise ErrorExtraccion(f"no está instalado el programa «{orden[0]}»") from error
        except subprocess.TimeoutExpired as error:
            raise ErrorExtraccion(f"«{orden[0]}» ha tardado más de {self.TIEMPO_MAXIMO} s") from error
        if resultado.returncode != 0 and not resultado.stdout:
            mensaje = resultado.stderr.decode("utf-8", "replace").strip().splitlines()
            raise ErrorExtraccion(mensaje[-1] if mensaje else f"«{orden[0]}» ha fallado")
        return self._recortar(resultado.stdout.decode("utf-8", "replace"))
