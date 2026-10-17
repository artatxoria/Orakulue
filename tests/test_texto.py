"""Pruebas de la fase 3: extracción, idioma, casi duplicados y datos personales."""

import zipfile
from pathlib import Path

from orakulue.aplicacion.detector_casi_duplicados import DetectorCasiDuplicados
from orakulue.aplicacion.detector_datos_personales import DetectorDatosPersonales
from orakulue.aplicacion.extraccion_textos import ExtraccionTextos
from orakulue.dominio.documento import Documento
from orakulue.dominio.marca_datos_personales import NivelRiesgo
from orakulue.dominio.texto_extraido import EstadoExtraccion, TextoExtraido
from orakulue.infraestructura.almacen_textos import AlmacenTextos
from orakulue.infraestructura.extractores.extractor_zip_xml import ExtractorZipXml
from orakulue.interfaz.informe_texto import InformeTexto
from orakulue.utilidades.detector_idioma import DetectorIdioma

PARRAFO = (
    "La normalización de bases de datos es el proceso de organizar las tablas para "
    "reducir la redundancia y mejorar la integridad de los datos almacenados. "
)


def docx(ruta: Path, parrafos: list[str]) -> Path:
    """Crea un .docx mínimo con los párrafos indicados."""
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    cuerpo = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in parrafos)
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("word/document.xml", f'<w:document xmlns:w="{w}"><w:body>{cuerpo}</w:body></w:document>')
    return ruta


def odt(ruta: Path, parrafos: list[str]) -> Path:
    """Crea un .odt mínimo con los párrafos indicados."""
    t = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    cuerpo = "".join(f"<text:p>{p}</text:p>" for p in parrafos)
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("content.xml", f'<office:document-content xmlns:office="o" xmlns:text="{t}">{cuerpo}</office:document-content>')
    return ruta


def test_extrae_docx_y_odt_parrafo_a_parrafo(tmp_path):
    extractor = ExtractorZipXml()
    assert extractor.extraer(docx(tmp_path / "a.docx", ["Hola", "mundo"])) == "Hola\nmundo"
    assert extractor.extraer(odt(tmp_path / "a.odt", ["Kaixo", "mundua"])) == "Kaixo\nmundua"


def test_un_zip_danado_es_error_y_un_texto_corto_es_sin_texto(tmp_path):
    roto = tmp_path / "roto.docx"
    roto.write_bytes(b"esto no es un zip")
    corto = docx(tmp_path / "corto.docx", ["casi nada"])
    largo = docx(tmp_path / "largo.docx", [PARRAFO * 3])
    documentos = [Documento(r, 1, 0, h) for r, h in ((roto, "h1"), (corto, "h2"), (largo, "h3"))]

    with AlmacenTextos(tmp_path / "bd.sqlite", tmp_path / "textos") as almacen:
        resumen = ExtraccionTextos(almacen).ejecutar(documentos)
        estados = {h: e for h, e, *_ in almacen.metadatos()}
        # Incremental: la segunda pasada no tiene nada pendiente.
        assert ExtraccionTextos(almacen).ejecutar(documentos).pendientes == 0

    assert resumen.pendientes == 3
    assert estados == {
        "h1": EstadoExtraccion.ERROR, "h2": EstadoExtraccion.SIN_TEXTO, "h3": EstadoExtraccion.CORRECTA,
    }


def test_detecta_castellano_euskera_e_ingles():
    detector = DetectorIdioma()
    assert detector.detectar(PARRAFO * 5) == "es"
    assert detector.detectar(
        "Datu-baseen normalizazioa taulak antolatzeko prozesua da eta erredundantzia "
        "murrizteko behar da. Ez da erraza baina beste modu bat ere badago eta hau da onena. " * 5
    ) == "eu"
    assert detector.detectar(
        "Database normalization is the process of organizing tables to reduce redundancy and "
        "improve the integrity of the data that is stored in them. " * 5
    ) == "en"
    assert detector.detectar("1 2 3 4") == "?"


