"""Caso de uso: medir lo bien que busca el buscador con un juego de preguntas.

Cada pregunta trae los documentos que deberían salir. Se mide:

- **acierto en 10**: proporción de preguntas en las que alguno de los
  esperados aparece entre los diez primeros;
- **rango recíproco medio**: 1 si el esperado sale primero, 1/2 si sale
  segundo… La media premia que salga arriba, no solo que salga.

Con estas cifras, cualquier ajuste del buscador se juzga con datos.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path

from orakulue.aplicacion.buscador import Buscador


@dataclass(frozen=True)
class PreguntaPrueba:
    """Una pregunta del juego de prueba. Solo la usa ``EvaluadorBusqueda``.

    Atributos:
        texto: la pregunta, como la haría una persona.
        esperados: huellas de los documentos que deberían salir (basta uno).
        comentario: qué se espera, en palabras (para leer el informe).
    """

    texto: str
    esperados: tuple[str, ...]
    comentario: str = ""


@dataclass(frozen=True)
class ResultadoEvaluacion:
    """Cifras de un modo de búsqueda. Solo la usa ``EvaluadorBusqueda``.

    Atributos:
        modo: modo evaluado.
        acierto: proporción de aciertos en los diez primeros.
        rango_reciproco: rango recíproco medio.
        fallos: preguntas sin acierto.
    """

    modo: str
    acierto: float
    rango_reciproco: float
    fallos: tuple[str, ...]


class EvaluadorBusqueda:
    """Evalúa el buscador con un juego de preguntas."""

    PROFUNDIDAD = 10

    @staticmethod
    def leer(ruta: Path) -> list[PreguntaPrueba]:
        """Lee el juego de preguntas de un fichero TOML.

        Formato: tablas ``[[pregunta]]`` con ``texto``, ``esperados`` (lista
        de huellas o de sus primeros caracteres) y ``comentario``.

        Raises:
            FileNotFoundError: si no existe el fichero.
        """
        with ruta.open("rb") as fichero:
            datos = tomllib.load(fichero)
        return [
            PreguntaPrueba(p["texto"], tuple(p["esperados"]), p.get("comentario", ""))
            for p in datos.get("pregunta", [])
        ]

    def evaluar(self, buscador: Buscador, preguntas: list[PreguntaPrueba], modo: str) -> ResultadoEvaluacion:
        """Pasa todas las preguntas por un modo de búsqueda.

        Los esperados pueden ser huellas abreviadas: se compara el principio.
        """
        aciertos, reciprocos, fallos = 0, 0.0, []
        for pregunta in preguntas:
            encontrados = [r.info.huella for r in buscador.buscar(pregunta.texto, self.PROFUNDIDAD, modo)]
            posicion = next(
                (n for n, h in enumerate(encontrados, start=1) if any(h.startswith(e) for e in pregunta.esperados)),
                None,
            )
            if posicion is None:
                fallos.append(pregunta.texto)
            else:
                aciertos += 1
                reciprocos += 1 / posicion
        total = len(preguntas) or 1
        return ResultadoEvaluacion(modo, aciertos / total, reciprocos / total, tuple(fallos))
