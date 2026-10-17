"""Caso de uso: obtener los grupos de duplicados exactos, listos para revisar."""

from pathlib import Path

from orakulue.dominio.grupo_duplicados import GrupoDuplicados
from orakulue.infraestructura.almacen_inventario import AlmacenInventario


class DetectorDuplicados:
    """Extrae del inventario los documentos repetidos, ordenados por interés.

    Solo detecta duplicados **exactos** (mismo contenido byte a byte). Las
    versiones distintas de un mismo documento o el mismo texto en otro formato
    se tratan en la fase 3, comparando el texto extraído.
    """

    def __init__(self, almacen: AlmacenInventario, prioridad_original: list[Path]) -> None:
        """Prepara el detector.

        Args:
            almacen: inventario ya actualizado.
            prioridad_original: rutas preferidas para el original, en orden.
        """
        self._almacen = almacen
        self._prioridad_original = list(prioridad_original)

    def detectar(self) -> list[GrupoDuplicados]:
        """Devuelve los grupos de duplicados.

        Se ordenan por espacio recuperable, de más a menos, para que la
        revisión empiece por lo que más pesa.

        Returns:
            Lista de grupos ordenada.
        """
        return sorted(
            self._almacen.grupos_duplicados(),
            key=lambda g: (-g.espacio_recuperable, g.huella),
        )

    def original_propuesto(self, grupo: GrupoDuplicados) -> Path:
        """Ruta de la copia que se propone conservar como original.

        Args:
            grupo: grupo de duplicados.

        Returns:
            Ruta del original propuesto.
        """
        return grupo.elegir_original(self._prioridad_original).ruta
