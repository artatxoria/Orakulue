"""Caso de uso: responder a una pregunta con lo que hay en el fondo, citando.

Busca los pasajes que mejor responden, se los da a un modelo de lenguaje con la
orden de no salirse de ellos y de citar cada afirmación, y devuelve la
respuesta con la lista de fuentes.

Los pasajes de documentos con datos personales **nunca** se envían a la API;
solo se usan cuando la respuesta se redacta en local.
"""

from dataclasses import dataclass, field

from orakulue.aplicacion.buscador import Buscador
from orakulue.dominio.consumo_llamada import ConsumoLlamada
from orakulue.dominio.info_documento import InfoDocumento
from orakulue.infraestructura.cliente_local import ClienteLocal
from orakulue.infraestructura.cliente_modelo import ClienteModelo

INSTRUCCIONES_RESPUESTA = """\
Eres el asistente documental de un formador de informática y competencias \
digitales que trabaja en Euskadi. Respondes a sus preguntas usando solo los \
pasajes de su propio fondo documental que se te dan, numerados.

- Responde en castellano, aunque los pasajes estén en euskera o en inglés.
- Usa solo lo que dicen los pasajes. Cada afirmación lleva la cita del pasaje \
del que sale, así: [3]. Si combinas varios, [1][4].
- Si los pasajes no bastan para responder, dilo claramente y di qué falta; no \
completes con conocimiento propio.
- Piensa en alguien que prepara formación: si los pasajes traen ejercicios, \
ejemplos o explicaciones aprovechables, señálalos.
- No reproduzcas datos personales que aparezcan en los pasajes.
- Sé breve y concreto.
"""


@dataclass
class Respuesta:
    """Respuesta a una pregunta. Solo la usa ``Respondedor``.

    Atributos:
        texto: la respuesta redactada.
        fuentes: documento de cada pasaje numerado, en orden.
        consumo: tokens gastados en la API, o ``None`` en local.
        omitidos_por_privacidad: documentos relevantes que no se han enviado
            por tener datos personales.
    """

    texto: str
    fuentes: list[InfoDocumento] = field(default_factory=list)
    consumo: ConsumoLlamada | None = None
    omitidos_por_privacidad: int = 0


class Respondedor:
    """Busca, compone el mensaje y pide la respuesta."""

    #: Documentos que se consideran y pasajes que se envían como máximo.
    DOCUMENTOS = 8
    PASAJES = 10
    PASAJES_POR_DOCUMENTO = 2

    def __init__(self, buscador: Buscador) -> None:
        """Prepara el respondedor.

        Args:
            buscador: buscador híbrido.
        """
        self._buscador = buscador

    def responder(
        self, pregunta: str, *, cliente: ClienteModelo | None = None, modelo: str = "",
        local: ClienteLocal | None = None,
    ) -> Respuesta:
        """Responde a una pregunta.

        Se pasa ``cliente`` y ``modelo`` para usar la API, o ``local`` para
        redactar en el propio equipo.

        Args:
            pregunta: la pregunta.
            cliente: cliente de la API.
            modelo: modelo de la API.
            local: cliente del modelo local.

        Returns:
            La respuesta con sus fuentes.

        Raises:
            ValueError: si no se indica ni API ni local.
        """
        if local is None and cliente is None:
            raise ValueError("Hay que indicar el cliente de la API o el local.")
        en_local = local is not None
        resultados = self._buscador.buscar(pregunta, self.DOCUMENTOS)
        pasajes: list[tuple[InfoDocumento, str]] = []
        omitidos = 0
        for resultado in resultados:
            if resultado.info.personal and not en_local:
                omitidos += 1
                continue
            for pieza in resultado.piezas[: self.PASAJES_POR_DOCUMENTO]:
                if len(pasajes) < self.PASAJES:
                    tipo, texto = self._buscador.texto_pieza(pieza)
                    pasajes.append((resultado.info, f"(ficha) {texto}" if tipo == "ficha" else texto))

        if not pasajes:
            return Respuesta("No hay en el fondo nada que responda a esta pregunta"
                             + (" que se pueda enviar a la API." if omitidos else "."),
                             omitidos_por_privacidad=omitidos)
        mensaje = "\n\n".join(
            f"[{n}] {info.titulo} — {info.rutas[0].name}\n{texto}" for n, (info, texto) in enumerate(pasajes, start=1)
        ) + f"\n\nPregunta: {pregunta}"
        if en_local:
            return Respuesta(local.redactar(INSTRUCCIONES_RESPUESTA, mensaje), [i for i, _ in pasajes],
                             omitidos_por_privacidad=0)
        texto, consumo = cliente.redactar(modelo, INSTRUCCIONES_RESPUESTA, mensaje)
        return Respuesta(texto, [i for i, _ in pasajes], consumo, omitidos)
