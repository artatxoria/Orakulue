"""Esquema JSON de una propuesta de curso.

Sigue los apartados de los cursos del catálogo actual (área estratégica,
descripción, objetivos de aprendizaje, público objetivo, justificación
formativa), para que una propuesta aceptada pase al catálogo casi tal cual. La
duración no se pide: la decide quien imparte.
"""

from typing import Any


class EsquemaPropuestaCurso:
    """Construye el esquema de la propuesta de curso."""

    @classmethod
    def json(cls) -> dict[str, Any]:
        """Devuelve el esquema completo (todos los campos obligatorios)."""
        texto = {"type": "string"}
        lista = {"type": "array", "items": texto}
        fuente = {"type": "array", "items": {"type": "integer"}}

        def objeto(propiedades: dict[str, Any]) -> dict[str, Any]:
            return {"type": "object", "properties": propiedades, "required": list(propiedades),
                    "additionalProperties": False}

        return objeto({
            "titulo": texto,
            "area_estrategica": texto,
            "descripcion": texto,
            "objetivos": lista,
            "publico_objetivo": texto,
            "requisitos_previos": lista,
            "justificacion": texto,
            "modulos": {"type": "array", "items": objeto({
                "titulo": texto,
                "contenidos": lista,
                "material_existente": {"type": "array", "items": objeto({"fuentes": fuente, "que": texto})},
                "ejercicios_disponibles": {"type": "array", "items": objeto({"fuentes": fuente, "descripcion": texto})},
            })},
            "falta_por_preparar": lista,
            "diferencia_con_catalogo": texto,
            "observaciones": texto,
        })
