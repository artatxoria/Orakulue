"""Lista completa de duplicados en CSV, para revisarla en una hoja de cálculo.

El Markdown solo detalla los grupos más pesados; aquí va todo, una fila por
fichero, con una columna que dice si es el original propuesto. Así se puede
filtrar por carpeta o corregir la propuesta antes de la fase 2.
"""

import csv
from pathlib import Path

from orakulue.aplicacion.detector_duplicados import DetectorDuplicados
from orakulue.dominio.grupo_duplicados import GrupoDuplicados


class ExportadorCsvDuplicados:
    """Escribe los grupos de duplicados en un CSV."""

    COLUMNAS = ["grupo", "propuesta", "ruta", "nombre", "tamano_bytes", "huella"]

    def __init__(self, grupos: list[GrupoDuplicados], detector: DetectorDuplicados) -> None:
        """Prepara la exportación.

        Args:
            grupos: grupos ya ordenados.
            detector: para saber qué copia se propone como original.
        """
        self._grupos = grupos
        self._detector = detector

    def escribir(self, ruta: Path) -> None:
        """Escribe el CSV.

        Se usa punto y coma como separador y UTF-8 con BOM porque es lo que
        LibreOffice y Excel abren bien en castellano sin preguntar nada.

        Args:
            ruta: fichero de destino; su carpeta se crea si falta.
        """
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with ruta.open("w", newline="", encoding="utf-8-sig") as fichero:
            escritor = csv.writer(fichero, delimiter=";")
            escritor.writerow(self.COLUMNAS)
            for numero, grupo in enumerate(self._grupos, start=1):
                original = self._detector.original_propuesto(grupo)
                for documento in grupo.documentos:
                    escritor.writerow([
                        numero,
                        "original" if documento.ruta == original else "copia",
                        str(documento.ruta),
                        documento.ruta.name,
                        documento.tamano,
                        grupo.huella,
                    ])
