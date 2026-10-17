"""Esquema JSON que debe cumplir la respuesta del modelo.

Se pasa a la API como salida estructurada (``output_config.format``): el modelo
queda obligado a devolver exactamente estos campos, y una respuesta mal formada
no llega a guardarse como ficha.
"""

from typing import Any


class EsquemaFicha:
    """Construye el esquema JSON de la ficha."""

    TIPOS = ["manual", "libro", "apuntes", "ejercicios", "presentacion", "examen",
             "plantilla", "normativa", "propuesta", "administrativo", "otro"]
    NIVELES = ["iniciacion", "intermedio", "avanzado", "no_aplica"]
    INTERES = ["alto", "medio", "bajo", "ninguno"]
    VIGENCIA = ["actual", "desactualizado", "no_determinable"]
    SOLUCION = ["si", "no", "no_consta"]

    @classmethod
    def json(cls) -> dict[str, Any]:
        """Devuelve el esquema completo.

        Todos los campos son obligatorios y no se admiten campos extra, como
        exige la salida estructurada. Lo que no aplique se devuelve vacío.

        Returns:
            Diccionario con el esquema JSON.
        """
        texto = {"type": "string"}
        lista_textos = {"type": "array", "items": texto}

        def objeto(propiedades: dict[str, Any]) -> dict[str, Any]:
            return {
                "type": "object",
                "properties": propiedades,
                "required": list(propiedades),
                "additionalProperties": False,
            }

        def enumerado(valores: list[str]) -> dict[str, Any]:
            return {"type": "string", "enum": valores}

        return objeto({
            "titulo": texto,
            "tipo": enumerado(cls.TIPOS),
            "tema": texto,
            "temas": lista_textos,
            "nivel": enumerado(cls.NIVELES),
            "idioma": enumerado(["es", "eu", "en", "otro"]),
            "publico": texto,
            "vigencia": objeto({"estado": enumerado(cls.VIGENCIA), "motivo": texto}),
            "interes": enumerado(cls.INTERES),
            "motivo_interes": texto,
            "resumen": texto,
            "teoria": {"type": "array", "items": objeto({"concepto": texto, "donde": texto})},
            "ejercicios": {"type": "array", "items": objeto({
                "descripcion": texto, "practica": texto,
                "con_solucion": enumerado(cls.SOLUCION), "donde": texto,
            })},
            "ideas_curso": {"type": "array", "items": objeto({
                "titulo": texto, "destinatarios": texto, "aprendizaje": texto,
            })},
            "ideas_pildora": {"type": "array", "items": objeto({"titulo": texto, "objetivo": texto})},
            "observaciones": texto,
        })
