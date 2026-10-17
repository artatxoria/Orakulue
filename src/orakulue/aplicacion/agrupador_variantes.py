"""Caso de uso: decidir qué documentos son variantes de uno mismo.

En el fondo hay versiones de un documento: el mismo guion guardado en ``.odt``
y retocado después en ``.docx``, o la misma propuesta para varios clientes. En
la búsqueda deben salir como un solo resultado con sus variantes debajo, no
ocupando varios puestos.

Dos documentos son variantes si:

- la fase 3 los puso en el mismo grupo de casi duplicados, o
- sus fichas tienen exactamente el mismo título (sin contar mayúsculas,
  tildes ni signos). Esto recoge las versiones retocadas, cuyo texto puede
  diferir más de lo que admite la detección de casi duplicados.
"""

import re
import unicodedata

from orakulue.dominio.info_documento import InfoDocumento


class AgrupadorVariantes:
    """Asigna a cada documento la clave de su grupo de variantes."""

    def agrupar(self, catalogo: dict[str, InfoDocumento], grupos: dict[int, list[str]]) -> dict[str, str]:
        """Devuelve, por huella, una clave común a todas sus variantes.

        Los documentos sin variantes no aparecen en el resultado.

        Args:
            catalogo: información de cada documento (para los títulos).
            grupos: grupos de casi duplicados de la fase 3.

        Returns:
            Diccionario huella → clave de grupo.
        """
        padre: dict[str, str] = {}

        def raiz(x: str) -> str:
            padre.setdefault(x, x)
            while padre[x] != x:
                padre[x] = padre[padre[x]]
                x = padre[x]
            return x

        def unir(a: str, b: str) -> None:
            padre[raiz(a)] = raiz(b)

        for huellas in grupos.values():
            miembros = [h for h in huellas if h in catalogo]
            for otra in miembros[1:]:
                unir(miembros[0], otra)

        por_titulo: dict[str, str] = {}
        for huella, info in catalogo.items():
            # Solo los títulos de ficha: el nombre de fichero («main.pdf»,
            # «intro.pdf») coincide demasiado entre documentos distintos.
            if info.ruta_ficha is None:
                continue
            clave = self._normalizar(info.titulo)
            if len(clave) < 12:
                continue  # títulos tan cortos («Ejercicio 3») no identifican nada
            if clave in por_titulo:
                unir(por_titulo[clave], huella)
            else:
                por_titulo[clave] = huella

        miembros_por_raiz: dict[str, list[str]] = {}
        for huella in list(padre):
            miembros_por_raiz.setdefault(raiz(huella), []).append(huella)
        return {h: r for r, lista in miembros_por_raiz.items() if len(lista) > 1 for h in lista}

    @staticmethod
    def _normalizar(titulo: str) -> str:
        """Minúsculas, sin tildes y sin signos."""
        sin = unicodedata.normalize("NFKD", titulo.lower())
        sin = "".join(c for c in sin if not unicodedata.combining(c))
        return re.sub(r"[^a-z0-9]+", " ", sin).strip()
