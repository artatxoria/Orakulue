"""Caso de uso: agrupar los contenidos distintos cuyo texto es casi igual.

No toca el disco ni decide nada: el resultado es una lista para revisar. Los
casi duplicados son ficheros distintos y nunca se sustituyen por enlaces.
"""

from collections import defaultdict
from collections.abc import Iterable

from orakulue.dominio.grupo_casi_duplicados import GrupoCasiDuplicados
from orakulue.utilidades.boceto_textual import BocetoTextual


class DetectorCasiDuplicados:
    """Compara bocetos de texto y agrupa los que se parecen."""

    #: Parecido a partir del cual dos textos se consideran casi duplicados.
    UMBRAL = 0.80
    #: Valores compartidos mínimos para molestarse en comparar dos bocetos.
    #: Descarta de un plumazo la inmensa mayoría de parejas sin relación.
    MINIMO_COMPARTIDOS = 16
    #: Un valor que aparece en tantos bocetos es una frase hecha (un pie de
    #: página de plantilla, una licencia) y no ayuda a distinguir nada.
    MAXIMO_POR_VALOR = 50

    def __init__(self, boceto: BocetoTextual | None = None) -> None:
        """Prepara el detector.

        Args:
            boceto: calculador de bocetos; por defecto, el estándar.
        """
        self._boceto = boceto or BocetoTextual()

    def detectar(self, textos: Iterable[tuple[str, str]]) -> list[GrupoCasiDuplicados]:
        """Agrupa los textos casi iguales.

        Args:
            textos: pares (huella, texto).

        Returns:
            Grupos de dos o más huellas, de mayor a menor tamaño.
        """
        bocetos = {h: b for h, t in textos if (b := self._boceto.boceto(t))}
        parejas = self._parejas_parecidas(bocetos)
        return self._agrupar(parejas)

    def _parejas_parecidas(self, bocetos: dict[str, tuple[int, ...]]) -> list[tuple[str, str, float]]:
        """Encuentra las parejas por encima del umbral.

        Un índice inverso (valor → huellas que lo tienen) da las parejas que
        comparten valores sin comparar todas contra todas.
        """
        indice: dict[int, list[str]] = defaultdict(list)
        for huella, boceto in bocetos.items():
            for valor in boceto:
                indice[valor].append(huella)
        compartidos: dict[tuple[str, str], int] = defaultdict(int)
        for huellas in indice.values():
            if 1 < len(huellas) <= self.MAXIMO_POR_VALOR:
                for i, a in enumerate(huellas):
                    for b in huellas[i + 1 :]:
                        compartidos[(a, b) if a < b else (b, a)] += 1
        parejas = []
        for (a, b), n in compartidos.items():
            if n >= self.MINIMO_COMPARTIDOS:
                parecido = self._boceto.similitud(bocetos[a], bocetos[b])
                if parecido >= self.UMBRAL:
                    parejas.append((a, b, parecido))
        return parejas

    @staticmethod
    def _agrupar(parejas: list[tuple[str, str, float]]) -> list[GrupoCasiDuplicados]:
        """Une las parejas en grupos (si A se parece a B y B a C, van juntos)."""
        padre: dict[str, str] = {}

        def raiz(x: str) -> str:
            padre.setdefault(x, x)
            while padre[x] != x:
                padre[x] = padre[padre[x]]
                x = padre[x]
            return x

        for a, b, _ in parejas:
            padre[raiz(a)] = raiz(b)
        miembros: dict[str, list[str]] = defaultdict(list)
        parecidos: dict[str, list[float]] = defaultdict(list)
        for a, b, parecido in parejas:
            parecidos[raiz(a)].append(parecido)
        for huella in list(padre):
            miembros[raiz(huella)].append(huella)
        grupos = [
            GrupoCasiDuplicados(tuple(sorted(m)), min(parecidos[r]), max(parecidos[r]))
            for r, m in miembros.items()
            if len(m) > 1
        ]
        return sorted(grupos, key=lambda g: (-len(g.huellas), g.huellas))
