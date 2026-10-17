"""Caso de uso: ejecutar un plan de centralización con todas las comprobaciones.

Es el único módulo, junto con ``Deshacedor``, que modifica el disco. Nunca
borra: los documentos se mueven y las copias sobrantes se apartan a la carpeta
de retirados.
"""

import errno
import os
from collections.abc import Callable
from pathlib import Path

from orakulue.dominio.operacion import Operacion, TipoOperacion
from orakulue.dominio.plan_centralizacion import PlanCentralizacion
from orakulue.infraestructura.calculador_huellas import CalculadorHuellas
from orakulue.infraestructura.registro_operaciones import RegistroOperaciones


class ErrorCentralizacion(Exception):
    """Una comprobación ha fallado y la ejecución se ha detenido.

    Atributos:
        lote: lote afectado, para poder deshacerlo.
    """

    def __init__(self, mensaje: str, lote: int) -> None:
        """Crea el error.

        Args:
            mensaje: explicación en castellano.
            lote: lote en el que ha ocurrido.
        """
        super().__init__(mensaje)
        self.lote = lote


class EjecutorCentralizacion:
    """Ejecuta un plan operación a operación, registrando cada paso.

    Ante la primera comprobación que falle se detiene: es preferible un lote a
    medias, que se puede deshacer, a seguir sobre un disco que no es el que se
    planificó.
    """

    def __init__(
        self,
        registro: RegistroOperaciones,
        calculador: CalculadorHuellas,
        avisar_avance: Callable[[int, int], None] | None = None,
    ) -> None:
        """Prepara el ejecutor.

        Args:
            registro: donde se anota cada operación.
            calculador: para comprobar huellas antes de retirar una copia.
            avisar_avance: función opcional que recibe (hechas, total).
        """
        self._registro = registro
        self._calculador = calculador
        self._avisar_avance = avisar_avance

    def ejecutar(self, plan: PlanCentralizacion, descripcion: str) -> int:
        """Ejecuta el plan completo.

        Args:
            plan: plan calculado por ``PlanificadorCentralizacion``.
            descripcion: texto para reconocer el lote.

        Returns:
            Identificador del lote.

        Raises:
            ErrorCentralizacion: si alguna comprobación falla. Las operaciones
                anteriores quedan hechas y registradas.
        """
        lote = self._registro.nuevo_lote(descripcion, plan.operaciones)
        registradas = self._registro.operaciones(lote)
        for numero, registrada in enumerate(registradas, start=1):
            try:
                self._aplicar(registrada.operacion)
            except (OSError, ValueError) as error:
                mensaje = self._explicar(registrada.operacion, error)
                self._registro.marcar(registrada.id, RegistroOperaciones.FALLIDA, mensaje)
                raise ErrorCentralizacion(
                    f"{mensaje}\nSe han hecho {numero - 1} de {len(registradas)} operaciones "
                    f"del lote {lote}. Para volver atrás: orakulue deshacer --lote {lote}",
                    lote,
                ) from error
            self._registro.marcar(registrada.id, RegistroOperaciones.HECHA)
            if self._avisar_avance and numero % 500 == 0:
                self._avisar_avance(numero, len(registradas))
        return lote

    def _aplicar(self, operacion: Operacion) -> None:
        """Comprueba y aplica una operación.

        Args:
            operacion: la operación.

        Raises:
            ValueError: si una comprobación previa falla.
            OSError: si el sistema rechaza la operación.
        """
        if operacion.tipo is TipoOperacion.ENLAZAR:
            self._enlazar(operacion)
            return
        self._comprobar_sin_cambios(operacion)
        if operacion.tipo is TipoOperacion.RETIRAR:
            # Solo se aparta una copia si su contenido es de verdad el del
            # original: si alguien la editó, el enlace mostraría otra cosa.
            if self._calculador.calcular(operacion.origen) != operacion.huella:
                raise ValueError("su contenido ya no coincide con el del original")
        self._mover(operacion.origen, operacion.destino)

    @staticmethod
    def _comprobar_sin_cambios(operacion: Operacion) -> None:
        """Comprueba que el fichero sigue siendo el que se inventarió.

        Args:
            operacion: MOVER o RETIRAR.

        Raises:
            ValueError: si no existe, es un enlace o ha cambiado.
        """
        origen = operacion.origen
        if origen.is_symlink() or not origen.is_file():
            raise ValueError("ya no es un fichero normal (¿se movió o se borró?)")
        datos = origen.lstat()
        if datos.st_size != operacion.tamano or datos.st_mtime_ns != operacion.modificado_ns:
            raise ValueError("ha cambiado desde el inventario")

    @staticmethod
    def _mover(origen: Path, destino: Path) -> None:
        """Mueve un fichero sin sobrescribir nada.

        Se usa ``os.rename``, que en el mismo disco es instantáneo y atómico.
        Si el destino estuviera en otro disco fallaría con ``EXDEV``, y eso es
        lo que se quiere: una copia entre discos no es atómica y no se hace.

        Args:
            origen: fichero que se mueve.
            destino: ruta nueva.

        Raises:
            ValueError: si el destino ya existe.
            OSError: si el sistema rechaza el movimiento.
        """
        if destino.exists() or destino.is_symlink():
            raise ValueError(f"el destino {destino} ya existe")
        destino.parent.mkdir(parents=True, exist_ok=True)
        os.rename(origen, destino)

    @staticmethod
    def _enlazar(operacion: Operacion) -> None:
        """Crea el enlace simbólico en el sitio que quedó libre.

        El enlace es absoluto: si alguien mueve la carpeta que contiene el
        enlace, sigue apuntando al mismo documento del fondo.

        Args:
            operacion: ENLAZAR.

        Raises:
            ValueError: si el sitio está ocupado o el destino no existe.
        """
        if operacion.origen.exists() or operacion.origen.is_symlink():
            raise ValueError("el sitio del enlace está ocupado")
        if not operacion.destino.is_file():
            raise ValueError(f"el documento del fondo {operacion.destino} no existe")
        operacion.origen.symlink_to(operacion.destino)

    @staticmethod
    def _explicar(operacion: Operacion, error: Exception) -> str:
        """Redacta en castellano por qué se ha detenido la ejecución.

        Args:
            operacion: operación que ha fallado.
            error: excepción recibida.

        Returns:
            Mensaje para la persona usuaria.
        """
        if isinstance(error, OSError) and error.errno == errno.EXDEV:
            causa = "el destino está en otro disco y no se copian ficheros entre discos"
        elif isinstance(error, OSError):
            causa = error.strerror or str(error)
        else:
            causa = str(error)
        return f"No se ha podido {operacion.tipo.value} «{operacion.origen}»: {causa}."
