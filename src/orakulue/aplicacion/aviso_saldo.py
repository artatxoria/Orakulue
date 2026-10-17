"""Caso de uso: decir en qué punto está el saldo, en términos comprensibles.

Norma 5: cuánto queda, cuánto se ha gastado y cuántas ejecuciones más aguanta
al ritmo actual. Es información, nunca motivo para parar.
"""

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal


@dataclass(frozen=True)
class AvisoSaldo:
    """Estado estimado del saldo tras una ejecución.

    Atributos:
        variable_clave: variable de entorno de la clave, para nombrarla.
        saldo_declarado: saldo que el usuario declaró tener, o ``None`` si no
            lo ha declarado.
        gastado_total: gasto acumulado según el registro.
        gastado_ejecucion: gasto de esta ejecución.
        fecha_tarifas: fecha de la tabla de precios usada.
    """

    variable_clave: str
    saldo_declarado: Decimal | None
    gastado_total: Decimal
    gastado_ejecucion: Decimal
    fecha_tarifas: str

    #: Por debajo de esta proporción del saldo declarado, el aviso se resalta.
    UMBRAL_BAJO = Decimal("0.20")

    @property
    def restante(self) -> Decimal | None:
        """Saldo estimado que queda, o ``None`` si no hay saldo declarado."""
        if self.saldo_declarado is None:
            return None
        return self.saldo_declarado - self.gastado_total

    @property
    def ejecuciones_restantes(self) -> int | None:
        """Cuántas ejecuciones como esta caben en lo que queda."""
        if self.restante is None or self.gastado_ejecucion <= 0:
            return None
        return int((max(self.restante, Decimal(0)) / self.gastado_ejecucion).to_integral_value(ROUND_DOWN))

    @property
    def es_bajo(self) -> bool:
        """Si queda poco saldo según la estimación."""
        return (
            self.saldo_declarado is not None
            and self.saldo_declarado > 0
            and self.restante is not None
            and self.restante <= self.saldo_declarado * self.UMBRAL_BAJO
        )

    def redactar(self) -> str:
        """Texto del aviso, en castellano y sin códigos."""
        lineas = [
            f"Gasto de esta ejecución: {_dolares(self.gastado_ejecucion)}.",
            f"Gasto acumulado de Orakulue: {_dolares(self.gastado_total)}.",
        ]
        if self.restante is None:
            lineas.append(
                "No hay saldo declarado en la configuración, así que no se puede estimar lo que queda."
            )
        else:
            inicio = "ATENCIÓN, SALDO BAJO. " if self.es_bajo else ""
            linea = f"{inicio}Saldo estimado restante: {_dolares(self.restante)}"
            if self.ejecuciones_restantes is not None:
                linea += f", suficiente para unas {self.ejecuciones_restantes} ejecuciones como esta"
            lineas.append(linea + ".")
        lineas.append(
            f"Es una estimación con las tarifas del {self.fecha_tarifas} y solo cuenta lo gastado con "
            f"la clave {self.variable_clave}. El saldo es de toda la cuenta de Anthropic: si otras "
            "aplicaciones (como el CRM) gastan de la misma cuenta, el saldo real será menor. El dato "
            "bueno está en https://console.anthropic.com/settings/billing"
        )
        return "\n".join(lineas)


def _dolares(cantidad: Decimal) -> str:
    """Formatea dólares con coma decimal y cuatro decimales si es menos de un dólar."""
    decimales = 4 if abs(cantidad) < 1 else 2
    return f"{cantidad:.{decimales}f} $".replace(".", ",")
