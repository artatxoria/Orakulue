"""Pruebas de ExploradorDisco: qué entra en el inventario y qué se salta."""

from conftest import escribir

from orakulue.dominio.carpeta_omitida import MotivoOmision
from orakulue.infraestructura.explorador_disco import ExploradorDisco


def test_acepta_solo_extensiones_configuradas_sin_distinguir_mayusculas(configuracion):
    casa = configuracion.raices[0]
    escribir(casa / "a.pdf", b"x")
    escribir(casa / "b.PDF", b"x")
    escribir(casa / "c.txt", b"x")

    nombres = {d.ruta.name for d in ExploradorDisco(configuracion).recorrer()}

    assert nombres == {"a.pdf", "b.PDF"}


def test_descarta_ficheros_vacios(configuracion):
    casa = configuracion.raices[0]
    escribir(casa / "vacio.pdf", b"")

    assert list(ExploradorDisco(configuracion).recorrer()) == []


def test_salta_carpetas_excluidas_y_anota_el_motivo(configuracion):
    casa = configuracion.raices[0]
    escribir(casa / "privado" / "x.pdf", b"1")
    escribir(casa / "node_modules" / "x.pdf", b"2")
    escribir(casa / ".oculta" / "x.pdf", b"3")
    escribir(casa / "repo" / ".git" / "HEAD", b"ref")
    escribir(casa / "repo" / "x.pdf", b"4")
    escribir(casa / "tablet" / ".stfolder" / "marca", b"")
    escribir(casa / "tablet" / "x.pdf", b"5")
    escribir(casa / "bueno" / "x.pdf", b"6")

    explorador = ExploradorDisco(configuracion)
    rutas = [d.ruta for d in explorador.recorrer()]

    assert rutas == [casa / "bueno" / "x.pdf"]
    motivos = {o.ruta.name: o.motivo for o in explorador.carpetas_omitidas}
    assert motivos == {
        "privado": MotivoOmision.RUTA_EXCLUIDA,
        "node_modules": MotivoOmision.NOMBRE_EXCLUIDO,
        ".oculta": MotivoOmision.OCULTA,
        "repo": MotivoOmision.REPOSITORIO_GIT,
        "tablet": MotivoOmision.SYNCTHING,
    }


def test_no_sigue_ni_inventaria_enlaces_simbolicos(configuracion):
    casa = configuracion.raices[0]
    original = escribir(casa / "fondo" / "x.pdf", b"contenido")
    (casa / "enlace.pdf").symlink_to(original)
    (casa / "carpeta_enlazada").symlink_to(casa / "fondo", target_is_directory=True)

    rutas = [d.ruta for d in ExploradorDisco(configuracion).recorrer()]

    assert rutas == [original]


def test_salta_las_piezas_latex_pero_no_el_resto_del_proyecto(configuracion):
    casa = configuracion.raices[0]
    curso = casa / "en_Elaboracion" / "Curso PLN"
    escribir(curso / "main.tex", b"\\documentclass{book}")
    escribir(curso / "main.pdf", b"curso compilado")
    escribir(curso / "Pictures" / "intro.pdf", b"pieza")
    # Una carpeta Pictures sin .tex al lado no es de LaTeX: se recorre.
    escribir(casa / "fotos" / "Pictures" / "manual.pdf", b"material")

    explorador = ExploradorDisco(configuracion)
    rutas = {d.ruta for d in explorador.recorrer()}

    assert rutas == {curso / "main.pdf", casa / "fotos" / "Pictures" / "manual.pdf"}
    assert [(o.ruta, o.motivo) for o in explorador.carpetas_omitidas] == [
        (curso / "Pictures", MotivoOmision.PIEZAS_LATEX)
    ]


def test_excepcion_dentro_de_una_ruta_excluida_con_comodines(configuracion, tmp_path):
    from dataclasses import replace

    from orakulue.infraestructura.configuracion import Configuracion

    casa = configuracion.raices[0]
    examenes = casa / "reto" / "examenes"
    escribir(examenes / "Alumno Uno" / "entrega.pdf", b"1")
    escribir(examenes / "Alumno Dos" / "entrega.pdf", b"2")
    escribir(examenes / "suelto.pdf", b"3")
    escribir(examenes / "Resueltos" / "solucion.pdf", b"4")
    escribir(casa / "reto" / "enunciado.pdf", b"5")
    configuracion = replace(
        configuracion,
        rutas_excluidas=Configuracion._expandir([str(casa / "reto" / "examen*")]),
        excepciones=(examenes / "Resueltos",),
    )

    rutas = {d.ruta for d in ExploradorDisco(configuracion).recorrer()}

    assert rutas == {examenes / "Resueltos" / "solucion.pdf", casa / "reto" / "enunciado.pdf"}
