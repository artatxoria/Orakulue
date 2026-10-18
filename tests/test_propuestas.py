"""Pruebas de la fase 7, sin llamar a ningún modelo."""

import re
import zlib

import numpy as np

from orakulue.aplicacion.agrupador_ideas import AgrupadorIdeas
from orakulue.aplicacion.puntuador_candidatas import PuntuadorCandidatas
from orakulue.aplicacion.recolector_ideas import RecolectorIdeas
from orakulue.aplicacion.redactor_propuestas import RedactorPropuestas
from orakulue.dominio.propuesta import Propuesta
from orakulue.infraestructura.lector_catalogo import CursoCatalogo, LectorCatalogo
from orakulue.interfaz.redactor_propuesta_curso import RedactorPropuestaCurso
from orakulue.interfaz.redactor_propuesta_pildora import RedactorPropuestaPildora


class Vectores:
    """Bolsa de palabras: textos con las mismas palabras dan vectores iguales."""

    def vectores(self, textos):
        matriz = np.zeros((len(textos), 128), dtype=np.float32)
        for i, texto in enumerate(textos):
            for palabra in re.findall(r"\w+", texto.lower()):
                matriz[i, zlib.crc32(palabra.encode()) % 128] += 1
        normas = np.linalg.norm(matriz, axis=1, keepdims=True)
        return matriz / np.where(normas == 0, 1, normas)


def ficha(huella, interes="alto", idioma="es", ideas=("Tablas dinámicas para ventas",), ejercicios=True):
    return huella, ({
        "titulo": f"Documento {huella}", "tipo": "manual", "tema": "Excel", "temas": [], "nivel": "intermedio",
        "idioma": idioma, "publico": "", "vigencia": {"estado": "actual", "motivo": ""}, "interes": interes,
        "motivo_interes": "", "resumen": "Resumen.", "teoria": [{"concepto": "Tablas", "donde": ""}],
        "ejercicios": [{"descripcion": "Ejercicio", "practica": "tablas", "con_solucion": "si", "donde": ""}]
        if ejercicios else [],
        "ideas_curso": [{"titulo": t, "destinatarios": "empresas", "aprendizaje": "informes"} for t in ideas],
        "ideas_pildora": [], "observaciones": "",
    }, "momento", None)


def test_lee_los_cursos_activos_del_catalogo_y_salta_los_comentados(tmp_path):
    catalogo = tmp_path / "Catalogo"
    (catalogo / "partes").mkdir(parents=True)
    (catalogo / "excel").mkdir()
    (catalogo / "partes" / "empresas.tex").write_text(
        "\\part{Datos}\n\\input{./excel/tablas}\n%\\input{./excel/retirado}\n", encoding="utf-8")
    (catalogo / "excel" / "tablas.tex").write_text(
        "\\chapter{Análisis con Tablas Dinámicas}\n\\begin{description}\n"
        "\\item[Descripción] Curso de \\textbf{tablas}.\n\\item[Público] Todos.\n\\end{description}", encoding="utf-8")
    (catalogo / "excel" / "retirado.tex").write_text("\\chapter{Retirado}", encoding="utf-8")

    cursos = LectorCatalogo().leer([catalogo / "partes" / "empresas.tex"])

    assert [c.titulo for c in cursos] == ["Análisis con Tablas Dinámicas"]
    assert "tablas" in cursos[0].texto and "textbf" not in cursos[0].texto


def test_las_ideas_iguales_se_agrupan_y_puntuan_mas_con_mas_respaldo():
    fichas = dict([
        ficha("a"), ficha("b"), ficha("c", idioma="eu"),
        ficha("d", interes="medio", ideas=("Programación en Python",), ejercicios=False),
        ficha("e", interes="bajo", ideas=("Idea de un documento sin interés",)),
    ])
    ideas = RecolectorIdeas().recolectar(fichas, personales={"b"})
    assert {i.huella for i in ideas} == {"a", "c", "d"}  # fuera el personal y el de interés bajo

    candidatas = AgrupadorIdeas(Vectores()).agrupar(ideas)
    puntuadas = PuntuadorCandidatas(Vectores(), []).puntuar(candidatas)
    assert puntuadas[0].titulo == "Tablas dinámicas para ventas"
    assert set(puntuadas[0].huellas) == {"a", "c"}
    assert puntuadas[0].desglose["euskera"] > 0 and puntuadas[0].puntuacion > puntuadas[1].puntuacion


