"""Órdenes de la fase 7.

- ``candidatas``: reúne, agrupa y puntúa las ideas del fondo y escribe el
  informe de candidatas (local, gratis).
- ``prueba-propuestas``: simulacro de la prueba de modelos sobre las mejores
  candidatas; con ``--ejecutar``, la hace de verdad.
- ``proponer``: simulacro de la tanda (N cursos y N píldoras); con
  ``--ejecutar``, la redacta. Las ya redactadas no se repiten.
- ``exportar-propuesta CLAVE``: borrador para Bibliotecario.
"""

import math
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from orakulue.aplicacion.agrupador_ideas import AgrupadorIdeas
from orakulue.aplicacion.aviso_saldo import AvisoSaldo
from orakulue.aplicacion.catalogo_documentos import CatalogoDocumentos
from orakulue.aplicacion.seleccion_fichables import SeleccionFichables
from orakulue.aplicacion.preparador_peticion import INSTRUCCIONES
from orakulue.aplicacion.puntuador_candidatas import PuntuadorCandidatas
from orakulue.aplicacion.recolector_ideas import RecolectorIdeas
from orakulue.aplicacion.redactor_propuestas import INSTRUCCIONES_PROPUESTA, RedactorPropuestas
from orakulue.aplicacion.selector_tanda import SelectorTanda
from orakulue.dominio.candidata import Candidata
from orakulue.dominio.consumo_llamada import ConsumoLlamada
from orakulue.infraestructura.almacen_analisis import AlmacenAnalisis
from orakulue.infraestructura.almacen_fichas import AlmacenFichas
from orakulue.infraestructura.almacen_inventario import AlmacenInventario
from orakulue.infraestructura.almacen_propuestas import AlmacenPropuestas
from orakulue.infraestructura.catalogo_tarifas import FECHA_TARIFAS, CatalogoTarifas
from orakulue.infraestructura.cliente_modelo import ClienteModelo, ErrorLlamada
from orakulue.infraestructura.cliente_vectores import ClienteVectores, ErrorVectores
from orakulue.infraestructura.configuracion import Configuracion
from orakulue.infraestructura.error_saldo_agotado import ErrorSaldoAgotado
from orakulue.infraestructura.lector_catalogo import LectorCatalogo
from orakulue.infraestructura.registro_consumo import RegistroConsumo
from orakulue.interfaz.exportador_bibliotecario import ExportadorBibliotecario
from orakulue.interfaz.indice_propuestas import IndicePropuestas
from orakulue.interfaz.redactor_propuesta_curso import RedactorPropuestaCurso
from orakulue.utilidades.formato import Formato
from orakulue.interfaz.redactor_propuesta_pildora import RedactorPropuestaPildora


