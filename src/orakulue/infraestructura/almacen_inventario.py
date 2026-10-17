"""Persistencia del inventario en SQLite.

Guardar el inventario permite que las pasadas siguientes sean incrementales:
solo se vuelve a leer lo que ha cambiado. También es la base que usará la
fase 2 para mover documentos y sustituir copias por enlaces.
"""

import sqlite3
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from orakulue.dominio.documento import Documento
from orakulue.dominio.grupo_duplicados import GrupoDuplicados

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS pasadas (
    id          INTEGER PRIMARY KEY,
    inicio      TEXT NOT NULL,
    fin         TEXT
);
CREATE TABLE IF NOT EXISTS documentos (
    ruta            TEXT PRIMARY KEY,
    tamano          INTEGER NOT NULL,
    modificado_ns   INTEGER NOT NULL,
    huella          TEXT,
    ultima_pasada   INTEGER NOT NULL REFERENCES pasadas(id)
);
CREATE INDEX IF NOT EXISTS documentos_huella ON documentos(huella);
"""


class AlmacenInventario:
    """Base de datos del inventario.

    Se usa como gestor de contexto para garantizar que la conexión se cierra::

        with AlmacenInventario(ruta) as almacen:
            ...
    """

    def __init__(self, ruta_base_datos: Path) -> None:
        """Abre (o crea) la base de datos.

        Args:
            ruta_base_datos: fichero SQLite; su carpeta se crea si no existe.

        Raises:
            sqlite3.Error: si el fichero no se puede abrir.
        """
        ruta_base_datos.parent.mkdir(parents=True, exist_ok=True)
        self._conexion = sqlite3.connect(ruta_base_datos)
        self._conexion.executescript(_ESQUEMA)

    def __enter__(self) -> "AlmacenInventario":
        """Devuelve el propio almacén al entrar en un bloque ``with``."""
        return self

    def __exit__(self, *_excepcion: object) -> None:
        """Confirma los cambios pendientes y cierra la conexión."""
        self.cerrar()

    def cerrar(self) -> None:
        """Confirma los cambios pendientes y cierra la conexión."""
        self._conexion.commit()
        self._conexion.close()

    def iniciar_pasada(self) -> int:
        """Registra el comienzo de una pasada de inventario.

        Returns:
            Identificador de la pasada.
        """
        cursor = self._conexion.execute(
            "INSERT INTO pasadas (inicio) VALUES (?)", (self._ahora(),)
        )
        self._conexion.commit()
        return int(cursor.lastrowid)

    def cerrar_pasada(self, pasada: int) -> int:
        """Da por terminada una pasada y olvida lo que ya no está en el disco.

        Un documento que no se ha visto en esta pasada se ha borrado, movido o
        excluido; mantenerlo daría duplicados fantasma en el informe.

        Args:
            pasada: identificador devuelto por ``iniciar_pasada``.

        Returns:
            Número de documentos eliminados del inventario.
        """
        cursor = self._conexion.execute(
            "DELETE FROM documentos WHERE ultima_pasada <> ?", (pasada,)
        )
        self._conexion.execute(
            "UPDATE pasadas SET fin = ? WHERE id = ?", (self._ahora(), pasada)
        )
        self._conexion.commit()
        return cursor.rowcount

    def obtener(self, ruta: Path) -> Documento | None:
        """Busca un documento por su ruta.

        Args:
            ruta: ruta absoluta.

        Returns:
            El documento guardado, o ``None`` si no está.
        """
        fila = self._conexion.execute(
            "SELECT ruta, tamano, modificado_ns, huella FROM documentos WHERE ruta = ?",
            (str(ruta),),
        ).fetchone()
        return self._como_documento(fila) if fila else None

    def guardar(self, documento: Documento, pasada: int) -> None:
        """Inserta o actualiza un documento y lo marca como visto.

        No confirma la transacción: se confirma cada cierto número de
        documentos (``confirmar``) para no escribir en disco a cada fichero.

        Args:
            documento: documento con o sin huella.
            pasada: pasada en la que se ha visto.
        """
        self._conexion.execute(
            """
            INSERT INTO documentos (ruta, tamano, modificado_ns, huella, ultima_pasada)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(ruta) DO UPDATE SET
                tamano = excluded.tamano,
                modificado_ns = excluded.modificado_ns,
                huella = excluded.huella,
                ultima_pasada = excluded.ultima_pasada
            """,
            (str(documento.ruta), documento.tamano, documento.modificado_ns,
             documento.huella, pasada),
        )

    def confirmar(self) -> None:
        """Confirma en disco los cambios pendientes."""
        self._conexion.commit()

    def documentos(self) -> Iterator[Documento]:
        """Recorre todos los documentos inventariados, por ruta.

        Yields:
            Cada ``Documento`` guardado.
        """
        cursor = self._conexion.execute(
            "SELECT ruta, tamano, modificado_ns, huella FROM documentos ORDER BY ruta"
        )
        for fila in cursor:
            yield self._como_documento(fila)

    def grupos_duplicados(self) -> list[GrupoDuplicados]:
        """Agrupa los documentos que comparten huella.

        Returns:
            Un ``GrupoDuplicados`` por cada huella con dos o más ficheros, sin
            orden particular.
        """
        filas = self._conexion.execute(
            """
            SELECT ruta, tamano, modificado_ns, huella FROM documentos
            WHERE huella IN (
                SELECT huella FROM documentos
                WHERE huella IS NOT NULL
                GROUP BY huella HAVING COUNT(*) > 1
            )
            ORDER BY huella, ruta
            """
        ).fetchall()
        grupos: dict[str, list[Documento]] = {}
        for fila in filas:
            documento = self._como_documento(fila)
            grupos.setdefault(documento.huella, []).append(documento)
        return [
            GrupoDuplicados(huella, documentos[0].tamano, tuple(documentos))
            for huella, documentos in grupos.items()
        ]

    @staticmethod
    def _como_documento(fila: tuple) -> Documento:
        """Convierte una fila de la tabla en ``Documento``."""
        ruta, tamano, modificado_ns, huella = fila
        return Documento(Path(ruta), tamano, modificado_ns, huella)

    @staticmethod
    def _ahora() -> str:
        """Fecha y hora local en formato ISO, para las pasadas."""
        return datetime.now().isoformat(timespec="seconds")
