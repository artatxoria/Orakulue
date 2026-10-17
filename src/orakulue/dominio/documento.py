"""Entidad Documento: un fichero de documentación tal como lo ve el inventario."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Documento:
    """Fichero inventariado.

    Atributos:
        ruta: ruta absoluta del fichero.
        tamano: tamaño en bytes.
        modificado_ns: fecha de modificación en nanosegundos desde la época
            Unix. Junto con ``tamano`` permite saber si el fichero ha cambiado
            sin volver a leerlo.
        huella: huella SHA-256 del contenido en hexadecimal, o ``None`` si
            todavía no se ha calculado o no se pudo leer.
    """

    ruta: Path
    tamano: int
    modificado_ns: int
    huella: str | None = None

    def sin_cambios_respecto_a(self, otro: "Documento") -> bool:
        """Indica si ``otro`` describe el mismo fichero sin modificar.

        Se usa para reaprovechar la huella de una pasada anterior: si el tamaño
        y la fecha coinciden, recalcularla sería leer el disco para nada.

        Args:
            otro: el mismo fichero visto en otra pasada.

        Returns:
            ``True`` si ruta, tamaño y fecha de modificación coinciden.
        """
        return (
            self.ruta == otro.ruta
            and self.tamano == otro.tamano
            and self.modificado_ns == otro.modificado_ns
        )

    def con_huella(self, huella: str) -> "Documento":
        """Devuelve una copia del documento con la huella indicada.

        Args:
            huella: huella SHA-256 en hexadecimal.

        Returns:
            Nuevo ``Documento`` idéntico salvo por la huella.
        """
        return Documento(self.ruta, self.tamano, self.modificado_ns, huella)