class OrdenesPropuestas:
    """Ejecuta las órdenes de la fase 7."""

    #: Tokens de salida previstos por propuesta, para el presupuesto.
    SALIDA_PREVISTA = 4_000
    CARACTERES_POR_TOKEN = 3

    def __init__(self, configuracion: Configuracion) -> None:
        """Prepara las órdenes.

        Args:
            configuracion: configuración completa.
        """
        self._configuracion = configuracion
        self._propuestas = configuracion.propuestas
        self._vectores = ClienteVectores()

    def candidatas(self) -> int:
        """Calcula las candidatas y escribe su informe.

        Returns:
            0 si va bien; 1 si Ollama no responde.
        """
        try:
            candidatas, _, documentos = self._calcular()
        except ErrorVectores as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        ruta = self._configuracion.carpeta_informes / f"candidatas-{datetime.now():%Y%m%d-%H%M}.md"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(self._informe_candidatas(candidatas, documentos), encoding="utf-8")
        print(f"{len(candidatas)} candidatas. Informe: {ruta}")
        return 0

    def prueba(self, ejecutar: bool) -> int:
        """Simulacro o ejecución de la prueba de modelos.

        Se toman las mejores candidatas: dos tercios cursos y un tercio
        píldoras, para ver los dos tipos.

        Returns:
            0 si va bien; 1 si falla Ollama, la clave o el saldo.
        """
        try:
            candidatas, fichas, documentos = self._calcular()
        except ErrorVectores as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        cantidad = self._propuestas.propuestas_prueba
        cursos = math.ceil(cantidad * 2 / 3)
        elegidas = ([c for c in candidatas if c.tipo == "curso"][:cursos]
                    + [c for c in candidatas if c.tipo == "pildora"][: cantidad - cursos])
        redactor = RedactorPropuestas(fichas, self._catalogo())
        modelos = list(self._propuestas.modelos_prueba)

        if not ejecutar:
            tarifas = CatalogoTarifas()
            entrada = sum(len(redactor.mensaje(c, redactor.fuentes(c))) + len(INSTRUCCIONES_PROPUESTA)
                          for c in elegidas) // self.CARACTERES_POR_TOKEN
            print(f"Simulacro de la prueba: {len(elegidas)} propuestas con {', '.join(modelos)}.")
            for c in elegidas:
                print(f"  - [{c.tipo}] {c.titulo} ({len(c.huellas)} documentos, {c.puntuacion} puntos)")
            for modelo in modelos:
                coste = tarifas.de(modelo).coste(
                    ConsumoLlamada(modelo, entrada, self.SALIDA_PREVISTA * len(elegidas)))
                print(f"  Coste estimado con {modelo}: {coste:.2f} $".replace(".", ","))
            print("No se ha gastado nada. Para hacerla: orakulue prueba-propuestas --ejecutar")
            return 0

        fichas_conf = self._configuracion.fichas
        try:
            cliente = ClienteModelo(fichas_conf.variable_clave, INSTRUCCIONES, fichas_conf.esfuerzo)
        except ErrorLlamada as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        sello = datetime.now().strftime("%Y%m%d-%H%M")
        ejecucion, carpeta = f"prueba-propuestas-{sello}", self._configuracion.base_datos.parent / "prueba_propuestas" / sello
        tarifas, costes, filas, codigo = CatalogoTarifas(), {}, {}, 0
        with RegistroConsumo(self._configuracion.base_datos) as registro:
            try:
                for modelo in modelos:
                    costes[modelo] = Decimal(0)
                    for candidata in elegidas:
                        print(f"  {modelo}: {candidata.titulo}", flush=True)
                        try:
                            resultado = redactor.redactar(candidata, cliente, modelo, self._propuestas.esfuerzo)
                        except ErrorLlamada as error:
                            filas.setdefault(candidata.clave, {})[modelo] = f"error: {error}"
                            if getattr(error, "consumo", None):
                                registro.anotar(ejecucion, None, error.consumo, tarifas.de(error.consumo.modelo).coste(error.consumo))
                            continue
                        coste = tarifas.de(resultado.consumo.modelo).coste(resultado.consumo)
                        registro.anotar(ejecucion, None, resultado.consumo, coste)
                        costes[modelo] += coste
                        destino = carpeta / modelo / f"{candidata.clave}.md"
                        destino.parent.mkdir(parents=True, exist_ok=True)
                        destino.write_text(self._markdown(resultado.propuesta, documentos), encoding="utf-8")
                        filas.setdefault(candidata.clave, {})[modelo] = str(destino)
            except ErrorSaldoAgotado as error:
                print(f"Prueba detenida.\n{error}", file=sys.stderr)
                codigo = 1
            aviso = AvisoSaldo(fichas_conf.variable_clave, fichas_conf.saldo_declarado,
                               registro.gastado(), registro.gastado(ejecucion), FECHA_TARIFAS).redactar()
        informe = self._informe_prueba(elegidas, modelos, filas, costes, aviso)
        ruta = self._configuracion.carpeta_informes / f"prueba-propuestas-{sello}.md"
        ruta.write_text(informe, encoding="utf-8")
        print(f"{aviso}\nInforme: {ruta}")
        return codigo

    def proponer(self, ejecutar: bool) -> int:
        """Simulacro o redacción de la tanda de propuestas.

        Se toman las ``cursos`` mejores candidatas de curso y las
        ``pildoras`` mejores de píldora que aún no estén redactadas. Lo hecho se
        guarda propuesta a propuesta: si algo corta, se continúa sin pagar dos
        veces.

        Returns:
            0 si va bien; 1 si falla Ollama, la clave o el saldo.
        """
        try:
            candidatas, fichas, documentos = self._calcular()
        except ErrorVectores as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        base = self._configuracion.base_datos
        with AlmacenPropuestas(base) as almacen:
            hechas = almacen.hechas()
        selector = SelectorTanda(self._vectores)
        elegidas = (selector.elegir(candidatas, "curso", self._propuestas.cursos, hechas)
                    + selector.elegir(candidatas, "pildora", self._propuestas.pildoras, hechas))
        redactor, modelo = RedactorPropuestas(fichas, self._catalogo()), self._propuestas.modelo
        if not ejecutar:
            entrada = sum(len(redactor.mensaje(c, redactor.fuentes(c))) + len(INSTRUCCIONES_PROPUESTA)
                          for c in elegidas) // self.CARACTERES_POR_TOKEN
            salida = self._salida_medida(modelo) or self.SALIDA_PREVISTA
            coste = CatalogoTarifas().de(modelo).coste(ConsumoLlamada(modelo, entrada, salida * len(elegidas)))
            importe = f"{coste:.2f}".replace(".", ",")
            print(f"Simulacro: {len(elegidas)} propuestas por redactar con {modelo} "
                  f"({sum(c.tipo == 'curso' for c in elegidas)} cursos y "
                  f"{sum(c.tipo == 'pildora' for c in elegidas)} píldoras). Coste estimado: {importe} $.")
            for c in elegidas:
                print(f"  - [{c.tipo}] {c.titulo} ({c.puntuacion} puntos)" + (f" — {c.en_catalogo}" if c.en_catalogo else ""))
            print("No se ha gastado nada. Para redactarlas: orakulue proponer --ejecutar")
            return 0

        fichas_conf = self._configuracion.fichas
        try:
            cliente = ClienteModelo(fichas_conf.variable_clave, INSTRUCCIONES, fichas_conf.esfuerzo)
        except ErrorLlamada as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        ejecucion = f"propuestas-{datetime.now():%Y%m%d-%H%M}"
        tarifas, carpeta, codigo, errores = CatalogoTarifas(), self._propuestas.carpeta, 0, 0
        with RegistroConsumo(base) as registro, AlmacenPropuestas(base) as almacen:
            try:
                for numero, candidata in enumerate(elegidas, start=1):
                    print(f"  {numero}/{len(elegidas)} {candidata.titulo}", flush=True)
                    try:
                        resultado = redactor.redactar(candidata, cliente, modelo, self._propuestas.esfuerzo)
                    except ErrorLlamada as error:
                        errores += 1
                        print(f"    sin propuesta: {error}", file=sys.stderr)
                        if getattr(error, "consumo", None):
                            registro.anotar(ejecucion, None, error.consumo, tarifas.de(error.consumo.modelo).coste(error.consumo))
                        continue
                    registro.anotar(ejecucion, None, resultado.consumo,
                                    tarifas.de(resultado.consumo.modelo).coste(resultado.consumo))
                    propuesta = resultado.propuesta
                    destino = (carpeta / ("cursos" if propuesta.tipo == "curso" else "pildoras")
                               / f"{Formato.slug(propuesta.titulo)}-{propuesta.clave[-4:]}.md")
                    destino.parent.mkdir(parents=True, exist_ok=True)
                    destino.write_text(self._markdown(propuesta, documentos), encoding="utf-8")
                    almacen.guardar(propuesta, destino)
            except ErrorSaldoAgotado as error:
                print(f"Redacción detenida.\n{error}", file=sys.stderr)
                codigo = 1
            indice = IndicePropuestas().escribir(carpeta, almacen.todas())
            aviso = AvisoSaldo(fichas_conf.variable_clave, fichas_conf.saldo_declarado,
                               registro.gastado(), registro.gastado(ejecucion), FECHA_TARIFAS).redactar()
        print(f"Propuestas redactadas: {len(elegidas) - errores} de {len(elegidas)}. Índice: {indice}\n{aviso}")
        return codigo

    def exportar(self, clave: str) -> int:
        """Exporta una propuesta como borrador para Bibliotecario.

        Returns:
            0 si va bien; 1 si la clave no existe.
        """
        base = self._configuracion.base_datos
        with AlmacenPropuestas(base) as almacen:
            encontrada = almacen.por_clave(clave)
        if encontrada is None:
            print(f"No hay ninguna propuesta con la clave {clave}. Mira las claves en el índice de propuestas.",
                  file=sys.stderr)
            return 1
        _, _, documentos = self._documentos()
        destino = ExportadorBibliotecario(documentos, Path.home()).exportar(
            encontrada[0], self._propuestas.carpeta / "_bibliotecario")
        print(f"Borrador para Bibliotecario: {destino}\n(curso.yaml con apartados de origen propio y fuentes.md)")
        return 0

    def _salida_medida(self, modelo: str) -> int | None:
        """Tokens de salida medios del modelo en las propuestas ya hechas."""
        with RegistroConsumo(self._configuracion.base_datos) as registro:
            return registro.salida_media(modelo)

    def _documentos(self):
        """Fichas, catálogo de documentos y títulos por huella (sin vectores)."""
        base = self._configuracion.base_datos
        with AlmacenInventario(base) as inventario:
            lista = list(inventario.documentos())
        with AlmacenFichas(base) as almacen_fichas:
            fichas, todas = almacen_fichas.con_datos(), almacen_fichas.todas()
        with AlmacenAnalisis(base) as analisis:
            marcas = analisis.marcas()
        seleccion = SeleccionFichables(rutas_personales=self._configuracion.fichas.rutas_personales)
        catalogo_docs = CatalogoDocumentos(seleccion).construir(lista, todas, {r: h for h, (_, _, r) in fichas.items()}, marcas)
        return fichas, catalogo_docs, {h: (i.titulo, i.rutas[0]) for h, i in catalogo_docs.items()}

    def _calcular(self) -> tuple[list[Candidata], dict, dict[str, tuple[str, Path]]]:
        """Reúne, agrupa y puntúa las ideas.

        Returns:
            (candidatas ordenadas, datos de las fichas, huella → (título, ruta)).
        """
        fichas, catalogo_docs, documentos = self._documentos()
        personales = {h for h, i in catalogo_docs.items() if i.personal}
        ideas = RecolectorIdeas().recolectar(fichas, personales)
        candidatas = AgrupadorIdeas(self._vectores).agrupar(ideas)
        return PuntuadorCandidatas(self._vectores, self._catalogo()).puntuar(candidatas), fichas, documentos

    def _catalogo(self):
        """Cursos del catálogo actual."""
        return LectorCatalogo().leer(list(self._propuestas.catalogos))

    @staticmethod
    def _markdown(propuesta, documentos) -> str:
        """Markdown con la plantilla de su tipo."""
        redactor = (RedactorPropuestaCurso if propuesta.tipo == "curso" else RedactorPropuestaPildora)(
            documentos, Path.home())
        return redactor.redactar(propuesta)

    @staticmethod
    def _informe_candidatas(candidatas: list[Candidata], documentos) -> str:
        """Informe con las 40 mejores candidatas de cada tipo y su desglose."""
        partes = ["# Orakulue — Candidatas a propuesta",
                  f"{datetime.now():%d/%m/%Y %H:%M}. {len(candidatas)} candidatas. Puntuación desglosada: "
                  "respaldo (documentos y su interés), ejercicios, vigencia, euskera y relación con el catálogo."]
        for tipo, titulo in (("curso", "Cursos"), ("pildora", "Píldoras")):
            filas = [
                f"| {n} | {c.titulo} | {len(c.huellas)} | {c.puntuacion} | "
                + ", ".join(f"{k} {v}" for k, v in c.desglose.items()) + f" | {c.en_catalogo} |"
                for n, c in enumerate([x for x in candidatas if x.tipo == tipo][:40], start=1)
            ]
            partes.append(f"## {titulo}\n\n| # | Candidata | Documentos | Puntos | Desglose | Catálogo |\n"
                          "|---:|---|---:|---:|---|---|\n" + "\n".join(filas))
        return "\n\n".join(partes) + "\n"

    @staticmethod
    def _informe_prueba(elegidas, modelos, filas, costes, aviso) -> str:
        """Informe comparativo de la prueba."""
        cabecera = "| Propuesta | " + " | ".join(modelos) + " |"
        separador = "|---|" + "---|" * len(modelos)
        cuerpo = []
        for c in elegidas:
            celdas = []
            for m in modelos:
                valor = filas.get(c.clave, {}).get(m, "—")
                celdas.append(f"[abrir]({valor})" if valor.startswith("/") else valor)
            cuerpo.append(f"| [{c.tipo}] {c.titulo} | " + " | ".join(celdas) + " |")
        coste = "\n".join(f"- {m}: {v:.4f} $".replace(".", ",") for m, v in costes.items())
        return "\n\n".join([
            "# Orakulue — Prueba de modelos para las propuestas",
            f"{datetime.now():%d/%m/%Y %H:%M}. Tarifas del {FECHA_TARIFAS}.",
            "\n".join([cabecera, separador, *cuerpo]),
            f"## Coste\n\n{coste}",
            "## Saldo\n\n" + aviso.replace("\n", "\n\n"),
        ]) + "\n"
