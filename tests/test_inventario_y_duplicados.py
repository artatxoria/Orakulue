"""Pruebas del flujo completo: inventariar, detectar duplicados e informar."""

import os

from conftest import escribir

from orakulue.aplicacion.detector_duplicados import DetectorDuplicados
from orakulue.aplicacion.inventariador import Inventariador
from orakulue.infraestructura.almacen_inventario import AlmacenInventario
from orakulue.infraestructura.calculador_huellas import CalculadorHuellas
from orakulue.infraestructura.explorador_disco import ExploradorDisco
from orakulue.interfaz.exportador_csv_duplicados import ExportadorCsvDuplicados
from orakulue.interfaz.informe_duplicados import InformeDuplicados


class CalculadorQueCuenta(CalculadorHuellas):
    """Calculador que anota qué ficheros lee, para comprobar el reaprovechamiento."""

    def __init__(self):
        self.leidos = []

    def calcular(self, ruta):
        self.leidos.append(ruta)
        return super().calcular(ruta)


def inventariar(configuracion, calculador=None):
    """Hace una pasada y devuelve el resumen."""
    with AlmacenInventario(configuracion.base_datos) as almacen:
        return Inventariador(
            ExploradorDisco(configuracion), calculador or CalculadorHuellas(), almacen
        ).ejecutar()


def test_detecta_duplicados_aunque_tengan_nombres_distintos(configuracion):
    casa = configuracion.raices[0]
    escribir(casa / "Descargas" / "manual (1).pdf", b"mismo contenido")
    escribir(casa / "formakuntza" / "Python" / "manual_python.pdf", b"mismo contenido")
    escribir(casa / "otro.pdf", b"contenido distinto")

    inventariar(configuracion)
    with AlmacenInventario(configuracion.base_datos) as almacen:
        detector = DetectorDuplicados(almacen, list(configuracion.prioridad_original))
        grupos = detector.detectar()

        assert len(grupos) == 1
        assert grupos[0].copias_sobrantes == 1
        assert grupos[0].espacio_recuperable == len(b"mismo contenido")
        # El original propuesto es el que ya está en formakuntza.
        assert detector.original_propuesto(grupos[0]).name == "manual_python.pdf"


def test_la_segunda_pasada_no_vuelve_a_leer_lo_que_no_ha_cambiado(configuracion):
    casa = configuracion.raices[0]
    escribir(casa / "a.pdf", b"a")
    b = escribir(casa / "b.pdf", b"b")

    inventariar(configuracion)
    b.write_bytes(b"b modificado")
    os.utime(b, ns=(1, 1))  # fecha distinta garantizada aunque el reloj no avance
    calculador = CalculadorQueCuenta()
    resumen = inventariar(configuracion, calculador)

    assert calculador.leidos == [b]
    assert resumen.huellas_reutilizadas == 1


def test_olvida_los_documentos_que_ya_no_estan(configuracion):
    casa = configuracion.raices[0]
    escribir(casa / "a.pdf", b"x")
    b = escribir(casa / "b.pdf", b"x")

    inventariar(configuracion)
    b.unlink()
    resumen = inventariar(configuracion)

    assert resumen.desaparecidos == 1
    with AlmacenInventario(configuracion.base_datos) as almacen:
        assert almacen.grupos_duplicados() == []


def test_un_fichero_ilegible_no_detiene_la_pasada(configuracion):
    casa = configuracion.raices[0]
    escribir(casa / "bueno.pdf", b"x")
    malo = escribir(casa / "malo.pdf", b"y")
    malo.chmod(0)
    try:
        resumen = inventariar(configuracion)
    finally:
        malo.chmod(0o644)

    if os.geteuid() != 0:  # root lee aunque no haya permiso
        assert [r for r, _ in resumen.errores] == [malo]
    assert resumen.encontrados == 2


def test_el_informe_y_el_csv_se_escriben_y_marcan_el_original(configuracion):
    casa = configuracion.raices[0]
    escribir(casa / "Descargas" / "copia.pdf", b"igual")
    escribir(casa / "formakuntza" / "original.pdf", b"igual")

    resumen = inventariar(configuracion)
    with AlmacenInventario(configuracion.base_datos) as almacen:
        detector = DetectorDuplicados(almacen, list(configuracion.prioridad_original))
        grupos = detector.detectar()
        ruta_md = configuracion.carpeta_informes / "informe.md"
        ruta_csv = configuracion.carpeta_informes / "informe.csv"
        InformeDuplicados(
            list(almacen.documentos()), grupos, detector, resumen, casa, ruta_csv.name
        ).escribir(ruta_md)
        ExportadorCsvDuplicados(grupos, detector).escribir(ruta_csv)

    informe = ruta_md.read_text(encoding="utf-8")
    assert "★ `~/formakuntza/original.pdf`" in informe
    assert "no ha movido, renombrado ni borrado nada" in informe
    filas = ruta_csv.read_text(encoding="utf-8-sig").splitlines()
    assert filas[0] == "grupo;propuesta;ruta;nombre;tamano_bytes;huella"
    assert sum(";original;" in f for f in filas) == 1
