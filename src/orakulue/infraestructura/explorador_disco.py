"""Recorrido del disco en busca de documentos.

Decide qué carpetas se recorren y qué ficheros cuentan como documentación. No
lee contenidos: solo nombres y metadatos, para que sea rápido.
"""

import os
from collections.abc import Iterator
from pathlib import Path

from orakulue.dominio.carpeta_omitida import CarpetaOmitida, MotivoOmision
from orakulue.dominio.documento import Documento
from orakulue.infraestructura.configuracion import Configuracion


class ExploradorDisco:
    """Encuentra documentos bajo las raíces configuradas.

    Las carpetas saltadas se van guardando en ``carpetas_omitidas`` para que el
    informe pueda decir qué se ha dejado fuera y por qué.
    """

    def __init__(self, configuracion: Configuracion) -> None:
        """Prepara el explorador.

        Args:
            configuracion: criterios de inclusión y exclusión.
        """
        self._configuracion = configuracion
        self.carpetas_omitidas: list[CarpetaOmitida] = []

    def recorrer(self) -> Iterator[Documento]:
        """Recorre las raíces y produce los documentos encontrados, sin huella.

        Los enlaces simbólicos no se siguen ni se inventarían: tras la fase 2
        las copias serán enlaces al fondo, y contarlas otra vez falsearía el
        inventario. Una raíz repetida o contenida en otra no produce
        documentos duplicados.

        Yields:
            Un ``Documento`` por cada fichero regular aceptado.
        """
        self.carpetas_omitidas = []
        vistas: set[Path] = set()
        for raiz in self._configuracion.raices:
            for actual, subcarpetas, ficheros in os.walk(
                raiz, topdown=True, onerror=self._anotar_error, followlinks=False
            ):
                carpeta = Path(actual)
                if carpeta in vistas:
                    subcarpetas.clear()
                    continue
                vistas.add(carpeta)
                # Podar en el sitio: os.walk solo baja a lo que quede en la lista.
                subcarpetas[:] = [
                    nombre for nombre in sorted(subcarpetas)
                    if self._se_recorre(carpeta / nombre)
                ]
                for nombre in sorted(ficheros):
                    documento = self._como_documento(carpeta / nombre)
                    if documento is not None:
                        yield documento

    def _se_recorre(self, carpeta: Path) -> bool:
        """Decide si se baja a una carpeta y, si no, anota el motivo.

        Args:
            carpeta: ruta absoluta de la subcarpeta.

        Returns:
            ``True`` si debe recorrerse.
        """
        motivo = self._motivo_omision(carpeta)
        if motivo is None:
            return True
        self.carpetas_omitidas.append(CarpetaOmitida(carpeta, motivo))
        return False

    def _motivo_omision(self, carpeta: Path) -> MotivoOmision | None:
        """Devuelve por qué se salta una carpeta, o ``None`` si no se salta.

        Args:
            carpeta: ruta absoluta.

        Returns:
            El motivo de omisión, o ``None``.
        """
        configuracion = self._configuracion
        if carpeta.is_symlink():
            # No es una omisión que interese contar: os.walk tampoco la seguiría.
            return None
        if self._esta_excluida(carpeta):
            return MotivoOmision.RUTA_EXCLUIDA
        if carpeta.name in configuracion.nombres_excluidos:
            return MotivoOmision.NOMBRE_EXCLUIDO
        if configuracion.excluir_ocultas and carpeta.name.startswith("."):
            return MotivoOmision.OCULTA
        if configuracion.excluir_repositorios_git and (carpeta / ".git").exists():
            return MotivoOmision.REPOSITORIO_GIT
        if configuracion.excluir_carpetas_syncthing and (carpeta / ".stfolder").exists():
            return MotivoOmision.SYNCTHING
        if carpeta.name in configuracion.carpetas_piezas_latex and self._contiene_tex(carpeta.parent):
            return MotivoOmision.PIEZAS_LATEX
        return None

    def _esta_excluida(self, carpeta: Path) -> bool:
        """Indica si una carpeta cae dentro de una ruta excluida sin excepción.

        Una excepción gana a la exclusión que la contiene: así una carpeta de
        entregas de alumnos se salta entera salvo su subcarpeta de soluciones.
        Para que el explorador llegue hasta la excepción, las carpetas que la
        contienen tampoco se saltan; sus ficheros sueltos sí se descartan
        (``_como_documento``).

        Args:
            carpeta: ruta absoluta.

        Returns:
            ``True`` si debe saltarse.
        """
        configuracion = self._configuracion
        if any(carpeta.is_relative_to(e) for e in configuracion.excepciones):
            return False
        if not any(carpeta.is_relative_to(r) for r in configuracion.rutas_excluidas):
            return False
        # Contiene una excepción más abajo: hay que bajar para alcanzarla.
        return not any(e.is_relative_to(carpeta) for e in configuracion.excepciones)

    def _solo_de_paso(self, carpeta: Path) -> bool:
        """Indica si se recorre una carpeta excluida solo para llegar a una excepción.

        Args:
            carpeta: ruta absoluta.

        Returns:
            ``True`` si está dentro de una ruta excluida y no dentro de una
            excepción; sus ficheros no deben inventariarse.
        """
        configuracion = self._configuracion
        return (
            any(carpeta.is_relative_to(r) for r in configuracion.rutas_excluidas)
            and not any(carpeta.is_relative_to(e) for e in configuracion.excepciones)
        )

    @staticmethod
    def _contiene_tex(carpeta: Path) -> bool:
        """Indica si una carpeta tiene algún ``.tex`` directamente dentro.

        Sirve para reconocer las carpetas de piezas de un proyecto LaTeX
        (``Pictures`` junto a ``main.tex``): sus PDF son portadas, cabeceras de
        capítulo y figuras repetidas a propósito en cada curso. Llevarlas al
        fondo mezclaría piezas de compilación con material de consulta.

        No se salta el proyecto entero: una carpeta con un ``.tex`` suelto en
        su raíz puede contener cientos de documentos de verdad, como ocurre
        con ``en_Elaboracion``.

        Args:
            carpeta: ruta absoluta.

        Returns:
            ``True`` si contiene al menos un fichero ``.tex``; ``False`` también
            si no se puede leer (ya lo anotará ``os.walk``).
        """
        try:
            with os.scandir(carpeta) as entradas:
                return any(
                    e.name.lower().endswith(".tex") and e.is_file(follow_symlinks=False)
                    for e in entradas
                )
        except OSError:
            return False

    def _como_documento(self, ruta: Path) -> Documento | None:
        """Convierte un fichero en ``Documento`` si cumple los criterios.

        Args:
            ruta: ruta absoluta del fichero.

        Returns:
            El documento, o ``None`` si es un enlace, no tiene una extensión
            aceptada, es demasiado pequeño o no se puede consultar.
        """
        extension = ruta.suffix.lower().lstrip(".")
        if extension not in self._configuracion.extensiones:
            return None
        if self._esta_excluida(ruta.parent) or self._solo_de_paso(ruta.parent):
            return None
        try:
            datos = ruta.lstat()
        except OSError:
            return None
        # lstat + comprobación de tipo: descarta enlaces, tuberías y dispositivos.
        if not os.path.isfile(ruta) or ruta.is_symlink():
            return None
        if datos.st_size < self._configuracion.tamano_minimo:
            return None
        return Documento(ruta, datos.st_size, datos.st_mtime_ns)

    def _anotar_error(self, error: OSError) -> None:
        """Registra una carpeta que no se pudo abrir.

        Args:
            error: excepción que ``os.walk`` entrega en lugar de lanzarla.
        """
        if error.filename:
            self.carpetas_omitidas.append(
                CarpetaOmitida(Path(error.filename), MotivoOmision.SIN_PERMISO)
            )
