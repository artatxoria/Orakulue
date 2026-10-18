"""Registro de las propuestas redactadas.

Guarda la respuesta completa del modelo, como las fichas: así el Markdown se
puede rehacer (otra plantilla, el formato de SPRI cuando llegue) sin pagar otra
vez, y una propuesta hecha no se vuelve a pedir.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from orakulue.dominio.propuesta import Propuesta

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS propuestas (
    clave       TEXT PRIMARY KEY,
    tipo        TEXT NOT NULL,
    titulo      TEXT NOT NULL,
    modelo      TEXT NOT NULL,
    puntuacion  REAL NOT NULL,
    desglose    TEXT NOT NULL,
    en_catalogo TEXT NOT NULL,
    fuentes     TEXT NOT NULL,
    datos       TEXT NOT NULL,
    ruta        TEXT NOT NULL,
    momento     TEXT NOT NULL
);
"""


class AlmacenPropuestas:
    """Propuestas redactadas."""

    def __init__(self, ruta_base_datos: Path) -> None:
        """Abre el almacén.

        Args:
            ruta_base_datos: fichero SQLite compartido con el inventario.
        """
        ruta_base_datos.parent.mkdir(parents=True, exist_ok=True)
        self._conexion = sqlite3.connect(ruta_base_datos)
        self._conexion.executescript(_ESQUEMA)

    def __enter__(self) -> "AlmacenPropuestas":
        """Devuelve el propio almacén al entrar en un bloque ``with``."""
        return self

    def __exit__(self, *_excepcion: object) -> None:
        """Confirma y cierra la conexión."""
        self._conexion.commit()
        self._conexion.close()

    def hechas(self) -> set[str]:
        """Claves de las candidatas ya redactadas."""
        return {c for (c,) in self._conexion.execute("SELECT clave FROM propuestas")}

    def guardar(self, propuesta: Propuesta, ruta: Path) -> None:
        """Registra una propuesta escrita en disco y lo confirma al momento."""
        self._conexion.execute(
            "INSERT OR REPLACE INTO propuestas VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (propuesta.clave, propuesta.tipo, propuesta.titulo, propuesta.modelo, propuesta.puntuacion,
             json.dumps(propuesta.desglose, ensure_ascii=False), propuesta.en_catalogo,
             json.dumps(list(propuesta.fuentes)), json.dumps(propuesta.datos, ensure_ascii=False),
             str(ruta), datetime.now().isoformat(timespec="seconds")),
        )
        self._conexion.commit()

    def todas(self) -> list[tuple[Propuesta, Path]]:
        """Todas las propuestas con su fichero, de mejor a peor puntuación."""
        filas = self._conexion.execute(
            "SELECT clave, tipo, modelo, puntuacion, desglose, en_catalogo, fuentes, datos, ruta "
            "FROM propuestas ORDER BY puntuacion DESC"
        ).fetchall()
        return [
            (Propuesta(f[1], f[0], f[2], json.loads(f[7]), tuple(json.loads(f[6])), f[3],
                       json.loads(f[4]), f[5]), Path(f[8]))
            for f in filas
        ]

    def por_clave(self, clave: str) -> tuple[Propuesta, Path] | None:
        """Una propuesta por su clave."""
        return next(((p, r) for p, r in self.todas() if p.clave == clave), None)
