"""Cálculo de vectores de significado con un modelo local en Ollama.

Corre en el PC de sobremesa: los textos no salen del equipo y no cuesta nada.
Se habla con la API HTTP de Ollama directamente, con la biblioteca estándar,
para no añadir otra dependencia.
"""

import json
import urllib.error
import urllib.request

import numpy as np


class ErrorVectores(Exception):
    """No se han podido calcular los vectores (Ollama parado, modelo ausente…)."""


class ClienteVectores:
    """Convierte textos en vectores normalizados."""

    #: Textos por petición. Más grande no acelera apenas y ocupa más memoria
    #: de la tarjeta gráfica.
    LOTE = 32

    def __init__(self, url: str = "http://localhost:11434", modelo: str = "bge-m3") -> None:
        """Prepara el cliente.

        Args:
            url: dirección de Ollama.
            modelo: modelo de vectores. ``bge-m3`` es multilingüe: una pregunta
                en castellano encuentra textos en euskera o en inglés.
        """
        self._url = url.rstrip("/")
        self.modelo = modelo

    def vectores(self, textos: list[str]) -> np.ndarray:
        """Calcula los vectores de una lista de textos.

        Se normalizan a longitud 1: así el producto escalar es directamente
        la similitud del coseno.

        Args:
            textos: textos.

        Returns:
            Matriz de ``len(textos)`` filas, en ``float32``.

        Raises:
            ErrorVectores: si Ollama no responde o devuelve algo inesperado.
        """
        filas = []
        for inicio in range(0, len(textos), self.LOTE):
            filas += self._pedir(textos[inicio : inicio + self.LOTE])
        matriz = np.asarray(filas, dtype=np.float32)
        normas = np.linalg.norm(matriz, axis=1, keepdims=True)
        return matriz / np.where(normas == 0, 1, normas)

    def _pedir(self, textos: list[str]) -> list[list[float]]:
        """Una petición a ``/api/embed``."""
        cuerpo = json.dumps({"model": self.modelo, "input": textos}).encode()
        peticion = urllib.request.Request(
            f"{self._url}/api/embed", data=cuerpo, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(peticion, timeout=600) as respuesta:
                datos = json.loads(respuesta.read())
        except urllib.error.URLError as error:
            raise ErrorVectores(
                f"No se puede hablar con Ollama en {self._url} ({error}). ¿Está en marcha? "
                f"Prueba con: ollama list"
            ) from error
        if "embeddings" not in datos or len(datos["embeddings"]) != len(textos):
            raise ErrorVectores(f"Ollama no ha devuelto vectores con el modelo {self.modelo}: {datos}")
        return datos["embeddings"]
