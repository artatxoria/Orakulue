"""Persistencia de los análisis de la fase 3: datos personales y casi duplicados.

La fase 4 los consulta para saber qué no debe enviar a un servicio externo y
qué documentos son variantes de otro.
"""

import sqlite3
from pathlib import Path

from orakulue.dominio.grupo_casi_duplicados import GrupoCasiDuplicados
from orakulue.dominio.marca_datos_personales import MarcaDatosPersonales, NivelRiesgo

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS datos_personales (
    huella          TEXT PRIMARY KEY,
    nivel           TEXT NOT NULL,
    identificadores INTEGER NOT NULL,
    correos         INTEGER NOT NULL,
    telefonos       INTEGER NOT NULL,
    rotulos         INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS casi_duplicados (
    grupo               INTEGER NOT NULL,
    huella              TEXT NOT NULL,
    similitud_minima    REAL NOT NULL,
    similitud_maxima    REAL NOT NULL,
    PRIMARY KEY (grupo, huella)
);
"""


class AlmacenAnalisis:
    """Guarda y recupera los resultados del análisis de textos."""

    def __init__(self, ruta_base_datos: Path) -> None:
        """Abre el almacén.

        Args:
            ruta_base_datos: fichero SQLite compartido con el inventario.
        """
        ruta_base_datos.parent.mkdir(parents=True, exist_ok=True)
        self._conexion = sqlite3.connect(ruta_base_datos)
        self._conexion.executescript(_ESQUEMA)

    def __enter__(self) -> "AlmacenAnalisis":
        """Devuelve el propio almacén al entrar en un bloque ``with``."""
        return self

    def __exit__(self, *_excepcion: object) -> None:
        """Confirma y cierra la conexión."""
        self._conexion.commit()
        self._conexion.close()

    def sustituir(self, marcas: list[MarcaDatosPersonales], grupos: list[GrupoCasiDuplicados]) -> None:
        """Reemplaza por completo los resultados anteriores.

        El análisis se recalcula entero cada vez (es rápido), así que no hay
        resultados viejos que conservar.

        Args:
            marcas: una por contenido analizado.
            grupos: grupos de casi duplicados.
        """
        self._conexion.execute("DELETE FROM datos_personales")
        self._conexion.execute("DELETE FROM casi_duplicados")
        self._conexion.executemany(
            "INSERT INTO datos_personales VALUES (?, ?, ?, ?, ?, ?)",
            [(m.huella, m.nivel.value, m.identificadores, m.correos, m.telefonos, m.rotulos) for m in marcas],
        )
        self._conexion.executemany(
            "INSERT INTO casi_duplicados VALUES (?, ?, ?, ?)",
            [
                (numero, h, g.similitud_minima, g.similitud_maxima)
                for numero, g in enumerate(grupos, start=1)
                for h in g.huellas
            ],
        )
        self._conexion.commit()

    def marcas(self) -> dict[str, MarcaDatosPersonales]:
        """Marcas de datos personales por huella."""
        return {
            f[0]: MarcaDatosPersonales(f[0], NivelRiesgo(f[1]), f[2], f[3], f[4], f[5])
            for f in self._conexion.execute("SELECT * FROM datos_personales")
        }
