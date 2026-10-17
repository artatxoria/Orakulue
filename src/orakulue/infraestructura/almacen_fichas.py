"""Registro de las fichas escritas y de los lotes enviados al proveedor.

Es lo que hace reanudable la fase 4: una ficha registrada no se vuelve a pedir,
y un lote enviado cuyos resultados no se han recogido se recoge antes de enviar
nada nuevo. Así nunca se paga dos veces lo mismo.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from orakulue.dominio.ficha import Ficha

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS fichas (
    huella      TEXT PRIMARY KEY,
    modelo      TEXT NOT NULL,
    ruta        TEXT NOT NULL,
    titulo      TEXT NOT NULL,
    tipo        TEXT NOT NULL,
    tema        TEXT NOT NULL,
    interes     TEXT NOT NULL,
    momento     TEXT NOT NULL,
    datos       TEXT
);
CREATE TABLE IF NOT EXISTS lotes_api (
    id          TEXT PRIMARY KEY,
    modelo      TEXT NOT NULL,
    peticiones  INTEGER NOT NULL,
    creado      TEXT NOT NULL,
    recogido    INTEGER NOT NULL DEFAULT 0
);
"""


class AlmacenFichas:
    """Fichas hechas y lotes enviados."""

    def __init__(self, ruta_base_datos: Path) -> None:
        """Abre el almacén.

        Args:
            ruta_base_datos: fichero SQLite compartido con el inventario.
        """
        ruta_base_datos.parent.mkdir(parents=True, exist_ok=True)
        self._conexion = sqlite3.connect(ruta_base_datos)
        self._conexion.executescript(_ESQUEMA)
        columnas = {f[1] for f in self._conexion.execute("PRAGMA table_info(fichas)")}
        if "datos" not in columnas:
            # Versión anterior sin la respuesta del modelo: se añade la columna
            # y se rellena recogiendo otra vez el lote (gratis mientras el
            # proveedor lo conserve).
            self._conexion.execute("ALTER TABLE fichas ADD COLUMN datos TEXT")

    def __enter__(self) -> "AlmacenFichas":
        """Devuelve el propio almacén al entrar en un bloque ``with``."""
        return self

    def __exit__(self, *_excepcion: object) -> None:
        """Confirma y cierra la conexión."""
        self._conexion.commit()
        self._conexion.close()

    def hechas(self) -> set[str]:
        """Huellas que ya tienen ficha."""
        return {h for (h,) in self._conexion.execute("SELECT huella FROM fichas")}

    def guardar(self, ficha: Ficha, ruta: Path) -> None:
        """Registra una ficha escrita en disco y lo confirma al momento.

        Args:
            ficha: la ficha.
            ruta: fichero Markdown donde se ha escrito.
        """
        # Se guarda también la respuesta completa del modelo: con ella se
        # pueden volver a escribir las fichas (otro formato, otra organización)
        # sin pagar otra vez.
        d = ficha.datos
        self._conexion.execute(
            "INSERT OR REPLACE INTO fichas VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ficha.huella, ficha.modelo, str(ruta), ficha.titulo, d["tipo"], d["tema"], d["interes"],
             datetime.now().isoformat(timespec="seconds"), json.dumps(d, ensure_ascii=False)),
        )
        self._conexion.commit()

    def todas(self) -> list[tuple[Path, str, str, str, str]]:
        """Todas las fichas: (ruta, título, tipo, tema, interés)."""
        return [
            (Path(r), titulo, tipo, tema, interes)
            for r, titulo, tipo, tema, interes in self._conexion.execute(
                "SELECT ruta, titulo, tipo, tema, interes FROM fichas ORDER BY tema, titulo"
            )
        ]

    def con_datos(self) -> dict[str, tuple[dict, str, Path]]:
        """Fichas con su respuesta guardada: huella → (datos, momento, ruta).

        Las fichas antiguas sin respuesta guardada no aparecen (habría que
        rellenarlas con ``fichar --reescribir``).
        """
        return {
            huella: (json.loads(datos), momento, Path(ruta))
            for huella, datos, momento, ruta in self._conexion.execute(
                "SELECT huella, datos, momento, ruta FROM fichas WHERE datos IS NOT NULL"
            )
        }

    def registrar_lote(self, identificador: str, modelo: str, peticiones: int) -> None:
        """Anota un lote recién enviado, antes de esperar sus resultados.

        Se anota nada más crearlo: si el proceso se corta mientras se espera,
        el lote ya está pagado y sus resultados tienen que poder recogerse.
        """
        self._conexion.execute(
            "INSERT INTO lotes_api (id, modelo, peticiones, creado) VALUES (?, ?, ?, ?)",
            (identificador, modelo, peticiones, datetime.now().isoformat(timespec="seconds")),
        )
        self._conexion.commit()

    def lote_pendiente(self) -> tuple[str, str] | None:
        """El lote enviado cuyos resultados aún no se han recogido, si lo hay.

        Returns:
            (identificador, modelo), o ``None``.
        """
        fila = self._conexion.execute(
            "SELECT id, modelo FROM lotes_api WHERE recogido = 0 ORDER BY creado LIMIT 1"
        ).fetchone()
        return (fila[0], fila[1]) if fila else None

    def ultimo_lote_recogido(self) -> str | None:
        """Identificador del último lote cuyos resultados se recogieron."""
        fila = self._conexion.execute(
            "SELECT id FROM lotes_api WHERE recogido = 1 ORDER BY creado DESC LIMIT 1"
        ).fetchone()
        return fila[0] if fila else None

    def marcar_recogido(self, identificador: str) -> None:
        """Da por recogidos los resultados de un lote."""
        self._conexion.execute("UPDATE lotes_api SET recogido = 1 WHERE id = ?", (identificador,))
        self._conexion.commit()
