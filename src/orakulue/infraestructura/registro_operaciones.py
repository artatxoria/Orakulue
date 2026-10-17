"""Registro en SQLite de cada operación de centralización.

Cada ejecución es un **lote**. Antes de tocar nada se guardan todas sus
operaciones como pendientes, y cada una se marca al terminar. Si el proceso se
corta a mitad, el registro dice exactamente qué se hizo y permite deshacerlo.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from orakulue.dominio.operacion import Operacion, TipoOperacion

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS lotes (
    id          INTEGER PRIMARY KEY,
    creado      TEXT NOT NULL,
    descripcion TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS operaciones (
    id              INTEGER PRIMARY KEY,
    lote            INTEGER NOT NULL REFERENCES lotes(id),
    orden           INTEGER NOT NULL,
    tipo            TEXT NOT NULL,
    origen          TEXT NOT NULL,
    destino         TEXT NOT NULL,
    huella          TEXT NOT NULL,
    tamano          INTEGER NOT NULL,
    modificado_ns   INTEGER NOT NULL,
    estado          TEXT NOT NULL DEFAULT 'pendiente',
    mensaje         TEXT,
    momento         TEXT
);
CREATE INDEX IF NOT EXISTS operaciones_lote ON operaciones(lote, orden);
"""


@dataclass(frozen=True)
class OperacionRegistrada:
    """Operación tal como consta en el registro.

    Atributos:
        id: identificador en la base de datos.
        operacion: la operación.
        estado: ``pendiente``, ``hecha``, ``fallida`` o ``deshecha``.
    """

    id: int
    operacion: Operacion
    estado: str


class RegistroOperaciones:
    """Lotes y operaciones de la centralización.

    Comparte fichero con el inventario, pero no sus tablas.
    """

    PENDIENTE = "pendiente"
    HECHA = "hecha"
    FALLIDA = "fallida"
    DESHECHA = "deshecha"

    def __init__(self, ruta_base_datos: Path) -> None:
        """Abre (o crea) el registro.

        Args:
            ruta_base_datos: fichero SQLite.
        """
        ruta_base_datos.parent.mkdir(parents=True, exist_ok=True)
        self._conexion = sqlite3.connect(ruta_base_datos)
        self._conexion.executescript(_ESQUEMA)

    def __enter__(self) -> "RegistroOperaciones":
        """Devuelve el propio registro al entrar en un bloque ``with``."""
        return self

    def __exit__(self, *_excepcion: object) -> None:
        """Confirma y cierra la conexión."""
        self._conexion.commit()
        self._conexion.close()

    def nuevo_lote(self, descripcion: str, operaciones: list[Operacion]) -> int:
        """Guarda un lote con todas sus operaciones pendientes.

        Args:
            descripcion: texto libre para reconocer el lote.
            operaciones: operaciones en orden de ejecución.

        Returns:
            Identificador del lote.
        """
        cursor = self._conexion.execute(
            "INSERT INTO lotes (creado, descripcion) VALUES (?, ?)", (self._ahora(), descripcion)
        )
        lote = int(cursor.lastrowid)
        self._conexion.executemany(
            """INSERT INTO operaciones
               (lote, orden, tipo, origen, destino, huella, tamano, modificado_ns)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (lote, orden, o.tipo.value, str(o.origen), str(o.destino),
                 o.huella, o.tamano, o.modificado_ns)
                for orden, o in enumerate(operaciones)
            ],
        )
        self._conexion.commit()
        return lote

    def operaciones(self, lote: int) -> list[OperacionRegistrada]:
        """Devuelve las operaciones de un lote en orden de ejecución.

        Args:
            lote: identificador del lote.

        Returns:
            Lista de operaciones registradas (vacía si el lote no existe).
        """
        filas = self._conexion.execute(
            """SELECT id, tipo, origen, destino, huella, tamano, modificado_ns, estado
               FROM operaciones WHERE lote = ? ORDER BY orden""",
            (lote,),
        ).fetchall()
        return [
            OperacionRegistrada(
                fila[0],
                Operacion(TipoOperacion(fila[1]), Path(fila[2]), Path(fila[3]), fila[4], fila[5], fila[6]),
                fila[7],
            )
            for fila in filas
        ]

    def marcar(self, id_operacion: int, estado: str, mensaje: str | None = None) -> None:
        """Cambia el estado de una operación y lo confirma en disco al momento.

        Se confirma una a una a propósito: si el proceso se corta, el registro
        tiene que reflejar la última operación hecha, no la última confirmada
        por lotes.

        Args:
            id_operacion: identificador de la operación.
            estado: nuevo estado.
            mensaje: explicación opcional (sobre todo en fallos).
        """
        self._conexion.execute(
            "UPDATE operaciones SET estado = ?, mensaje = ?, momento = ? WHERE id = ?",
            (estado, mensaje, self._ahora(), id_operacion),
        )
        self._conexion.commit()

    def lotes(self) -> list[tuple[int, str, str, dict[str, int]]]:
        """Resume todos los lotes.

        Returns:
            Por lote: identificador, fecha, descripción y recuento por estado.
        """
        resultado = []
        for lote, creado, descripcion in self._conexion.execute(
            "SELECT id, creado, descripcion FROM lotes ORDER BY id"
        ).fetchall():
            estados = dict(self._conexion.execute(
                "SELECT estado, COUNT(*) FROM operaciones WHERE lote = ? GROUP BY estado", (lote,)
            ).fetchall())
            resultado.append((lote, creado, descripcion, estados))
        return resultado

    @staticmethod
    def _ahora() -> str:
        """Fecha y hora local en formato ISO."""
        return datetime.now().isoformat(timespec="seconds")
