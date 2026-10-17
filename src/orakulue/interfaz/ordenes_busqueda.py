"""Órdenes de la fase 5: ``indexar``, ``buscar``, ``preguntar`` y
``evaluar-busqueda``.

Todas son locales y gratuitas salvo ``preguntar`` sin ``--local``, que usa la
API (muy barato) y anota el gasto como la fase 4.
"""

import sys
from datetime import datetime
from pathlib import Path

from orakulue.aplicacion.aviso_saldo import AvisoSaldo
from orakulue.aplicacion.buscador import Buscador
from orakulue.aplicacion.catalogo_documentos import CatalogoDocumentos
from orakulue.aplicacion.evaluador_busqueda import EvaluadorBusqueda
from orakulue.aplicacion.indexador import Indexador
from orakulue.aplicacion.preparador_peticion import INSTRUCCIONES
from orakulue.aplicacion.respondedor import Respondedor
from orakulue.infraestructura.almacen_analisis import AlmacenAnalisis
from orakulue.infraestructura.almacen_fichas import AlmacenFichas
from orakulue.infraestructura.almacen_indice import AlmacenIndice
from orakulue.infraestructura.almacen_inventario import AlmacenInventario
from orakulue.infraestructura.almacen_textos import AlmacenTextos
from orakulue.infraestructura.catalogo_tarifas import FECHA_TARIFAS, CatalogoTarifas
from orakulue.infraestructura.cliente_local import ClienteLocal
from orakulue.infraestructura.cliente_modelo import ClienteModelo, ErrorLlamada
from orakulue.infraestructura.cliente_vectores import ClienteVectores, ErrorVectores
from orakulue.infraestructura.configuracion import Configuracion
from orakulue.infraestructura.error_saldo_agotado import ErrorSaldoAgotado
from orakulue.infraestructura.registro_consumo import RegistroConsumo
from orakulue.utilidades.formato import Formato


