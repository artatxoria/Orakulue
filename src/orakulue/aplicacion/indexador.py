"""Caso de uso: crear y mantener al día el índice del buscador.

Incremental por huella, como el resto de Orakulue: solo se indexa lo nuevo o lo
cambiado, y se quita lo que ya no está en el inventario. Todo es local: los
vectores se calculan en el PC de sobremesa con Ollama.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from orakulue.dominio.documento import Documento
from orakulue.dominio.texto_extraido import EstadoExtraccion
from orakulue.infraestructura.almacen_indice import AlmacenIndice
from orakulue.infraestructura.almacen_textos import AlmacenTextos
from orakulue.infraestructura.cliente_vectores import ClienteVectores
from orakulue.utilidades.troceador import Troceador


@dataclass
class ResumenIndexacion:
    """Lo hecho en una pasada. Solo la usa ``Indexador``.

    Atributos:
        documentos: documentos cuyo texto se ha indexado.
        trozos: trozos de texto indexados.
        fichas: fichas indexadas.
        olvidados: contenidos quitados del índice.
    """

    documentos: int = 0
    trozos: int = 0
    fichas: int = 0
    olvidados: int = 0


class Indexador:
    """Trocea, calcula vectores y guarda en el índice."""

    #: Caracteres de texto que se indexan como máximo por documento. Cabe un
    #: libro largo entero; lo demás suele ser repetición o anexos.
    MAXIMO_TEXTO = 300_000
    #: En las hojas de cálculo, mucho menos: más allá son filas de datos que
    #: solo meten ruido en la búsqueda.
    MAXIMO_HOJAS = 20_000
    _HOJAS = (".xls", ".xlsx", ".ods")

    def __init__(
        self,
        indice: AlmacenIndice,
        vectores: ClienteVectores,
        troceador: Troceador | None = None,
        avisar_avance: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Prepara el indexador.

        Args:
            indice: almacén del índice.
            vectores: cliente de vectores.
            troceador: troceador de textos.
            avisar_avance: función opcional (qué, hechos, total).
        """
        self._indice = indice
        self._vectores = vectores
        self._troceador = troceador or Troceador()
        self._avisar = avisar_avance

    def ejecutar(
        self,
        documentos: list[Documento],
        textos: AlmacenTextos,
        fichas: dict[str, tuple[dict, str, Path]],
    ) -> ResumenIndexacion:
        """Pone el índice al día.

        Args:
            documentos: inventario completo.
            textos: almacén de textos.
            fichas: fichas con sus datos (huella → (datos, momento, ruta)).

        Returns:
            Resumen de la pasada.

        Raises:
            ErrorVectores: si Ollama no está disponible.
        """
        resumen = ResumenIndexacion()
        rutas: dict[str, Path] = {}
        for documento in sorted(documentos, key=lambda d: str(d.ruta)):
            if documento.huella:
                rutas.setdefault(documento.huella, documento.ruta)
        legibles = {
            h for h, estado, *_ in textos.metadatos() if estado is EstadoExtraccion.CORRECTA and h in rutas
        }

        ya_trozos = self._indice.indexados("trozo")
        ya_fichas = self._indice.indexados("ficha")
        sobran = (set(ya_trozos) - legibles) | (set(ya_fichas) - set(fichas))
        if sobran:
            self._indice.olvidar(sobran)
            resumen.olvidados = len(sobran)

        pendientes = sorted(legibles - set(ya_trozos))
        for numero, huella in enumerate(pendientes, start=1):
            limite = self.MAXIMO_HOJAS if rutas[huella].suffix.lower() in self._HOJAS else self.MAXIMO_TEXTO
            trozos = self._troceador.trocear(textos.leer(huella)[:limite])
            if trozos:
                self._indice.sustituir(huella, "trozo", "1", trozos, self._vectores.vectores(trozos))
                resumen.documentos += 1
                resumen.trozos += len(trozos)
            if self._avisar and numero % 50 == 0:
                self._avisar("textos", numero, len(pendientes))

        cambiadas = [h for h, (_, momento, _) in fichas.items() if ya_fichas.get(h) != momento]
        for numero, huella in enumerate(sorted(cambiadas), start=1):
            datos, momento, _ = fichas[huella]
            texto = self.texto_ficha(datos)
            self._indice.sustituir(huella, "ficha", momento, [texto], self._vectores.vectores([texto]))
            resumen.fichas += 1
            if self._avisar and numero % 200 == 0:
                self._avisar("fichas", numero, len(cambiadas))
        return resumen

    @staticmethod
    def texto_ficha(datos: dict) -> str:
        """Texto con el que se indexa una ficha.

        Se juntan los campos que describen el contenido (no los de
        organización, como el nivel o la vigencia), para que la ficha se
        parezca a las preguntas que se le harán.
        """
        partes = [datos["titulo"], datos["tema"], ", ".join(datos["temas"]), datos["resumen"]]
        partes += [t["concepto"] for t in datos["teoria"]]
        partes += [f"Ejercicio: {e['descripcion']} ({e['practica']})" for e in datos["ejercicios"]]
        partes += [f"Idea de curso: {c['titulo']}. {c['aprendizaje']}" for c in datos["ideas_curso"]]
        partes += [f"Idea de píldora: {p['titulo']}. {p['objetivo']}" for p in datos["ideas_pildora"]]
        return "\n".join(p for p in partes if p)
