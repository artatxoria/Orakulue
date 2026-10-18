"""Entidad IdeaFormativa: una idea de curso o de píldora sacada de una ficha."""

from dataclasses import dataclass


@dataclass(frozen=True)
class IdeaFormativa:
    """Idea propuesta por la ficha de un documento.

    Atributos:
        tipo: ``curso`` o ``pildora``.
        titulo: título de la idea.
        texto: título y descripción juntos, para compararla con otras.
        huella: documento del que sale.
        interes: interés formativo del documento (``alto`` o ``medio``).
        idioma: idioma del documento.
        actual: si el documento está vigente (no desactualizado).
        con_ejercicios: si el documento trae ejercicios aprovechables.
    """

    tipo: str
    titulo: str
    texto: str
    huella: str
    interes: str
    idioma: str
    actual: bool
    con_ejercicios: bool