class OrdenesBusqueda:
    """Ejecuta las órdenes del buscador."""

    def __init__(self, configuracion: Configuracion) -> None:
        """Prepara las órdenes.

        Args:
            configuracion: configuración completa.
        """
        self._configuracion = configuracion
        self._base = configuracion.base_datos
        self._datos = configuracion.base_datos.parent
        self._vectores = ClienteVectores()

    def indexar(self) -> int:
        """Crea o actualiza el índice.

        Returns:
            0 si va bien; 1 si Ollama no responde.
        """
        with AlmacenInventario(self._base) as inventario:
            documentos = list(inventario.documentos())
        with AlmacenFichas(self._base) as fichas:
            datos_fichas = fichas.con_datos()
        with AlmacenIndice(self._base) as indice, AlmacenTextos(self._base, self._datos / "textos") as textos:
            try:
                resumen = Indexador(indice, self._vectores, avisar_avance=lambda q, n, t: print(
                    f"  {q}: {Formato.cifra(n)} de {Formato.cifra(t)}", flush=True
                )).ejecutar(documentos, textos, datos_fichas)
            except ErrorVectores as error:
                print(f"Indexación detenida: {error}\nLo hecho se conserva; vuelve a lanzar la orden.",
                      file=sys.stderr)
                return 1
            cifras = indice.cifras()
        print(
            f"Indexados {Formato.cifra(resumen.documentos)} documentos ({Formato.cifra(resumen.trozos)} trozos) "
            f"y {Formato.cifra(resumen.fichas)} fichas; quitados {resumen.olvidados}.\n"
            f"Índice: {Formato.cifra(cifras.get('trozo', 0))} trozos y {Formato.cifra(cifras.get('ficha', 0))} fichas."
        )
        return 0

    def buscar(self, consulta: str, cantidad: int, modo: str) -> int:
        """Muestra los documentos que mejor responden a una consulta."""
        try:
            with AlmacenIndice(self._base) as indice:
                resultados = Buscador(indice, self._vectores, self._catalogo()).buscar(consulta, cantidad, modo)
        except ErrorVectores as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        if not resultados:
            print("Nada encontrado.")
        for numero, r in enumerate(resultados, start=1):
            info = r.info
            marcas = " · ".join(x for x in (info.materia, f"interés {info.interes}" if info.interes else "",
                                             "DATOS PERSONALES" if info.personal else "") if x)
            pasaje = " ".join(r.pasaje.split())[:220]
            print(f"\n{numero}. {info.titulo}" + (f"  [{marcas}]" if marcas else ""))
            print(f"   {Formato.ruta(info.rutas[0], Path.home())}")
            if info.ruta_ficha:
                print(f"   ficha: {Formato.ruta(info.ruta_ficha, Path.home())}")
            print(f"   «{pasaje}…»")
        return 0

    def preguntar(self, pregunta: str, local: bool) -> int:
        """Responde a una pregunta citando las fuentes."""
        fichas = self._configuracion.fichas
        try:
            with AlmacenIndice(self._base) as indice:
                respondedor = Respondedor(Buscador(indice, self._vectores, self._catalogo()))
                if local:
                    respuesta = respondedor.responder(pregunta, local=ClienteLocal())
                else:
                    cliente = ClienteModelo(fichas.variable_clave, INSTRUCCIONES, fichas.esfuerzo)
                    respuesta = respondedor.responder(pregunta, cliente=cliente, modelo=fichas.modelo)
        except (ErrorVectores, ErrorLlamada, ErrorSaldoAgotado) as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        print(respuesta.texto.strip() + "\n\nFuentes:")
        for numero, info in enumerate(respuesta.fuentes, start=1):
            print(f"  [{numero}] {info.titulo} — {Formato.ruta(info.rutas[0], Path.home())}")
        if respuesta.omitidos_por_privacidad:
            print(f"\n{respuesta.omitidos_por_privacidad} documentos relevantes tienen datos personales y no se "
                  "han enviado a la API. Con --local se usarían sin salir del equipo.")
        if respuesta.consumo is not None:
            with RegistroConsumo(self._base) as registro:
                ejecucion = f"pregunta-{datetime.now():%Y%m%d-%H%M%S}"
                coste = CatalogoTarifas().de(respuesta.consumo.modelo).coste(respuesta.consumo)
                registro.anotar(ejecucion, None, respuesta.consumo, coste)
                aviso = AvisoSaldo(fichas.variable_clave, fichas.saldo_declarado,
                                   registro.gastado(), coste, FECHA_TARIFAS)
            # Tras cada pregunta solo se recuerda el saldo si va bajo: el
            # aviso completo en cada consulta sería ruido.
            print(f"\nCoste de la pregunta: {coste:.4f} $".replace(".", ","))
            if aviso.es_bajo:
                print(aviso.redactar())
        return 0

    def evaluar(self, ruta_preguntas: Path) -> int:
        """Evalúa el buscador con el juego de preguntas y escribe un informe."""
        try:
            preguntas = EvaluadorBusqueda.leer(ruta_preguntas)
        except FileNotFoundError:
            print(f"No existe el juego de preguntas {ruta_preguntas}.", file=sys.stderr)
            return 1
        evaluador = EvaluadorBusqueda()
        try:
            with AlmacenIndice(self._base) as indice:
                buscador = Buscador(indice, self._vectores, self._catalogo())
                resultados = [evaluador.evaluar(buscador, preguntas, m) for m in Buscador.MODOS]
        except ErrorVectores as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        filas = [f"| {r.modo} | {r.acierto:.0%} | {r.rango_reciproco:.2f} |".replace(".", ",") for r in resultados]
        fallos = [f"- **{r.modo}**: " + "; ".join(f"«{f}»" for f in r.fallos) for r in resultados if r.fallos]
        informe = "\n\n".join([
            "# Orakulue — Evaluación del buscador",
            f"{datetime.now():%d/%m/%Y %H:%M}. {len(preguntas)} preguntas de `{ruta_preguntas.name}`.",
            "| Modo | Acierto en 10 | Rango recíproco medio |\n|---|---:|---:|\n" + "\n".join(filas),
            "## Preguntas sin acierto\n\n" + ("\n".join(fallos) if fallos else "Ninguna."),
        ]) + "\n"
        ruta = self._configuracion.carpeta_informes / f"evaluacion-busqueda-{datetime.now():%Y%m%d-%H%M}.md"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(informe, encoding="utf-8")
        print("\n".join(filas) + f"\nInforme: {ruta}")
        return 0

    def _catalogo(self):
        """Información de presentación de cada documento."""
        with AlmacenInventario(self._base) as inventario:
            documentos = list(inventario.documentos())
        with AlmacenFichas(self._base) as fichas:
            todas = fichas.todas()
            huellas = {ruta: h for h, (_, _, ruta) in fichas.con_datos().items()}
        with AlmacenAnalisis(self._base) as analisis:
            marcas = analisis.marcas()
        return CatalogoDocumentos().construir(documentos, todas, huellas, marcas)
