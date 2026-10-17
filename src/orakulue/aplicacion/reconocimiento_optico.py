"""Caso de uso: pasar el OCR por los PDF que se quedaron sin texto.

Va aparte de la extracción normal porque es mucho más lento: se lanza a
propósito, sobre lo que lo necesita, y cada documento se intenta una sola vez.
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from orakulue.dominio.documento import Documento
from orakulue.dominio.texto_extraido import EstadoExtraccion, TextoExtraido
from orakulue.infraestructura.almacen_textos import AlmacenTextos
from orakulue.infraestructura.extractores.extractor_ocr import ExtractorOcr
from orakulue.infraestructura.extractores.extractor_texto import ErrorExtraccion
from orakulue.utilidades.detector_idioma import DetectorIdioma


class ReconocimientoOptico:
    """Reconoce el texto de los PDF marcados «sin texto»."""

    #: Mismo criterio que la extracción normal para dar el texto por bueno.
    MINIMO_CARACTERES = 200
    #: Documentos a la vez. Cada Tesseract usa un núcleo; se dejan libres
    #: algunos de los doce del equipo para que siga siendo usable.
    HILOS = 8

    def __init__(
        self,
        almacen: AlmacenTextos,
        extractor: ExtractorOcr | None = None,
        detector_idioma: DetectorIdioma | None = None,
        avisar_avance: Callable[[int, int], None] | None = None,
    ) -> None:
        """Prepara el reconocimiento.

        Args:
            almacen: textos ya extraídos; aquí se guardan los nuevos.
            extractor: lector OCR.
            detector_idioma: decide el idioma del texto reconocido.
            avisar_avance: función opcional que recibe (hechos, total).
        """
        self._almacen = almacen
        self._extractor = extractor or ExtractorOcr()
        self._idioma = detector_idioma or DetectorIdioma()
        self._avisar_avance = avisar_avance

    def pendientes(self, documentos: list[Documento]) -> dict[str, Path]:
        """PDF sin texto que todavía no han pasado por el OCR.

        Args:
            documentos: inventario completo.

        Returns:
            Una ruta por huella pendiente.
        """
        sin_texto = {
            h for h, estado, _, extractor, _, _ in self._almacen.metadatos()
            if estado is EstadoExtraccion.SIN_TEXTO and extractor != self._extractor.nombre
        }
        pendientes: dict[str, Path] = {}
        for documento in sorted(documentos, key=lambda d: str(d.ruta)):
            if documento.huella in sin_texto and documento.ruta.suffix.lower() == ".pdf":
                pendientes.setdefault(documento.huella, documento.ruta)
        return pendientes

    def ejecutar(self, documentos: list[Documento]) -> dict[EstadoExtraccion, int]:
        """Pasa el OCR por todos los pendientes.

        Lo que el OCR tampoco consigue leer se guarda como «sin texto» con el
        extractor OCR anotado, para no volver a intentarlo en cada pasada.

        Args:
            documentos: inventario completo.

        Returns:
            Número de resultados de cada estado.
        """
        pendientes = self.pendientes(documentos)
        cuenta: dict[EstadoExtraccion, int] = {}
        with ThreadPoolExecutor(max_workers=self.HILOS) as hilos:
            resultados = hilos.map(lambda par: self._reconocer(*par), pendientes.items())
            for numero, texto in enumerate(resultados, start=1):
                self._almacen.guardar(texto)
                self._almacen.confirmar()
                cuenta[texto.estado] = cuenta.get(texto.estado, 0) + 1
                if self._avisar_avance and numero % 10 == 0:
                    self._avisar_avance(numero, len(pendientes))
        return cuenta

    def _reconocer(self, huella: str, ruta: Path) -> TextoExtraido:
        """Reconoce un PDF y clasifica el resultado (nunca lanza excepciones)."""
        nombre = self._extractor.nombre
        try:
            texto = self._extractor.extraer(ruta)
        except ErrorExtraccion as error:
            return TextoExtraido(huella, EstadoExtraccion.SIN_TEXTO, "", nombre, mensaje=f"OCR: {error}")
        except Exception as error:  # noqa: BLE001 — un PDF raro no debe parar la pasada
            return TextoExtraido(huella, EstadoExtraccion.SIN_TEXTO, "", nombre, mensaje=f"OCR: {error}")
        if len(texto.strip()) < self.MINIMO_CARACTERES:
            return TextoExtraido(huella, EstadoExtraccion.SIN_TEXTO, texto, nombre, mensaje="OCR sin resultado")
        return TextoExtraido(huella, EstadoExtraccion.CORRECTA, texto, nombre, self._idioma.detectar(texto))
