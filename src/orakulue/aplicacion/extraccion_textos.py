"""Caso de uso: extraer el texto de cada contenido distinto del inventario.

Solo lee los documentos. El texto se guarda aparte, en ``datos/textos``.
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from orakulue.dominio.documento import Documento
from orakulue.dominio.texto_extraido import EstadoExtraccion, TextoExtraido
from orakulue.infraestructura.almacen_textos import AlmacenTextos
from orakulue.infraestructura.extractores.extractor_texto import ErrorExtraccion
from orakulue.infraestructura.extractores.selector_extractores import SelectorExtractores
from orakulue.utilidades.detector_idioma import DetectorIdioma


@dataclass
class ResumenExtraccion:
    """Cifras de una pasada de extracción. Solo la usa ``ExtraccionTextos``.

    Atributos:
        pendientes: contenidos que había que extraer en esta pasada.
        por_estado: número de resultados de cada estado.
    """

    pendientes: int = 0
    por_estado: dict[EstadoExtraccion, int] = field(default_factory=dict)


class ExtraccionTextos:
    """Extrae en paralelo el texto de los contenidos que aún no lo tienen.

    Es incremental por huella: un contenido ya extraído no se vuelve a leer,
    esté donde esté y se llame como se llame.
    """

    #: Por debajo de estos caracteres se considera que no hay texto. Un PDF
    #: escaneado suele dar solo saltos de página y algún número suelto.
    MINIMO_CARACTERES = 200
    #: Hilos simultáneos. Los extractores pasan casi todo el tiempo esperando
    #: a ``pdftotext`` o al disco, así que los hilos sí aceleran.
    HILOS = 8

    def __init__(
        self,
        almacen: AlmacenTextos,
        selector: SelectorExtractores | None = None,
        detector_idioma: DetectorIdioma | None = None,
        avisar_avance: Callable[[int, int], None] | None = None,
    ) -> None:
        """Prepara la extracción.

        Args:
            almacen: donde se guardan los textos.
            selector: elige el extractor de cada documento.
            detector_idioma: decide el idioma de cada texto.
            avisar_avance: función opcional que recibe (hechos, total).
        """
        self._almacen = almacen
        self._selector = selector or SelectorExtractores()
        self._idioma = detector_idioma or DetectorIdioma()
        self._avisar_avance = avisar_avance

    def ejecutar(self, documentos: list[Documento]) -> ResumenExtraccion:
        """Extrae el texto de los contenidos nuevos.

        Args:
            documentos: inventario completo; se toma una ruta por huella.

        Returns:
            Resumen de la pasada.
        """
        ya_hechas = self._almacen.huellas_extraidas()
        por_huella: dict[str, Path] = {}
        for documento in sorted(documentos, key=lambda d: str(d.ruta)):
            if documento.huella and documento.huella not in ya_hechas:
                por_huella.setdefault(documento.huella, documento.ruta)

        resumen = ResumenExtraccion(pendientes=len(por_huella))
        with ThreadPoolExecutor(max_workers=self.HILOS) as hilos:
            resultados = hilos.map(lambda par: self._extraer(*par), por_huella.items())
            # Se guarda desde el hilo principal: SQLite no admite que varios
            # hilos escriban por la misma conexión.
            for numero, texto in enumerate(resultados, start=1):
                self._almacen.guardar(texto)
                resumen.por_estado[texto.estado] = resumen.por_estado.get(texto.estado, 0) + 1
                if numero % 100 == 0:
                    self._almacen.confirmar()
                    if self._avisar_avance:
                        self._avisar_avance(numero, resumen.pendientes)
        self._almacen.confirmar()
        return resumen

    def _extraer(self, huella: str, ruta: Path) -> TextoExtraido:
        """Extrae el texto de un documento y lo clasifica.

        Args:
            huella: huella del contenido.
            ruta: una de sus rutas.

        Returns:
            Resultado de la extracción (nunca lanza excepciones: un documento
            ilegible no detiene la pasada).
        """
        extractor = self._selector.para(ruta)
        if extractor is None:
            return TextoExtraido(huella, EstadoExtraccion.ERROR, "", "-", mensaje="formato sin extractor")
        try:
            texto = extractor.extraer(ruta)
        except ErrorExtraccion as error:
            return TextoExtraido(huella, EstadoExtraccion.ERROR, "", extractor.nombre, mensaje=str(error))
        except Exception as error:  # noqa: BLE001 — un fichero raro no debe parar la pasada
            return TextoExtraido(
                huella, EstadoExtraccion.ERROR, "", extractor.nombre, mensaje=f"error inesperado: {error}"
            )
        if len(texto.strip()) < self.MINIMO_CARACTERES:
            return TextoExtraido(huella, EstadoExtraccion.SIN_TEXTO, texto, extractor.nombre)
        return TextoExtraido(
            huella, EstadoExtraccion.CORRECTA, texto, extractor.nombre, self._idioma.detectar(texto)
        )
