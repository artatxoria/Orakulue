"""Caso de uso: puntuar las candidatas con criterios explicables.

La puntuación no es una caja negra: se guarda el desglose por criterio para
que el informe diga por qué cada candidata está donde está.
"""

import math

import numpy as np

from orakulue.dominio.candidata import Candidata
from orakulue.infraestructura.cliente_vectores import ClienteVectores
from orakulue.infraestructura.lector_catalogo import CursoCatalogo


class PuntuadorCandidatas:
    """Calcula la puntuación de cada candidata."""

    _PESO_INTERES = {"alto": 2.0, "medio": 1.0}
    #: Escalones de parecido con el **título** de un curso del catálogo (se
    #: compara con el título y no con la descripción porque, medido, el
    #: título da el parecido real: «SQL para la extracción de datos» frente a
    #: «SQL para el Análisis y Gestión de Datos», 0,84 por título y 0,65 por
    #: descripción). Cada escalón dice qué parte de la puntuación conserva:
    #: lo que ya se ofrece no se elimina, porque puede ser una actualización.
    ESCALONES_CATALOGO = ((0.80, 0.3, "ya lo ofreces"), (0.68, 0.7, "parecido a"))

    def __init__(self, vectores: ClienteVectores, catalogo: list[CursoCatalogo]) -> None:
        """Prepara el puntuador.

        Args:
            vectores: cliente de vectores, para comparar con el catálogo.
            catalogo: cursos que ya se ofrecen.
        """
        self._vectores = vectores
        self._catalogo = catalogo
        self._matriz_catalogo = vectores.vectores([c.titulo for c in catalogo]) if catalogo else None

    def puntuar(self, candidatas: list[Candidata]) -> list[Candidata]:
        """Puntúa y ordena de mejor a peor.

        Criterios, cada uno con su peso en el desglose:

        - **respaldo**: suma del interés de los documentos distintos que la
          sugieren, en escala logarítmica (de 1 a 2 documentos es un salto;
          de 20 a 21, no);
        - **ejercicios**: proporción de esos documentos con ejercicios;
        - **vigencia**: proporción de documentos al día;
        - **euskera**: un plus si hay material en euskera;
        - **catálogo**: si se parece a un curso que ya se ofrece, conserva solo
          una parte, según ``ESCALONES_CATALOGO``.

        Returns:
            Las candidatas, ordenadas.
        """
        if not candidatas:
            return []
        textos = [c.ideas[0].titulo for c in candidatas]
        vectores = self._vectores.vectores(textos)
        for candidata, vector in zip(candidatas, vectores):
            por_documento = {}
            for idea in candidata.ideas:
                por_documento.setdefault(idea.huella, idea)
            documentos = list(por_documento.values())
            respaldo = math.log1p(sum(self._PESO_INTERES.get(d.interes, 0) for d in documentos)) * 3
            ejercicios = sum(d.con_ejercicios for d in documentos) / len(documentos)
            vigencia = sum(d.actual for d in documentos) / len(documentos)
            euskera = 0.5 if any(d.idioma == "eu" for d in documentos) else 0.0
            desglose = {"respaldo": respaldo, "ejercicios": ejercicios, "vigencia": vigencia, "euskera": euskera}
            total = sum(desglose.values())
            if self._matriz_catalogo is not None:
                similitudes = self._matriz_catalogo @ vector
                mejor = int(np.argmax(similitudes))
                for umbral, factor, etiqueta in self.ESCALONES_CATALOGO:
                    if similitudes[mejor] >= umbral:
                        candidata.en_catalogo = f"{etiqueta}: {self._catalogo[mejor].titulo}"
                        desglose["catálogo"] = -total * (1 - factor)
                        total *= factor
                        break
            candidata.desglose = {k: round(v, 2) for k, v in desglose.items()}
            candidata.puntuacion = round(total, 2)
        return sorted(candidatas, key=lambda c: (-c.puntuacion, c.clave))
