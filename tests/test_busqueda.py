"""Pruebas de la fase 5 con un cliente de vectores simulado (sin Ollama)."""

import re
import zlib
from pathlib import Path

import numpy as np

from orakulue.aplicacion.buscador import Buscador
from orakulue.aplicacion.evaluador_busqueda import EvaluadorBusqueda, PreguntaPrueba
from orakulue.aplicacion.indexador import Indexador
from orakulue.aplicacion.respondedor import Respondedor
from orakulue.dominio.documento import Documento
from orakulue.dominio.info_documento import InfoDocumento
from orakulue.dominio.texto_extraido import EstadoExtraccion, TextoExtraido
from orakulue.infraestructura.almacen_indice import AlmacenIndice
from orakulue.infraestructura.almacen_textos import AlmacenTextos
from orakulue.utilidades.troceador import Troceador


class VectoresDePalabras:
    """Imita un modelo de vectores: bolsa de palabras con sinónimos fijos.

    «buscarv» y «buscar valor» comparten dimensión, para comprobar que el
    buscador por significado encuentra lo que el de palabras no ve.
    """

    SINONIMOS = {"buscarv": "buscar", "valor": "buscar", "bilatu": "buscar"}

    def vectores(self, textos):
        matriz = np.zeros((len(textos), 64), dtype=np.float32)
        for i, texto in enumerate(textos):
            for palabra in re.findall(r"\w+", texto.lower()):
                palabra = self.SINONIMOS.get(palabra, palabra)
                matriz[i, zlib.crc32(palabra.encode()) % 64] += 1
        normas = np.linalg.norm(matriz, axis=1, keepdims=True)
        return matriz / np.where(normas == 0, 1, normas)


TEXTOS = {
    "a" * 64: "La función BUSCARV localiza un dato en la primera columna de una tabla.",
    "b" * 64: "Las tablas dinámicas resumen grandes cantidades de datos en Excel.",
    "c" * 64: "Lista de alumnos con sus notas finales: datos personales.",
}


def preparar(tmp_path):
    """Índice de juguete con tres documentos; el tercero, personal."""
    base = tmp_path / "bd.sqlite"
    documentos = [Documento(tmp_path / f"{h[0]}.pdf", 1, 0, h) for h in TEXTOS]
    with AlmacenTextos(base, tmp_path / "textos") as textos:
        for h, t in TEXTOS.items():
            textos.guardar(TextoExtraido(h, EstadoExtraccion.CORRECTA, t, "x", "es"))
        textos.confirmar()
        with AlmacenIndice(base) as indice:
            resumen = Indexador(indice, VectoresDePalabras()).ejecutar(documentos, textos, {})
    catalogo = {
        h: InfoDocumento(h, (tmp_path / f"{h[0]}.pdf",), f"Documento {h[0]}", personal=(h[0] == "c"))
        for h in TEXTOS
    }
    return base, documentos, catalogo, resumen


def test_el_troceador_respeta_parrafos_y_no_pasa_del_tamano():
    texto = "\n\n".join(f"Párrafo {i}. " + "palabra " * 40 for i in range(20))
    trozos = Troceador(tamano=500, solape=50).trocear(texto)
    assert len(trozos) > 1
    assert all(len(t) <= 560 for t in trozos)
    assert all(not t.startswith("alabra") for t in trozos)  # no empieza a mitad de palabra


def test_indexar_es_incremental_y_olvida_lo_que_ya_no_esta(tmp_path):
    base, documentos, _, resumen = preparar(tmp_path)
    assert resumen.documentos == 3
    with AlmacenTextos(base, tmp_path / "textos") as textos, AlmacenIndice(base) as indice:
        otra = Indexador(indice, VectoresDePalabras()).ejecutar(documentos[:2], textos, {})
        assert (otra.documentos, otra.olvidados) == (0, 1)
        assert set(indice.indexados("trozo")) == {"a" * 64, "b" * 64}


