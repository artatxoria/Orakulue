"""Pruebas de la fase 6: web y conector MCP sobre un fondo de juguete.

No se levanta ningún servidor ni se llama a Ollama ni a la API: la web se
prueba con el cliente de pruebas de Starlette y el conector llamando a sus
herramientas como lo haría Claude.
"""

import asyncio
import re
import zlib
from dataclasses import replace

import numpy as np
import pytest
from conftest import escribir
from starlette.testclient import TestClient

from orakulue.aplicacion.indexador import Indexador
from orakulue.aplicacion.inventariador import Inventariador
from orakulue.aplicacion.servicio_fondo import ServicioFondo
from orakulue.dominio.ficha import Ficha
from orakulue.dominio.marca_datos_personales import MarcaDatosPersonales, NivelRiesgo
from orakulue.dominio.texto_extraido import EstadoExtraccion, TextoExtraido
from orakulue.infraestructura.almacen_analisis import AlmacenAnalisis
from orakulue.infraestructura.almacen_fichas import AlmacenFichas
from orakulue.infraestructura.almacen_indice import AlmacenIndice
from orakulue.infraestructura.almacen_inventario import AlmacenInventario
from orakulue.infraestructura.almacen_textos import AlmacenTextos
from orakulue.infraestructura.calculador_huellas import CalculadorHuellas
from orakulue.infraestructura.explorador_disco import ExploradorDisco
from orakulue.interfaz.conector_mcp import ConectorMcp
from orakulue.interfaz.redactor_ficha import RedactorFicha
from orakulue.interfaz.web.aplicacion_web import AplicacionWeb

SECRETO = "Ane Etxeberria Aguirre, nota final 9"


class Vectores:
    """Vectores de bolsa de palabras, deterministas, sin Ollama."""

    def vectores(self, textos):
        matriz = np.zeros((len(textos), 64), dtype=np.float32)
        for i, texto in enumerate(textos):
            for palabra in re.findall(r"\w+", texto.lower()):
                matriz[i, zlib.crc32(palabra.encode()) % 64] += 1
        normas = np.linalg.norm(matriz, axis=1, keepdims=True)
        return matriz / np.where(normas == 0, 1, normas)


def datos_ficha(titulo):
    return {
        "titulo": titulo, "tipo": "manual", "tema": "Excel — tablas dinámicas", "temas": [], "nivel": "iniciacion",
        "idioma": "es", "publico": "principiantes", "vigencia": {"estado": "actual", "motivo": ""},
        "interes": "alto", "motivo_interes": "sirve tal cual", "resumen": "Manual de tablas dinámicas.",
        "teoria": [], "ejercicios": [], "ideas_curso": [], "ideas_pildora": [], "observaciones": "",
    }


@pytest.fixture
def fondo(configuracion, tmp_path):
    """Fondo con un manual normal y una lista de notas con datos personales."""
    casa = configuracion.raices[0]
    manual = escribir(casa / "formakuntza" / "tablas.pdf", b"manual")
    notas = escribir(casa / "formakuntza" / "notas.pdf", b"notas")
    base = configuracion.base_datos
    with AlmacenInventario(base) as almacen:
        Inventariador(ExploradorDisco(configuracion), CalculadorHuellas(), almacen).ejecutar()
        documentos = list(almacen.documentos())
    huella = {d.ruta.name: d.huella for d in documentos}
    with AlmacenTextos(base, tmp_path / "textos") as textos:
        textos.guardar(TextoExtraido(huella["tablas.pdf"], EstadoExtraccion.CORRECTA,
                                     "Las tablas dinámicas resumen datos en Excel paso a paso.", "x", "es"))
        textos.guardar(TextoExtraido(huella["notas.pdf"], EstadoExtraccion.CORRECTA,
                                     f"Tablas dinámicas: notas del curso. {SECRETO}", "x", "es"))
        textos.confirmar()
    carpeta = tmp_path / "fichas"
    redactor = RedactorFicha(casa)
    with AlmacenFichas(base) as fichas:
        for nombre, ruta in (("tablas.pdf", manual), ("notas.pdf", notas)):
            ficha = Ficha(huella[nombre], (ruta,), "claude-haiku-5-5", datos_ficha(f"Ficha de {nombre}"))
            destino = carpeta / redactor.nombre_fichero(ficha)
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(redactor.redactar(ficha) + ("\n" + SECRETO if nombre == "notas.pdf" else ""))
            fichas.guardar(ficha, destino)
        datos_fichas = fichas.con_datos()
    with AlmacenAnalisis(base) as analisis:
        analisis.sustituir([MarcaDatosPersonales(huella["notas.pdf"], NivelRiesgo.MEDIO, 0, 0, 0, 0, 6)], [])
    with AlmacenIndice(base) as indice, AlmacenTextos(base, tmp_path / "textos") as textos:
        Indexador(indice, Vectores()).ejecutar(documentos, textos, datos_fichas)
    # El servicio busca los textos junto a la base de datos.
    (base.parent / "textos").mkdir(exist_ok=True)
    servicio = ServicioFondo(replace(configuracion), Vectores())
    yield servicio, huella, casa
    servicio.cerrar()


def test_la_web_busca_muestra_fichas_y_descarga_solo_del_inventario(fondo):
    servicio, huella, casa = fondo
    cliente = TestClient(AplicacionWeb(servicio, casa).construir())

    pagina = cliente.get("/", params={"q": "tablas dinámicas"})
    assert pagina.status_code == 200 and "Ficha de tablas.pdf" in pagina.text
    assert "datos personales" in pagina.text  # la de notas sale marcada

    assert cliente.get(f"/ficha/{huella['tablas.pdf']}").status_code == 200
    original = cliente.get(f"/original/{huella['tablas.pdf']}")
    assert original.status_code == 200 and original.content == b"manual"
    # Nada fuera del inventario: ni rutas inventadas ni huellas desconocidas.
    assert cliente.get("/original/..%2F..%2Fetc%2Fpasswd").status_code == 404
    assert cliente.get("/original/" + "f" * 64).status_code == 404
    assert cliente.get("/materias").status_code == 200


def test_el_conector_nunca_devuelve_el_contenido_de_un_documento_personal(fondo):
    servicio, huella, casa = fondo
    servidor = ConectorMcp(servicio, casa).construir()

    def llamar(herramienta, **argumentos):
        resultado = asyncio.run(servidor.call_tool(herramienta, argumentos))
        return "".join(c.text for c in resultado.content)

    busqueda = llamar("buscar", consulta="tablas dinámicas notas")
    assert "Ficha de notas.pdf" in busqueda and "datos personales" in busqueda
    assert SECRETO not in busqueda
    for herramienta, argumentos in (("leer_ficha", {}), ("leer_pasajes", {"consulta": "notas"})):
        texto = llamar(herramienta, huella=huella["notas.pdf"], **argumentos)
        assert SECRETO not in texto and "datos personales" in texto
    assert "Manual de tablas dinámicas" in llamar("leer_ficha", huella=huella["tablas.pdf"])
    assert "paso a paso" in llamar("leer_pasajes", huella=huella["tablas.pdf"], consulta="tablas dinámicas")
    assert SECRETO not in llamar("materias")
