"""Extracción de texto de formatos que son un ZIP con XML dentro.

Word, Excel y PowerPoint modernos (``.docx``, ``.xlsx``, ``.pptx``),
LibreOffice (``.odt``, ``.ods``, ``.odp``) y los libros EPUB son ficheros ZIP
con el contenido en XML o XHTML. Leerlo directamente es rápido, no necesita
programas externos y no depende de que LibreOffice esté instalado.
"""

import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

from orakulue.infraestructura.extractores.extractor_texto import ErrorExtraccion, ExtractorTexto

# Por formato: qué ficheros internos leer y qué etiquetas son párrafos.
# Se compara solo el nombre local de la etiqueta, sin espacio de nombres.
_FORMATOS: dict[str, tuple[str, set[str]]] = {
    "docx": (r"word/(document|footnotes|endnotes)\.xml", {"p"}),
    "pptx": (r"ppt/(slides/slide|notesSlides/notesSlide)\d+\.xml", {"p"}),
    "xlsx": (r"xl/sharedStrings\.xml", {"si"}),
    "odt": (r"content\.xml", {"p", "h"}),
    "ods": (r"content\.xml", {"p", "h"}),
    "odp": (r"content\.xml", {"p", "h"}),
}


class _TextoHtml(HTMLParser):
    """Acumula el texto de un documento XHTML (capítulos de un EPUB)."""

    def __init__(self) -> None:
        """Prepara el lector con la lista de fragmentos vacía."""
        super().__init__()
        self.partes: list[str] = []

    def handle_data(self, data: str) -> None:
        """Guarda cada fragmento de texto.

        ``handle_data`` es el nombre que impone ``HTMLParser``.

        Args:
            data: texto entre etiquetas.
        """
        self.partes.append(data)


class ExtractorZipXml(ExtractorTexto):
    """Lee el texto de los formatos ofimáticos basados en ZIP y XML."""

    extensiones = frozenset(_FORMATOS) | {"epub"}

    def extraer(self, ruta: Path) -> str:
        """Abre el ZIP y recorre sus ficheros de contenido en orden.

        Args:
            ruta: documento.

        Returns:
            Texto, un párrafo por línea.

        Raises:
            ErrorExtraccion: si no es un ZIP válido o el XML está dañado.
        """
        formato = ruta.suffix.lower().lstrip(".")
        try:
            with zipfile.ZipFile(ruta) as paquete:
                if formato == "epub":
                    return self._recortar(self._epub(paquete))
                patron, parrafos = _FORMATOS[formato]
                miembros = sorted(
                    (n for n in paquete.namelist() if re.fullmatch(patron, n)),
                    key=self._orden_natural,
                )
                lineas: list[str] = []
                for miembro in miembros:
                    with paquete.open(miembro) as contenido:
                        lineas += self._parrafos(contenido, parrafos)
                    if sum(map(len, lineas)) > self.LIMITE_CARACTERES:
                        break
                return self._recortar("\n".join(lineas))
        except (zipfile.BadZipFile, ElementTree.ParseError, KeyError, OSError) as error:
            raise ErrorExtraccion(f"el fichero está dañado o no es {formato}: {error}") from error
        except RuntimeError as error:
            # zipfile lanza RuntimeError con los ZIP cifrados.
            raise ErrorExtraccion("el documento está protegido con contraseña") from error

    @staticmethod
    def _parrafos(contenido, parrafos: set[str]) -> list[str]:
        """Devuelve el texto de cada párrafo de un XML, leyéndolo en flujo.

        Se usa ``iterparse`` para no cargar en memoria hojas de cálculo con
        cientos de miles de celdas.
        """
        lineas = []
        for _evento, elemento in ElementTree.iterparse(contenido, events=("end",)):
            if elemento.tag.rsplit("}", 1)[-1] in parrafos:
                texto = "".join(elemento.itertext()).strip()
                if texto:
                    lineas.append(texto)
                elemento.clear()
        return lineas

    @staticmethod
    def _epub(paquete: zipfile.ZipFile) -> str:
        """Concatena el texto de todos los capítulos XHTML de un EPUB."""
        partes = []
        for nombre in sorted(paquete.namelist(), key=ExtractorZipXml._orden_natural):
            if nombre.lower().endswith((".xhtml", ".html", ".htm")):
                lector = _TextoHtml()
                lector.feed(paquete.read(nombre).decode("utf-8", "replace"))
                partes.append("".join(lector.partes))
        return "\n".join(partes)

    @staticmethod
    def _orden_natural(nombre: str) -> list:
        """Clave para que ``slide10`` vaya detrás de ``slide9``."""
        return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", nombre)]
