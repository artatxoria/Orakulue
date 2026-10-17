"""Entidad TarifaModelo: lo que cuesta cada tipo de token en un modelo."""

from dataclasses import dataclass
from decimal import Decimal

from orakulue.dominio.consumo_llamada import ConsumoLlamada

_MILLON = Decimal(1_000_000)


@dataclass(frozen=True)
class TarifaModelo:
    """Precios de un modelo, en dólares por millón de tokens.

    Atributos:
        modelo: identificador del modelo en la API.
        entrada: tokens de entrada sin caché.
        salida: tokens de salida (incluido el razonamiento).
        lectura_cache: tokens de entrada servidos desde la caché.
        escritura_cache: tokens de entrada escritos en la caché.
    """

    modelo: str
    entrada: Decimal
    salida: Decimal
    lectura_cache: Decimal
    escritura_cache: Decimal

    #: La API por lotes cobra la mitad de todos los tokens.
    DESCUENTO_LOTES = Decimal("0.5")

    def coste(self, consumo: ConsumoLlamada) -> Decimal:
        """Calcula lo que costó una llamada.

        No se redondea: el redondeo se hace solo al mostrarlo, para que sumar
        miles de llamadas pequeñas no acumule error.

        Args:
            consumo: tokens de la llamada.

        Returns:
            Coste en dólares.
        """
        coste = (
            Decimal(consumo.entrada) * self.entrada
            + Decimal(consumo.salida) * self.salida
            + Decimal(consumo.lectura_cache) * self.lectura_cache
            + Decimal(consumo.escritura_cache) * self.escritura_cache
        ) / _MILLON
        return coste * self.DESCUENTO_LOTES if consumo.por_lotes else coste
