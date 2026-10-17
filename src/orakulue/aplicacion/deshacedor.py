"""Caso de uso: deshacer un lote de centralización.

Recorre las operaciones hechas en orden contrario y aplica la inversa de
cada una. Tras deshacer, el disco vuelve a como estaba: cada documento en su
sitio y sin enlaces.
"""

import os

from orakulue.dominio.operacion import Operacion, TipoOperacion
from orakulue.infraestructura.registro_operaciones import RegistroOperaciones


class Deshacedor:
    """Revierte las operaciones hechas de un lote."""

    def __init__(self, registro: RegistroOperaciones) -> None:
        """Prepara el deshacedor.

        Args:
            registro: registro de operaciones.
        """
        self._registro = registro

    def deshacer(self, lote: int) -> tuple[int, list[str]]:
        """Deshace todo lo que se hizo en un lote.

        Una operación que no se puede revertir (alguien ocupó el sitio, o el
        enlace ya no es el que se creó) no detiene el proceso: se anota y se
        sigue con las demás, porque dejar a medias un deshacer es peor.

        Args:
            lote: identificador del lote.

        Returns:
            Número de operaciones revertidas y avisos de las que no.
        """
        revertidas, avisos = 0, []
        hechas = [r for r in self._registro.operaciones(lote) if r.estado == RegistroOperaciones.HECHA]
        for registrada in reversed(hechas):
            try:
                self._revertir(registrada.operacion)
            except (OSError, ValueError) as error:
                avisos.append(f"{registrada.operacion.origen}: {error}")
                continue
            self._registro.marcar(registrada.id, RegistroOperaciones.DESHECHA)
            revertidas += 1
        return revertidas, avisos

    @staticmethod
    def _revertir(operacion: Operacion) -> None:
        """Aplica la inversa de una operación.

        Args:
            operacion: operación hecha.

        Raises:
            ValueError: si el disco no está como lo dejó la operación.
            OSError: si el sistema rechaza el cambio.
        """
        if operacion.tipo is TipoOperacion.ENLAZAR:
            if not operacion.origen.is_symlink() or operacion.origen.readlink() != operacion.destino:
                raise ValueError("el enlace ya no es el que creó Orakulue; no se toca")
            operacion.origen.unlink()
            return
        # MOVER y RETIRAR: devolver el fichero a su sitio.
        if operacion.origen.exists() or operacion.origen.is_symlink():
            raise ValueError("su sitio original está ocupado")
        if not operacion.destino.is_file():
            raise ValueError(f"no se encuentra en {operacion.destino}")
        operacion.origen.parent.mkdir(parents=True, exist_ok=True)
        os.rename(operacion.destino, operacion.origen)

