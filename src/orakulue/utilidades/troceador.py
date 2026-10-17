"""Troceado del texto de un documento en pasajes para el buscador.

Un buscador por significado compara la pregunta con trozos de texto, no con
documentos enteros: un libro de 300 páginas «trata de todo» y no se parece a
ninguna pregunta concreta. Los trozos deben ser lo bastante pequeños para que
cada uno trate de una cosa y lo bastante grandes para tener sentido solos.
"""

import re


class Troceador:
    """Divide un texto en trozos de tamaño parecido, respetando los párrafos."""

    def __init__(self, tamano: int = 1_500, solape: int = 200) -> None:
        """Prepara el troceador.

        Args:
            tamano: caracteres objetivo por trozo.
            solape: caracteres que se repiten entre un trozo y el siguiente,
                para que una idea partida justo en la frontera aparezca entera
                en alguno de los dos.
        """
        self._tamano = tamano
        self._solape = solape

    def trocear(self, texto: str) -> list[str]:
        """Devuelve los trozos de un texto.

        Se acumulan párrafos hasta llegar al tamaño objetivo. Un párrafo más
        largo que el tamaño se parte por frases, y una frase descomunal (una
        tabla volcada sin puntos) se parte a pelo.

        Args:
            texto: texto completo.

        Returns:
            Lista de trozos, sin vacíos.
        """
        piezas: list[str] = []
        for parrafo in re.split(r"\n\s*\n|\f", texto):
            parrafo = re.sub(r"[ \t]+", " ", parrafo).strip()
            if not parrafo:
                continue
            if len(parrafo) <= self._tamano:
                piezas.append(parrafo)
            else:
                piezas += self._partir(parrafo)

        trozos, actual = [], ""
        for pieza in piezas:
            if actual and len(actual) + len(pieza) + 1 > self._tamano:
                trozos.append(actual)
                # El solape arranca en un límite de palabra para no empezar
                # el siguiente trozo con media palabra.
                cola = actual[-self._solape :]
                actual = cola[cola.find(" ") + 1 :] if " " in cola else ""
            actual = f"{actual}\n{pieza}" if actual else pieza
        if actual.strip():
            trozos.append(actual)
        return trozos

    def _partir(self, parrafo: str) -> list[str]:
        """Parte un párrafo largo por frases y, si hace falta, a pelo."""
        partes, actual = [], ""
        for frase in re.split(r"(?<=[.!?;:])\s+", parrafo):
            while len(frase) > self._tamano:
                partes.append(frase[: self._tamano])
                frase = frase[self._tamano :]
            if actual and len(actual) + len(frase) + 1 > self._tamano:
                partes.append(actual)
                actual = frase
            else:
                actual = f"{actual} {frase}" if actual else frase
        if actual:
            partes.append(actual)
        return partes
