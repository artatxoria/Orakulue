"""Caso de uso: inventariar el disco y calcular las huellas de los documentos.

Solo lee. No mueve, no renombra y no borra nada del disco.
"""

from collections.abc import Callable

from orakulue.dominio.resumen_inventario import ResumenInventario
from orakulue.infraestructura.almacen_inventario import AlmacenInventario
from orakulue.infraestructura.calculador_huellas import CalculadorHuellas
from orakulue.infraestructura.explorador_disco import ExploradorDisco


class Inventariador:
    """Recorre el disco, calcula huellas y actualiza el almacén.

    Las pasadas son incrementales: un documento cuyo tamaño y fecha de
    modificación no han cambiado conserva la huella anterior sin volver a
    leerse. La primera pasada lee todo; las siguientes, casi nada.
    """

    # Cada cuántos documentos se confirma la base de datos y se informa del
    # avance. Si la pasada se interrumpe, se pierde como mucho este trabajo.
    CADA_CUANTOS = 250

    def __init__(
        self,
        explorador: ExploradorDisco,
        calculador: CalculadorHuellas,
        almacen: AlmacenInventario,
        avisar_avance: Callable[[ResumenInventario], None] | None = None,
    ) -> None:
        """Prepara el inventariador.

        Args:
            explorador: encuentra los documentos.
            calculador: calcula las huellas.
            almacen: guarda el inventario.
            avisar_avance: función opcional a la que se llama periódicamente
                con el resumen parcial, para mostrar el progreso.
        """
        self._explorador = explorador
        self._calculador = calculador
        self._almacen = almacen
        self._avisar_avance = avisar_avance

    def ejecutar(self) -> ResumenInventario:
        """Hace una pasada completa de inventario.

        Un fichero ilegible no detiene la pasada: se anota en el resumen y se
        guarda sin huella, para que no figure en ningún grupo de duplicados.

        Returns:
            Resumen con las cifras de la pasada.
        """
        resumen = ResumenInventario()
        pasada = self._almacen.iniciar_pasada()

        for documento in self._explorador.recorrer():
            resumen.encontrados += 1
            anterior = self._almacen.obtener(documento.ruta)
            if anterior and anterior.huella and anterior.sin_cambios_respecto_a(documento):
                documento = anterior
                resumen.huellas_reutilizadas += 1
            else:
                try:
                    documento = documento.con_huella(self._calculador.calcular(documento.ruta))
                    resumen.huellas_calculadas += 1
                    resumen.bytes_leidos += documento.tamano
                except OSError as error:
                    resumen.errores.append((documento.ruta, error.strerror or str(error)))
            self._almacen.guardar(documento, pasada)

            if resumen.encontrados % self.CADA_CUANTOS == 0:
                self._almacen.confirmar()
                if self._avisar_avance:
                    self._avisar_avance(resumen)

        resumen.desaparecidos = self._almacen.cerrar_pasada(pasada)
        resumen.carpetas_omitidas = list(self._explorador.carpetas_omitidas)
        return resumen
