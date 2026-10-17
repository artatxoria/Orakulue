"""Entidad Operacion: un cambio elemental en el disco durante la centralización.

Toda la fase 2 se descompone en operaciones de tres tipos, cada una con su
inversa, para poder registrarlas una a una y deshacerlas en orden contrario.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class TipoOperacion(Enum):
    """Clases de operación. Solo la usa ``Operacion``."""

    MOVER = "mover"
    """Llevar un documento a su sitio en el fondo. Inversa: devolverlo."""

    RETIRAR = "retirar"
    """Apartar una copia sobrante a la carpeta de retirados, en lugar de
    borrarla. Inversa: devolverla a su sitio."""

    ENLAZAR = "enlazar"
    """Crear un enlace simbólico donde estaba el documento. Inversa: quitarlo."""


@dataclass(frozen=True)
class Operacion:
    """Un paso de la centralización.

    Atributos:
        tipo: qué se hace.
        origen: para MOVER y RETIRAR, el fichero que se mueve; para ENLAZAR,
            la ruta donde se crea el enlace.
        destino: para MOVER y RETIRAR, adónde va el fichero; para ENLAZAR, a
            qué apunta el enlace.
        huella: huella del contenido afectado, para comprobarla antes de
            actuar.
        tamano: tamaño en bytes del documento.
        modificado_ns: fecha de modificación según el inventario; si el
            fichero ha cambiado desde entonces, no se toca.
    """

    tipo: TipoOperacion
    origen: Path
    destino: Path
    huella: str
    tamano: int
    modificado_ns: int
