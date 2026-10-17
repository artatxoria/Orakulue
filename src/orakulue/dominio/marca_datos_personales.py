"""Entidad MarcaDatosPersonales: indicios de datos personales en un texto.

Guarda solo **cuántos** indicios hay de cada tipo, nunca los valores: el
informe y la base de datos no deben convertirse en un listado de DNI.
"""

from dataclasses import dataclass
from enum import Enum


class NivelRiesgo(Enum):
    """Gravedad de los indicios. Solo la usa ``MarcaDatosPersonales``."""

    NINGUNO = "ninguno"
    BAJO = "bajo"
    """Algún indicio suelto: un correo, un teléfono o un rótulo de formulario.
    Normal en material de formación; no se excluye."""
    MEDIO = "medio"
    """Varios correos o teléfonos, o un formulario rellenado. Se excluye de
    la fase 4 salvo revisión."""
    ALTO = "alto"
    """Un DNI, NIE o IBAN con dígito de control válido. Se excluye de la
    fase 4 salvo revisión."""


@dataclass(frozen=True)
class MarcaDatosPersonales:
    """Recuento de indicios de un contenido.

    Atributos:
        huella: huella del contenido.
        nivel: nivel de riesgo resultante.
        identificadores: DNI, NIE e IBAN válidos distintos.
        correos: direcciones de correo distintas (sin las de ejemplo).
        telefonos: teléfonos españoles distintos.
        rotulos: rótulos de formulario personal («nombre y apellidos»…).
    """

    huella: str
    nivel: NivelRiesgo
    identificadores: int
    correos: int
    telefonos: int
    rotulos: int

    @property
    def excluir_de_fichas(self) -> bool:
        """Si el contenido no debe enviarse a un servicio externo."""
        return self.nivel in (NivelRiesgo.MEDIO, NivelRiesgo.ALTO)
