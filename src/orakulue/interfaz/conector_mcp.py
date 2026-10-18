"""Conector MCP: Orakulue como herramienta de Claude.

Claude Code y la app de escritorio, en el PC de sobremesa, lo arrancan como un
proceso local y le hablan por la entrada y salida estándar (transporte
*stdio*). No abre ningún puerto ni expone nada en la red.

Todo lo que devuelve llega a Anthropic. Por eso, de los documentos con datos
personales solo se dice que existen y dónde están: su texto y su ficha no se
devuelven nunca.
"""

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from orakulue.aplicacion.servicio_fondo import ServicioFondo
from orakulue.dominio.info_documento import InfoDocumento
from orakulue.utilidades.formato import Formato

INSTRUCCIONES_CONECTOR = """\
Orakulue es el fondo documental de un formador de informática y competencias \
digitales: manuales, libros, apuntes, ejercicios y presentaciones, en castellano, \
euskera e inglés, cada uno con una ficha (resumen, teoría, ejercicios \
aprovechables, ideas de curso y de píldora formativa).

Para preparar formación o responder sobre el material: usa `buscar` (en \
lenguaje natural; encuentra también material en euskera con preguntas en \
castellano), después `leer_ficha` de los documentos prometedores y \
`leer_pasajes` cuando necesites el texto concreto. `materias` da una visión \
general. Cita siempre el documento del que sale cada cosa. Los documentos \
marcados con datos personales no se pueden leer por este conector.
"""

_PERSONAL = "contiene datos personales: su contenido no se puede consultar por el conector"


class ConectorMcp:
    """Construye el servidor MCP sobre un ``ServicioFondo``."""

    def __init__(self, servicio: ServicioFondo, personal: Path | None = None) -> None:
        """Prepara el conector.

        Args:
            servicio: fachada del fondo.
            personal: directorio personal, para abreviar rutas.
        """
        self._servicio = servicio
        self._personal = personal or Path.home()

    def construir(self) -> MCPServer:
        """Devuelve el servidor con sus cuatro herramientas registradas."""
        servidor = MCPServer("orakulue", instructions=INSTRUCCIONES_CONECTOR)
        servidor.tool(description=(
            "Busca en el fondo documental de formación. Devuelve los documentos más útiles para la "
            "consulta, con su huella (para leer_ficha y leer_pasajes), materia, interés formativo y el "
            "pasaje que mejor casa."
        ))(self.buscar)
        servidor.tool(description="Ficha completa de un documento, por su huella.")(self.leer_ficha)
        servidor.tool(description=(
            "Pasajes del texto de un documento (por su huella) que mejor responden a una consulta."
        ))(self.leer_pasajes)
        servidor.tool(description="Materias del fondo con sus documentos de más interés formativo.")(self.materias)
        return servidor

    def buscar(self, consulta: str, cantidad: int = 10) -> str:
        """Herramienta ``buscar``.

        Args:
            consulta: lo que se busca, en lenguaje natural.
            cantidad: documentos que se devuelven (máximo 20).

        Returns:
            Lista en Markdown.
        """
        resultados = self._servicio.buscar(consulta, max(1, min(cantidad, 20)))
        if not resultados:
            return "No hay nada en el fondo que case con esa consulta."
        bloques = []
        for numero, r in enumerate(resultados, start=1):
            lineas = [f"{numero}. **{r.info.titulo}** — huella `{r.info.huella}`", f"   {self._marcas(r.info)}"]
            if r.info.personal:
                lineas.append(f"   ({_PERSONAL})")
            else:
                lineas.append(f"   Pasaje: «{' '.join(r.pasaje.split())[:400]}»")
            if r.variantes:
                lineas.append(f"   Otras versiones: {len(r.variantes)}")
            bloques.append("\n".join(lineas))
        return "\n\n".join(bloques)

    def leer_ficha(self, huella: str) -> str:
        """Herramienta ``leer_ficha``."""
        info = self._servicio.documento(huella)
        if info is None:
            return "No hay ningún documento con esa huella."
        if info.personal:
            return f"«{info.titulo}» {_PERSONAL}."
        ficha = self._servicio.ficha(huella, para_fuera=True)
        return ficha or f"«{info.titulo}» no tiene ficha. Usa leer_pasajes para ver su texto."

    def leer_pasajes(self, huella: str, consulta: str, cantidad: int = 3) -> str:
        """Herramienta ``leer_pasajes``."""
        info = self._servicio.documento(huella)
        if info is None:
            return "No hay ningún documento con esa huella."
        if info.personal:
            return f"«{info.titulo}» {_PERSONAL}."
        pasajes = self._servicio.pasajes(huella, consulta, max(1, min(cantidad, 8)), para_fuera=True)
        if not pasajes:
            return f"Ningún pasaje de «{info.titulo}» casa con esa consulta."
        return f"Pasajes de «{info.titulo}»:\n\n" + "\n\n---\n\n".join(pasajes)

    def materias(self) -> str:
        """Herramienta ``materias``: cada materia con sus diez documentos de más interés."""
        bloques = []
        for materia, lista in self._servicio.materias().items():
            filas = "\n".join(f"- {i.titulo} (interés {i.interes}) — `{i.huella}`" for i in lista[:10])
            bloques.append(f"## {materia} ({len(lista)} documentos)\n\n{filas}")
        return "\n\n".join(bloques)

    def _marcas(self, info: InfoDocumento) -> str:
        """Materia, interés y ruta en una línea."""
        partes = [p for p in (info.materia, f"interés {info.interes}" if info.interes else "") if p]
        partes.append(Formato.ruta(info.rutas[0], self._personal))
        return " · ".join(partes)
