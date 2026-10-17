"""Línea de órdenes de Orakulue.

Órdenes disponibles:

- ``inventariar``: recorre el disco, calcula huellas y escribe el informe.
- ``informe``: vuelve a escribir el informe con el inventario guardado, sin
  recorrer el disco (útil tras cambiar las prioridades del original).
- ``centralizar``: simulacro de la fase 2; con ``--ejecutar``, la aplica.
- ``deshacer --lote N``: revierte un lote de centralización.
- ``lotes``: lista los lotes ejecutados.
- ``extraer``: extrae el texto de cada contenido y lo analiza (fase 3).
- ``analizar``: repite el análisis de casi duplicados y datos personales.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from orakulue.aplicacion.detector_duplicados import DetectorDuplicados
from orakulue.aplicacion.inventariador import Inventariador
from orakulue.dominio.resumen_inventario import ResumenInventario
from orakulue.infraestructura.almacen_inventario import AlmacenInventario
from orakulue.infraestructura.calculador_huellas import CalculadorHuellas
from orakulue.infraestructura.configuracion import Configuracion, ErrorConfiguracion
from orakulue.infraestructura.explorador_disco import ExploradorDisco
from orakulue.interfaz.exportador_csv_duplicados import ExportadorCsvDuplicados
from orakulue.interfaz.informe_duplicados import InformeDuplicados
from orakulue.interfaz.ordenes_centralizacion import OrdenesCentralizacion
from orakulue.interfaz.ordenes_texto import OrdenesTexto
from orakulue.utilidades.formato import Formato

# Raíz del proyecto: tres niveles por encima de este fichero (src/orakulue/interfaz).
RAIZ_PROYECTO = Path(__file__).resolve().parents[3]


class LineaOrdenes:
    """Interpreta los argumentos y ejecuta la orden pedida."""

    def __init__(self) -> None:
        """Define las órdenes y sus opciones."""
        self._analizador = argparse.ArgumentParser(
            prog="orakulue",
            description="Inventario y deduplicación del fondo documental de formación.",
        )
        self._analizador.add_argument(
            "--config",
            type=Path,
            default=RAIZ_PROYECTO / "configuracion" / "orakulue.toml",
            help="fichero de configuración (por defecto configuracion/orakulue.toml)",
        )
        ordenes = self._analizador.add_subparsers(dest="orden", required=True)
        ordenes.add_parser("inventariar", help="recorre el disco y escribe el informe")
        ordenes.add_parser("informe", help="escribe el informe con el inventario guardado")
        centralizar = ordenes.add_parser(
            "centralizar", help="simulacro de centralización en el fondo (no toca nada)"
        )
        centralizar.add_argument(
            "--ejecutar", action="store_true", help="aplica el plan de verdad"
        )
        deshacer = ordenes.add_parser("deshacer", help="revierte un lote de centralización")
        deshacer.add_argument("--lote", type=int, required=True, help="número de lote")
        ordenes.add_parser("lotes", help="lista los lotes de centralización")
        ordenes.add_parser("extraer", help="extrae el texto de los documentos y lo analiza")
        ordenes.add_parser("analizar", help="busca casi duplicados y datos personales")

    def ejecutar(self, argumentos: list[str]) -> int:
        """Ejecuta la orden indicada.

        Args:
            argumentos: argumentos sin el nombre del programa.

        Returns:
            Código de salida: 0 si todo va bien, 1 si una orden de
            centralización no ha terminado bien, 2 si la configuración es
            incorrecta.
        """
        opciones = self._analizador.parse_args(argumentos)
        try:
            configuracion = Configuracion.desde_fichero(opciones.config, RAIZ_PROYECTO)
        except ErrorConfiguracion as error:
            print(f"Error de configuración: {error}", file=sys.stderr)
            return 2

        if opciones.orden == "extraer":
            return OrdenesTexto(configuracion).extraer()
        if opciones.orden == "analizar":
            return OrdenesTexto(configuracion).analizar()
        if opciones.orden in ("centralizar", "deshacer", "lotes"):
            try:
                centralizacion = OrdenesCentralizacion(configuracion)
            except ValueError as error:
                print(f"Error de configuración: {error}", file=sys.stderr)
                return 2
            if opciones.orden == "centralizar":
                return centralizacion.centralizar(opciones.ejecutar)
            if opciones.orden == "deshacer":
                return centralizacion.deshacer(opciones.lote)
            return centralizacion.lotes()

        with AlmacenInventario(configuracion.base_datos) as almacen:
            resumen = None
            if opciones.orden == "inventariar":
                resumen = self._inventariar(configuracion, almacen)
            self._escribir_informe(configuracion, almacen, resumen)
        return 0

    def _inventariar(
        self, configuracion: Configuracion, almacen: AlmacenInventario
    ) -> ResumenInventario:
        """Hace la pasada de inventario mostrando el avance.

        Args:
            configuracion: criterios de búsqueda.
            almacen: inventario donde se guarda.

        Returns:
            Resumen de la pasada.
        """
        inventariador = Inventariador(
            ExploradorDisco(configuracion),
            CalculadorHuellas(),
            almacen,
            avisar_avance=self._mostrar_avance,
        )
        resumen = inventariador.ejecutar()
        print(
            f"Inventario terminado: {Formato.cifra(resumen.encontrados)} documentos, "
            f"{Formato.cifra(resumen.huellas_calculadas)} leídos "
            f"({Formato.tamano(resumen.bytes_leidos)}), "
            f"{Formato.cifra(resumen.huellas_reutilizadas)} sin cambios, "
            f"{len(resumen.errores)} ilegibles."
        )
        return resumen

    @staticmethod
    def _mostrar_avance(resumen: ResumenInventario) -> None:
        """Muestra en una línea el avance de la pasada."""
        print(
            f"  … {Formato.cifra(resumen.encontrados)} documentos, "
            f"{Formato.tamano(resumen.bytes_leidos)} leídos",
            flush=True,
        )

    @staticmethod
    def _escribir_informe(
        configuracion: Configuracion,
        almacen: AlmacenInventario,
        resumen: ResumenInventario | None,
    ) -> None:
        """Escribe el informe Markdown y el CSV con sello de fecha.

        Args:
            configuracion: dónde se escriben los informes.
            almacen: inventario.
            resumen: resumen de la pasada, si la ha habido.
        """
        detector = DetectorDuplicados(almacen, list(configuracion.prioridad_original))
        grupos = detector.detectar()
        sello = datetime.now().strftime("%Y%m%d-%H%M")
        ruta_md = configuracion.carpeta_informes / f"duplicados-{sello}.md"
        ruta_csv = configuracion.carpeta_informes / f"duplicados-{sello}.csv"

        InformeDuplicados(
            list(almacen.documentos()), grupos, detector, resumen, Path.home(), ruta_csv.name
        ).escribir(ruta_md)
        ExportadorCsvDuplicados(grupos, detector).escribir(ruta_csv)
        print(f"Informe: {ruta_md}\nLista completa: {ruta_csv}")


def principal() -> int:
    """Punto de entrada del programa instalado como ``orakulue``.

    Returns:
        Código de salida.
    """
    return LineaOrdenes().ejecutar(sys.argv[1:])
