"""Pruebas de la fase 2: planificar, ejecutar y deshacer la centralización.

Todas trabajan sobre un disco de juguete en una carpeta temporal y comprueban
el estado real de los ficheros, no solo lo que dice el registro.
"""

import os
from pathlib import Path

import pytest
from conftest import escribir

from orakulue.aplicacion.deshacedor import Deshacedor
from orakulue.aplicacion.ejecutor_centralizacion import EjecutorCentralizacion, ErrorCentralizacion
from orakulue.aplicacion.inventariador import Inventariador
from orakulue.aplicacion.planificador_centralizacion import PlanificadorCentralizacion
from orakulue.dominio.operacion import TipoOperacion
from orakulue.infraestructura.almacen_inventario import AlmacenInventario
from orakulue.infraestructura.calculador_huellas import CalculadorHuellas
from orakulue.infraestructura.configuracion_centralizacion import ConfiguracionCentralizacion
from orakulue.infraestructura.explorador_disco import ExploradorDisco
from orakulue.infraestructura.registro_operaciones import RegistroOperaciones


@pytest.fixture
def disco(configuracion, tmp_path):
    """Disco de juguete con un duplicado, un único y un documento en zona viva."""
    casa = configuracion.raices[0]
    escribir(casa / "formakuntza" / "errekurtsoak" / "Python" / "manual.pdf", b"manual")
    escribir(casa / "Descargas" / "manual (1).pdf", b"manual")
    escribir(casa / "Descargas" / "unico.pdf", b"unico")
    escribir(casa / "formakuntza" / "errekurtsoak" / "en_Elaboracion" / "curso.pdf", b"vivo")
    escribir(casa / "Descargas" / "copia_del_vivo.pdf", b"vivo")
    centralizacion = ConfiguracionCentralizacion(
        carpeta_fondo=casa / "formakuntza" / "fondo",
        carpeta_retirados=tmp_path / "retirados",
        zonas_vivas=(casa / "formakuntza" / "errekurtsoak" / "en_Elaboracion",),
        correspondencias=(
            (casa / "formakuntza" / "errekurtsoak", ""),
            (casa / "Descargas", "descargas"),
        ),
        destino_por_defecto="otros",
        personal=casa,
    )
    with AlmacenInventario(configuracion.base_datos) as almacen:
        Inventariador(ExploradorDisco(configuracion), CalculadorHuellas(), almacen).ejecutar()
        documentos = list(almacen.documentos())
    plan = PlanificadorCentralizacion(centralizacion, list(configuracion.prioridad_original)).planificar(documentos)
    return casa, centralizacion, plan


def instantanea(raiz: Path) -> dict[str, tuple[str, bytes | str]]:
    """Estado de un árbol: por ruta, si es fichero (con contenido) o enlace (con destino)."""
    estado = {}
    for actual, _carpetas, ficheros in os.walk(raiz):
        for nombre in ficheros:
            ruta = Path(actual) / nombre
            estado[str(ruta.relative_to(raiz))] = (
                ("enlace", str(ruta.readlink())) if ruta.is_symlink() else ("fichero", ruta.read_bytes())
            )
    return estado


def test_el_plan_mueve_el_original_retira_la_copia_y_respeta_la_zona_viva(disco):
    casa, centralizacion, plan = disco
    fondo = centralizacion.carpeta_fondo

    movidos = {o.origen.name: o.destino for o in plan.operaciones if o.tipo is TipoOperacion.MOVER}
    retirados = [o.origen.name for o in plan.operaciones if o.tipo is TipoOperacion.RETIRAR]

    assert movidos["manual.pdf"] == fondo / "Python" / "manual.pdf"
    assert movidos["unico.pdf"] == fondo / "descargas" / "unico.pdf"
    # La copia fuera de la zona viva va al fondo; la de la zona viva se queda.
    assert movidos["copia_del_vivo.pdf"] == fondo / "descargas" / "copia_del_vivo.pdf"
    assert retirados == ["manual (1).pdf"]
    assert plan.en_zona_viva == [casa / "formakuntza" / "errekurtsoak" / "en_Elaboracion" / "curso.pdf"]
    assert len(plan.duplicados_con_zona_viva) == 1


def test_ejecutar_deja_enlaces_que_leen_lo_mismo_y_no_borra_nada(disco, configuracion):
    casa, centralizacion, plan = disco
    with RegistroOperaciones(configuracion.base_datos) as registro:
        EjecutorCentralizacion(registro, CalculadorHuellas()).ejecutar(plan, "prueba")

    copia = casa / "Descargas" / "manual (1).pdf"
    assert copia.is_symlink() and copia.read_bytes() == b"manual"
    assert (casa / "formakuntza" / "errekurtsoak" / "Python" / "manual.pdf").is_symlink()
    assert (centralizacion.carpeta_fondo / "Python" / "manual.pdf").read_bytes() == b"manual"
    # La copia sobrante está apartada, no borrada.
    assert (centralizacion.carpeta_retirados / "Descargas" / "manual (1).pdf").read_bytes() == b"manual"
    # La zona viva no se ha tocado.
    vivo = casa / "formakuntza" / "errekurtsoak" / "en_Elaboracion" / "curso.pdf"
    assert not vivo.is_symlink() and vivo.read_bytes() == b"vivo"


