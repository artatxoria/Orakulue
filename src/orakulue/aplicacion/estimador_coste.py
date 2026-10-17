"""Caso de uso: estimar lo que costará fichar antes de gastar nada.

Es una estimación por longitud de texto, sin llamar al proveedor. La prueba
comparativa da después el coste real por ficha, que es el dato bueno.
"""

from decimal import Decimal

from orakulue.aplicacion.preparador_peticion import INSTRUCCIONES, PreparadorPeticion
from orakulue.aplicacion.seleccion_fichables import Fichable
from orakulue.dominio.consumo_llamada import ConsumoLlamada
from orakulue.dominio.tarifa_modelo import TarifaModelo


class EstimadorCoste:
    """Calcula el coste previsible de fichar una lista de contenidos."""

    #: Caracteres por token. En castellano y euskera ronda 3,5; se usa 3 para
    #: que la estimación peque por exceso y no por defecto.
    CARACTERES_POR_TOKEN = 3
    #: Tokens de salida previstos por ficha (ficha más razonamiento con
    #: esfuerzo bajo). Se sustituirá por el medido en la prueba.
    SALIDA_POR_FICHA = 2_000
    #: Cabecera del mensaje (nombre del fichero, idioma, longitud…).
    CABECERA = 150

    def tokens_entrada(self, fichable: Fichable) -> int:
        """Tokens de entrada previstos para un contenido."""
        enviado = min(
            fichable.caracteres,
            PreparadorPeticion.PRINCIPIO + PreparadorPeticion.CENTRO + PreparadorPeticion.FINAL,
        )
        return (len(INSTRUCCIONES) + enviado) // self.CARACTERES_POR_TOKEN + self.CABECERA

    def estimar(
        self, fichables: list[Fichable], tarifa: TarifaModelo, por_lotes: bool, salida_por_ficha: int | None = None
    ) -> Decimal:
        """Coste total estimado.

        Las instrucciones se cuentan como entrada normal, sin descuento de
        caché: si al final se cachean, el coste real será algo menor.

        Args:
            fichables: contenidos.
            tarifa: tarifa del modelo.
            por_lotes: si se usaría la API por lotes.
            salida_por_ficha: tokens de salida medidos, si ya se conocen.

        Returns:
            Dólares.
        """
        salida = salida_por_ficha or self.SALIDA_POR_FICHA
        consumo = ConsumoLlamada(
            modelo=tarifa.modelo,
            entrada=sum(self.tokens_entrada(f) for f in fichables),
            salida=salida * len(fichables),
            por_lotes=por_lotes,
        )
        return tarifa.coste(consumo)
