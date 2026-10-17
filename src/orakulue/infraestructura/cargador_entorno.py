"""Carga de variables de entorno desde el fichero privado ``.env`` del proyecto.

Así la clave de la API no tiene que estar exportada en cada terminal. El
fichero está en ``.gitignore`` y debe tener permisos solo para su dueño.
"""

import os
from pathlib import Path


class CargadorEntorno:
    """Lee líneas ``NOMBRE=valor`` y las pone en el entorno del proceso."""

    def cargar(self, ruta: Path) -> list[str]:
        """Carga las variables que todavía no estén definidas.

        Una variable ya exportada en la terminal **gana** al fichero: así se
        puede probar otra clave sin tocarlo.

        Args:
            ruta: fichero ``.env``. Si no existe, no hace nada.

        Returns:
            Nombres de las variables cargadas (nunca sus valores).
        """
        if not ruta.is_file():
            return []
        cargadas = []
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            nombre, valor = (parte.strip() for parte in linea.split("=", 1))
            if nombre and nombre not in os.environ:
                os.environ[nombre] = valor.strip("\"'")
                cargadas.append(nombre)
        return cargadas
