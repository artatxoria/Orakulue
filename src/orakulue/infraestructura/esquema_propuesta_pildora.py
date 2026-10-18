"""Esquema JSON de una propuesta de píldora formativa.

Va en su propio módulo a propósito: el formato de las píldoras es libre por
ahora, pero es probable que haya que ajustarse más adelante a uno concreto
(por ejemplo, el de SPRI). Cuando llegue, se cambia este esquema y la
plantilla de su Markdown, y el resto del proceso no se toca.
"""

from typing import Any


class EsquemaPropuestaPildora:
    """Construye el esquema de la propuesta de píldora."""

    @classmethod
    def json(cls) -> dict[str, Any]:
        """Devuelve el esquema completo (todos los campos obligatorios)."""
        texto = {"type": "string"}
        lista = {"type": "array", "items": texto}

        def objeto(propiedades: dict[str, Any]) -> dict[str, Any]:
            return {"type": "object", "properties": propiedades, "required": list(propiedades),
                    "additionalProperties": False}

        return objeto({
            "titulo": texto,
            "problema_de_empresa": texto,
            "destinatarios": texto,
            "objetivo": texto,
            "resultado_esperado": texto,
            "contenidos": lista,
            "practica_principal": texto,
            "material_existente": {"type": "array", "items": objeto({
                "fuentes": {"type": "array", "items": {"type": "integer"}}, "que": texto,
            })},
            "falta_por_preparar": lista,
            "diferencia_con_catalogo": texto,
            "observaciones": texto,
        })
