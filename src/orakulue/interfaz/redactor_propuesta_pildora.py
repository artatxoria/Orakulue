"""Markdown de una propuesta de píldora formativa.

Plantilla propia, separada de la de los cursos: cuando haya que seguir un
formato concreto (por ejemplo, el de SPRI), se cambia aquí y en
``EsquemaPropuestaPildora``, sin tocar lo demás.
"""

import json
from pathlib import Path

from orakulue.dominio.propuesta import Propuesta
from orakulue.utilidades.formato import Formato


class RedactorPropuestaPildora:
    """Escribe una propuesta de píldora."""

    def __init__(self, documentos: dict[str, tuple[str, Path]], personal: Path) -> None:
        """Prepara el redactor.

        Args:
            documentos: huella → (título de su ficha, ruta).
            personal: directorio personal, para abreviar rutas.
        """
        self._documentos = documentos
        self._personal = personal

    def redactar(self, propuesta: Propuesta) -> str:
        """Devuelve el Markdown completo."""
        d = propuesta.datos
        cabecera = {
            "tipo": "pildora", "titulo": propuesta.titulo, "clave": propuesta.clave, "modelo": propuesta.modelo,
            "puntuacion": propuesta.puntuacion, "desglose": propuesta.desglose,
            "relacion_catalogo": propuesta.en_catalogo,
        }
        fuentes = "\n".join(
            f"- [{n}] {self._documentos.get(h, (h[:12], Path('?')))[0]} — "
            f"`{Formato.ruta(self._documentos.get(h, ('', Path('?')))[1], self._personal)}`"
            for n, h in enumerate(propuesta.fuentes, start=1)
        )
        partes = [
            "---\n" + "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in cabecera.items()) + "\n---",
            f"# {propuesta.titulo}",
            f"**El problema de empresa.** {d['problema_de_empresa']}",
            f"**Para quién.** {d['destinatarios']}",
            f"**Objetivo.** {d['objetivo']}",
            f"**Al terminar.** {d['resultado_esperado']}",
            "**Duración y modalidad.** _A decidir._",
            "## Contenidos\n\n" + "\n".join(f"- {c}" for c in d["contenidos"]),
            f"## Práctica principal\n\n{d['practica_principal']}",
            ("## Material en el fondo\n\n" + "\n".join(
                f"- {m['que']} " + "".join(f"[{n}]" for n in m["fuentes"]) for m in d["material_existente"]))
            if d["material_existente"] else "",
            "## Falta por preparar\n\n" + ("\n".join(f"- {f}" for f in d["falta_por_preparar"]) or "Nada destacable."),
            f"## Diferencia con el catálogo\n\n{d['diferencia_con_catalogo']}",
            f"## Observaciones\n\n{d['observaciones']}" if d["observaciones"].strip() else "",
            f"## Fuentes\n\n{fuentes}",
        ]
        return "\n\n".join(p for p in partes if p) + "\n"
