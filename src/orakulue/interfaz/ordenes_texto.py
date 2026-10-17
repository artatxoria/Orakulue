"""Órdenes de la fase 3: ``extraer`` y ``analizar``.

Las dos son de solo lectura respecto a los documentos: el texto y los
resultados se guardan en ``datos/``.
"""

from datetime import datetime
from pathlib import Path

from orakulue.aplicacion.detector_casi_duplicados import DetectorCasiDuplicados
from orakulue.aplicacion.detector_datos_personales import DetectorDatosPersonales
from orakulue.aplicacion.extraccion_textos import ExtraccionTextos
from orakulue.dominio.texto_extraido import EstadoExtraccion
from orakulue.infraestructura.almacen_analisis import AlmacenAnalisis
from orakulue.infraestructura.almacen_inventario import AlmacenInventario
from orakulue.infraestructura.almacen_textos import AlmacenTextos
from orakulue.infraestructura.configuracion import Configuracion
from orakulue.interfaz.informe_texto import InformeTexto
from orakulue.utilidades.formato import Formato


class OrdenesTexto:
    """Ejecuta las órdenes de extracción y análisis de texto."""

    def __init__(self, configuracion: Configuracion) -> None:
        """Prepara las órdenes.

        Los textos se guardan en ``textos/`` junto a la base de datos, que ya
        está fuera de git por contener información privada.

        Args:
            configuracion: configuración completa.
        """
        self._configuracion = configuracion
        self._carpeta_textos = configuracion.base_datos.parent / "textos"

    def extraer(self) -> int:
        """Extrae el texto de los contenidos que aún no lo tienen y analiza.

        Returns:
            Código de salida (siempre 0: un documento ilegible no es un fallo
            de la orden).
        """
        with AlmacenInventario(self._configuracion.base_datos) as inventario:
            documentos = list(inventario.documentos())
        with AlmacenTextos(self._configuracion.base_datos, self._carpeta_textos) as textos:
            resumen = ExtraccionTextos(
                textos,
                avisar_avance=lambda n, t: print(f"  … {Formato.cifra(n)} de {Formato.cifra(t)}", flush=True),
            ).ejecutar(documentos)
        detalle = ", ".join(f"{Formato.cifra(n)} {e.value}" for e, n in resumen.por_estado.items())
        print(f"Extracción: {Formato.cifra(resumen.pendientes)} contenidos nuevos ({detalle or 'ninguno'}).")
        return self.analizar()

    def analizar(self) -> int:
        """Detecta casi duplicados y datos personales y escribe el informe.

        Returns:
            Código de salida (siempre 0).
        """
        with AlmacenInventario(self._configuracion.base_datos) as inventario:
            rutas: dict[str, list[Path]] = {}
            for documento in inventario.documentos():
                if documento.huella:
                    rutas.setdefault(documento.huella, []).append(documento.ruta)
        with AlmacenTextos(self._configuracion.base_datos, self._carpeta_textos) as textos:
            # Solo cuenta lo que sigue en el inventario: un contenido que ya
            # no está en el disco no interesa.
            metadatos = [m for m in textos.metadatos() if m[0] in rutas]
            correctos = [m[0] for m in metadatos if m[1] is EstadoExtraccion.CORRECTA]
            grupos = DetectorCasiDuplicados().detectar((h, textos.leer(h)) for h in correctos)
            detector = DetectorDatosPersonales()
            marcas = [detector.analizar(h, textos.leer(h)) for h in correctos]
        with AlmacenAnalisis(self._configuracion.base_datos) as analisis:
            analisis.sustituir(marcas, grupos)

        sello = datetime.now().strftime("%Y%m%d-%H%M")
        ruta = self._configuracion.carpeta_informes / f"texto-{sello}.md"
        InformeTexto(metadatos, rutas, grupos, marcas, Path.home()).escribir(ruta)
        excluidos = sum(1 for m in marcas if m.excluir_de_fichas)
        print(
            f"Análisis: {Formato.cifra(len(grupos))} grupos de casi duplicados, "
            f"{Formato.cifra(excluidos)} documentos con datos personales (excluidos de la fase 4).\n"
            f"Informe: {ruta}"
        )
        return 0
