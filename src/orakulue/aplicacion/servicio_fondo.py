"""Caso de uso: fachada única del fondo para la web y el conector de Claude.

Reúne en un solo objeto lo que necesitan las dos puertas de entrada (buscar,
leer fichas y pasajes, descargar originales, preguntar), para que ninguna
duplique lógica. El índice se carga una sola vez y se comparte entre las
peticiones, protegido con un cerrojo.

Regla de privacidad que se aplica aquí, en un solo sitio: de un documento con
datos personales se puede saber que existe y dónde está, pero **su texto y su
ficha no salen** por ninguna de las dos puertas cuando el destino es un
servicio externo.
"""

import threading
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from orakulue.aplicacion.agrupador_variantes import AgrupadorVariantes
from orakulue.aplicacion.buscador import Buscador, ResultadoBusqueda
from orakulue.aplicacion.catalogo_documentos import CatalogoDocumentos
from orakulue.aplicacion.preparador_peticion import INSTRUCCIONES
from orakulue.aplicacion.respondedor import Respondedor, Respuesta
from orakulue.dominio.info_documento import InfoDocumento
from orakulue.infraestructura.almacen_analisis import AlmacenAnalisis
from orakulue.infraestructura.almacen_fichas import AlmacenFichas
from orakulue.infraestructura.almacen_indice import AlmacenIndice
from orakulue.infraestructura.almacen_inventario import AlmacenInventario
from orakulue.infraestructura.almacen_propuestas import AlmacenPropuestas
from orakulue.infraestructura.catalogo_tarifas import CatalogoTarifas
from orakulue.infraestructura.cliente_local import ClienteLocal
from orakulue.infraestructura.cliente_modelo import ClienteModelo
from orakulue.infraestructura.cliente_vectores import ClienteVectores
from orakulue.infraestructura.configuracion import Configuracion
from orakulue.infraestructura.registro_consumo import RegistroConsumo
from orakulue.utilidades.clasificador_materias import ClasificadorMaterias


@dataclass(frozen=True)
class RespuestaConCoste:
    """Respuesta a una pregunta y lo que ha costado. Solo la usa ``ServicioFondo``.

    Atributos:
        respuesta: la respuesta con sus fuentes.
        coste: dólares gastados (0 en local).
    """

    respuesta: Respuesta
    coste: Decimal


