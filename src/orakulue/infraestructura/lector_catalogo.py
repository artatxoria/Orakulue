"""Lectura de los catálogos de cursos en LaTeX: lo que ya se ofrece.

Cada catálogo es un fichero de partes con ``\\input{…}`` a un fichero por curso,
y cada curso empieza con ``\\chapter{Título}`` seguido de sus apartados
(descripción, objetivos…). Se leen solo los ``\\input`` activos: los
comentados son cursos retirados del catálogo a propósito.
"""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CursoCatalogo:
    """Un curso del catálogo actual. Solo la usa ``LectorCatalogo``.

    Atributos:
        titulo: título del curso.
        texto: título y descripción, sin órdenes de LaTeX.
        catalogo: nombre del catálogo del que sale.
    """

    titulo: str
    texto: str
    catalogo: str


class LectorCatalogo:
    """Extrae los cursos de los catálogos."""

    _INPUT = re.compile(r"^[^%\n]*\\input\{([^}]+)\}", re.MULTILINE)
    _CAPITULO = re.compile(r"\\chapter\*?\{([^}]+)\}")
    _DESCRIPCION = re.compile(r"\\item\[Descripci[oó]n\]\s*(.+?)(?=\\item\[|\\end\{description\})", re.S)

    def leer(self, partes: list[Path]) -> list[CursoCatalogo]:
        """Lee los cursos de una lista de ficheros de partes.

        Args:
            partes: ficheros como ``partes/empresas.tex``.

        Returns:
            Cursos encontrados; los ficheros que falten se ignoran.
        """
        cursos = []
        for fichero in partes:
            if not fichero.is_file():
                continue
            base = fichero.parent.parent  # las rutas de \input son relativas a la carpeta del catálogo
            for relativa in self._INPUT.findall(fichero.read_text(encoding="utf-8", errors="replace")):
                curso = base / (relativa if relativa.endswith(".tex") else f"{relativa}.tex")
                cursos += self._cursos_de(curso, fichero.stem)
        return cursos

    def _cursos_de(self, fichero: Path, catalogo: str) -> list[CursoCatalogo]:
        """Cursos de un fichero (normalmente uno)."""
        if not fichero.is_file():
            return []
        texto = fichero.read_text(encoding="utf-8", errors="replace")
        cursos = []
        for capitulo in self._CAPITULO.finditer(texto):
            resto = texto[capitulo.end():]
            descripcion = self._DESCRIPCION.search(resto)
            limpio = self._limpiar(descripcion.group(1)) if descripcion else ""
            titulo = self._limpiar(capitulo.group(1))
            cursos.append(CursoCatalogo(titulo, f"{titulo}. {limpio}"[:1500], catalogo))
        return cursos

    @staticmethod
    def _limpiar(texto: str) -> str:
        """Quita órdenes de LaTeX y espacios sobrantes."""
        texto = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", " ", texto)
        return " ".join(texto.replace("{", " ").replace("}", " ").replace("~", " ").split())
