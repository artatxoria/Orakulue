"""Entidad CarpetaOmitida: carpeta que el explorador decidió no recorrer."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class MotivoOmision(Enum):
    """Razón por la que se salta una carpeta. Solo la usa ``CarpetaOmitida``."""

    RUTA_EXCLUIDA = "ruta excluida en la configuración"
    NOMBRE_EXCLUIDO = "nombre excluido en la configuración"
    OCULTA = "carpeta oculta"
    REPOSITORIO_GIT = "repositorio git"
    PIEZAS_LATEX = "piezas de compilación de un proyecto LaTeX"
    SYNCTHING = "carpeta de Syncthing"
    SIN_PERMISO = "sin permiso de lectura"


@dataclass(frozen=True)
class CarpetaOmitida:
    """Carpeta no recorrida, con su motivo, para que el informe lo explique.

    Atributos:
        ruta: ruta absoluta de la carpeta.
        motivo: por qué se ha saltado.
    """

    ruta: Path
    motivo: MotivoOmision
