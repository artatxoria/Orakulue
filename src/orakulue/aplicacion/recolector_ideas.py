"""Caso de uso: reunir las ideas de curso y de píldora de las fichas."""

from orakulue.dominio.idea_formativa import IdeaFormativa


class RecolectorIdeas:
    """Saca las ideas de las fichas de interés alto y medio.

    Las fichas de documentos con datos personales ya están retiradas, así que
    sus ideas no entran. Se recibe además el conjunto de huellas personales
    para no depender de que la retirada se haya hecho.
    """

    INTERESES = ("alto", "medio")

    def recolectar(self, fichas: dict[str, tuple[dict, str, object]], personales: set[str]) -> list[IdeaFormativa]:
        """Devuelve todas las ideas.

        Args:
            fichas: datos de cada ficha (huella → (datos, momento, ruta)).
            personales: huellas con datos personales, que se excluyen.

        Returns:
            Ideas de curso y de píldora.
        """
        ideas = []
        for huella, (datos, _momento, _ruta) in sorted(fichas.items()):
            if datos["interes"] not in self.INTERESES or huella in personales:
                continue
            comun = dict(
                huella=huella, interes=datos["interes"], idioma=datos["idioma"],
                actual=datos["vigencia"]["estado"] != "desactualizado", con_ejercicios=bool(datos["ejercicios"]),
            )
            for c in datos["ideas_curso"]:
                ideas.append(IdeaFormativa(
                    "curso", c["titulo"].strip(), f"{c['titulo']}. Para {c['destinatarios']}. {c['aprendizaje']}", **comun
                ))
            for p in datos["ideas_pildora"]:
                ideas.append(IdeaFormativa("pildora", p["titulo"].strip(), f"{p['titulo']}. {p['objetivo']}", **comun))
        return [i for i in ideas if i.titulo]