def test_lo_que_ya_esta_en_el_catalogo_baja_y_se_explica():
    fichas = dict([ficha("a"), ficha("b")])
    candidatas = AgrupadorIdeas(Vectores()).agrupar(RecolectorIdeas().recolectar(fichas, set()))
    catalogo = [CursoCatalogo("Tablas dinámicas para ventas", "", "empresas")]
    sin = PuntuadorCandidatas(Vectores(), []).puntuar([c for c in candidatas])[0].puntuacion
    con = PuntuadorCandidatas(Vectores(), catalogo).puntuar(candidatas)[0]
    assert con.en_catalogo.startswith("ya lo ofreces") and con.puntuacion < sin


def test_el_mensaje_numera_las_fuentes_e_incluye_el_catalogo():
    fichas = dict([ficha("a"), ficha("b", interes="medio")])
    candidata = AgrupadorIdeas(Vectores()).agrupar(RecolectorIdeas().recolectar(fichas, set()))[0]
    redactor = RedactorPropuestas(fichas, [CursoCatalogo("Word básico", "", "empresas")])
    fuentes = redactor.fuentes(candidata)
    mensaje = redactor.mensaje(candidata, fuentes)
    assert fuentes == ["a", "b"]  # primero el de interés alto
    assert "[1] Documento a" in mensaje and "[2] Documento b" in mensaje and "- Word básico" in mensaje


def test_las_plantillas_citan_las_fuentes_y_no_ponen_duracion(tmp_path):
    documentos = {"a": ("Manual de tablas", tmp_path / "manual.pdf")}
    curso = Propuesta("curso", "curso-a", "m", {
        "titulo": "Tablas", "area_estrategica": "Datos", "descripcion": "D", "objetivos": ["O"],
        "publico_objetivo": "P", "requisitos_previos": [], "justificacion": "J",
        "modulos": [{"titulo": "M1", "contenidos": ["C"], "material_existente": [{"fuentes": [1], "que": "Teoría"}],
                     "ejercicios_disponibles": []}],
        "falta_por_preparar": ["Casos"], "diferencia_con_catalogo": "Nueva", "observaciones": "",
    }, ("a",), 10.0)
    texto = RedactorPropuestaCurso(documentos, tmp_path).redactar(curso)
    assert "Teoría [1]" in texto and "[1] Manual de tablas" in texto and "_A decidir._" in texto
    pildora = Propuesta("pildora", "pildora-a", "m", {
        "titulo": "Validar datos", "problema_de_empresa": "Errores", "destinatarios": "Administración",
        "objetivo": "O", "resultado_esperado": "R", "contenidos": ["C"], "practica_principal": "P",
        "material_existente": [{"fuentes": [1], "que": "Ejemplos"}], "falta_por_preparar": [],
        "diferencia_con_catalogo": "Nueva", "observaciones": "",
    }, ("a",), 5.0)
    assert "Ejemplos [1]" in RedactorPropuestaPildora(documentos, tmp_path).redactar(pildora)


def test_no_se_duplica_la_numeracion_de_los_modulos(tmp_path):
    curso = Propuesta("curso", "c", "m", {
        "titulo": "T", "area_estrategica": "", "descripcion": "", "objetivos": [], "publico_objetivo": "",
        "requisitos_previos": [], "justificacion": "", "falta_por_preparar": [], "diferencia_con_catalogo": "",
        "observaciones": "",
        "modulos": [{"titulo": t, "contenidos": [], "material_existente": [], "ejercicios_disponibles": []}
                    for t in ("1. Preparar los datos", "Módulo 2: Filtros", "Resumir")],
    }, (), 1.0)
    texto = RedactorPropuestaCurso({}, tmp_path).redactar(curso)
    assert "### 1. Preparar los datos" in texto and "### 2. Filtros" in texto and "### 3. Resumir" in texto


