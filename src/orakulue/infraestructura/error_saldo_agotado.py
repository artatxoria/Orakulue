"""Error por falta de saldo en la cuenta del proveedor (norma 5)."""


class ErrorSaldoAgotado(Exception):
    """La cuenta asociada a una clave se ha quedado sin saldo.

    Es el único error que debe cortar una ejecución por motivos de gasto: los
    avisos de saldo bajo nunca paran nada.

    Atributos:
        variable: variable de entorno de la clave que ha fallado.
    """

    #: Frases con las que el proveedor anuncia la falta de saldo. Se mira el
    #: texto y no el código HTTP, porque el mismo 400 sirve para «sin saldo» y
    #: para «petición mal formada»: confundirlos mandaría a recargar la tarjeta
    #: sin motivo.
    FRASES = ("credit balance is too low", "insufficient credit", "purchase credits")

    def __init__(self, variable: str, mensaje_original: str) -> None:
        """Construye el error con un mensaje en castellano.

        Args:
            variable: variable de entorno de la clave.
            mensaje_original: mensaje del proveedor, para contrastar.
        """
        self.variable = variable
        super().__init__(
            f"Se ha agotado el saldo de la cuenta de Anthropic asociada a la clave "
            f"{variable}. Las fichas ya escritas están guardadas; al recargar, la orden "
            f"continuará donde se quedó sin volver a pagar lo hecho. Recarga en "
            f"https://console.anthropic.com/settings/billing\n"
            f"Mensaje original del proveedor: {mensaje_original}"
        )

    @classmethod
    def es_falta_de_saldo(cls, mensaje: str) -> bool:
        """Indica si un mensaje de error del proveedor habla de falta de saldo.

        Ante la duda, ``False``: un falso positivo es peor que un error normal.

        Args:
            mensaje: texto del error.
        """
        minusculas = mensaje.lower()
        return any(frase in minusculas for frase in cls.FRASES)
