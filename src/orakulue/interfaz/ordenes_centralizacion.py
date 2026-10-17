"""Órdenes de la fase 2: ``centralizar``, ``deshacer`` y ``lotes``.

Se separan de ``LineaOrdenes`` porque son las únicas que modifican el disco y
conviene tenerlas juntas y a la vista.
"""

import sys
from datetime import datetime

from orakulue.aplicacion.deshacedor import Deshacedor
from orakulue.aplicacion.ejecutor_centralizacion import EjecutorCentralizacion, ErrorCentralizacion
from orakulue.aplicacion.planificador_centralizacion import PlanificadorCentralizacion
from orakulue.dominio.operacion import TipoOperacion
from orakulue.infraestructura.almacen_inventario import AlmacenInventario
from orakulue.infraestructura.calculador_huellas import CalculadorHuellas
from orakulue.infraestructura.configuracion import Configuracion
from orakulue.infraestructura.registro_operaciones import RegistroOperaciones
from orakulue.interfaz.informe_centralizacion import InformeCentralizacion
from orakulue.utilidades.formato import Formato


class OrdenesCentralizacion:
    """Ejecuta las órdenes de centralización."""

    def __init__(self, configuracion: Configuracion) -> None:
        """Prepara las órdenes.

        Args:
            configuracion: configuración completa; debe tener sección
                ``[centralizacion]``.

        Raises:
            ValueError: si falta la sección ``[centralizacion]``.
        """
        if configuracion.centralizacion is None:
            raise ValueError("La configuración no tiene sección [centralizacion].")
        self._configuracion = configuracion
        self._centralizacion = configuracion.centralizacion

    def centralizar(self, ejecutar: bool) -> int:
        """Calcula el plan, escribe el informe y, si se pide, lo ejecuta.

        Sin ``ejecutar`` es un simulacro: no toca el disco.

        Args:
            ejecutar: si se aplica el plan de verdad.

        Returns:
            Código de salida: 0 si todo va bien, 1 si la ejecución se detuvo.
        """
        with AlmacenInventario(self._configuracion.base_datos) as almacen:
            documentos = list(almacen.documentos())
        plan = PlanificadorCentralizacion(
            self._centralizacion, list(self._configuracion.prioridad_original)
        ).planificar(documentos)

        sello = datetime.now().strftime("%Y%m%d-%H%M")
        tipo = "ejecucion" if ejecutar else "simulacro"
        ruta_md = self._configuracion.carpeta_informes / f"centralizacion-{tipo}-{sello}.md"
        ruta_csv = ruta_md.with_suffix(".csv")
        InformeCentralizacion(plan, self._centralizacion, ruta_csv.name).escribir(ruta_md, ruta_csv)
        print(
            f"{Formato.cifra(plan.cuenta(TipoOperacion.MOVER))} documentos al fondo, "
            f"{Formato.cifra(plan.cuenta(TipoOperacion.RETIRAR))} copias retiradas, "
            f"{Formato.cifra(plan.cuenta(TipoOperacion.ENLAZAR))} enlaces.\n"
            f"Informe: {ruta_md}"
        )
        if not ejecutar:
            print("Simulacro: no se ha tocado nada. Para aplicarlo: orakulue centralizar --ejecutar")
            return 0

        with RegistroOperaciones(self._configuracion.base_datos) as registro:
            ejecutor = EjecutorCentralizacion(
                registro, CalculadorHuellas(),
                avisar_avance=lambda n, t: print(f"  … {Formato.cifra(n)} de {Formato.cifra(t)}", flush=True),
            )
            try:
                lote = ejecutor.ejecutar(plan, f"centralización {sello}")
            except ErrorCentralizacion as error:
                print(f"Ejecución detenida.\n{error}", file=sys.stderr)
                return 1
        print(
            f"Lote {lote} terminado. Ejecuta «orakulue inventariar» para actualizar el "
            f"inventario. Para volver atrás: orakulue deshacer --lote {lote}"
        )
        return 0

    def deshacer(self, lote: int) -> int:
        """Revierte un lote.

        Args:
            lote: identificador del lote.

        Returns:
            0 si se ha revertido todo, 1 si ha quedado algo sin revertir.
        """
        with RegistroOperaciones(self._configuracion.base_datos) as registro:
            revertidas, avisos = Deshacedor(registro).deshacer(lote)
        print(f"Lote {lote}: {Formato.cifra(revertidas)} operaciones revertidas.")
        for aviso in avisos:
            print(f"  No revertida: {aviso}", file=sys.stderr)
        return 1 if avisos else 0

    def lotes(self) -> int:
        """Muestra los lotes ejecutados y el estado de sus operaciones.

        Returns:
            Siempre 0.
        """
        with RegistroOperaciones(self._configuracion.base_datos) as registro:
            lotes = registro.lotes()
        if not lotes:
            print("No hay lotes.")
        for lote, creado, descripcion, estados in lotes:
            resumen = ", ".join(f"{n} {e}" for e, n in sorted(estados.items()))
            print(f"Lote {lote} · {creado} · {descripcion} · {resumen}")
        return 0
