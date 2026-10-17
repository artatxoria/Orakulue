"""Extracción de texto de PDF con ``pdftotext`` (Poppler)."""

from pathlib import Path

from orakulue.infraestructura.extractores.extractor_programa_externo import ExtractorProgramaExterno


class ExtractorPdf(ExtractorProgramaExterno):
    """Lee la capa de texto de un PDF.

    Un PDF escaneado no tiene capa de texto y devuelve casi nada: eso no es un
    error, sino un documento que necesitará reconocimiento óptico.
    """

    extensiones = frozenset({"pdf"})

    def orden(self, ruta: Path) -> list[str]:
        """``pdftotext -enc UTF-8 <fichero> -`` escribe el texto en la salida."""
        return ["pdftotext", "-enc", "UTF-8", str(ruta), "-"]
