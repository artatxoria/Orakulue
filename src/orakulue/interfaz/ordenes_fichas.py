"""Órdenes de la fase 4.

- ``prueba-modelos``: simulacro de la prueba comparativa (muestra, coste
  estimado y presupuesto del fondo). Con ``--ejecutar``, la hace de verdad.
- ``fichar``: simulacro del fichado del fondo (cuántas fichas y cuánto
  costará). Con ``--ejecutar``, envía el lote, espera y recoge. Si hay un lote
  enviado sin recoger, lo recoge primero: ya está pagado. Con
  ``--reescribir``, vuelve a descargar el último lote recogido (gratis) y
  reescribe sus fichas sin anotar gasto.

Las fichas de la prueba se guardan en ``datos/prueba_modelos/``, fuera de git y
fuera de la carpeta definitiva de fichas: son para comparar, no para quedarse.
"""

import sys
from datetime import datetime
from pathlib import Path

from orakulue.aplicacion.aviso_saldo import AvisoSaldo
from orakulue.aplicacion.estimador_coste import EstimadorCoste
from orakulue.aplicacion.fichado_fondo import FichadoFondo
from orakulue.aplicacion.preparador_peticion import INSTRUCCIONES
from orakulue.aplicacion.prueba_comparativa import PruebaComparativa
from orakulue.aplicacion.seleccion_fichables import ResultadoSeleccion, SeleccionFichables
from orakulue.infraestructura.almacen_analisis import AlmacenAnalisis
from orakulue.infraestructura.almacen_fichas import AlmacenFichas
from orakulue.infraestructura.almacen_inventario import AlmacenInventario
from orakulue.infraestructura.almacen_textos import AlmacenTextos
from orakulue.infraestructura.catalogo_tarifas import FECHA_TARIFAS, CatalogoTarifas
from orakulue.infraestructura.cliente_modelo import ClienteModelo, ErrorLlamada
from orakulue.infraestructura.configuracion import Configuracion
from orakulue.infraestructura.error_saldo_agotado import ErrorSaldoAgotado
from orakulue.infraestructura.registro_consumo import RegistroConsumo
from orakulue.interfaz.indice_fichas import IndiceFichas
from orakulue.interfaz.informe_prueba import InformePrueba
from orakulue.interfaz.redactor_ficha import RedactorFicha


