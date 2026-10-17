"""Registro en SQLite de lo consumido en el proveedor, llamada a llamada.

Es la base de la estimación del saldo: el proveedor no lo publica, pero la suma
de lo gastado según la tarifa, restada del saldo declarado, avisa con tiempo.
"""

import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from orakulue.dominio.consumo_llamada import ConsumoLlamada

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS consumos (
    id              INTEGER PRIMARY KEY,
    momento         TEXT NOT NULL,
    ejecucion       TEXT NOT NULL,
    huella          TEXT,
    modelo          TEXT NOT NULL,
    entrada         INTEGER NOT NULL,
    salida          INTEGER NOT NULL,
    lectura_cache   INTEGER NOT NULL,
    escritura_cache INTEGER NOT NULL,
    por_lotes       INTEGER NOT NULL,
    coste           TEXT NOT NULL
);
"""


class RegistroConsumo:
    """Anota cada llamada con su coste y suma lo gastado."""

    def __init__(self, ruta_base_datos: Path) -> None:
        """Abre el registro.

        Args:
            ruta_base_datos: fichero SQLite compartido con el inventario.
        """
        ruta_base_datos.parent.mkdir(parents=True, exist_ok=True)
        self._conexion = sqlite3.connect(ruta_base_datos)
        self._conexion.executescript(_ESQUEMA)

    def __enter__(self) -> "RegistroConsumo":
        """Devuelve el propio registro al entrar en un bloque ``with``."""
        return self

    def __exit__(self, *_excepcion: object) -> None:
        """Confirma y cierra la conexión."""
        self._conexion.commit()
        self._conexion.close()

    def anotar(self, ejecucion: str, huella: str | None, consumo: ConsumoLlamada, coste: Decimal) -> None:
        """Guarda una llamada y lo confirma al momento.

        Se confirma una a una: si la ejecución se corta, lo gastado hasta ese
        punto tiene que constar, porque se ha pagado.

        Args:
            ejecucion: identificador de la ejecución (para separar el gasto de
                esta vez del acumulado).
            huella: contenido fichado, si lo hay.
            consumo: tokens de la llamada.
            coste: coste calculado con la tarifa.
        """
        self._conexion.execute(
            "INSERT INTO consumos (momento, ejecucion, huella, modelo, entrada, salida, lectura_cache, "
            "escritura_cache, por_lotes, coste) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), ejecucion, huella, consumo.modelo,
             consumo.entrada, consumo.salida, consumo.lectura_cache, consumo.escritura_cache,
             int(consumo.por_lotes), str(coste)),
        )
        self._conexion.commit()

    def salida_media(self, modelo: str) -> int | None:
        """Tokens de salida medios por llamada de un modelo, si hay datos.

        Sirve para que el presupuesto use lo medido en la prueba en lugar de
        un supuesto.
        """
        fila = self._conexion.execute(
            "SELECT AVG(salida), COUNT(*) FROM consumos WHERE modelo = ?", (modelo,)
        ).fetchone()
        return int(fila[0]) if fila and fila[1] else None

    def gastado(self, ejecucion: str | None = None) -> Decimal:
        """Suma lo gastado, en total o en una ejecución.

        Se suma en Python con ``Decimal`` y no con SQL, que lo haría en coma
        flotante y arrastraría error con miles de llamadas.

        Args:
            ejecucion: si se indica, solo esa ejecución.

        Returns:
            Dólares gastados según la tarifa.
        """
        if ejecucion is None:
            filas = self._conexion.execute("SELECT coste FROM consumos")
        else:
            filas = self._conexion.execute("SELECT coste FROM consumos WHERE ejecucion = ?", (ejecucion,))
        return sum((Decimal(c) for (c,) in filas), Decimal(0))