class ServicioFondo:
    """Acceso de solo lectura al fondo (salvo el gasto de las preguntas)."""

    def __init__(self, configuracion: Configuracion, vectores: ClienteVectores | None = None) -> None:
        """Abre el índice y construye el catálogo.

        Args:
            configuracion: configuración completa.
            vectores: cliente de vectores (sustituible en pruebas).
        """
        self._configuracion = configuracion
        self._vectores = vectores or ClienteVectores()
        self._cerrojo = threading.Lock()
        self._indice = AlmacenIndice(configuracion.base_datos, entre_hilos=True)
        self.recargar()

    def recargar(self) -> None:
        """Vuelve a leer inventario, fichas y marcas (tras indexar de nuevo)."""
        base = self._configuracion.base_datos
        with AlmacenInventario(base) as inventario:
            documentos = list(inventario.documentos())
        with AlmacenFichas(base) as fichas:
            todas = fichas.todas()
            huellas = {ruta: h for h, (_, _, ruta) in fichas.con_datos().items()}
        with AlmacenAnalisis(base) as analisis:
            marcas, grupos = analisis.marcas(), analisis.grupos()
        catalogo = CatalogoDocumentos().construir(documentos, todas, huellas, marcas)
        with self._cerrojo:
            self._catalogo = catalogo
            self._buscador = Buscador(self._indice, self._vectores, catalogo,
                                      AgrupadorVariantes().agrupar(catalogo, grupos))

    def buscar(self, consulta: str, cantidad: int = 10, modo: str = "hibrido") -> list[ResultadoBusqueda]:
        """Búsqueda híbrida (local, gratis)."""
        with self._cerrojo:
            return self._buscador.buscar(consulta, cantidad, modo)

    def documento(self, huella: str) -> InfoDocumento | None:
        """Información de un documento, o ``None`` si no está en el inventario."""
        return self._catalogo.get(huella)

    def ficha(self, huella: str, para_fuera: bool) -> str | None:
        """Markdown de la ficha de un documento.

        Args:
            huella: contenido.
            para_fuera: si el texto va a salir hacia un servicio externo (el
                conector de Claude). Entonces no se da la ficha de un documento
                con datos personales.

        Returns:
            El Markdown, o ``None`` si no hay ficha o no se puede dar.
        """
        info = self._catalogo.get(huella)
        if info is None or info.ruta_ficha is None or (para_fuera and info.personal):
            return None
        return info.ruta_ficha.read_text(encoding="utf-8") if info.ruta_ficha.is_file() else None

    def pasajes(self, huella: str, consulta: str, cantidad: int = 3, para_fuera: bool = True) -> list[str]:
        """Los pasajes de un documento que mejor casan con una consulta.

        Returns:
            Textos, vacío si el documento es personal y el destino es externo.
        """
        info = self._catalogo.get(huella)
        if info is None or (para_fuera and info.personal):
            return []
        with self._cerrojo:
            # Se busca con margen y se filtra por documento: el buscador
            # devuelve las piezas de cada resultado ordenadas.
            for resultado in self._buscador.buscar(consulta, 50):
                if huella in {resultado.info.huella, *(v.huella for v in resultado.variantes)}:
                    textos = [self._buscador.texto_pieza(p) for p in resultado.piezas]
                    return [t for tipo, t in textos if tipo == "trozo"][:cantidad]
        return []

    def original(self, huella: str) -> Path | None:
        """Fichero original de un documento, para descargarlo.

        Solo se devuelven rutas del inventario, elegidas por huella: nunca una
        ruta que venga de fuera. Así no se puede pedir ningún fichero que no
        sea un documento del fondo.
        """
        info = self._catalogo.get(huella)
        if info is None:
            return None
        return next((r for r in info.rutas if r.is_file()), None)

    def materias(self) -> dict[str, list[InfoDocumento]]:
        """Documentos con ficha e interés formativo, por materia."""
        por_materia: dict[str, list[InfoDocumento]] = defaultdict(list)
        orden = {"alto": 0, "medio": 1, "bajo": 2}
        for info in self._catalogo.values():
            if info.materia and info.interes in orden:
                por_materia[info.materia].append(info)
        for lista in por_materia.values():
            lista.sort(key=lambda i: (orden[i.interes], i.titulo.lower()))
        return dict(sorted(por_materia.items(),
                           key=lambda par: (par[0] == ClasificadorMaterias.OTRAS, -len(par[1]))))

    def propuestas(self) -> list:
        """Propuestas redactadas (fase 7) con su fichero, de mejor a peor."""
        with AlmacenPropuestas(self._configuracion.base_datos) as almacen:
            return almacen.todas()

    def propuesta(self, clave: str) -> tuple | None:
        """Una propuesta y su Markdown, o ``None`` si no existe."""
        with AlmacenPropuestas(self._configuracion.base_datos) as almacen:
            encontrada = almacen.por_clave(clave)
        if encontrada is None:
            return None
        propuesta, ruta = encontrada
        return propuesta, ruta.read_text(encoding="utf-8") if ruta.is_file() else ""

    def preguntar(self, pregunta: str, local: bool) -> RespuestaConCoste:
        """Responde a una pregunta y anota el gasto si se usa la API.

        Raises:
            ErrorLlamada, ErrorSaldoAgotado, ErrorVectores: como en la línea
                de órdenes.
        """
        fichas = self._configuracion.fichas
        with self._cerrojo:
            respondedor = Respondedor(self._buscador)
            if local:
                return RespuestaConCoste(respondedor.responder(pregunta, local=ClienteLocal()), Decimal(0))
            cliente = ClienteModelo(fichas.variable_clave, INSTRUCCIONES, fichas.esfuerzo)
            respuesta = respondedor.responder(pregunta, cliente=cliente, modelo=fichas.modelo)
        coste = Decimal(0)
        if respuesta.consumo is not None:
            coste = CatalogoTarifas().de(respuesta.consumo.modelo).coste(respuesta.consumo)
            with RegistroConsumo(self._configuracion.base_datos) as registro:
                registro.anotar(f"web-{datetime.now():%Y%m%d-%H%M%S}", None, respuesta.consumo, coste)
        return RespuestaConCoste(respuesta, coste)

    def cerrar(self) -> None:
        """Cierra el índice."""
        self._indice.__exit__()
