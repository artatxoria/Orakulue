"""Entidad PlanCentralizacion: todo lo que haría la fase 2, antes de hacerlo."""

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from orakulue.dominio.operacion import Operacion, TipoOperacion


@dataclass
class PlanCentralizacion:
    """Lista ordenada de operaciones y datos para explicarla.

    El orden importa: para cada documento, primero se mueve el original,
    después se enlaza su sitio antiguo y por último se retiran y enlazan sus
    copias. Ejecutarlas en este orden y deshacerlas en el contrario deja
    siempre el disco en un estado coherente.

    Atributos:
        operaciones: pasos en orden de ejecución.
        en_zona_viva: documentos que se quedan donde están por estar en una
            zona de trabajo activo.
        duplicados_con_zona_viva: documentos que se llevan al fondo pero
            tienen una copia idéntica en una zona viva, que se conserva.
        renombrados: destinos que chocaban con otro y se han renombrado,
            como pares (destino previsto, destino final).
        ya_en_fondo: documentos que ya estaban en el fondo.
        en_su_sitio: documentos fuera de ``carpetas_al_fondo`` que se quedan
            donde están (modo «solo enlazar»); si tenían copias, ellos son el
            original al que apuntan los enlaces.
    """

    operaciones: list[Operacion] = field(default_factory=list)
    en_zona_viva: list[Path] = field(default_factory=list)
    duplicados_con_zona_viva: list[Path] = field(default_factory=list)
    renombrados: list[tuple[Path, Path]] = field(default_factory=list)
    ya_en_fondo: int = 0
    en_su_sitio: list[Path] = field(default_factory=list)

    def cuenta(self, tipo: TipoOperacion) -> int:
        """Número de operaciones de un tipo.

        Args:
            tipo: tipo de operación.

        Returns:
            Cuántas hay en el plan.
        """
        return sum(1 for o in self.operaciones if o.tipo is tipo)

    def bytes_de(self, tipo: TipoOperacion) -> int:
        """Bytes afectados por las operaciones de un tipo.

        Args:
            tipo: tipo de operación.

        Returns:
            Suma de tamaños.
        """
        return sum(o.tamano for o in self.operaciones if o.tipo is tipo)

    def por_destino(self, fondo: Path, niveles: int = 1) -> Counter:
        """Cuántos documentos van a cada subcarpeta del fondo.

        Args:
            fondo: carpeta del fondo.
            niveles: profundidad de agrupación.

        Returns:
            Contador de subcarpeta relativa a número de documentos.
        """
        resultado: Counter = Counter()
        for operacion in self.operaciones:
            if operacion.tipo is TipoOperacion.MOVER:
                partes = operacion.destino.relative_to(fondo).parts[:-1][:niveles]
                resultado[Path(*partes) if partes else Path(".")] += 1
        return resultado
