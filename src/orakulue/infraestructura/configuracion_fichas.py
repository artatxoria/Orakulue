"""Parámetros de la fase 4, leídos de la sección ``[fichas]`` de la configuración."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path


@dataclass(frozen=True)
class ConfiguracionFichas:
    """Dónde van las fichas, con qué modelo y con qué clave.

    Atributos:
        carpeta: carpeta de las fichas en Markdown.
        modelo: modelo que escribe las fichas del fondo.
        modelos_prueba: modelos que se comparan en la prueba.
        documentos_prueba: cuántos documentos entran en la prueba.
        variable_clave: variable de entorno con la clave de Anthropic.
        saldo_declarado: saldo en dólares que el usuario dice tener, o
            ``None`` si no lo ha declarado (el proveedor no lo publica).
        esfuerzo: nivel de esfuerzo del modelo.
    """

    carpeta: Path
    modelo: str
    modelos_prueba: tuple[str, ...]
    documentos_prueba: int
    variable_clave: str
    saldo_declarado: Decimal | None
    esfuerzo: str

    @classmethod
    def desde_seccion(cls, seccion: dict) -> "ConfiguracionFichas":
        """Interpreta la sección ``[fichas]``.

        Args:
            seccion: contenido de la sección (puede estar vacía).

        Returns:
            La configuración, con valores por omisión razonables.

        Raises:
            ValueError: si el saldo declarado no es un número.
        """
        saldo = seccion.get("saldo_declarado_dolares")
        try:
            saldo_decimal = None if saldo in (None, "") else Decimal(str(saldo))
        except InvalidOperation as error:
            raise ValueError(f"saldo_declarado_dolares no es un número: {saldo!r}") from error
        return cls(
            carpeta=Path(seccion.get("carpeta", "~/Documentos/formakuntza/fichas")).expanduser().absolute(),
            modelo=seccion.get("modelo", "claude-haiku-5-5"),
            modelos_prueba=tuple(seccion.get(
                "modelos_prueba", ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"]
            )),
            documentos_prueba=int(seccion.get("documentos_prueba", 20)),
            variable_clave=seccion.get("variable_clave", "CLAVE_API_ANTHROPIC_ORAKULUE"),
            saldo_declarado=saldo_decimal,
            esfuerzo=seccion.get("esfuerzo", "low"),
        )
