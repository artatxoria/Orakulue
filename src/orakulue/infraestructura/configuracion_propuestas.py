"""Parámetros de la fase 7, leídos de la sección ``[propuestas]``."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ConfiguracionPropuestas:
    """Dónde van las propuestas, con qué modelo y contra qué catálogo.

    Atributos:
        carpeta: carpeta de las propuestas en Markdown.
        modelo: modelo que redacta.
        modelos_prueba: modelos que se comparan en la prueba.
        propuestas_prueba: cuántas propuestas entran en la prueba.
        cursos: cursos de la tanda.
        pildoras: píldoras de la tanda.
        esfuerzo: nivel de esfuerzo del modelo.
        catalogos: ficheros de partes de los catálogos actuales.
    """

    carpeta: Path
    modelo: str
    modelos_prueba: tuple[str, ...]
    propuestas_prueba: int
    cursos: int
    pildoras: int
    esfuerzo: str
    catalogos: tuple[Path, ...]

    @classmethod
    def desde_seccion(cls, seccion: dict) -> "ConfiguracionPropuestas":
        """Interpreta la sección, con valores por omisión."""
        return cls(
            carpeta=Path(seccion.get("carpeta", "~/Documentos/formakuntza/propuestas")).expanduser().absolute(),
            modelo=seccion.get("modelo", "claude-sonnet-5-5"),
            modelos_prueba=tuple(seccion.get("modelos_prueba", ["claude-sonnet-5-5", "claude-opus-5-5"])),
            propuestas_prueba=int(seccion.get("propuestas_prueba", 3)),
            cursos=int(seccion.get("cursos", 20)),
            pildoras=int(seccion.get("pildoras", 20)),
            esfuerzo=seccion.get("esfuerzo", "medium"),
            catalogos=tuple(Path(c).expanduser().absolute() for c in seccion.get("catalogos", [])),
        )
