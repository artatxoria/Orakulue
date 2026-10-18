"""Caso de uso: agrupar las ideas parecidas en propuestas candidatas.

Cada ficha propone ideas mirando solo su documento, así que la misma propuesta
aparece muchas veces con palabras distintas. Se agrupan por significado con los
vectores de ``bge-m3``, en local y sin coste.
"""

import numpy as np

from orakulue.dominio.candidata import Candidata
from orakulue.dominio.idea_formativa import IdeaFormativa
from orakulue.infraestructura.cliente_vectores import ClienteVectores


class AgrupadorIdeas:
    """Agrupamiento por líderes: sencillo, rápido y sin cadenas."""

    #: Similitud mínima con el centro de un grupo para entrar en él. Con
    #: ``bge-m3``, dos títulos que dicen lo mismo con otras palabras rondan
    #: 0,85; dos de la misma materia pero distinto enfoque, 0,70.
    UMBRAL = 0.82
    _PESO_INTERES = {"alto": 2, "medio": 1}

    def __init__(self, vectores: ClienteVectores) -> None:
        """Prepara el agrupador.

        Args:
            vectores: cliente de vectores.
        """
        self._vectores = vectores

    def agrupar(self, ideas: list[IdeaFormativa]) -> list[Candidata]:
        """Agrupa las ideas de cada tipo por separado.

        Se recorren de más a menos interés. Cada idea entra en el grupo cuyo
        centro más se le parezca, si pasa del umbral, o abre uno nuevo. Se
        compara con el centro y no con cualquier miembro para evitar las
        cadenas: A parecida a B, B a C… y al final un grupo que lo mezcla todo.

        Returns:
            Candidatas de los dos tipos, sin ordenar.
        """
        candidatas = []
        for tipo in ("curso", "pildora"):
            del_tipo = sorted(
                (i for i in ideas if i.tipo == tipo),
                key=lambda i: (-self._PESO_INTERES.get(i.interes, 0), i.huella, i.titulo),
            )
            if not del_tipo:
                continue
            matriz = self._vectores.vectores([i.texto for i in del_tipo])
            centros: list[np.ndarray] = []
            grupos: list[Candidata] = []
            for idea, vector in zip(del_tipo, matriz):
                if centros:
                    similitudes = np.stack(centros) @ vector
                    mejor = int(np.argmax(similitudes))
                    if similitudes[mejor] >= self.UMBRAL:
                        grupos[mejor].ideas.append(idea)
                        n = len(grupos[mejor].ideas)
                        centro = centros[mejor] * (n - 1) / n + vector / n
                        centros[mejor] = centro / (np.linalg.norm(centro) or 1)
                        continue
                centros.append(vector)
                grupos.append(Candidata(tipo, [idea]))
            candidatas += grupos
        return candidatas
