"""Entidad ConsumoLlamada: los tokens que gastó una llamada al modelo."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ConsumoLlamada:
    """Tokens de una llamada, tal como los informa la respuesta del proveedor.

    El proveedor no dice cuánto saldo queda, pero sí cuántos tokens de cada
    clase ha consumido cada llamada: es la base de la estimación del gasto.

    Atributos:
        modelo: modelo que atendió la llamada (puede ser distinto del pedido
            si actuó un modelo de respaldo).
        entrada: tokens de entrada sin caché.
        salida: tokens de salida, razonamiento incluido.
        lectura_cache: tokens leídos de la caché.
        escritura_cache: tokens escritos en la caché.
        por_lotes: si la llamada fue por la API por lotes (mitad de precio).
    """

    modelo: str
    entrada: int
    salida: int
    lectura_cache: int = 0
    escritura_cache: int = 0
    por_lotes: bool = False