class OrdenesFichas:
    """Ejecuta las órdenes de la fase 4."""

    def __init__(self, configuracion: Configuracion) -> None:
        """Prepara las órdenes.

        Args:
            configuracion: configuración completa.
        """
        self._configuracion = configuracion
        self._fichas = configuracion.fichas
        self._datos = configuracion.base_datos.parent

    def prueba_modelos(self, ejecutar: bool) -> int:
        """Simulacro o ejecución de la prueba comparativa.

        Args:
            ejecutar: si se llama de verdad a los modelos.

        Returns:
            0 si todo va bien; 1 si se agota el saldo o falta la clave.
        """
        seleccion = self._seleccionar()
        prueba = PruebaComparativa()
        muestra = prueba.muestra(seleccion.fichables, self._fichas.documentos_prueba)
        modelos = list(self._fichas.modelos_prueba)
        sello = datetime.now().strftime("%Y%m%d-%H%M")
        ruta = self._configuracion.carpeta_informes / f"prueba-modelos-{sello}.md"

        if not ejecutar:
            InformePrueba(seleccion, muestra, modelos, Path.home()).escribir(ruta)
            print(f"Simulacro: {len(muestra)} documentos y {len(modelos)} modelos; no se ha gastado nada.\n"
                  f"Informe: {ruta}")
            return 0

        ejecucion = f"prueba-{sello}"
        try:
            cliente = ClienteModelo(self._fichas.variable_clave, INSTRUCCIONES, self._fichas.esfuerzo)
        except ErrorLlamada as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        resultados, codigo = None, 0
        with RegistroConsumo(self._configuracion.base_datos) as registro, \
                AlmacenTextos(self._configuracion.base_datos, self._datos / "textos") as textos:
            try:
                resultados = prueba.ejecutar(
                    muestra, modelos, cliente, textos, registro, ejecucion,
                    self._datos / "prueba_modelos" / sello, RedactorFicha(Path.home()),
                    avisar_avance=lambda m, n, t: print(f"  {m}: {n} de {t}", flush=True),
                )
            except ErrorSaldoAgotado as error:
                print(f"Prueba detenida.\n{error}", file=sys.stderr)
                codigo = 1
            aviso = AvisoSaldo(
                self._fichas.variable_clave, self._fichas.saldo_declarado,
                registro.gastado(), registro.gastado(ejecucion), FECHA_TARIFAS,
            ).redactar()
        InformePrueba(seleccion, muestra, modelos, Path.home(), resultados or [], aviso).escribir(ruta)
        print(f"{aviso}\nInforme: {ruta}")
        return codigo

    def fichar(self, ejecutar: bool) -> int:
        """Simulacro o fichado del fondo completo por lotes.

        Args:
            ejecutar: si se envía de verdad.

        Returns:
            0 si todo va bien; 1 si falta la clave, se agota el saldo o falla
            el proveedor.
        """
        base, modelo = self._configuracion.base_datos, self._fichas.modelo
        seleccion = self._seleccionar()
        fichado = FichadoFondo()
        with AlmacenFichas(base) as fichas, RegistroConsumo(base) as registro:
            pendiente = fichas.lote_pendiente()
            pendientes = fichado.pendientes(seleccion.fichables, fichas.hechas())
            salida = registro.salida_media(modelo)
        if not ejecutar and pendiente is None:
            coste = EstimadorCoste().estimar(pendientes, CatalogoTarifas().de(modelo), True, salida)
            importe = f"{coste:.2f}".replace(".", ",")
            print(
                f"Simulacro: {len(pendientes)} fichas pendientes con {modelo} por lotes.\n"
                f"Coste estimado: {importe} $ "
                + (f"(con {salida} tokens de salida por ficha, medidos en la prueba).\n" if salida
                   else "(sin medición previa).\n")
                + "No se ha gastado nada. Para fichar: orakulue fichar --ejecutar"
            )
            return 0

        try:
            cliente = ClienteModelo(self._fichas.variable_clave, INSTRUCCIONES, self._fichas.esfuerzo)
        except ErrorLlamada as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        sello = datetime.now().strftime("%Y%m%d-%H%M")
        ejecucion, codigo = f"fichas-{sello}", 0
        with AlmacenFichas(base) as fichas, RegistroConsumo(base) as registro, \
                AlmacenTextos(base, self._datos / "textos") as textos:
            try:
                if pendiente is None:
                    if not pendientes:
                        print("No hay fichas pendientes.")
                        return 0
                    identificador = fichado.enviar(pendientes, modelo, cliente, textos, fichas)
                    print(f"Lote {identificador} enviado con {len(pendientes)} peticiones.", flush=True)
                else:
                    identificador = pendiente[0]
                    print(f"Hay un lote enviado sin recoger ({identificador}); se recoge antes de nada.")
                fichado.esperar(identificador, cliente, avisar=lambda c: print(
                    "  " + ", ".join(f"{n} {e}" for e, n in c.items() if n), flush=True))
                resultado = fichado.recoger(
                    identificador, {f.huella: f for f in seleccion.fichables}, cliente, fichas,
                    registro, ejecucion, self._fichas.carpeta, RedactorFicha(Path.home()),
                )
                indice = IndiceFichas().escribir(self._fichas.carpeta, fichas.todas())
                print(
                    f"Fichas escritas: {resultado.con_interes} con interés formativo y "
                    f"{resultado.sin_interes} sin interés. Sin ficha: {len(resultado.errores)}.\n"
                    f"Índice: {indice}"
                )
                for huella, motivo in list(resultado.errores.items())[:20]:
                    print(f"  sin ficha {huella[:12]}…: {motivo}", file=sys.stderr)
            except ErrorSaldoAgotado as error:
                print(f"Fichado detenido.\n{error}", file=sys.stderr)
                codigo = 1
            except ErrorLlamada as error:
                print(f"Fichado detenido: {error}\nVuelve a lanzar la orden para continuar.", file=sys.stderr)
                codigo = 1
            print(AvisoSaldo(
                self._fichas.variable_clave, self._fichas.saldo_declarado,
                registro.gastado(), registro.gastado(ejecucion), FECHA_TARIFAS,
            ).redactar())
        return codigo

    def reescribir(self) -> int:
        """Reescribe las fichas del último lote recogido, sin coste.

        El proveedor conserva los resultados de un lote 29 días. Descargarlos
        otra vez es gratis; sirve para aplicar mejoras de formato o rellenar
        los datos guardados de cada ficha sin volver a pagar.

        Returns:
            0 si todo va bien; 1 si no hay lote o falla el proveedor.
        """
        base = self._configuracion.base_datos
        seleccion = self._seleccionar()
        try:
            cliente = ClienteModelo(self._fichas.variable_clave, INSTRUCCIONES, self._fichas.esfuerzo)
        except ErrorLlamada as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        with AlmacenFichas(base) as fichas:
            identificador = fichas.ultimo_lote_recogido()
            if identificador is None:
                print("No hay ningún lote recogido que reescribir.")
                return 1
            try:
                resultado = FichadoFondo().recoger(
                    identificador, {f.huella: f for f in seleccion.fichables}, cliente, fichas, None,
                    "reescritura", self._fichas.carpeta, RedactorFicha(Path.home()),
                )
            except ErrorLlamada as error:
                print(f"No se ha podido descargar el lote: {error}", file=sys.stderr)
                return 1
            indice = IndiceFichas().escribir(self._fichas.carpeta, fichas.todas())
        print(f"Reescritas {resultado.con_interes + resultado.sin_interes} fichas del lote {identificador}, "
              f"sin coste. Índice: {indice}")
        return 0

    def _seleccionar(self) -> ResultadoSeleccion:
        """Aplica las reglas de selección sobre el inventario y los análisis."""
        base = self._configuracion.base_datos
        with AlmacenInventario(base) as inventario:
            documentos = list(inventario.documentos())
        with AlmacenTextos(base, self._datos / "textos") as textos:
            metadatos = list(textos.metadatos())
        with AlmacenAnalisis(base) as analisis:
            marcas, grupos = analisis.marcas(), analisis.grupos()
        return SeleccionFichables().seleccionar(documentos, metadatos, marcas, grupos)
