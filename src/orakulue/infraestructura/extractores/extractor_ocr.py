"""Reconocimiento óptico de caracteres para PDF escaneados.

Cada página se convierte en imagen con ``pdftoppm`` y se lee con Tesseract.
Todo ocurre en una carpeta temporal: el PDF original no se modifica.
"""

import os
import subprocess
import tempfile
from pathlib import Path

from orakulue.infraestructura.extractores.extractor_texto import ErrorExtraccion, ExtractorTexto


class ExtractorOcr(ExtractorTexto):
    """Lee el texto de un PDF sin capa de texto."""

    extensiones = frozenset({"pdf"})

    #: Idiomas de Tesseract, en orden de preferencia. Leer con los tres a la
    #: vez es algo más lento, pero acierta con las tildes del castellano y con
    #: las palabras vascas sin saber de antemano en qué idioma está cada PDF.
    IDIOMAS = "spa+eus+eng"
    #: Resolución de las imágenes. 200 ppp basta para texto impreso y cuesta
    #: la mitad que 300.
    RESOLUCION = 200
    #: Páginas que se leen como máximo. Para la ficha y la búsqueda basta con
    #: el grueso del documento; un libro escaneado de 400 páginas no puede
    #: monopolizar la pasada.
    LIMITE_PAGINAS = 60
    #: Segundos máximos por página.
    TIEMPO_POR_PAGINA = 120

    def extraer(self, ruta: Path) -> str:
        """Rasteriza y reconoce las páginas del PDF.

        Args:
            ruta: PDF escaneado.

        Returns:
            Texto reconocido, con un salto de página entre páginas.

        Raises:
            ErrorExtraccion: si el PDF no se puede rasterizar o falta un programa.
        """
        with tempfile.TemporaryDirectory(prefix="orakulue-ocr-") as temporal:
            prefijo = Path(temporal) / "pagina"
            self._ejecutar([
                "pdftoppm", "-r", str(self.RESOLUCION), "-gray", "-png",
                "-l", str(self.LIMITE_PAGINAS), str(ruta), str(prefijo),
            ], self.TIEMPO_POR_PAGINA * 4)
            paginas = sorted(Path(temporal).glob("pagina*.png"))
            if not paginas:
                raise ErrorExtraccion("el PDF no tiene páginas que convertir en imagen")
            textos = [
                self._ejecutar(["tesseract", str(p), "-", "-l", self.IDIOMAS], self.TIEMPO_POR_PAGINA)
                for p in paginas
            ]
        return self._recortar("\f".join(textos))

    @staticmethod
    def _ejecutar(orden: list[str], tiempo: int) -> str:
        """Ejecuta un programa y devuelve su salida.

        Tesseract usa por defecto varios hilos por página; se limita a uno
        porque la extracción ya procesa varios documentos a la vez, y repartir
        de más hace que todo vaya más lento.

        Args:
            orden: argumentos del programa.
            tiempo: segundos máximos.

        Returns:
            Salida estándar como texto.

        Raises:
            ErrorExtraccion: si falla, no existe o tarda demasiado.
        """
        entorno = {**os.environ, "OMP_THREAD_LIMIT": "1"}
        try:
            resultado = subprocess.run(orden, capture_output=True, timeout=tiempo, check=False, env=entorno)
        except FileNotFoundError as error:
            raise ErrorExtraccion(f"no está instalado el programa «{orden[0]}»") from error
        except subprocess.TimeoutExpired as error:
            raise ErrorExtraccion(f"«{orden[0]}» ha tardado más de {tiempo} s") from error
        if resultado.returncode != 0:
            mensaje = resultado.stderr.decode("utf-8", "replace").strip().splitlines()
            raise ErrorExtraccion(mensaje[-1] if mensaje else f"«{orden[0]}» ha fallado")
        return resultado.stdout.decode("utf-8", "replace")
