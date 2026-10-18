"""Markdown de una propuesta de curso, con los apartados del catálogo."""

import json
import re
from pathlib import Path

from orakulue.dominio.propuesta import Propuesta
from orakulue.utilidades.formato import Formato


class RedactorPropuestaCurso:
    """Escribe una propuesta de curso legible en Obsidian, la tablet o la web."""

    def __init__(self, documentos: dict[str, tuple[str, Path]], personal: Path) -> None:
        """Prepara el redactor.

        Args:
            documentos: huella → (título de su ficha, ruta), para la lista de fuentes.
            personal: directorio personal, para abreviar rutas.
        """
        self._documentos = documentos
        self._personal = personal

    def redactar(self, propuesta: Propuesta) -> str:
        """Devuelve el Markdown completo."""
        d = propuesta.datos
        partes = [
            self._cabecera(propuesta),
            f"# {propuesta.titulo}",
            f"**Área estratégica.** {d['area_estrategica']}",
            f"**Descripción.** {d['descripcion']}",
            "**Objetivos de aprendizaje**\n\n" + "\n".join(f"- {o}" for o in d["objetivos"]),
            f"**Público objetivo.** {d['publico_objetivo']}",
            ("**Requisitos previos**\n\n" + "\n".join(f"- {r}" for r in d["requisitos_previos"]))
            if d["requisitos_previos"] else "",
            "**Duración y modalidad.** _A decidir._",
            f"**Justificación formativa.** {d['justificacion']}",
            "## Temario",
        ]
        for numero, modulo in enumerate(d["modulos"], start=1):
            # Algunos modelos numeran ellos mismos los módulos («1. Preparar…»):
            # se quita esa numeración para no duplicarla con la de la plantilla.
            titulo = re.sub(r"^\s*(m[oó]dulo\s*)?\d+[.):-]\s*", "", modulo["titulo"], flags=re.I)
            bloque = [f"### {numero}. {titulo}", "\n".join(f"- {c}" for c in modulo["contenidos"])]
            if modulo["material_existente"]:
                bloque.append("Material en el fondo:\n" + "\n".join(
                    f"- {m['que']} {self._citas(m['fuentes'])}" for m in modulo["material_existente"]))
            if modulo["ejercicios_disponibles"]:
                bloque.append("Ejercicios disponibles:\n" + "\n".join(
                    f"- {e['descripcion']} {self._citas(e['fuentes'])}" for e in modulo["ejercicios_disponibles"]))
            partes.append("\n\n".join(bloque))
        partes += [
            "## Falta por preparar\n\n" + ("\n".join(f"- {f}" for f in d["falta_por_preparar"]) or "Nada destacable."),
            f"## Diferencia con el catálogo\n\n{d['diferencia_con_catalogo']}",
            f"## Observaciones\n\n{d['observaciones']}" if d["observaciones"].strip() else "",
            self._fuentes(propuesta),
        ]
        return "\n\n".join(p for p in partes if p) + "\n"

    def _cabecera(self, propuesta: Propuesta) -> str:
        """Cabecera YAML (valores como JSON, que es YAML válido)."""
        lineas = {
            "tipo": "curso", "titulo": propuesta.titulo, "clave": propuesta.clave, "modelo": propuesta.modelo,
            "puntuacion": propuesta.puntuacion, "desglose": propuesta.desglose,
            "relacion_catalogo": propuesta.en_catalogo,
        }
        return "---\n" + "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in lineas.items()) + "\n---"

    def _citas(self, numeros: list[int]) -> str:
        """Citas como [1][3]."""
        return "".join(f"[{n}]" for n in numeros)

    def _fuentes(self, propuesta: Propuesta) -> str:
        """Lista numerada de documentos fuente."""
        lineas = []
        for numero, huella in enumerate(propuesta.fuentes, start=1):
            titulo, ruta = self._documentos.get(huella, (huella[:12], Path("?")))
            lineas.append(f"[{numero}] {titulo} — `{Formato.ruta(ruta, self._personal)}`")
        return "## Fuentes\n\n" + "\n".join(f"- {l}" for l in lineas)
