"""Entidad TextoExtraido: el resultado de leer el texto de un documento."""

from dataclasses import dataclass
from enum import Enum


class EstadoExtraccion(Enum):
    """Cómo ha ido la extracción. Solo la usa ``TextoExtraido``."""

    CORRECTA = "correcta"
    """Se ha obtenido texto suficiente."""

    SIN_TEXTO = "sin texto"
    """El documento no tiene capa de texto (típicamente, un PDF escaneado).
    Necesitará reconocimiento óptico de caracteres."""

    ERROR = "error"
    """El fichero no se ha podido leer (dañado, protegido o formato raro)."""


@dataclass(frozen=True)
class TextoExtraido:
    """Texto de un contenido, identificado por su huella.

    Se guarda por huella y no por ruta: dos copias idénticas tienen el mismo
    texto y basta con extraerlo una vez.

    Atributos:
        huella: huella del contenido.
        estado: resultado de la extracción.
        texto: el texto, o cadena vacía si no lo hay.
        extractor: nombre del extractor usado.
        idioma: código del idioma predominante (``es``, ``eu``, ``en``) o
            ``?`` si no se ha podido determinar.
        mensaje: explicación en caso de error.
    """

    huella: str
    estado: EstadoExtraccion
    texto: str
    extractor: str
    idioma: str = "?"
    mensaje: str = ""
