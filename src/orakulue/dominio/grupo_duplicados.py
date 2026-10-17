"""Entidad GrupoDuplicados: varios ficheros con exactamente el mismo contenido."""

from dataclasses import dataclass
from pathlib import Path

from orakulue.dominio.documento import Documento


@dataclass(frozen=True)
class GrupoDuplicados:
    """Conjunto de documentos que comparten huella, y por tanto contenido.

    Atributos:
        huella: huella SHA-256 común.
        tamano: tamaño en bytes de cada copia.
        documentos: las copias, al menos dos.
    """

    huella: str
    tamano: int
    documentos: tuple[Documento, ...]

    def __post_init__(self) -> None:
        """Comprueba que el grupo tiene sentido.

        Raises:
            ValueError: si hay menos de dos documentos o alguno no comparte la
                huella del grupo.
        """
        if len(self.documentos) < 2:
            raise ValueError("Un grupo de duplicados necesita al menos dos documentos.")
        if any(d.huella != self.huella for d in self.documentos):
            raise ValueError("Todos los documentos del grupo deben compartir huella.")

    @property
    def copias_sobrantes(self) -> int:
        """Número de copias que sobran si se conserva una sola."""
        return len(self.documentos) - 1

    @property
    def espacio_recuperable(self) -> int:
        """Bytes que se liberarían dejando una copia y enlazando el resto."""
        return self.copias_sobrantes * self.tamano

    def elegir_original(self, prioridades: list[Path]) -> Documento:
        """Propone qué copia debe considerarse el original.

        Criterio, por este orden:

        1. La copia que esté dentro de la ruta de ``prioridades`` que aparezca
           antes en la lista: si ya hay una copia en el fondo o en los recursos
           de formación, ese es su sitio natural y no hace falta moverla.
        2. La ruta menos profunda: suele ser la carpeta donde se guardó a
           propósito, frente a copias enterradas en subcarpetas de proyectos.
        3. La modificación más antigua: la primera descarga.
        4. La ruta alfabéticamente menor, para que la elección sea estable.

        Args:
            prioridades: rutas absolutas ordenadas de más a menos preferente.

        Returns:
            El documento propuesto como original.
        """

        def rango_prioridad(documento: Documento) -> int:
            for posicion, raiz in enumerate(prioridades):
                if documento.ruta.is_relative_to(raiz):
                    return posicion
            return len(prioridades)

        return min(
            self.documentos,
            key=lambda d: (
                rango_prioridad(d),
                len(d.ruta.parts),
                d.modificado_ns,
                str(d.ruta),
            ),
        )