def test_deshacer_devuelve_el_disco_exactamente_a_como_estaba(disco, configuracion):
    casa, centralizacion, plan = disco
    antes = instantanea(casa)
    with RegistroOperaciones(configuracion.base_datos) as registro:
        lote = EjecutorCentralizacion(registro, CalculadorHuellas()).ejecutar(plan, "prueba")
        assert instantanea(casa) != antes
        revertidas, avisos = Deshacedor(registro).deshacer(lote)

    assert avisos == []
    assert revertidas == len(plan.operaciones)
    assert instantanea(casa) == antes


def test_si_un_fichero_cambio_tras_el_inventario_se_detiene_y_se_puede_deshacer(disco, configuracion):
    casa, _centralizacion, plan = disco
    antes = instantanea(casa)
    cambiado = casa / "Descargas" / "unico.pdf"
    cambiado.write_bytes(b"unico, pero editado")

    with RegistroOperaciones(configuracion.base_datos) as registro:
        with pytest.raises(ErrorCentralizacion) as error:
            EjecutorCentralizacion(registro, CalculadorHuellas()).ejecutar(plan, "prueba")
        assert "ha cambiado desde el inventario" in str(error.value)
        assert cambiado.read_bytes() == b"unico, pero editado"
        Deshacedor(registro).deshacer(error.value.lote)

    antes["Descargas/unico.pdf"] = ("fichero", b"unico, pero editado")
    assert instantanea(casa) == antes


def test_una_copia_editada_no_se_retira(disco, configuracion):
    casa, _centralizacion, plan = disco
    copia = casa / "Descargas" / "manual (1).pdf"
    # Mismo tamaño y misma fecha que en el inventario, contenido distinto:
    # solo la huella lo delata.
    datos = copia.stat()
    copia.write_bytes(b"MANUAL")
    os.utime(copia, ns=(datos.st_atime_ns, datos.st_mtime_ns))

    with RegistroOperaciones(configuracion.base_datos) as registro:
        with pytest.raises(ErrorCentralizacion) as error:
            EjecutorCentralizacion(registro, CalculadorHuellas()).ejecutar(plan, "prueba")
    assert "ya no coincide" in str(error.value)
    assert not copia.is_symlink() and copia.read_bytes() == b"MANUAL"


def test_dos_documentos_distintos_con_el_mismo_destino_no_se_pisan(configuracion, tmp_path):
    casa = configuracion.raices[0]
    escribir(casa / "a" / "x.pdf", b"uno")
    escribir(casa / "b" / "x.pdf", b"dos")
    centralizacion = ConfiguracionCentralizacion(
        carpeta_fondo=casa / "fondo",
        carpeta_retirados=tmp_path / "retirados",
        zonas_vivas=(),
        # Las dos carpetas van a la misma subcarpeta del fondo.
        correspondencias=((casa / "a", "juntos"), (casa / "b", "juntos")),
        destino_por_defecto="otros",
        personal=casa,
    )
    with AlmacenInventario(configuracion.base_datos) as almacen:
        Inventariador(ExploradorDisco(configuracion), CalculadorHuellas(), almacen).ejecutar()
        plan = PlanificadorCentralizacion(centralizacion, []).planificar(list(almacen.documentos()))

    destinos = sorted(o.destino.name for o in plan.operaciones if o.tipo is TipoOperacion.MOVER)
    assert destinos == ["x (2).pdf", "x.pdf"]
    assert len(plan.renombrados) == 1


def test_solo_enlazar_deja_el_original_en_su_sitio_y_enlaza_las_copias(configuracion, tmp_path):
    casa = configuracion.raices[0]
    escribir(casa / "lana" / "cliente" / "contrato.pdf", b"contrato")
    escribir(casa / "lana" / "cliente" / "copia" / "contrato.pdf", b"contrato")
    escribir(casa / "lana" / "cliente" / "material.pdf", b"material")
    escribir(casa / "formakuntza" / "material.pdf", b"material")
    escribir(casa / "lana" / "unico.pdf", b"unico")
    centralizacion = ConfiguracionCentralizacion(
        carpeta_fondo=casa / "formakuntza" / "fondo",
        carpeta_retirados=tmp_path / "retirados",
        zonas_vivas=(),
        correspondencias=((casa / "formakuntza", ""),),
        destino_por_defecto="otros",
        personal=casa,
        carpetas_al_fondo=(casa / "formakuntza",),
    )
    with AlmacenInventario(configuracion.base_datos) as almacen:
        Inventariador(ExploradorDisco(configuracion), CalculadorHuellas(), almacen).ejecutar()
        plan = PlanificadorCentralizacion(centralizacion, []).planificar(list(almacen.documentos()))
    with RegistroOperaciones(configuracion.base_datos) as registro:
        EjecutorCentralizacion(registro, CalculadorHuellas()).ejecutar(plan, "prueba")

    # Lo que solo está fuera del fondo se queda en su sitio.
    assert not (casa / "lana" / "unico.pdf").is_symlink()
    original = casa / "lana" / "cliente" / "contrato.pdf"
    assert not original.is_symlink()
    copia = casa / "lana" / "cliente" / "copia" / "contrato.pdf"
    assert copia.is_symlink() and copia.readlink() == original
    # Si hay copia en una carpeta que va al fondo, el original es esa y va al fondo.
    material = casa / "lana" / "cliente" / "material.pdf"
    assert material.readlink() == centralizacion.carpeta_fondo / "material.pdf"
    assert sorted(p.name for p in plan.en_su_sitio) == ["contrato.pdf", "unico.pdf"]
