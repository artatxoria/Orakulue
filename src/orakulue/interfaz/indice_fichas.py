"""Índice de las fichas para Obsidian, por materia y nivel de interés.

Es la puerta de entrada al fondo sin IA: abrir el índice, mirar un tema y
saltar a la ficha. Usa enlaces de Obsidian (``[[nombre|título]]``).
"""

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from orakulue.utilidades.clasificador_materias import ClasificadorMaterias


class IndiceFichas:
    """Escribe ``_indice.md`` en la carpeta de fichas, por materia."""

    _ORDEN_INTERES = {"alto": 0, "medio": 1, "bajo": 2}

    def __init__(self, clasificador: ClasificadorMaterias | None = None) -> None:
        """Prepara el índice.

        Args:
            clasificador: decide la materia de cada ficha.
        """
        self._clasificador = clasificador or ClasificadorMaterias()

    def escribir(self, carpeta: Path, fichas: list[tuple[Path, str, str, str, str]]) -> Path:
        """Escribe el índice.

        Cada materia lista primero lo de interés alto, luego medio y bajo. Las
        fichas sin interés formativo no aparecen: están en ``_sin_interes/``.

        Args:
            carpeta: carpeta de las fichas.
            fichas: (ruta, título, tipo, tema, interés) de cada ficha.

        Returns:
            Ruta del índice.
        """
        por_materia: dict[str, list[tuple[int, str, str, str, str]]] = defaultdict(list)
        sin_interes = 0
        for ruta, titulo, tipo, tema, interes in fichas:
            if interes == "ninguno":
                sin_interes += 1
                continue
            materia = self._clasificador.clasificar(tema, titulo)
            por_materia[materia].append((self._ORDEN_INTERES.get(interes, 3), titulo.lower(), ruta.stem,
                                         titulo, f"{interes} · {tipo}"))

        con_interes = sum(len(v) for v in por_materia.values())
        # Las materias con más fichas primero; «Otras» siempre al final.
        materias = sorted(por_materia, key=lambda m: (m == ClasificadorMaterias.OTRAS, -len(por_materia[m]), m))
        partes = [
            "# Fondo documental — índice de fichas",
            f"Actualizado el {datetime.now():%d/%m/%Y}. {con_interes} fichas con interés formativo, en "
            f"{len(materias)} materias; otras {sin_interes} sin interés en `_sin_interes/`.",
            "**Materias:** " + " · ".join(f"[[#{m}|{m}]] ({len(por_materia[m])})" for m in materias),
        ]
        for materia in materias:
            lineas = "\n".join(
                f"- [[{stem}|{titulo.replace('|', '/')}]] · {detalle}"
                for _, _, stem, titulo, detalle in sorted(por_materia[materia])
            )
            partes.append(f"## {materia}\n\n{lineas}")
        ruta = carpeta / "_indice.md"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text("\n\n".join(partes) + "\n", encoding="utf-8")
        return ruta
