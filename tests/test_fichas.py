"""Pruebas de la fase 4 con un proveedor simulado: no se gasta nada."""

import json
from pathlib import Path
from types import SimpleNamespace

from orakulue.aplicacion.fichado_fondo import FichadoFondo
from orakulue.aplicacion.preparador_peticion import PreparadorPeticion
from orakulue.aplicacion.seleccion_fichables import Fichable
from orakulue.dominio.texto_extraido import EstadoExtraccion, TextoExtraido
from orakulue.infraestructura.almacen_fichas import AlmacenFichas
from orakulue.infraestructura.almacen_textos import AlmacenTextos
from orakulue.infraestructura.registro_consumo import RegistroConsumo
from orakulue.interfaz.indice_fichas import IndiceFichas
from orakulue.interfaz.redactor_ficha import RedactorFicha


def datos_ficha(titulo: str, interes: str) -> dict:
    """Respuesta válida del modelo."""
    vacio = interes == "ninguno"
    return {
        "titulo": titulo, "tipo": "manual", "tema": "Excel — funciones", "temas": [], "nivel": "intermedio",
        "idioma": "es", "publico": "personas usuarias de oficina",
        "vigencia": {"estado": "actual", "motivo": ""}, "interes": interes, "motivo_interes": "porque sí",
        "resumen": "Resumen.", "teoria": [] if vacio else [{"concepto": "BUSCARV", "donde": "tema 3"}],
        "ejercicios": [], "ideas_curso": [], "ideas_pildora": [], "observaciones": "",
    }


def mensaje(datos: dict) -> SimpleNamespace:
    """Imita un mensaje de la API."""
    return SimpleNamespace(
        model="claude-haiku-5-5", stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=1000, output_tokens=500, cache_read_input_tokens=0,
                              cache_creation_input_tokens=0),
        content=[SimpleNamespace(type="text", text=json.dumps(datos))],
    )


class ClienteSimulado:
    """Proveedor de mentira: el lote tarda una consulta en terminar."""

    def __init__(self, respuestas):
        self.respuestas, self.lotes, self.consultas = respuestas, [], 0

    def crear_lote(self, modelo, peticiones):
        self.lotes.append([p.huella for p in peticiones])
        return "lote_1"

    def estado_lote(self, identificador):
        self.consultas += 1
        return self.consultas > 1, {"en proceso": 0 if self.consultas > 1 else 2}

    def resultados_lote(self, identificador):
        yield from self.respuestas


def test_el_ciclo_completo_escribe_fichas_anota_gasto_y_no_repite(tmp_path):
    base, carpeta = tmp_path / "bd.sqlite", tmp_path / "fichas"
    fichables = [
        Fichable("a" * 64, (tmp_path / "manual.pdf",), "es", 500),
        Fichable("b" * 64, (tmp_path / "factura.pdf",), "es", 500),
        Fichable("c" * 64, (tmp_path / "roto.pdf",), "es", 500),
    ]
    cliente = ClienteSimulado([
        ("a" * 64, mensaje(datos_ficha("Manual de Excel", "alto")), ""),
        ("b" * 64, mensaje(datos_ficha("Factura", "ninguno")), ""),
        ("c" * 64, None, "error del proveedor: overloaded"),
    ])
    fichado = FichadoFondo()
    with AlmacenFichas(base) as fichas, RegistroConsumo(base) as registro, \
            AlmacenTextos(base, tmp_path / "textos") as textos:
        for f in fichables:
            textos.guardar(TextoExtraido(f.huella, EstadoExtraccion.CORRECTA, "texto " * 50, "x", "es"))
        textos.confirmar()
        identificador = fichado.enviar(fichables, "claude-haiku-5-5", cliente, textos, fichas)
        # Registrado antes de esperar: si se corta aquí, se puede recoger.
        assert fichas.lote_pendiente() == ("lote_1", "claude-haiku-5-5")
        fichado.esperar(identificador, cliente, dormir=lambda s: None)
        resultado = fichado.recoger(identificador, {f.huella: f for f in fichables}, cliente,
                                    fichas, registro, "prueba", carpeta, RedactorFicha(tmp_path))
        hechas, gastado = fichas.hechas(), registro.gastado("prueba")
        assert fichas.lote_pendiente() is None
        indice = IndiceFichas().escribir(carpeta, fichas.todas())

    assert (resultado.con_interes, resultado.sin_interes, list(resultado.errores)) == (1, 1, ["c" * 64])
    assert hechas == {"a" * 64, "b" * 64}
    # El que falló vuelve a quedar pendiente; los hechos no se repiten.
    assert [f.huella for f in fichado.pendientes(fichables, hechas)] == ["c" * 64]
    assert len(list((carpeta / "_sin_interes").glob("*.md"))) == 1
    texto = indice.read_text(encoding="utf-8")
    assert "[[Manual-de-Excel-aaaaaaaa|Manual de Excel]]" in texto and "## Excel y hojas de cálculo" in texto
    assert gastado > 0


def test_los_documentos_largos_se_envian_en_tres_trozos_y_los_cortos_enteros():
    preparador = PreparadorPeticion()
    corto = preparador.preparar("h", Path("/a/b.pdf"), "hola " * 100, "es")
    largo = preparador.preparar("h", Path("/a/b.pdf"), "x" * 200_000, "es")
    assert not corto.recortado and "hola" in corto.mensaje
    assert largo.recortado and largo.mensaje.count("[… corte") == 2
    assert largo.caracteres_texto < 45_000


def test_las_materias_distinguen_palabras_completas_y_raices():
    from orakulue.utilidades.clasificador_materias import ClasificadorMaterias

    k = ClasificadorMaterias()
    assert k.clasificar("Power Query en Excel", "") == "Power BI y Power Query"
    assert k.clasificar("Machine learning con Python", "") == "Inteligencia artificial"
    assert k.clasificar("Gestión de contenidos multimedia", "") != "Inteligencia artificial"  # «media» no es «ia»
    assert k.clasificar("Plan financiero de una startup", "") == "Empresa, emprendimiento y gestión"
    assert k.clasificar("Recetas de cocina", "") == ClasificadorMaterias.OTRAS
