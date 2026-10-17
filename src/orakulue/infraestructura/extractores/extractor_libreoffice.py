"""Extracción de texto con LibreOffice, para los formatos que no cubre nadie más.

LibreOffice tarda en arrancar, así que solo se usa para lo raro (RTF).
"""

from pathlib import Path

from orakulue.infraestructura.extractores.extractor_programa_externo import ExtractorProgramaExterno


class ExtractorLibreOffice(ExtractorProgramaExterno):
    """``soffice --headless --cat`` escribe el texto del documento en la salida."""

    extensiones = frozenset({"rtf"})

    def orden(self, ruta: Path) -> list[str]:
        """Orden de LibreOffice sin interfaz gráfica."""
        return ["soffice", "--headless", "--cat", str(ruta)]
