"""Utilidades comunes de las pruebas: un disco de juguete y su configuración."""

from pathlib import Path

import pytest

from orakulue.infraestructura.configuracion import Configuracion


def escribir(ruta: Path, contenido: bytes) -> Path:
    """Crea un fichero con su carpeta y devuelve la ruta."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(contenido)
    return ruta


@pytest.fixture
def configuracion(tmp_path: Path) -> Configuracion:
    """Configuración que recorre ``tmp_path/casa`` con exclusiones típicas."""
    casa = tmp_path / "casa"
    casa.mkdir()
    return Configuracion(
        raices=(casa,),
        extensiones=frozenset({"pdf", "docx"}),
        tamano_minimo=1,
        nombres_excluidos=frozenset({"node_modules"}),
        rutas_excluidas=(casa / "privado",),
        excluir_ocultas=True,
        excluir_repositorios_git=True,
        excluir_carpetas_syncthing=True,
        carpetas_piezas_latex=frozenset({"Pictures"}),
        prioridad_original=(casa / "formakuntza",),
        base_datos=tmp_path / "datos" / "inventario.sqlite",
        carpeta_informes=tmp_path / "datos" / "informes",
    )
