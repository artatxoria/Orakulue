"""Configuración de Orakulue, leída de un fichero TOML.

Centraliza la interpretación del fichero para que el resto del programa reciba
rutas absolutas ya resueltas y no tenga que saber nada de TOML ni de ``~``.
"""

import glob
import tomllib
from dataclasses import dataclass
from pathlib import Path


class ErrorConfiguracion(Exception):
    """El fichero de configuración falta o tiene un valor no válido."""


@dataclass(frozen=True)
class Configuracion:
    """Parámetros de trabajo, con todas las rutas ya absolutas.

    Atributos:
        raices: carpetas desde las que se busca.
        extensiones: extensiones aceptadas, en minúsculas y sin punto.
        tamano_minimo: tamaño mínimo en bytes para inventariar un fichero.
        nombres_excluidos: nombres de carpeta que se saltan donde estén.
        rutas_excluidas: árboles completos que se saltan. En el fichero admiten
            comodines (``*``, ``**``), que se expanden al leerlo.
        excluir_ocultas: si se saltan las carpetas que empiezan por punto.
        excluir_repositorios_git: si se saltan las carpetas con ``.git``.
        excluir_carpetas_syncthing: si se saltan las carpetas con ``.stfolder``.
        carpetas_piezas_latex: nombres de carpeta (``Pictures``, ``images``…)
            que se saltan cuando están junto a un ``.tex``.
        prioridad_original: rutas preferidas para el original de un duplicado.
        base_datos: fichero SQLite del inventario.
        carpeta_informes: carpeta donde se escriben los informes.
        excepciones: carpetas que se recorren aunque estén dentro de una ruta
            excluida (p. ej. ``Resueltos`` dentro de una carpeta de entregas).
    """

    raices: tuple[Path, ...]
    extensiones: frozenset[str]
    tamano_minimo: int
    nombres_excluidos: frozenset[str]
    rutas_excluidas: tuple[Path, ...]
    excluir_ocultas: bool
    excluir_repositorios_git: bool
    excluir_carpetas_syncthing: bool
    carpetas_piezas_latex: frozenset[str]
    prioridad_original: tuple[Path, ...]
    base_datos: Path
    carpeta_informes: Path
    excepciones: tuple[Path, ...] = ()

    @classmethod
    def desde_fichero(cls, ruta_fichero: Path, raiz_proyecto: Path) -> "Configuracion":
        """Lee y valida un fichero de configuración.

        Args:
            ruta_fichero: fichero TOML.
            raiz_proyecto: carpeta desde la que se resuelven las rutas
                relativas de la sección ``[rutas]``.

        Returns:
            La configuración ya interpretada.

        Raises:
            ErrorConfiguracion: si el fichero no existe, no es TOML válido o le
                falta alguna clave obligatoria.
        """
        if not ruta_fichero.is_file():
            raise ErrorConfiguracion(
                f"No existe el fichero de configuración {ruta_fichero}. "
                "Copia configuracion/orakulue.ejemplo.toml a configuracion/orakulue.toml."
            )
        try:
            with ruta_fichero.open("rb") as fichero:
                datos = tomllib.load(fichero)
        except tomllib.TOMLDecodeError as error:
            raise ErrorConfiguracion(f"{ruta_fichero} no es TOML válido: {error}") from error

        try:
            inventario = datos["inventario"]
            duplicados = datos.get("duplicados", {})
            rutas = datos["rutas"]
            return cls(
                raices=tuple(cls._absoluta(r) for r in inventario["raices"]),
                extensiones=frozenset(e.lower().lstrip(".") for e in inventario["extensiones"]),
                tamano_minimo=int(inventario.get("tamano_minimo", 1)),
                nombres_excluidos=frozenset(inventario.get("nombres_excluidos", [])),
                rutas_excluidas=cls._expandir(inventario.get("rutas_excluidas", [])),
                excluir_ocultas=bool(inventario.get("excluir_ocultas", True)),
                excluir_repositorios_git=bool(inventario.get("excluir_repositorios_git", True)),
                excluir_carpetas_syncthing=bool(inventario.get("excluir_carpetas_syncthing", True)),
                carpetas_piezas_latex=frozenset(inventario.get("carpetas_piezas_latex", [])),
                prioridad_original=tuple(
                    cls._absoluta(r) for r in duplicados.get("prioridad_original", [])
                ),
                base_datos=cls._absoluta(rutas["base_datos"], raiz_proyecto),
                carpeta_informes=cls._absoluta(rutas["informes"], raiz_proyecto),
                excepciones=tuple(cls._absoluta(r) for r in inventario.get("excepciones", [])),
            )
        except KeyError as error:
            raise ErrorConfiguracion(
                f"Falta la clave {error} en {ruta_fichero}."
            ) from error

    @classmethod
    def _expandir(cls, rutas: list[str]) -> tuple[Path, ...]:
        """Convierte en absolutas las rutas excluidas, expandiendo comodines.

        Los comodines evitan escribir en la configuración una línea por alumno
        o por grupo (``.../producto */Grupo *``). Una ruta sin comodines se
        conserva aunque no exista todavía; una con comodines solo aporta las
        carpetas que existen en el momento de leer el fichero.

        Args:
            rutas: rutas tal como aparecen en el TOML.

        Returns:
            Rutas absolutas, sin repetir y en orden.
        """
        resultado: list[Path] = []
        for ruta in rutas:
            if glob.has_magic(ruta):
                patron = str(Path(ruta).expanduser())
                resultado += sorted(
                    Path(r).absolute() for r in glob.glob(patron, recursive=True)
                    if Path(r).is_dir()
                )
            else:
                resultado.append(cls._absoluta(ruta))
        return tuple(dict.fromkeys(resultado))

    @staticmethod
    def _absoluta(ruta: str, base: Path | None = None) -> Path:
        """Convierte una ruta del fichero en absoluta.

        Args:
            ruta: ruta tal como aparece en el TOML, con ``~`` opcional.
            base: carpeta para resolver rutas relativas; si es ``None`` se
                usa el directorio de trabajo.

        Returns:
            Ruta absoluta normalizada. No se resuelven enlaces simbólicos: la
            ruta debe compararse con las que da el explorador, que tampoco los
            sigue.
        """
        expandida = Path(ruta).expanduser()
        if not expandida.is_absolute() and base is not None:
            expandida = base / expandida
        return expandida.absolute()
