"""Persistencia de los textos extraídos.

El texto de cada contenido se guarda en un fichero propio, por huella, y sus
datos (estado, idioma, extractor) en la base de datos. Así se puede leer un
texto sin cargar los demás, y las fases siguientes los reaprovechan sin volver
a abrir los documentos originales.
"""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

from orakulue.dominio.texto_extraido import EstadoExtraccion, TextoExtraido

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS textos (
    huella      TEXT PRIMARY KEY,
    estado      TEXT NOT NULL,
    caracteres  INTEGER NOT NULL,
    extractor   TEXT NOT NULL,
    idioma      TEXT NOT NULL,
    mensaje     TEXT NOT NULL
);
"""


class AlmacenTextos:
    """Textos por huella: metadatos en SQLite y contenido en ficheros."""

    def __init__(self, ruta_base_datos: Path, carpeta_textos: Path) -> None:
        """Abre el almacén.

        Args:
            ruta_base_datos: fichero SQLite compartido con el inventario.
            carpeta_textos: carpeta donde se guardan los ``.txt``.
        """
        ruta_base_datos.parent.mkdir(parents=True, exist_ok=True)
        self._conexion = sqlite3.connect(ruta_base_datos)
        self._conexion.executescript(_ESQUEMA)
        self._carpeta = carpeta_textos

    def __enter__(self) -> "AlmacenTextos":
        """Devuelve el propio almacén al entrar en un bloque ``with``."""
        return self

    def __exit__(self, *_excepcion: object) -> None:
        """Confirma y cierra la conexión."""
        self._conexion.commit()
        self._conexion.close()

    def huellas_extraidas(self) -> set[str]:
        """Huellas que ya tienen un resultado guardado, sea cual sea."""
        return {h for (h,) in self._conexion.execute("SELECT huella FROM textos")}

    def guardar(self, texto: TextoExtraido) -> None:
        """Guarda un resultado de extracción, sustituyendo el anterior.

        Args:
            texto: resultado.
        """
        ruta = self._ruta(texto.huella)
        if texto.texto:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(texto.texto, encoding="utf-8")
        self._conexion.execute(
            "INSERT OR REPLACE INTO textos VALUES (?, ?, ?, ?, ?, ?)",
            (texto.huella, texto.estado.value, len(texto.texto), texto.extractor,
             texto.idioma, texto.mensaje),
        )

    def confirmar(self) -> None:
        """Confirma en disco los cambios pendientes."""
        self._conexion.commit()

    def olvidar(self, huellas: set[str]) -> None:
        """Borra los resultados de unas huellas para que se vuelvan a extraer.

        Args:
            huellas: huellas que se olvidan.
        """
        self._conexion.executemany("DELETE FROM textos WHERE huella = ?", [(h,) for h in huellas])
        self._conexion.commit()

    def metadatos(self) -> Iterator[tuple[str, EstadoExtraccion, int, str, str, str]]:
        """Recorre los metadatos de todos los textos.

        Yields:
            (huella, estado, caracteres, extractor, idioma, mensaje).
        """
        for fila in self._conexion.execute("SELECT * FROM textos ORDER BY huella"):
            yield fila[0], EstadoExtraccion(fila[1]), fila[2], fila[3], fila[4], fila[5]

    def leer(self, huella: str) -> str:
        """Devuelve el texto de una huella, o cadena vacía si no lo hay.

        Args:
            huella: huella del contenido.
        """
        ruta = self._ruta(huella)
        return ruta.read_text(encoding="utf-8") if ruta.is_file() else ""

    def _ruta(self, huella: str) -> Path:
        """Fichero de texto de una huella.

        Se reparten en subcarpetas por los dos primeros caracteres para no
        tener miles de ficheros en una sola carpeta.
        """
        return self._carpeta / huella[:2] / f"{huella}.txt"
