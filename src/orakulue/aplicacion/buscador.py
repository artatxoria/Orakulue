"""Caso de uso: buscar en el fondo por palabras, por significado o por ambos.

La búsqueda es local: no sale nada del PC de sobremesa ni cuesta nada.
"""

from collections import defaultdict
from dataclasses import dataclass

from orakulue.dominio.info_documento import InfoDocumento
from orakulue.infraestructura.almacen_indice import AlmacenIndice
from orakulue.infraestructura.cliente_vectores import ClienteVectores


@dataclass(frozen=True)
class ResultadoBusqueda:
    """Un documento encontrado. Solo la usa ``Buscador``.

    Atributos:
        info: datos del documento.
        puntuacion: puntuación de la fusión (mayor es mejor; solo sirve para
            ordenar).
        pasaje: el trozo de texto que mejor casa con la consulta.
        piezas: identificadores de las piezas del documento que han salido,
            de mejor a peor (para elegir pasajes al responder).
    """

    info: InfoDocumento
    puntuacion: float
    pasaje: str
    piezas: tuple[int, ...]


class Buscador:
    """Búsqueda híbrida con fusión por rango recíproco."""

    MODOS = ("hibrido", "palabras", "significado")
    #: Candidatos que aporta cada buscador antes de fusionar.
    CANDIDATOS = 200
    #: Constante de la fusión por rango recíproco. 60 es el valor del
    #: artículo original y funciona bien sin ajustar: suaviza la ventaja de
    #: los primeros puestos para que un documento que sale en los dos
    #: buscadores gane a uno que sale muy arriba en uno solo.
    K_RRF = 60
    #: Piezas que suman a la puntuación de un documento. Con más, un libro
    #: largo con muchos trozos tibios ganaría a un apunte corto que da justo
    #: en la diana.
    PIEZAS_POR_DOCUMENTO = 2
    #: Peso de una ficha frente a un trozo. La ficha resume el documento
    #: entero y casa mejor con preguntas generales («qué tengo de…»). Medido
    #: con el juego de preguntas de prueba: con peso 2 el acierto en los diez
    #: primeros pasó del 82 % al 91 %, y la mejora se mantenía con otros
    #: valores de K y de piezas por documento.
    PESO_FICHA = 2.0

    def __init__(self, indice: AlmacenIndice, vectores: ClienteVectores, catalogo: dict[str, InfoDocumento]) -> None:
        """Prepara el buscador.

        Args:
            indice: almacén del índice.
            vectores: cliente de vectores (para la consulta).
            catalogo: información de presentación por huella.
        """
        self._indice = indice
        self._vectores = vectores
        self._catalogo = catalogo

    def buscar(self, consulta: str, cantidad: int = 10, modo: str = "hibrido") -> list[ResultadoBusqueda]:
        """Busca documentos.

        Args:
            consulta: pregunta o palabras, en lenguaje natural.
            cantidad: documentos que se devuelven.
            modo: ``hibrido``, ``palabras`` o ``significado``.

        Returns:
            Documentos de mejor a peor.

        Raises:
            ValueError: si el modo no existe.
            ErrorVectores: si hace falta Ollama y no responde.
        """
        if modo not in self.MODOS:
            raise ValueError(f"modo de búsqueda desconocido: {modo}")
        rankings = []
        if modo in ("hibrido", "palabras"):
            rankings.append(self._indice.por_palabras(consulta, self.CANDIDATOS))
        if modo in ("hibrido", "significado"):
            vector = self._vectores.vectores([consulta])[0]
            rankings.append(self._indice.por_significado(vector, self.CANDIDATOS))

        puntos: dict[int, float] = defaultdict(float)
        for ranking in rankings:
            for posicion, pieza in enumerate(ranking, start=1):
                puntos[pieza] += 1 / (self.K_RRF + posicion)
        datos = self._indice.piezas(list(puntos))

        por_documento: dict[str, list[tuple[float, int]]] = defaultdict(list)
        for pieza, valor in puntos.items():
            if pieza in datos and datos[pieza][0] in self._catalogo:
                peso = self.PESO_FICHA if datos[pieza][1] == "ficha" else 1.0
                por_documento[datos[pieza][0]].append((valor * peso, pieza))

        resultados = []
        for huella, lista in por_documento.items():
            lista.sort(reverse=True)
            puntuacion = sum(v for v, _ in lista[: self.PIEZAS_POR_DOCUMENTO])
            # El pasaje es el mejor trozo de texto; si solo ha salido la
            # ficha, se muestra el principio de la ficha.
            trozos = [p for _, p in lista if datos[p][1] == "trozo"]
            pasaje = datos[trozos[0]][3] if trozos else datos[lista[0][1]][3]
            resultados.append(ResultadoBusqueda(
                self._catalogo[huella], puntuacion, pasaje, tuple(p for _, p in lista)
            ))
        resultados.sort(key=lambda r: (-r.puntuacion, r.info.huella))
        return resultados[:cantidad]

    def texto_pieza(self, pieza: int) -> tuple[str, str]:
        """Tipo y texto de una pieza (para componer respuestas)."""
        huella, tipo, _orden, texto = self._indice.piezas([pieza])[pieza]
        return tipo, texto