def test_agrupa_versiones_casi_iguales_y_separa_lo_distinto():
    base = " ".join(f"{PARRAFO} Apartado {i}." for i in range(60))
    version = base.replace("Apartado 7.", "Apartado siete, corregido.")
    otro = " ".join(f"Las redes neuronales aprenden representaciones del ejemplo {i}." for i in range(200))

    grupos = DetectorCasiDuplicados().detectar([("a", base), ("b", version), ("c", otro)])

    assert [g.huellas for g in grupos] == [("a", "b")]
    assert grupos[0].similitud_minima >= 0.8


def test_dni_e_iban_validos_dan_alto_y_los_inventados_no():
    detector = DetectorDatosPersonales()
    # 12345678Z es un DNI con letra correcta; ES9121000418450200051332 es el
    # IBAN de ejemplo oficial, con control válido.
    assert detector.analizar("h", "Alumno: 12345678Z").nivel is NivelRiesgo.ALTO
    assert detector.analizar("h", "Cuenta ES91 2100 0418 4502 0005 1332").nivel is NivelRiesgo.ALTO
    # Letra incorrecta: típico de un ejercicio inventado.
    assert detector.analizar("h", "Cliente 12345678A").nivel is NivelRiesgo.NINGUNO


def test_varios_correos_reales_dan_medio_pero_los_de_ejemplo_no():
    detector = DetectorDatosPersonales()
    reales = "ana@gmail.com, jon@hotmail.com, mikel@euskaltel.net"
    ejemplo = "usuario@example.com, otro@ejemplo.es, tercero@midominio.com"
    assert detector.analizar("h", reales).nivel is NivelRiesgo.MEDIO
    assert detector.analizar("h", ejemplo).nivel is NivelRiesgo.NINGUNO


def test_el_informe_nunca_muestra_los_datos_encontrados():
    marca = DetectorDatosPersonales().analizar("h1", "DNI: 12345678Z, correo ana@gmail.com")
    metadatos = [("h1", EstadoExtraccion.CORRECTA, 100, "x", "es", "")]
    informe = InformeTexto(metadatos, {"h1": [Path("/casa/a.pdf")]}, [], [marca], Path("/casa")).componer()

    assert "~/a.pdf" in informe
    assert "12345678Z" not in informe and "ana@gmail.com" not in informe


def test_los_correos_de_contacto_de_un_libro_largo_no_son_datos_personales():
    libro = PARRAFO * 2_000 + " autor@gmail.com editorial@anaya.es soporte@oreilly.com"
    assert DetectorDatosPersonales().analizar("h", libro).nivel is NivelRiesgo.BAJO


def test_el_ocr_solo_intenta_los_pdf_sin_texto_y_una_sola_vez(tmp_path):
    from orakulue.aplicacion.reconocimiento_optico import ReconocimientoOptico
    from orakulue.infraestructura.extractores.extractor_ocr import ExtractorOcr

    class OcrDeMentira(ExtractorOcr):
        """Devuelve texto para un PDF y nada para el otro, sin llamar a Tesseract."""

        def __init__(self):
            self.leidos = []

        def extraer(self, ruta):
            self.leidos.append(ruta.name)
            return PARRAFO * 3 if ruta.name == "escaneado.pdf" else ""

    with AlmacenTextos(tmp_path / "bd.sqlite", tmp_path / "textos") as almacen:
        for huella in ("h1", "h2", "h3"):
            estado = EstadoExtraccion.CORRECTA if huella == "h3" else EstadoExtraccion.SIN_TEXTO
            almacen.guardar(TextoExtraido(huella, estado, "", "ExtractorPdf"))
        documentos = [
            Documento(tmp_path / "escaneado.pdf", 1, 0, "h1"),
            Documento(tmp_path / "en_blanco.pdf", 1, 0, "h2"),
            Documento(tmp_path / "con_texto.pdf", 1, 0, "h3"),
        ]
        ocr = OcrDeMentira()
        cuenta = ReconocimientoOptico(almacen, extractor=ocr).ejecutar(documentos)
        estados = {h: e for h, e, *_ in almacen.metadatos()}
        # Segunda pasada: lo que el OCR ya intentó no se repite.
        ReconocimientoOptico(almacen, extractor=ocr).ejecutar(documentos)

    assert sorted(ocr.leidos) == ["en_blanco.pdf", "escaneado.pdf"]
    assert cuenta == {EstadoExtraccion.CORRECTA: 1, EstadoExtraccion.SIN_TEXTO: 1}
    assert estados["h1"] is EstadoExtraccion.CORRECTA and estados["h2"] is EstadoExtraccion.SIN_TEXTO


