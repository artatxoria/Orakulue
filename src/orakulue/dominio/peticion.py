"""Entidad Peticion: el mensaje que se envía al modelo para fichar un documento."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Peticion:
    """Lo que se envía para fichar un contenido.

    Atributos:
        huella: huella del contenido.
        mensaje: texto del mensaje del usuario (datos del documento y texto).
        caracteres_texto: caracteres del documento incluidos.
        recortado: si se ha enviado solo una parte.
    """

    huella: str
    mensaje: str
    caracteres_texto: int
    recortado: bool
