"""Índice de las propuestas para Obsidian, ordenado por puntuación."""

from datetime import datetime
from pathlib import Path

from orakulue.dominio.propuesta import Propuesta


class IndicePropuestas:
    """Escribe ``_indice.md`` en la carpeta de propuestas."""

    def escribir(self, carpeta: Path, propuestas: list[tuple[Propuesta, Path]]) -> Path:
        """Escribe el índice.

        Args:
            carpeta: carpeta de las propuestas.
            propuestas: propuestas con su fichero, de mejor a peor.

        Returns:
            Ruta del índice.
        """
        partes = [
            "# Propuestas de cursos y píldoras",
            f"Actualizado el {datetime.now():%d/%m/%Y}. Ordenadas por puntuación: respaldo en el fondo, "
            "ejercicios disponibles, vigencia, material en euskera y relación con el catálogo actual. "
            "Para pasar una a Bibliotecario: `orakulue exportar-propuesta <clave>`.",
        ]
        for tipo, titulo in (("curso", "Cursos"), ("pildora", "Píldoras")):
            filas = [
                f"| [[{ruta.stem}\\|{p.titulo.replace('|', '/')}]] | {p.puntuacion} | {p.en_catalogo or '—'} | `{p.clave}` |"
                for p, ruta in propuestas if p.tipo == tipo
            ]
            if filas:
                partes.append(f"## {titulo} ({len(filas)})\n\n| Propuesta | Puntos | Catálogo | Clave |\n"
                              "|---|---:|---|---|\n" + "\n".join(filas))
        ruta = carpeta / "_indice.md"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text("\n\n".join(partes) + "\n", encoding="utf-8")
        return ruta
