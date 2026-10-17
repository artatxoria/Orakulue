"""Llamadas al modelo de Anthropic para escribir fichas.

Es el único módulo que habla con el proveedor. Traduce sus respuestas y sus
errores a lo que entiende el resto del programa: un diccionario con la ficha,
el consumo de la llamada y errores en castellano.
"""

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import anthropic

from orakulue.dominio.consumo_llamada import ConsumoLlamada
from orakulue.dominio.peticion import Peticion
from orakulue.infraestructura.error_saldo_agotado import ErrorSaldoAgotado
from orakulue.infraestructura.esquema_ficha import EsquemaFicha


class ErrorLlamada(Exception):
    """Una llamada no ha producido una ficha utilizable (no es falta de saldo).

    Atributos:
        consumo: tokens gastados aunque la ficha no sirva (una respuesta
            cortada o una negativa también se cobran), o ``None`` si la llamada
            ni siquiera llegó a hacerse.
    """

    def __init__(self, mensaje: str, consumo: ConsumoLlamada | None = None) -> None:
        """Construye el error.

        Args:
            mensaje: explicación en castellano.
            consumo: tokens gastados, si los hubo.
        """
        super().__init__(mensaje)
        self.consumo = consumo


class ClienteModelo:
    """Pide fichas a un modelo de Anthropic de forma síncrona."""

    #: Modelos que admiten el respaldo automático del servidor ante una
    #: negativa por seguridad. Haiku no lo tiene.
    _CON_RESPALDO = {"claude-opus-5-5", "claude-sonnet-5-5"}
    #: Margen para el razonamiento y la ficha; con esfuerzo bajo sobra.
    MAX_TOKENS = 12_000

    def __init__(self, variable_clave: str, instrucciones: str, esfuerzo: str = "low") -> None:
        """Prepara el cliente.

        Args:
            variable_clave: variable de entorno con la clave de Orakulue.
            instrucciones: instrucciones comunes a todas las peticiones.
            esfuerzo: nivel de esfuerzo del modelo (``low`` basta para fichar).

        Raises:
            ErrorLlamada: si la variable no está definida.
        """
        clave = os.environ.get(variable_clave, "")
        if not clave:
            raise ErrorLlamada(
                f"No está definida la variable de entorno {variable_clave} con la clave de "
                "Anthropic de Orakulue."
            )
        self._variable = variable_clave
        self._instrucciones = instrucciones
        self._esfuerzo = esfuerzo
        self._cliente = anthropic.Anthropic(api_key=clave)

    def parametros(self, modelo: str, peticion: Peticion) -> dict[str, Any]:
        """Parámetros de la petición, comunes a la llamada directa y a los lotes.

        Las instrucciones van en ``system`` con marca de caché: son iguales en
        todas las peticiones y así se cobran a precio reducido.

        Args:
            modelo: identificador del modelo.
            peticion: petición preparada.

        Returns:
            Diccionario de parámetros para ``messages.create``.
        """
        return {
            "model": modelo,
            "max_tokens": self.MAX_TOKENS,
            "system": [{"type": "text", "text": self._instrucciones, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": peticion.mensaje}],
            "output_config": {
                "effort": self._esfuerzo,
                "format": {"type": "json_schema", "schema": EsquemaFicha.json()},
            },
        }

    def fichar(self, modelo: str, peticion: Peticion) -> tuple[dict[str, Any], ConsumoLlamada]:
        """Pide la ficha de un documento.

        En Opus y Sonnet se activa el respaldo del servidor: si el modelo se
        niega por un falso positivo de seguridad, el servidor reintenta con otro
        modelo dentro de la misma llamada, y el consumo se cobra al que respondió.

        Args:
            modelo: identificador del modelo.
            peticion: petición preparada.

        Returns:
            Los datos de la ficha y el consumo de la llamada.

        Raises:
            ErrorSaldoAgotado: si la cuenta no tiene saldo.
            ErrorLlamada: por cualquier otro fallo o respuesta inutilizable.
        """
        parametros = self.parametros(modelo, peticion)
        with self._traducir_errores():
            if modelo in self._CON_RESPALDO:
                respuesta = self._cliente.beta.messages.create(
                    **parametros, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
                )
            else:
                respuesta = self._cliente.messages.create(**parametros)
        return self.interpretar(respuesta, por_lotes=False)

    def redactar(self, modelo: str, instrucciones: str, mensaje: str) -> tuple[str, ConsumoLlamada]:
        """Pide una respuesta en texto libre (para contestar preguntas).

        Args:
            modelo: identificador del modelo.
            instrucciones: instrucciones de sistema de esta petición.
            mensaje: mensaje del usuario.

        Returns:
            El texto y el consumo.

        Raises:
            ErrorSaldoAgotado: si la cuenta no tiene saldo.
            ErrorLlamada: por cualquier otro fallo, o si el modelo se niega.
        """
        with self._traducir_errores():
            respuesta = self._cliente.messages.create(
                model=modelo, max_tokens=self.MAX_TOKENS, system=instrucciones,
                messages=[{"role": "user", "content": mensaje}],
                output_config={"effort": self._esfuerzo},
            )
        uso = respuesta.usage
        consumo = ConsumoLlamada(
            modelo=respuesta.model, entrada=uso.input_tokens or 0, salida=uso.output_tokens or 0,
            lectura_cache=getattr(uso, "cache_read_input_tokens", 0) or 0,
            escritura_cache=getattr(uso, "cache_creation_input_tokens", 0) or 0,
        )
        if respuesta.stop_reason == "refusal":
            raise ErrorLlamada("el modelo se ha negado a responder", consumo)
        texto = "".join(b.text for b in respuesta.content if b.type == "text")
        return texto, consumo

    def crear_lote(self, modelo: str, peticiones: list[Peticion]) -> str:
        """Envía un lote de peticiones a la API por lotes (mitad de precio).

        El identificador de cada petición es la huella del contenido: así cada
        resultado se asocia a su documento, lleguen en el orden que lleguen.
        La API por lotes no admite el respaldo ante negativas; con Haiku no
        hace falta, porque no lo tiene.

        Args:
            modelo: identificador del modelo.
            peticiones: peticiones preparadas.

        Returns:
            Identificador del lote.

        Raises:
            ErrorSaldoAgotado: si la cuenta no tiene saldo.
            ErrorLlamada: por cualquier otro fallo.
        """
        with self._traducir_errores():
            lote = self._cliente.messages.batches.create(requests=[
                {"custom_id": p.huella, "params": self.parametros(modelo, p)} for p in peticiones
            ])
        return lote.id

    def estado_lote(self, identificador: str) -> tuple[bool, dict[str, int]]:
        """Consulta un lote.

        Args:
            identificador: lote.

        Returns:
            Si ha terminado y el recuento de peticiones por estado.

        Raises:
            ErrorLlamada: si no se puede consultar.
        """
        with self._traducir_errores():
            lote = self._cliente.messages.batches.retrieve(identificador)
        cuentas = lote.request_counts
        return lote.processing_status == "ended", {
            "en proceso": cuentas.processing, "correctas": cuentas.succeeded,
            "con error": cuentas.errored, "canceladas": cuentas.canceled, "caducadas": cuentas.expired,
        }

    def resultados_lote(self, identificador: str) -> Iterator[tuple[str, Any | None, str]]:
        """Recorre los resultados de un lote terminado.

        Args:
            identificador: lote.

        Yields:
            (huella, mensaje de la API o ``None``, explicación del fallo si no
            hay mensaje).

        Raises:
            ErrorLlamada: si no se pueden descargar.
        """
        with self._traducir_errores():
            for resultado in self._cliente.messages.batches.results(identificador):
                tipo = resultado.result.type
                if tipo == "succeeded":
                    yield resultado.custom_id, resultado.result.message, ""
                elif tipo == "errored":
                    error = resultado.result.error
                    yield resultado.custom_id, None, f"error del proveedor: {getattr(error, 'error', error)}"
                else:
                    yield resultado.custom_id, None, f"petición {'cancelada' if tipo == 'canceled' else 'caducada'}"

    @contextmanager
    def _traducir_errores(self) -> Iterator[None]:
        """Convierte los errores del SDK en errores de Orakulue, en castellano.

        La falta de saldo se reconoce por el texto del mensaje, nunca por el
        código HTTP (norma 5).

        Raises:
            ErrorSaldoAgotado: si el mensaje habla de falta de saldo.
            ErrorLlamada: para cualquier otro error del proveedor o de red.
        """
        try:
            yield
        except anthropic.APIStatusError as error:
            mensaje = str(getattr(error, "message", error))
            if ErrorSaldoAgotado.es_falta_de_saldo(mensaje):
                raise ErrorSaldoAgotado(self._variable, mensaje) from error
            raise ErrorLlamada(f"el proveedor ha respondido con un error {error.status_code}: {mensaje}") from error
        except anthropic.APIConnectionError as error:
            raise ErrorLlamada(f"no se ha podido conectar con el proveedor: {error}") from error

    @staticmethod
    def interpretar(respuesta: Any, por_lotes: bool) -> tuple[dict[str, Any], ConsumoLlamada]:
        """Convierte una respuesta de la API en datos de ficha y consumo.

        Se usa también para los resultados de lotes, que traen el mismo objeto.

        Args:
            respuesta: mensaje devuelto por la API.
            por_lotes: si viene de la API por lotes.

        Returns:
            Los datos de la ficha y el consumo.

        Raises:
            ErrorLlamada: si el modelo se negó, se quedó sin espacio o no
                devolvió JSON.
        """
        uso = respuesta.usage
        consumo = ConsumoLlamada(
            modelo=respuesta.model,
            entrada=uso.input_tokens or 0,
            salida=uso.output_tokens or 0,
            lectura_cache=getattr(uso, "cache_read_input_tokens", 0) or 0,
            escritura_cache=getattr(uso, "cache_creation_input_tokens", 0) or 0,
            por_lotes=por_lotes,
        )
        if respuesta.stop_reason == "refusal":
            raise ErrorLlamada("el modelo se ha negado a fichar este documento", consumo)
        if respuesta.stop_reason == "max_tokens":
            raise ErrorLlamada("la respuesta se ha cortado por longitud", consumo)
        texto = next((b.text for b in respuesta.content if b.type == "text"), "")
        try:
            return json.loads(texto), consumo
        except json.JSONDecodeError as error:
            raise ErrorLlamada("la respuesta no es JSON válido", consumo) from error
