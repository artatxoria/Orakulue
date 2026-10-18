"""Caso de uso: decidir qué contenidos se fichan y con qué familia.

Reglas (docs/FASE4_DISENO.md):

- todo el inventario con texto leído, esté donde esté;
- fuera los marcados con datos personales de nivel medio o alto;
- fuera los que, por el nombre del fichero o de su carpeta, son casi seguro
  documentos con datos de personas (notas, asistencia, listas de alumnos),
  aunque el texto no lo delate;
- de cada grupo de casi duplicados, una sola ficha: la del miembro con más
  texto, que lista a los demás.
"""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from orakulue.dominio.documento import Documento
from orakulue.dominio.marca_datos_personales import MarcaDatosPersonales
from orakulue.dominio.texto_extraido import EstadoExtraccion
from orakulue.utilidades.nombres_de_pila import NombresDePila


@dataclass(frozen=True)
class Fichable:
    """Un contenido que va a fichar. Solo la usa ``SeleccionFichables``.

    Atributos:
        huella: huella del contenido.
        rutas: sus rutas en el disco.
        idioma: idioma detectado.
        caracteres: longitud de su texto.
        familia: rutas de los demás miembros de su grupo de casi duplicados.
    """

    huella: str
    rutas: tuple[Path, ...]
    idioma: str
    caracteres: int
    familia: tuple[Path, ...] = ()


@dataclass(frozen=True)
class ResultadoSeleccion:
    """Lo seleccionado y lo descartado, con el motivo. Solo la usa ``SeleccionFichables``.

    Atributos:
        fichables: lo que se ficha.
        por_datos_personales: huellas descartadas por datos personales.
        por_familia: huellas que no se fichan porque las representa otra.
        por_nombre: huellas descartadas por el nombre de su fichero o carpeta.
    """

    fichables: list[Fichable]
    por_datos_personales: int
    por_familia: int
    por_nombre: int = 0


class SeleccionFichables:
    """Aplica las reglas de selección."""

    #: Palabras que, en el nombre de un fichero o de su carpeta, delatan datos
    #: de personas. Se comparan sin tildes ni mayúsculas. Basta que aparezca
    #: una en cualquiera de las rutas del contenido.
    PALABRAS_SENSIBLES = (
        "notas finales", "calificaciones", "calificacion", "asistencia", "listado de alumnos",
        "lista de alumnos", "alumnado", "matricula", "nomina", "curriculum", "ikasleen zerrenda",
        "ikasle zerrenda", "kalifikazio", "asistentzia", "notak",
    )

    def __init__(self, palabras_sensibles: tuple[str, ...] | None = None) -> None:
        """Prepara la selección.

        Args:
            palabras_sensibles: lista propia de palabras (útil en pruebas).
        """
        palabras = palabras_sensibles if palabras_sensibles is not None else self.PALABRAS_SENSIBLES
        self._sensibles = re.compile(
            r"(?<![a-z])(?:" + "|".join(re.escape(self._normalizar(p)) for p in palabras) + r")(?![a-z])"
        ) if palabras else None

    def sensible_por_nombre(self, rutas: list[Path]) -> bool:
        """Si alguna ruta delata datos de personas por su nombre.

        Dos casos: una palabra sensible en el nombre del fichero o de su
        carpeta («notas finales», «asistencia»…), o un fichero que se llama
        como una persona («lopez_irene.docx»), que es como suelen llamarse
        las entregas de alumnos aunque su texto apenas tenga nombres.
        """
        for ruta in rutas:
            if NombresDePila.en_nombre_de_fichero(ruta.stem):
                return True
            if self._sensibles and self._sensibles.search(
                self._normalizar(f"{ruta.parent.name} {ruta.stem}").replace("_", " ")
            ):
                return True
        return False

    @staticmethod
    def _normalizar(texto: str) -> str:
        """Minúsculas y sin tildes."""
        sin = unicodedata.normalize("NFKD", texto.lower())
        return "".join(c for c in sin if not unicodedata.combining(c))

    def seleccionar(
        self,
        documentos: list[Documento],
        metadatos: list[tuple[str, EstadoExtraccion, int, str, str, str]],
        marcas: dict[str, MarcaDatosPersonales],
        grupos: dict[int, list[str]],
    ) -> ResultadoSeleccion:
        """Devuelve los contenidos que se fichan.

        Args:
            documentos: inventario completo.
            metadatos: metadatos de los textos (huella, estado, caracteres, …).
            marcas: marcas de datos personales por huella.
            grupos: grupos de casi duplicados (número → huellas).

        Returns:
            El resultado de la selección, ordenado por huella.
        """
        rutas: dict[str, list[Path]] = {}
        for documento in documentos:
            if documento.huella:
                rutas.setdefault(documento.huella, []).append(documento.ruta)
        leidos = {
            h: (caracteres, idioma)
            for h, estado, caracteres, _, idioma, _ in metadatos
            if estado is EstadoExtraccion.CORRECTA and h in rutas
        }
        excluidos = {h for h in leidos if h in marcas and marcas[h].excluir_de_fichas}
        por_nombre = {h for h in leidos if h not in excluidos and self.sensible_por_nombre(rutas[h])}
        candidatos = set(leidos) - excluidos - por_nombre

        representante: dict[str, list[str]] = {}
        representados: set[str] = set()
        for huellas in grupos.values():
            miembros = [h for h in huellas if h in candidatos]
            if len(miembros) < 2:
                continue
            # El miembro con más texto es el más completo para describir a todos.
            elegido = max(miembros, key=lambda h: (leidos[h][0], h))
            representante[elegido] = [h for h in miembros if h != elegido]
            representados |= set(representante[elegido])

        fichables = [
            Fichable(
                h, tuple(sorted(rutas[h])), leidos[h][1], leidos[h][0],
                tuple(sorted(r for otra in representante.get(h, []) for r in rutas[otra])),
            )
            for h in sorted(candidatos - representados)
        ]
        return ResultadoSeleccion(fichables, len(excluidos), len(representados), len(por_nombre))