def _curso_de_prueba():
    return Propuesta("curso", "curso-0123456789-0001", "claude-sonnet-5-5", {
        "titulo": "Tablas de Excel para pedidos", "area_estrategica": "Datos", "descripcion": "Ordenar pedidos.",
        "objetivos": ["Crear tablas"], "publico_objetivo": "Administración", "requisitos_previos": ["Excel básico"],
        "justificacion": "J", "falta_por_preparar": ["Casos de pedidos"], "diferencia_con_catalogo": "Nueva",
        "observaciones": "",
        "modulos": [{"titulo": "Preparar datos", "contenidos": ["Encabezados", "Un registro por fila"],
                     "material_existente": [], "ejercicios_disponibles": []}],
    }, ("a" * 64,), 12.5, {"respaldo": 10.0})


def test_el_borrador_para_bibliotecario_es_propio_y_sin_duracion(tmp_path):
    from orakulue.interfaz.exportador_bibliotecario import ExportadorBibliotecario

    documentos = {"a" * 64: ("Manual de tablas", tmp_path / "manual.pdf")}
    destino = ExportadorBibliotecario(documentos, tmp_path).exportar(_curso_de_prueba(), tmp_path / "borradores")
    yaml = (destino / "curso.yaml").read_text(encoding="utf-8")
    assert 'cliente: "propuesta propia"' in yaml and "duracion_horas: null" in yaml
    assert yaml.count("origen: propio") == 2 and 'id: "01_02"' in yaml
    assert '"excel-basico"' in yaml
    fuentes = (destino / "fuentes.md").read_text(encoding="utf-8")
    assert "[1] Manual de tablas" in fuentes and "Casos de pedidos" in fuentes


def test_las_propuestas_se_guardan_y_el_indice_las_lista(tmp_path):
    from orakulue.infraestructura.almacen_propuestas import AlmacenPropuestas
    from orakulue.interfaz.indice_propuestas import IndicePropuestas

    ruta = tmp_path / "propuestas" / "cursos" / "Tablas-0001.md"
    with AlmacenPropuestas(tmp_path / "bd.sqlite") as almacen:
        almacen.guardar(_curso_de_prueba(), ruta)
        assert almacen.hechas() == {"curso-0123456789-0001"}
        propuesta, guardada = almacen.por_clave("curso-0123456789-0001")
        indice = IndicePropuestas().escribir(tmp_path / "propuestas", almacen.todas())
    assert propuesta.datos["titulo"] == "Tablas de Excel para pedidos" and guardada == ruta
    assert "[[Tablas-0001\\|Tablas de Excel para pedidos]]" in indice.read_text(encoding="utf-8")


def test_la_tanda_funde_las_candidatas_repetidas():
    from orakulue.aplicacion.selector_tanda import SelectorTanda
    from orakulue.dominio.candidata import Candidata
    from orakulue.dominio.idea_formativa import IdeaFormativa

    def candidata(titulo, huella):
        return Candidata("pildora", [IdeaFormativa("pildora", titulo, titulo, huella, "alto", "es", True, True)])

    candidatas = [candidata("Verificar textos de IA", "a"), candidata("Verificar textos de IA", "b"),
                  candidata("Tablas dinámicas", "c"), candidata("Macros de Word", "d")]
    elegidas = SelectorTanda(Vectores()).elegir(candidatas, "pildora", 2, set())
    assert [c.titulo for c in elegidas] == ["Verificar textos de IA", "Tablas dinámicas"]
    assert set(elegidas[0].huellas) == {"a", "b"}
