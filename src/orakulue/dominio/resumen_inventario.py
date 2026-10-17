"""Entidad ResumenInventario: lo que ha ocurrido en una pasada de inventario."""

from dataclasses import dataclass, field
from pathlib import Path

from orakulue.dominio.carpeta_omitida import CarpetaOmitida


@dataclass
class ResumenInventario:
    """Cifras de una pasada, para mostrarlas al terminar y en el informe.

    Atributos:
        encontrados: documentos vistos en el disco.
        huellas_calculadas: documentos nuevos o modificados que se han leído.
        huellas_reutilizadas: documentos sin cambios cuya huella ya se tenía.
        desaparecidos: documentos de pasadas anteriores que ya no están.
        bytes_leidos: bytes leídos para calcular huellas.
        errores: ficheros que no se pudieron leer, con el mensaje del sistema.
        carpetas_omitidas: carpetas que no se recorrieron y por qué.
    """

    encontrados: int = 0
    huellas_calculadas: int = 0
    huellas_reutilizadas: int = 0
    desaparecidos: int = 0
    bytes_leidos: int = 0
    errores: list[tuple[Path, str]] = field(default_factory=list)
    carpetas_omitidas: list[CarpetaOmitida] = field(default_factory=list)
