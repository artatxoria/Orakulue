"""Caso de uso: fichar una muestra con varios modelos para elegir uno.

La muestra se elige variada (idiomas, formatos, longitudes) y siempre la misma
para una misma selección, para que repetir la prueba compare lo mismo.
"""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from orakulue.aplicacion.preparador_peticion import PreparadorPeticion
from orakulue.aplicacion.seleccion_fichables import Fichable
from orakulue.dominio.consumo_llamada import ConsumoLlamada
from orakulue.dominio.ficha import Ficha, FichaNoValida
from orakulue.infraestructura.almacen_textos import AlmacenTextos
from orakulue.infraestructura.catalogo_tarifas import CatalogoTarifas
from orakulue.infraestructura.cliente_modelo import ClienteModelo, ErrorLlamada
from orakulue.infraestructura.registro_consumo import RegistroConsumo

if TYPE_CHECKING:
    # Solo para la anotación de tipos: la aplicación no depende de la interfaz,
    # recibe el redactor ya construido.
    from orakulue.interfaz.redactor_ficha import RedactorFicha


@dataclass
class ResultadoModelo:
    """Lo obtenido con un modelo en la prueba. Solo la usa ``PruebaComparativa``.

    Atributos:
        modelo: identificador.
        fichas: ficha escrita por huella.
        errores: mensaje de error por huella.
        entrada: tokens de entrada (incluida caché).
        salida: tokens de salida.
        coste: dólares gastados.
    """

    modelo: str
    fichas: dict[str, Path] = field(default_factory=dict)
    errores: dict[str, str] = field(default_factory=dict)
    entrada: int = 0
    salida: int = 0
    coste: Decimal = Decimal(0)


class PruebaComparativa:
    """Elige la muestra y la ficha con cada modelo."""

    def muestra(self, fichables: list[Fichable], cantidad: int) -> list[Fichable]:
        """Elige una muestra variada.

        Se agrupa por idioma, familia de formato y longitud, y se toma uno de
        cada grupo por turnos hasta completar la cantidad. El euskera va primero
        porque es donde más se espera que difieran los modelos.

        Args:
            fichables: todos los contenidos que se pueden fichar.
            cantidad: tamaño de la muestra.

        Returns:
            Los elegidos.
        """
        grupos: dict[tuple, list[Fichable]] = defaultdict(list)
        for fichable in sorted(fichables, key=lambda f: f.huella):
            grupos[(fichable.idioma != "eu", self._formato(fichable), self._longitud(fichable))].append(fichable)
        colas = [grupos[clave] for clave in sorted(grupos)]
        elegidos: list[Fichable] = []
        while len(elegidos) < cantidad and any(colas):
            for cola in colas:
                if cola and len(elegidos) < cantidad:
                    elegidos.append(cola.pop(0))
        return elegidos

    def ejecutar(
        self,
        muestra: list[Fichable],
        modelos: list[str],
        cliente: ClienteModelo,
        textos: AlmacenTextos,
        registro: RegistroConsumo,
        ejecucion: str,
        carpeta: Path,
        redactor: "RedactorFicha",
        avisar_avance: Callable[[str, int, int], None] | None = None,
    ) -> list[ResultadoModelo]:
        """Ficha la muestra con cada modelo y guarda las fichas para compararlas.

        Cada llamada se anota en el registro de consumo al momento. La falta
        de saldo (``ErrorSaldoAgotado``) no se captura: es el único error que
        debe cortar la prueba.

        Args:
            muestra: contenidos de la prueba.
            modelos: modelos que se comparan.
            cliente: cliente del proveedor.
            textos: almacén de textos.
            registro: registro de consumo.
            ejecucion: identificador de esta ejecución.
            carpeta: dónde se guardan las fichas, una subcarpeta por modelo.
            redactor: convierte las fichas en Markdown.
            avisar_avance: función opcional (modelo, hechos, total).

        Returns:
            Un resultado por modelo.
        """
        preparador, tarifas = PreparadorPeticion(), CatalogoTarifas()
        resultados = []
        for modelo in modelos:
            resultado = ResultadoModelo(modelo)
            for numero, fichable in enumerate(muestra, start=1):
                peticion = preparador.preparar(
                    fichable.huella, fichable.rutas[0], textos.leer(fichable.huella), fichable.idioma
                )
                try:
                    datos, consumo = cliente.fichar(modelo, peticion)
                    ficha = Ficha(fichable.huella, fichable.rutas, consumo.modelo, datos, fichable.familia)
                except (ErrorLlamada, FichaNoValida) as error:
                    resultado.errores[fichable.huella] = str(error)
                    consumo = getattr(error, "consumo", None)
                    ficha = None
                if consumo is not None:
                    self._anotar(resultado, registro, ejecucion, fichable.huella, consumo, tarifas)
                if ficha is not None:
                    destino = carpeta / modelo / redactor.nombre_fichero(ficha)
                    destino.parent.mkdir(parents=True, exist_ok=True)
                    destino.write_text(redactor.redactar(ficha), encoding="utf-8")
                    resultado.fichas[fichable.huella] = destino
                if avisar_avance:
                    avisar_avance(modelo, numero, len(muestra))
            resultados.append(resultado)
        return resultados

    @staticmethod
    def _anotar(
        resultado: ResultadoModelo, registro: RegistroConsumo, ejecucion: str,
        huella: str, consumo: ConsumoLlamada, tarifas: CatalogoTarifas,
    ) -> None:
        """Registra una llamada y la suma al resultado del modelo."""
        coste = tarifas.de(consumo.modelo).coste(consumo)
        registro.anotar(ejecucion, huella, consumo, coste)
        resultado.entrada += consumo.entrada + consumo.lectura_cache + consumo.escritura_cache
        resultado.salida += consumo.salida
        resultado.coste += coste

    @staticmethod
    def _formato(fichable: Fichable) -> str:
        """Familia de formato: PDF, texto de oficina, presentación u hoja."""
        extension = fichable.rutas[0].suffix.lower().lstrip(".")
        if extension in ("ppt", "pptx", "odp"):
            return "presentacion"
        if extension in ("xls", "xlsx", "ods"):
            return "hoja"
        return "pdf" if extension == "pdf" else "texto"

    @staticmethod
    def _longitud(fichable: Fichable) -> int:
        """0 corto, 1 medio, 2 largo (más de lo que se envía entero)."""
        if fichable.caracteres < 5_000:
            return 0
        return 1 if fichable.caracteres <= 40_000 else 2
