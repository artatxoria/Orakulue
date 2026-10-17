"""Caso de uso: fichar todo el fondo con la API por lotes.

Tres pasos: enviar las peticiones pendientes en un lote, esperar a que el
proveedor lo procese y recoger los resultados. Cada paso deja constancia en la
base de datos, de modo que si algo se corta se continúa donde se quedó.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from orakulue.aplicacion.preparador_peticion import PreparadorPeticion
from orakulue.aplicacion.seleccion_fichables import Fichable
from orakulue.dominio.ficha import Ficha, FichaNoValida
from orakulue.infraestructura.almacen_fichas import AlmacenFichas
from orakulue.infraestructura.almacen_textos import AlmacenTextos
from orakulue.infraestructura.catalogo_tarifas import CatalogoTarifas
from orakulue.infraestructura.cliente_modelo import ClienteModelo, ErrorLlamada
from orakulue.infraestructura.registro_consumo import RegistroConsumo

if TYPE_CHECKING:
    # Solo para la anotación: el redactor llega ya construido desde la interfaz.
    from orakulue.interfaz.redactor_ficha import RedactorFicha


@dataclass
class ResultadoRecogida:
    """Lo recogido de un lote. Solo la usa ``FichadoFondo``.

    Atributos:
        con_interes: fichas escritas en la carpeta principal.
        sin_interes: fichas mínimas escritas en ``_sin_interes``.
        errores: explicación por huella de lo que no ha dado ficha.
    """

    con_interes: int = 0
    sin_interes: int = 0
    errores: dict[str, str] = field(default_factory=dict)


class FichadoFondo:
    """Envía, espera y recoge el lote de fichas."""

    #: Segundos entre consultas del estado del lote. La mayoría de los lotes
    #: terminan en menos de una hora; consultar más a menudo no adelanta nada.
    INTERVALO = 60

    def pendientes(self, fichables: list[Fichable], hechas: set[str]) -> list[Fichable]:
        """Contenidos que aún no tienen ficha."""
        return [f for f in fichables if f.huella not in hechas]

    def enviar(
        self, pendientes: list[Fichable], modelo: str, cliente: ClienteModelo,
        textos: AlmacenTextos, fichas: AlmacenFichas,
    ) -> str:
        """Prepara las peticiones, envía el lote y lo registra.

        Returns:
            Identificador del lote.
        """
        preparador = PreparadorPeticion()
        peticiones = [
            preparador.preparar(f.huella, f.rutas[0], textos.leer(f.huella), f.idioma) for f in pendientes
        ]
        identificador = cliente.crear_lote(modelo, peticiones)
        fichas.registrar_lote(identificador, modelo, len(peticiones))
        return identificador

    def esperar(
        self, identificador: str, cliente: ClienteModelo,
        avisar: Callable[[dict[str, int]], None] | None = None,
        dormir: Callable[[float], None] = time.sleep,
    ) -> dict[str, int]:
        """Espera a que el proveedor termine el lote.

        Args:
            identificador: lote.
            cliente: cliente del proveedor.
            avisar: función opcional que recibe el recuento en cada consulta.
            dormir: función de espera (sustituible en las pruebas).

        Returns:
            Recuento final por estado.
        """
        while True:
            terminado, cuentas = cliente.estado_lote(identificador)
            if avisar:
                avisar(cuentas)
            if terminado:
                return cuentas
            dormir(self.INTERVALO)

    def recoger(
        self,
        identificador: str,
        fichables: dict[str, Fichable],
        cliente: ClienteModelo,
        fichas: AlmacenFichas,
        registro: RegistroConsumo | None,
        ejecucion: str,
        carpeta: Path,
        redactor: "RedactorFicha",
    ) -> ResultadoRecogida:
        """Descarga los resultados, escribe las fichas y anota el gasto.

        Lo que falla no se registra como hecho, así que la próxima ejecución
        lo volverá a pedir. El gasto de las respuestas inutilizables también
        se anota: se ha pagado.

        Args:
            identificador: lote terminado.
            fichables: contenidos por huella, para saber rutas y familia.
            cliente: cliente del proveedor.
            fichas: almacén de fichas.
            registro: registro de consumo, o ``None`` al reescribir fichas de
                un lote ya recogido: esas llamadas ya están anotadas y pagadas,
                y anotarlas otra vez falsearía el aviso de saldo.
            ejecucion: identificador de esta ejecución.
            carpeta: carpeta de las fichas.
            redactor: convierte la ficha en Markdown.

        Returns:
            Lo recogido.
        """
        tarifas, resultado = CatalogoTarifas(), ResultadoRecogida()
        for huella, mensaje, fallo in cliente.resultados_lote(identificador):
            fichable = fichables.get(huella)
            if mensaje is None or fichable is None:
                resultado.errores[huella] = fallo or "contenido que ya no está en el inventario"
                continue
            try:
                datos, consumo = ClienteModelo.interpretar(mensaje, por_lotes=True)
                ficha = Ficha(huella, fichable.rutas, consumo.modelo, datos, fichable.familia)
            except (ErrorLlamada, FichaNoValida) as error:
                resultado.errores[huella] = str(error)
                consumo, ficha = getattr(error, "consumo", None), None
            if consumo is not None and registro is not None:
                registro.anotar(ejecucion, huella, consumo, tarifas.de(consumo.modelo).coste(consumo))
            if ficha is None:
                continue
            destino = (carpeta / "_sin_interes" if ficha.sin_interes else carpeta) / redactor.nombre_fichero(ficha)
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(redactor.redactar(ficha), encoding="utf-8")
            fichas.guardar(ficha, destino)
            if ficha.sin_interes:
                resultado.sin_interes += 1
            else:
                resultado.con_interes += 1
        fichas.marcar_recogido(identificador)
        return resultado