def test_una_lista_de_alumnos_con_notas_es_dato_personal_y_un_libro_que_cita_autores_no():
    detector = DetectorDatosPersonales()
    notas = "Notas finales\n" + "\n".join(
        f"{n} Etxeberria Aguirre 7,5" for n in ("Ane", "Mikel", "Jon", "Leire", "Iker", "Maialen")
    )
    libro = PARRAFO * 3_000 + " Prólogo de Juan Pérez. Revisado por Ana García y Mikel Larrañaga."
    marca = detector.analizar("h", notas)
    assert marca.nivel is NivelRiesgo.MEDIO and marca.personas == 6
    assert detector.analizar("h", libro).nivel is not NivelRiesgo.MEDIO


def test_el_nombre_del_fichero_tambien_excluye():
    from orakulue.aplicacion.seleccion_fichables import SeleccionFichables

    seleccion = SeleccionFichables()
    assert seleccion.sensible_por_nombre([Path("/curso/IFCT0049/Notas Finales.pdf")])
    assert seleccion.sensible_por_nombre([Path("/curso/Control_de_asistencia/marzo.pdf")])
    assert not seleccion.sensible_por_nombre([Path("/fondo/Excel/Funciones de texto.pdf")])
    # «notas» dentro de otra palabra no cuenta.
    assert not seleccion.sensible_por_nombre([Path("/fondo/Word/Anotaciones al margen.docx")])


def test_el_aviso_de_saldo_dice_cuanto_queda_y_cuantas_ejecuciones_aguanta():
    from decimal import Decimal

    from orakulue.aplicacion.aviso_saldo import AvisoSaldo

    aviso = AvisoSaldo("CLAVE_X", Decimal("10"), Decimal("9"), Decimal("0.25"), "1 de enero")
    texto = aviso.redactar()
    assert aviso.es_bajo and aviso.ejecuciones_restantes == 4
    assert "SALDO BAJO" in texto and "CLAVE_X" in texto and "1,00 $" in texto
    assert "Sin saldo" not in texto


def test_la_falta_de_saldo_se_reconoce_por_el_texto_y_nombra_la_clave():
    from orakulue.infraestructura.error_saldo_agotado import ErrorSaldoAgotado

    assert ErrorSaldoAgotado.es_falta_de_saldo("Your credit balance is too low to access the Anthropic API.")
    # Un 400 por petición mal formada no es falta de saldo.
    assert not ErrorSaldoAgotado.es_falta_de_saldo("messages: field required")
    assert "CLAVE_X" in str(ErrorSaldoAgotado("CLAVE_X", "credit balance is too low"))


def test_el_coste_por_lotes_es_la_mitad():
    from decimal import Decimal

    from orakulue.dominio.consumo_llamada import ConsumoLlamada
    from orakulue.infraestructura.catalogo_tarifas import CatalogoTarifas

    tarifa = CatalogoTarifas().de("claude-haiku-5-5")
    directo = tarifa.coste(ConsumoLlamada("claude-haiku-5-5", 1_000_000, 1_000_000))
    lotes = tarifa.coste(ConsumoLlamada("claude-haiku-5-5", 1_000_000, 1_000_000, por_lotes=True))
    assert directo == Decimal("0.60") and lotes * 2 == directo
