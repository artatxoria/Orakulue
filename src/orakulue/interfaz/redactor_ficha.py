"""Conversión de una ficha a Markdown, con cabecera YAML para Obsidian."""

import json
import re
import unicodedata
from pathlib import Path

from orakulue.dominio.ficha import Ficha
from orakulue.utilidades.formato import Formato


class RedactorFicha:
    """Escribe una ficha como documento Markdown legible sin la IA delante."""

    _SOLUCION = {"si": "con solución", "no": "sin solución", "no_consta": "no consta si trae solución"}

    def __init__(self, personal: Path) -> None:
        """Prepara el redactor.

        Args:
            personal: directorio personal, para abreviar rutas.
        """
        self._personal = personal

    def nombre_fichero(self, ficha: Ficha) -> str:
        """Nombre del fichero: el título simplificado y el principio de la huella.

        La huella evita choques entre documentos con el mismo título y permite
        encontrar la ficha a partir del inventario.
        """
        base = unicodedata.normalize("NFKD", ficha.titulo)
        base = "".join(c for c in base if not unicodedata.combining(c))
        base = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-")[:70] or "documento"
        return f"{base}-{ficha.huella[:8]}.md"

    def redactar(self, ficha: Ficha) -> str:
        """Devuelve el Markdown completo de la ficha."""
        d = ficha.datos
        partes = [self._cabecera(ficha), f"# {ficha.titulo}", d["resumen"].strip()]
        if ficha.sin_interes:
            partes.append(f"**Sin interés formativo:** {d['motivo_interes'].strip()}")
        else:
            partes.append(f"**Interés formativo: {d['interes']}.** {d['motivo_interes'].strip()}")
            partes += [
                self._seccion("Teoría que contiene", [self._con_lugar(t["concepto"], t["donde"]) for t in d["teoria"]]),
                self._seccion("Ejercicios aprovechables", [
                    self._con_lugar(f"{e['descripcion']} — practica: {e['practica']} "
                                    f"({self._SOLUCION.get(e['con_solucion'], e['con_solucion'])})", e["donde"])
                    for e in d["ejercicios"]
                ]),
                self._seccion("Ideas de curso", [
                    f"**{c['titulo']}** — para {self._tras_preposicion(c['destinatarios'])}. {c['aprendizaje']}"
                    for c in d["ideas_curso"]
                ]),
                self._seccion("Ideas de píldora para SPRI", [
                    f"**{p['titulo']}** — {p['objetivo']}" for p in d["ideas_pildora"]
                ]),
            ]
        if d["observaciones"].strip():
            partes.append(f"## Observaciones\n\n{d['observaciones'].strip()}")
        partes.append("## Dónde está\n\n" + "\n".join(
            f"- `{Formato.ruta(r, self._personal)}`" for r in ficha.rutas
        ))
        if ficha.familia:
            partes.append("## Misma plantilla\n\nDocumentos hechos sobre el mismo modelo; esta ficha los "
                          "representa a todos.\n\n" + "\n".join(
                              f"- `{Formato.ruta(r, self._personal)}`" for r in ficha.familia))
        return "\n\n".join(p for p in partes if p) + "\n"

    def _cabecera(self, ficha: Ficha) -> str:
        """Cabecera YAML. Los textos se escriben como JSON, que es YAML válido
        y evita problemas con dos puntos, comillas o saltos de línea."""
        d = ficha.datos

        def valor(v) -> str:
            return json.dumps(v, ensure_ascii=False)

        lineas = {
            "titulo": ficha.titulo, "tipo": d["tipo"], "tema": d["tema"], "temas": d["temas"],
            "nivel": d["nivel"], "idioma": d["idioma"], "publico": d["publico"],
            "vigencia": d["vigencia"]["estado"], "motivo_vigencia": d["vigencia"]["motivo"],
            "interes": d["interes"], "huella": ficha.huella, "modelo": ficha.modelo,
            "rutas": [Formato.ruta(r, self._personal) for r in ficha.rutas],
        }
        return "---\n" + "\n".join(f"{k}: {valor(v)}" for k, v in lineas.items()) + "\n---"

    @staticmethod
    def _tras_preposicion(texto: str) -> str:
        """Pone en minúscula la inicial cuando va detrás de «para».

        No se toca si la segunda letra también es mayúscula: es una sigla
        («PYMES», «SPRI») y debe quedarse como está.
        """
        texto = texto.strip()
        if len(texto) > 1 and texto[0].isupper() and not texto[1].isupper():
            return texto[0].lower() + texto[1:]
        return texto

    @staticmethod
    def _seccion(titulo: str, elementos: list[str]) -> str:
        """Sección con viñetas, o nada si está vacía."""
        if not elementos:
            return ""
        return f"## {titulo}\n\n" + "\n".join(f"- {e}" for e in elementos)

    @staticmethod
    def _con_lugar(texto: str, donde: str) -> str:
        """Añade la localización entre paréntesis si la hay."""
        return f"{texto} ({donde})" if donde.strip() else texto
