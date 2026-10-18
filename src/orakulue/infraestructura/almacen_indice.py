"""Índice del buscador: piezas de texto, índice de palabras y vectores.

Todo vive en la misma base SQLite que el resto de Orakulue:

- ``piezas``: cada ficha y cada trozo de texto, con su vector en media
  precisión (2 bytes por dimensión).
- ``piezas_fts``: índice de palabras FTS5 sobre esas piezas.

Los vectores se cargan en memoria al buscar: con decenas de miles de piezas,
multiplicar la matriz entera es instantáneo y no hace falta un servidor de
vectores aparte.
"""

import re
import sqlite3
from pathlib import Path

import numpy as np

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS piezas (
    id      INTEGER PRIMARY KEY,
    huella  TEXT NOT NULL,
    tipo    TEXT NOT NULL,      -- 'ficha' o 'trozo'
    orden   INTEGER NOT NULL,
    texto   TEXT NOT NULL,
    vector  BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS piezas_huella ON piezas(huella, tipo);
CREATE VIRTUAL TABLE IF NOT EXISTS piezas_fts USING fts5(
    texto, content='piezas', content_rowid='id', tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS piezas_alta AFTER INSERT ON piezas BEGIN
    INSERT INTO piezas_fts(rowid, texto) VALUES (new.id, new.texto);
END;
CREATE TRIGGER IF NOT EXISTS piezas_baja AFTER DELETE ON piezas BEGIN
    INSERT INTO piezas_fts(piezas_fts, rowid, texto) VALUES ('delete', old.id, old.texto);
END;
CREATE TABLE IF NOT EXISTS indexados (
    huella  TEXT NOT NULL,
    tipo    TEXT NOT NULL,
    version TEXT NOT NULL,      -- para las fichas, el momento en que se escribió
    PRIMARY KEY (huella, tipo)
);
"""


class AlmacenIndice:
    """Lectura y escritura del índice del buscador."""

    #: Palabras vacías que se quitan de la consulta por palabras. Unidas con
    #: OR, «en», «de» o «eta» casarían con casi cualquier pieza y llenarían
    #: los candidatos de ruido.
    PALABRAS_VACIAS = frozenset(
        "el la los las un una unos unas de del al a en y o u que con por para como se su sus es son "
        "lo le les mi me te tu qué cómo cuál dónde hay tengo tiene sobre entre sin más muy ya pero "
        "eta edo da dira bat ez du dute ere nola zer non zein the and of to in is for on with what how".split()
    )

    def __init__(self, ruta_base_datos: Path, entre_hilos: bool = False) -> None:
        """Abre el índice.

        Args:
            ruta_base_datos: fichero SQLite compartido con el inventario.
            entre_hilos: permite usar la conexión desde varios hilos (la web
                atiende cada petición en un hilo). Quien lo active debe
                serializar el acceso con un cerrojo.
        """
        ruta_base_datos.parent.mkdir(parents=True, exist_ok=True)
        self._conexion = sqlite3.connect(ruta_base_datos, check_same_thread=not entre_hilos)
        self._conexion.executescript(_ESQUEMA)
        self._matriz: np.ndarray | None = None
        self._ids: np.ndarray | None = None

    def __enter__(self) -> "AlmacenIndice":
        """Devuelve el propio almacén al entrar en un bloque ``with``."""
        return self

    def __exit__(self, *_excepcion: object) -> None:
        """Confirma y cierra la conexión."""
        self._conexion.commit()
        self._conexion.close()

    def indexados(self, tipo: str) -> dict[str, str]:
        """Huellas indexadas de un tipo, con su versión."""
        return dict(self._conexion.execute("SELECT huella, version FROM indexados WHERE tipo = ?", (tipo,)))

    def sustituir(self, huella: str, tipo: str, version: str, textos: list[str], vectores: np.ndarray) -> None:
        """Reemplaza las piezas de un documento y lo confirma.

        Se confirma documento a documento: si la indexación se corta, lo hecho
        se conserva y se continúa desde ahí.

        Args:
            huella: contenido.
            tipo: ``ficha`` o ``trozo``.
            version: versión indexada.
            textos: textos de las piezas.
            vectores: un vector por texto.
        """
        self._borrar(huella, tipo)
        self._conexion.executemany(
            "INSERT INTO piezas (huella, tipo, orden, texto, vector) VALUES (?, ?, ?, ?, ?)",
            [(huella, tipo, i, t, v.astype(np.float16).tobytes()) for i, (t, v) in enumerate(zip(textos, vectores))],
        )
        self._conexion.execute(
            "INSERT OR REPLACE INTO indexados VALUES (?, ?, ?)", (huella, tipo, version)
        )
        self._conexion.commit()
        self._matriz = None

    def olvidar(self, huellas: set[str]) -> None:
        """Quita del índice los contenidos que ya no están en el inventario."""
        for huella in huellas:
            for tipo in ("ficha", "trozo"):
                self._borrar(huella, tipo)
        self._conexion.commit()
        self._matriz = None

    def olvidar_tipo(self, huellas: set[str], tipo: str) -> None:
        """Quita del índice las piezas de un tipo (p. ej. solo las fichas)."""
        for huella in huellas:
            self._borrar(huella, tipo)
        self._conexion.commit()
        self._matriz = None

    def por_palabras(self, consulta: str, limite: int) -> list[int]:
        """Piezas que mejor casan por palabras (BM25), de mejor a peor.

        La consulta del usuario se reduce a sus palabras, unidas con OR: así
        un signo raro no rompe la sintaxis de FTS5, y no hace falta que estén
        todas.

        Args:
            consulta: texto libre.
            limite: cuántas piezas devolver.

        Returns:
            Identificadores de pieza.
        """
        palabras = [p for p in re.findall(r"\w+", consulta)
                    if len(p) > 1 and p.lower() not in self.PALABRAS_VACIAS]
        if not palabras:
            return []
        expresion = " OR ".join(f'"{p}"' for p in palabras)
        return [i for (i,) in self._conexion.execute(
            "SELECT rowid FROM piezas_fts WHERE piezas_fts MATCH ? ORDER BY bm25(piezas_fts) LIMIT ?",
            (expresion, limite),
        )]

    def por_significado(self, vector: np.ndarray, limite: int) -> list[int]:
        """Piezas más parecidas a un vector, de mejor a peor.

        Args:
            vector: vector normalizado de la consulta.
            limite: cuántas piezas devolver.

        Returns:
            Identificadores de pieza.
        """
        matriz, ids = self._cargar()
        if len(ids) == 0:
            return []
        similitudes = matriz @ vector.astype(np.float32)
        limite = min(limite, len(ids))
        mejores = np.argpartition(-similitudes, limite - 1)[:limite]
        return [int(ids[i]) for i in mejores[np.argsort(-similitudes[mejores])]]

    def piezas(self, ids: list[int]) -> dict[int, tuple[str, str, int, str]]:
        """Datos de unas piezas: id → (huella, tipo, orden, texto)."""
        if not ids:
            return {}
        marcas = ",".join("?" * len(ids))
        return {
            f[0]: (f[1], f[2], f[3], f[4])
            for f in self._conexion.execute(
                f"SELECT id, huella, tipo, orden, texto FROM piezas WHERE id IN ({marcas})", ids
            )
        }

    def cifras(self) -> dict[str, int]:
        """Número de piezas por tipo."""
        return dict(self._conexion.execute("SELECT tipo, COUNT(*) FROM piezas GROUP BY tipo"))

    def _cargar(self) -> tuple[np.ndarray, np.ndarray]:
        """Carga todos los vectores en memoria la primera vez que se busca."""
        if self._matriz is None:
            filas = self._conexion.execute("SELECT id, vector FROM piezas ORDER BY id").fetchall()
            self._ids = np.array([f[0] for f in filas], dtype=np.int64)
            self._matriz = (
                np.frombuffer(b"".join(f[1] for f in filas), dtype=np.float16).reshape(len(filas), -1)
                .astype(np.float32)
                if filas else np.zeros((0, 0), dtype=np.float32)
            )
        return self._matriz, self._ids

    def _borrar(self, huella: str, tipo: str) -> None:
        """Borra las piezas de un documento y su registro."""
        self._conexion.execute("DELETE FROM piezas WHERE huella = ? AND tipo = ?", (huella, tipo))
        self._conexion.execute("DELETE FROM indexados WHERE huella = ? AND tipo = ?", (huella, tipo))
