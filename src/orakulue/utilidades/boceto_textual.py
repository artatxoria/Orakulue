"""Bocetos de textos para estimar su parecido sin compararlos enteros.

Técnica *bottom-k*: se trocea el texto en secuencias solapadas de ``n``
palabras, se calcula la huella de cada una y se guardan las ``k`` menores.
La proporción de valores compartidos entre los bocetos de dos textos estima
su índice de Jaccard: la parte común dividida por la unión de sus secuencias.
Con ``k = 256`` el error típico ronda el 3 %, de sobra para decidir si dos
documentos son casi el mismo.
"""

import heapq
import re
import unicodedata


class BocetoTextual:
    """Calcula y compara bocetos *bottom-k*."""

    def __init__(self, k: int = 256, palabras_por_trozo: int = 5, maximo_palabras: int = 150_000) -> None:
        """Prepara el calculador.

        Args:
            k: tamaño del boceto.
            palabras_por_trozo: longitud de cada secuencia de palabras.
            maximo_palabras: palabras que se miran como máximo; el principio
                de un libro basta para reconocerlo y así no se eterniza.
        """
        self.k = k
        self._n = palabras_por_trozo
        self._maximo = maximo_palabras

    def boceto(self, texto: str) -> tuple[int, ...]:
        """Devuelve el boceto de un texto, ordenado de menor a mayor.

        Se normaliza antes (minúsculas, sin tildes, solo letras y cifras) para
        que el mismo documento exportado a PDF y a Word, con diferencias de
        maquetación, se reconozca como el mismo.

        Las huellas usan ``hash()`` de Python, que es rápido y estable dentro
        de una misma ejecución; los bocetos no se guardan entre ejecuciones,
        así que no importa que cambie de una a otra.

        Args:
            texto: texto completo.

        Returns:
            Hasta ``k`` enteros; menos si el texto es muy corto.
        """
        palabras = self._palabras(texto)
        if len(palabras) < self._n:
            return ()
        trozos = {hash(" ".join(palabras[i : i + self._n])) for i in range(len(palabras) - self._n + 1)}
        return tuple(heapq.nsmallest(self.k, trozos))

    def similitud(self, a: tuple[int, ...], b: tuple[int, ...]) -> float:
        """Estima el índice de Jaccard entre dos textos a partir de sus bocetos.

        Se toman los ``k`` menores de la unión y se cuenta qué parte de ellos
        está en los dos bocetos.

        Args:
            a: boceto de un texto.
            b: boceto del otro.

        Returns:
            Valor entre 0 (nada en común) y 1 (iguales).
        """
        if not a or not b:
            return 0.0
        conjunto_a, conjunto_b = set(a), set(b)
        union = heapq.nsmallest(self.k, conjunto_a | conjunto_b)
        comunes = sum(1 for v in union if v in conjunto_a and v in conjunto_b)
        return comunes / len(union)

    def _palabras(self, texto: str) -> list[str]:
        """Normaliza y trocea en palabras."""
        sin_tildes = unicodedata.normalize("NFKD", texto.lower())
        sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
        return re.findall(r"[a-z0-9]+", sin_tildes)[: self._maximo]
