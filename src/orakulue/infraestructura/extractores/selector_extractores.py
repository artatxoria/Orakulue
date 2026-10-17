"""Elección del extractor adecuado para cada documento."""

from pathlib import Path

from orakulue.infraestructura.extractores.extractor_catdoc import ExtractorCatdoc
from orakulue.infraestructura.extractores.extractor_libreoffice import ExtractorLibreOffice
from orakulue.infraestructura.extractores.extractor_pdf import ExtractorPdf
from orakulue.infraestructura.extractores.extractor_texto import ExtractorTexto
from orakulue.infraestructura.extractores.extractor_zip_xml import ExtractorZipXml


class SelectorExtractores:
    """Asocia cada extensión a su extractor."""

    def __init__(self, extractores: list[ExtractorTexto] | None = None) -> None:
        """Registra los extractores disponibles.

        Args:
            extractores: lista propia (útil en pruebas); por defecto, todos.
        """
        self._por_extension: dict[str, ExtractorTexto] = {}
        for extractor in extractores or [
            ExtractorPdf(), ExtractorZipXml(), ExtractorCatdoc(), ExtractorLibreOffice()
        ]:
            for extension in extractor.extensiones:
                self._por_extension[extension] = extractor

    def para(self, ruta: Path) -> ExtractorTexto | None:
        """Devuelve el extractor de un documento.

        Args:
            ruta: documento.

        Returns:
            El extractor, o ``None`` si el formato no tiene ninguno.
        """
        return self._por_extension.get(ruta.suffix.lower().lstrip("."))