def test_el_significado_encuentra_lo_que_las_palabras_no(tmp_path):
    base, _, catalogo, _ = preparar(tmp_path)
    with AlmacenIndice(base) as indice:
        buscador = Buscador(indice, VectoresDePalabras(), catalogo)
        por_palabras = buscador.buscar("buscar valor", 3, "palabras")
        por_significado = buscador.buscar("buscar valor", 3, "significado")
        hibrido = buscador.buscar("tablas dinámicas", 3, "hibrido")
    assert all(r.info.huella != "a" * 64 for r in por_palabras)
    assert por_significado[0].info.huella == "a" * 64
    assert hibrido[0].info.huella == "b" * 64


class ApiSimulada:
    """Imita la API: guarda lo que recibe para comprobar qué se ha enviado."""

    def __init__(self):
        self.enviado = ""

    def redactar(self, modelo, instrucciones, mensaje):
        from orakulue.dominio.consumo_llamada import ConsumoLlamada

        self.enviado = mensaje
        return "Respuesta [1].", ConsumoLlamada(modelo, 100, 10)


def test_los_pasajes_personales_nunca_se_envian_a_la_api(tmp_path):
    base, _, catalogo, _ = preparar(tmp_path)
    api = ApiSimulada()
    with AlmacenIndice(base) as indice:
        respondedor = Respondedor(Buscador(indice, VectoresDePalabras(), catalogo))
        respuesta = respondedor.responder("notas de los alumnos", cliente=api, modelo="claude-haiku-5-5")
    assert "notas finales" not in api.enviado
    assert respuesta.omitidos_por_privacidad == 1
    assert all(not f.personal for f in respuesta.fuentes)


def test_el_evaluador_mide_acierto_y_rango(tmp_path):
    base, _, catalogo, _ = preparar(tmp_path)
    preguntas = [
        PreguntaPrueba("tablas dinámicas", ("bbbb",)),
        PreguntaPrueba("algo que no existe en ninguna parte", ("aaaa",)),
    ]
    with AlmacenIndice(base) as indice:
        resultado = EvaluadorBusqueda().evaluar(Buscador(indice, VectoresDePalabras(), catalogo), preguntas, "palabras")
    assert resultado.acierto == 0.5 and resultado.rango_reciproco == 0.5
    assert resultado.fallos == ("algo que no existe en ninguna parte",)


def test_las_versiones_salen_como_un_solo_resultado_y_heredan_lo_personal(tmp_path):
    from dataclasses import replace

    from orakulue.aplicacion.agrupador_variantes import AgrupadorVariantes

    base, _, catalogo, _ = preparar(tmp_path)
    ficha = tmp_path / "ficha.md"
    # «a» y «c» son versiones del mismo documento (mismo título de ficha);
    # «c» tiene datos personales.
    catalogo["a" * 64] = replace(catalogo["a" * 64], titulo="Guion del curso de tablas", ruta_ficha=ficha)
    catalogo["c" * 64] = replace(catalogo["c" * 64], titulo="Guion del curso de tablas.", ruta_ficha=ficha)
    variantes = AgrupadorVariantes().agrupar(catalogo, {})
    assert variantes["a" * 64] == variantes["c" * 64] and "b" * 64 not in variantes

    with AlmacenIndice(base) as indice:
        resultados = Buscador(indice, VectoresDePalabras(), catalogo, variantes).buscar(
            "función columna tabla alumnos notas", 5, "palabras"
        )
    huellas = [r.info.huella for r in resultados]
    assert ("a" * 64 in huellas) != ("c" * 64 in huellas)  # solo uno de los dos
    agrupado = next(r for r in resultados if r.variantes)
    assert agrupado.info.personal  # basta que una versión sea personal


def test_los_titulos_cortos_no_agrupan():
    from orakulue.aplicacion.agrupador_variantes import AgrupadorVariantes

    catalogo = {
        h: InfoDocumento(h, (Path(f"/{h}.pdf"),), "Ejercicio 3", ruta_ficha=Path("/f.md")) for h in ("x", "y")
    }
    assert AgrupadorVariantes().agrupar(catalogo, {}) == {}
