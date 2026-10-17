"""Caso de uso: calcular qué haría la centralización, sin tocar el disco.

El plan resultante es lo que se enseña en el simulacro y lo que después se
ejecuta, así que lo que se revisa es exactamente lo que se hará.
"""

from collections import defaultdict
from pathlib import Path

from orakulue.dominio.documento import Documento
from orakulue.dominio.grupo_duplicados import GrupoDuplicados
from orakulue.dominio.operacion import Operacion, TipoOperacion
from orakulue.dominio.plan_centralizacion import PlanCentralizacion
from orakulue.infraestructura.configuracion_centralizacion import ConfiguracionCentralizacion


class PlanificadorCentralizacion:
    """Convierte el inventario en un plan de operaciones."""

    def __init__(
        self, configuracion: ConfiguracionCentralizacion, prioridad_original: list[Path]
    ) -> None:
        """Prepara el planificador.

        Args:
            configuracion: fondo, zonas vivas y correspondencias.
            prioridad_original: rutas preferidas para el original de un grupo.
        """
        self._configuracion = configuracion
        self._prioridad = list(prioridad_original)

    def planificar(self, documentos: list[Documento]) -> PlanCentralizacion:
        """Calcula el plan completo.

        Para cada contenido distinto (cada huella):

        - lo que está en zonas vivas se queda como está;
        - del resto se elige un original, preferentemente entre las copias que
          pueden ir al fondo; si lo hay, se mueve al fondo y deja un enlace en
          su sitio; si todas están en zonas de «solo enlazar», el original se
          queda donde está;
        - las demás copias se retiran (no se borran) y en su sitio queda un
          enlace al original.

        Los documentos sin huella (ilegibles) no se tocan.

        Args:
            documentos: todo el inventario.

        Returns:
            El plan, con sus operaciones en orden de ejecución.
        """
        plan = PlanCentralizacion()
        reservados: set[Path] = set()
        por_huella: dict[str, list[Documento]] = defaultdict(list)
        for documento in documentos:
            if documento.huella is not None:
                por_huella[documento.huella].append(documento)

        for huella in sorted(por_huella):
            grupo = sorted(por_huella[huella], key=lambda d: str(d.ruta))
            vivos = [d for d in grupo if self._configuracion.en_zona_viva(d.ruta)]
            movibles = [d for d in grupo if d not in vivos]
            plan.en_zona_viva += [d.ruta for d in vivos]
            if not movibles:
                continue

            al_fondo = [d for d in movibles if self._configuracion.va_al_fondo(d.ruta)]
            if al_fondo:
                original = self._elegir_original(al_fondo)
                if vivos:
                    plan.duplicados_con_zona_viva.append(original.ruta)
                destino = self._destino_original(original, reservados, plan)
                self._operaciones_del_original(original, destino, plan)
            else:
                # Solo enlazar: el original se queda donde está y las copias
                # apuntan a él.
                original = self._elegir_original(movibles)
                destino = original.ruta
                plan.en_su_sitio.append(original.ruta)
            for copia in movibles:
                if copia is not original:
                    self._operaciones_de_copia(copia, destino, reservados, plan)
        return plan

    def _elegir_original(self, documentos: list[Documento]) -> Documento:
        """Elige el original entre las copias que se pueden mover.

        Args:
            documentos: copias con la misma huella, fuera de zonas vivas.

        Returns:
            El documento que irá al fondo.
        """
        if len(documentos) == 1:
            return documentos[0]
        grupo = GrupoDuplicados(documentos[0].huella, documentos[0].tamano, tuple(documentos))
        return grupo.elegir_original(self._prioridad)

    def _destino_original(
        self, original: Documento, reservados: set[Path], plan: PlanCentralizacion
    ) -> Path:
        """Calcula el sitio del original en el fondo, evitando choques.

        Args:
            original: documento que va al fondo.
            reservados: destinos ya asignados en este plan.
            plan: donde se anotan los renombrados.

        Returns:
            Ruta definitiva en el fondo.
        """
        previsto = self._configuracion.destino_en_fondo(original.ruta)
        if previsto == original.ruta:
            # Ya está en el fondo: no se mueve.
            reservados.add(previsto)
            return previsto
        definitivo = self._libre(previsto, reservados)
        if definitivo != previsto:
            plan.renombrados.append((previsto, definitivo))
        return definitivo

    def _operaciones_del_original(
        self, original: Documento, destino: Path, plan: PlanCentralizacion
    ) -> None:
        """Añade al plan el traslado del original y el enlace en su sitio.

        Args:
            original: documento que va al fondo.
            destino: su ruta en el fondo.
            plan: plan que se completa.
        """
        if destino == original.ruta:
            plan.ya_en_fondo += 1
            return
        plan.operaciones.append(self._operacion(TipoOperacion.MOVER, original, original.ruta, destino))
        plan.operaciones.append(self._operacion(TipoOperacion.ENLAZAR, original, original.ruta, destino))

    def _operaciones_de_copia(
        self, copia: Documento, destino: Path, reservados: set[Path], plan: PlanCentralizacion
    ) -> None:
        """Añade al plan la retirada de una copia y su enlace al original.

        Args:
            copia: copia sobrante.
            destino: ruta del original en el fondo.
            reservados: destinos ya asignados en este plan.
            plan: plan que se completa.
        """
        configuracion = self._configuracion
        if copia.ruta.is_relative_to(configuracion.personal):
            relativa = copia.ruta.relative_to(configuracion.personal)
        else:
            relativa = copia.ruta.relative_to(copia.ruta.anchor)
        retirada = self._libre(configuracion.carpeta_retirados / relativa, reservados)
        plan.operaciones.append(self._operacion(TipoOperacion.RETIRAR, copia, copia.ruta, retirada))
        plan.operaciones.append(self._operacion(TipoOperacion.ENLAZAR, copia, copia.ruta, destino))

    @staticmethod
    def _libre(ruta: Path, reservados: set[Path]) -> Path:
        """Devuelve una ruta no usada, añadiendo « (2)», « (3)»… si hace falta.

        Se comprueba tanto el disco como lo ya reservado en el plan: dos
        documentos distintos podrían caer en el mismo sitio del fondo si
        venían de carpetas que se agrupan juntas.

        Args:
            ruta: ruta deseada.
            reservados: rutas ya asignadas; se añade la elegida.

        Returns:
            Ruta libre.
        """
        candidata, numero = ruta, 2
        while candidata in reservados or candidata.exists() or candidata.is_symlink():
            candidata = ruta.with_name(f"{ruta.stem} ({numero}){ruta.suffix}")
            numero += 1
        reservados.add(candidata)
        return candidata

    @staticmethod
    def _operacion(tipo: TipoOperacion, documento: Documento, origen: Path, destino: Path) -> Operacion:
        """Crea una operación con los datos de control del documento."""
        return Operacion(tipo, origen, destino, documento.huella, documento.tamano, documento.modificado_ns)
