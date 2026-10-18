"""Caso de uso: elegir la tanda de candidatas que se redactan, sin repetidas.

El agrupamiento compara título y descripción, y con eso a veces deja separadas
dos ideas que son la misma («Verificación de contenidos generados por IA» y
«Verificación de información generada por IA»: 0,94 por título). Antes de
gastar en redactarlas, se comparan los títulos de las elegidas y las casi
iguales se funden en la de más puntuación.
"""

import numpy as np

from orakulue.dominio.candidata import Candidata
from orakulue.infraestructura.cliente_vectores import ClienteVectores


class SelectorTanda:
    """Elige las mejores candidatas de cada tipo, fundiendo las repetidas."""

    #: Parecido de títulos a partir del cual dos candidatas son la misma.
    #: Medido: repetidas reales 0,86–0,94; temas próximos pero distintos
    #: («GROUP BY y HAVING» frente a «agregados en SQL») 0,63.
    UMBRAL = 0.80

    def __init__(self, vectores: ClienteVectores) -> None:
        """Prepara el selector.

        Args:
            vectores: cliente de vectores.
        """
        self._vectores = vectores

    def elegir(self, candidatas: list[Candidata], tipo: str, cantidad: int, excluir: set[str]) -> list[Candidata]:
        """Devuelve hasta ``cantidad`` candidatas distintas de un tipo.

        Se recorren de mejor a peor. Una candidata casi igual a otra ya
        elegida no ocupa plaza: sus ideas se suman a la elegida, que así gana
        respaldo para la redacción.

        Args:
            candidatas: todas, ordenadas de mejor a peor.
            tipo: ``curso`` o ``pildora``.
            cantidad: cuántas hacen falta.
            excluir: claves ya redactadas, que no se vuelven a elegir.

        Returns:
            Las elegidas.
        """
        del_tipo = [c for c in candidatas if c.tipo == tipo]
        elegidas: list[Candidata] = []
        vectores: list[np.ndarray] = []
        # Se mira con margen: algunas se funden y hay que seguir buscando.
        for candidata in del_tipo[: cantidad * 4]:
            vector = self._vectores.vectores([candidata.titulo])[0]
            if vectores:
                similitudes = np.stack(vectores) @ vector
                mejor = int(np.argmax(similitudes))
                if similitudes[mejor] >= self.UMBRAL:
                    elegidas[mejor].ideas.extend(candidata.ideas)
                    continue
            if len([e for e in elegidas if e.clave not in excluir]) >= cantidad:
                break
            elegidas.append(candidata)
            vectores.append(vector)
        return [e for e in elegidas if e.clave not in excluir][:cantidad]
