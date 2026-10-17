"""Respuestas con un modelo de lenguaje local en Ollama.

Para preguntas sobre material delicado: nada sale del PC de sobremesa y no
cuesta nada. A cambio, la calidad es bastante peor que la de un modelo grande,
sobre todo en euskera.
"""

import json
import urllib.error
import urllib.request

from orakulue.infraestructura.cliente_vectores import ErrorVectores


class ClienteLocal:
    """Pide una respuesta a un modelo de chat de Ollama."""

    def __init__(self, url: str = "http://localhost:11434", modelo: str = "qwen2.5:7b-instruct") -> None:
        """Prepara el cliente.

        Args:
            url: dirección de Ollama.
            modelo: modelo de chat instalado en Ollama.
        """
        self._url = url.rstrip("/")
        self.modelo = modelo

    def redactar(self, instrucciones: str, mensaje: str) -> str:
        """Devuelve la respuesta del modelo local.

        Args:
            instrucciones: mensaje de sistema.
            mensaje: mensaje del usuario.

        Returns:
            Texto de la respuesta.

        Raises:
            ErrorVectores: si Ollama no responde (mismo error que los vectores:
                en los dos casos el remedio es arrancar Ollama).
        """
        cuerpo = json.dumps({
            "model": self.modelo, "stream": False,
            "messages": [{"role": "system", "content": instrucciones}, {"role": "user", "content": mensaje}],
            # Contexto amplio para que quepan los pasajes; temperatura baja
            # para que se ciña a ellos en lugar de improvisar.
            "options": {"num_ctx": 16384, "temperature": 0.2},
        }).encode()
        peticion = urllib.request.Request(
            f"{self._url}/api/chat", data=cuerpo, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(peticion, timeout=900) as respuesta:
                datos = json.loads(respuesta.read())
        except urllib.error.URLError as error:
            raise ErrorVectores(f"No se puede hablar con Ollama en {self._url} ({error}).") from error
        return datos.get("message", {}).get("content", "")
