"""Pruebas de GrupoDuplicados: validación y elección del original."""

from pathlib import Path

import pytest

from orakulue.dominio.documento import Documento
from orakulue.dominio.grupo_duplicados import GrupoDuplicados

HUELLA = "a" * 64


def documento(ruta: str, modificado_ns: int = 0) -> Documento:
    return Documento(Path(ruta), 100, modificado_ns, HUELLA)


def test_rechaza_grupos_de_un_solo_documento():
    with pytest.raises(ValueError):
        GrupoDuplicados(HUELLA, 100, (documento("/a.pdf"),))


def test_rechaza_huellas_distintas():
    otro = Documento(Path("/b.pdf"), 100, 0, "b" * 64)
    with pytest.raises(ValueError):
        GrupoDuplicados(HUELLA, 100, (documento("/a.pdf"), otro))


def test_la_prioridad_manda_sobre_la_profundidad():
    grupo = GrupoDuplicados(HUELLA, 100, (
        documento("/casa/Descargas/x.pdf"),
        documento("/casa/formakuntza/a/b/c/x.pdf"),
    ))
    original = grupo.elegir_original([Path("/casa/formakuntza")])
    assert original.ruta == Path("/casa/formakuntza/a/b/c/x.pdf")


def test_sin_prioridad_gana_la_ruta_menos_profunda_y_luego_la_mas_antigua():
    grupo = GrupoDuplicados(HUELLA, 100, (
        documento("/casa/a/b/x.pdf", modificado_ns=1),
        documento("/casa/a/y.pdf", modificado_ns=9),
        documento("/casa/c/z.pdf", modificado_ns=5),
    ))
    assert grupo.elegir_original([]).ruta == Path("/casa/c/z.pdf")
    assert grupo.espacio_recuperable == 200
