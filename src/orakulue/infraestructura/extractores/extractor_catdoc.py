"""Extracción de texto de formatos binarios antiguos de Microsoft Office.

Los ``.doc``, ``.xls`` y ``.ppt`` anteriores a 2007 no son XML. El paquete
``catdoc`` trae un lector para cada uno, rápidos y sin interfaz gráfica.
"""

from pathlib import Path

from orakulue.infraestructura.extractores.extractor_programa_externo import ExtractorProgramaExterno


class ExtractorCatdoc(ExtractorProgramaExterno):
    """Usa ``catdoc``, ``xls2csv`` o ``catppt`` según la extensión."""

    extensiones = frozenset({"doc", "xls", "ppt"})

    _PROGRAMAS = {"doc": "catdoc", "xls": "xls2csv", "ppt": "catppt"}

    def orden(self, ruta: Path) -> list[str]:
        """Elige el programa por la extensión y pide la salida en UTF-8."""
        programa = self._PROGRAMAS[ruta.suffix.lower().lstrip(".")]
        return [programa, "-d", "utf-8", str(ruta)]
