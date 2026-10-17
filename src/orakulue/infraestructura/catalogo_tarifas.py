"""Tarifas de los modelos que puede usar Orakulue.

Fuente: tabla de modelos de Anthropic, 6 de octubre de 2026 (entrada y salida
de todos; lectura de caché de Opus 5.5 y Sonnet 5.5). Las demás tarifas de caché
son un **supuesto** con la proporción habitual (lectura, 0,1 de la entrada;
escritura, 1,25): pesan muy poco aquí, porque solo se cachean las instrucciones
comunes. **Hay que revisarla
cuando cambien los precios**: un contador de gasto con precios viejos da avisos
falsos. Si se pide un modelo sin tarifa, se falla en vez de estimar con un
precio inventado.
"""

from decimal import Decimal

from orakulue.dominio.tarifa_modelo import TarifaModelo

#: Fecha de la tabla de precios, para mostrarla en los avisos.
FECHA_TARIFAS = "6 de octubre de 2026"


class CatalogoTarifas:
    """Tarifas conocidas, por identificador de modelo."""

    _TARIFAS = {
        t.modelo: t
        for t in (
            # Haiku 5.5: precio para peticiones de hasta 100.000 tokens; las
            # fichas se quedan muy por debajo (40.000 caracteres como máximo).
            TarifaModelo("claude-haiku-5-5", Decimal("0.10"), Decimal("0.50"), Decimal("0.01"), Decimal("0.125")),
            TarifaModelo("claude-sonnet-5-5", Decimal("2.00"), Decimal("10.00"), Decimal("0.20"), Decimal("2.50")),
            TarifaModelo("claude-opus-5-5", Decimal("4.00"), Decimal("20.00"), Decimal("0.20"), Decimal("5.00")),
            # Modelos a los que puede saltar el respaldo ante una negativa.
            TarifaModelo("claude-opus-5", Decimal("5.00"), Decimal("25.00"), Decimal("0.50"), Decimal("6.25")),
            TarifaModelo("claude-opus-4-8", Decimal("5.00"), Decimal("25.00"), Decimal("0.50"), Decimal("6.25")),
        )
    }

    def de(self, modelo: str) -> TarifaModelo:
        """Devuelve la tarifa de un modelo.

        Args:
            modelo: identificador del modelo.

        Returns:
            Su tarifa.

        Raises:
            KeyError: si no hay tarifa registrada para ese modelo.
        """
        if modelo not in self._TARIFAS:
            raise KeyError(
                f"No hay tarifa registrada para «{modelo}». Añádela en catalogo_tarifas.py "
                "antes de usarlo: un contador de gasto con un precio inventado es peor que ninguno."
            )
        return self._TARIFAS[modelo]

    def conocidos(self) -> list[str]:
        """Identificadores con tarifa."""
        return sorted(self._TARIFAS)
