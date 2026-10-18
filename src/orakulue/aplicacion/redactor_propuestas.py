"""Caso de uso: redactar una propuesta de curso o de píldora a partir de su candidata.

El modelo recibe, numeradas, las fichas de los documentos que respaldan la
candidata, las ideas que convergen en ella y los títulos del catálogo actual.
Debe construir la propuesta solo con eso y citar las fuentes: lo que no esté
en el fondo va a «falta por preparar», no se inventa.
"""

from dataclasses import dataclass

from orakulue.dominio.candidata import Candidata
from orakulue.dominio.consumo_llamada import ConsumoLlamada
from orakulue.dominio.propuesta import Propuesta
from orakulue.infraestructura.cliente_modelo import ClienteModelo
from orakulue.infraestructura.esquema_propuesta_curso import EsquemaPropuestaCurso
from orakulue.infraestructura.esquema_propuesta_pildora import EsquemaPropuestaPildora
from orakulue.infraestructura.lector_catalogo import CursoCatalogo

INSTRUCCIONES_PROPUESTA = """\
Eres asesor de producto de un formador de informática y competencias \
digitales que trabaja en Euskadi, en castellano y en euskera, para empresas, \
personas trabajadoras y personas desempleadas. Diseñas propuestas de formación \
nuevas a partir de su propio fondo documental.

Recibes una idea que aparece en varios documentos de su fondo, las fichas de \
esos documentos numeradas como fuentes [1], [2]… y la lista de cursos que ya \
ofrece. Con eso redactas una propuesta.

Criterios:
- Construye la propuesta con lo que hay en las fuentes. En «material \
existente» y «ejercicios disponibles» indica de qué fuentes sale cada cosa \
(sus números). Lo que una buena propuesta necesitaría y no esté en las \
fuentes va a «falta por preparar»: no lo inventes como si existiera.
- Escribe en castellano, en un tono profesional y concreto, como el de un \
catálogo de formación para empresas. Nada de vaguedades.
- No indiques duraciones, horas, sesiones ni precios: eso lo decide el \
formador.
- Si la idea se parece a un curso que ya ofrece, explica en \
«diferencia con el catálogo» en qué se distingue o si es mejor plantearla como \
actualización de ese curso. Si no se parece a ninguno, dilo.
- Para una píldora: una formación corta y práctica para empresas, centrada en \
un problema concreto y con una práctica principal que se lleve resuelta.
- No incluyas datos personales de nadie.
"""


@dataclass(frozen=True)
class ResultadoRedaccion:
    """Propuesta redactada y su consumo. Solo la usa ``RedactorPropuestas``.

    Atributos:
        propuesta: la propuesta.
        consumo: tokens gastados.
    """

    propuesta: Propuesta
    consumo: ConsumoLlamada


class RedactorPropuestas:
    """Compone el mensaje de una candidata y pide la propuesta."""

    #: Documentos que se dan como fuentes, como máximo.
    FUENTES = 8
    _ORDEN_INTERES = {"alto": 0, "medio": 1}

    def __init__(self, fichas: dict[str, tuple[dict, str, object]], catalogo: list[CursoCatalogo]) -> None:
        """Prepara el redactor.

        Args:
            fichas: datos de cada ficha (huella → (datos, momento, ruta)).
            catalogo: cursos que ya se ofrecen.
        """
        self._fichas = fichas
        self._catalogo = catalogo

    def fuentes(self, candidata: Candidata) -> list[str]:
        """Huellas que se dan como fuentes: primero las de interés alto, luego
        las que más ideas aportan al grupo."""
        aportes: dict[str, int] = {}
        for idea in candidata.ideas:
            aportes[idea.huella] = aportes.get(idea.huella, 0) + 1
        con_ficha = [h for h in aportes if h in self._fichas]
        con_ficha.sort(key=lambda h: (self._ORDEN_INTERES.get(self._fichas[h][0]["interes"], 2), -aportes[h], h))
        return con_ficha[: self.FUENTES]

    def mensaje(self, candidata: Candidata, fuentes: list[str]) -> str:
        """Mensaje para el modelo: idea, ideas convergentes, fuentes y catálogo."""
        convergentes = "\n".join(f"- {i.titulo}" for i in candidata.ideas[:15])
        bloques = []
        for numero, huella in enumerate(fuentes, start=1):
            d = self._fichas[huella][0]
            teoria = "; ".join(t["concepto"] for t in d["teoria"][:8])
            ejercicios = "\n".join(f"  - {e['descripcion']} (practica: {e['practica']})" for e in d["ejercicios"][:6])
            bloques.append(
                f"[{numero}] {d['titulo']} — {d['tipo']}, {d['idioma']}, nivel {d['nivel']}, "
                f"vigencia: {d['vigencia']['estado']}\nResumen: {d['resumen']}\nTeoría: {teoria or '—'}\n"
                f"Ejercicios:\n{ejercicios or '  —'}"
            )
        catalogo = "\n".join(f"- {c.titulo}" for c in self._catalogo)
        relacion = f"\nRelación detectada con el catálogo: {candidata.en_catalogo}" if candidata.en_catalogo else ""
        tipo = "un curso" if candidata.tipo == "curso" else "una píldora formativa para empresas"
        return (
            f"Redacta {tipo} a partir de esta idea: «{candidata.titulo}».{relacion}\n\n"
            f"La misma idea aparece, con otras palabras, en estos documentos del fondo:\n{convergentes}\n\n"
            f"Fuentes:\n\n" + "\n\n".join(bloques) + f"\n\nCursos que ya ofrece:\n{catalogo}"
        )

    def redactar(
        self, candidata: Candidata, cliente: ClienteModelo, modelo: str, esfuerzo: str | None = None
    ) -> ResultadoRedaccion:
        """Redacta la propuesta de una candidata.

        Raises:
            ErrorSaldoAgotado, ErrorLlamada: como en el resto de llamadas.
        """
        fuentes = self.fuentes(candidata)
        esquema = EsquemaPropuestaCurso.json() if candidata.tipo == "curso" else EsquemaPropuestaPildora.json()
        datos, consumo = cliente.pedir_json(
            modelo, INSTRUCCIONES_PROPUESTA, self.mensaje(candidata, fuentes), esquema, esfuerzo
        )
        propuesta = Propuesta(
            candidata.tipo, candidata.clave, consumo.modelo, datos, tuple(fuentes),
            candidata.puntuacion, dict(candidata.desglose), candidata.en_catalogo,
        )
        return ResultadoRedaccion(propuesta, consumo)
