"""Aplicación web de Orakulue: buscar, leer fichas, descargar y preguntar.

Escucha solo en la dirección de la VPN (ver ``ServidorWeb``) y es de solo
lectura respecto al fondo: no hay nada que permita escribir ni borrar. La única
escritura es la anotación del gasto de las preguntas.
"""

import re
from pathlib import Path

from markdown_it import MarkdownIt
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, Response
from starlette.routing import Route
from starlette.templating import Jinja2Templates

from orakulue.aplicacion.servicio_fondo import ServicioFondo
from orakulue.infraestructura.cliente_modelo import ErrorLlamada
from orakulue.infraestructura.cliente_vectores import ErrorVectores
from orakulue.infraestructura.error_saldo_agotado import ErrorSaldoAgotado
from orakulue.utilidades.formato import Formato

_HUELLA = re.compile(r"[0-9a-f]{64}")
_CLAVE_PROPUESTA = re.compile(r"(curso|pildora)-[0-9a-f]{10}-[0-9]{4}")


class AplicacionWeb:
    """Construye la aplicación Starlette sobre un ``ServicioFondo``."""

    def __init__(self, servicio: ServicioFondo, personal: Path | None = None) -> None:
        """Prepara la aplicación.

        Args:
            servicio: fachada del fondo.
            personal: directorio personal, para abreviar rutas en pantalla.
        """
        self._servicio = servicio
        self._personal = personal or Path.home()
        self._plantillas = Jinja2Templates(directory=str(Path(__file__).parent / "plantillas"))
        self._plantillas.env.filters["ruta"] = lambda r: Formato.ruta(r, self._personal)
        # Sin HTML incrustado: el texto de las fichas lo escribió un modelo a
        # partir de documentos ajenos, y no debe poder inyectar nada.
        self._markdown = MarkdownIt("commonmark", {"html": False}).enable("table")

    def construir(self) -> Starlette:
        """Devuelve la aplicación con sus rutas."""
        return Starlette(routes=[
            Route("/", self.inicio),
            Route("/ficha/{huella}", self.ficha),
            Route("/original/{huella}", self.original),
            Route("/preguntar", self.preguntar, methods=["GET", "POST"]),
            Route("/materias", self.materias),
            Route("/propuestas", self.propuestas),
            Route("/propuesta/{clave}", self.propuesta),
        ])

    async def inicio(self, peticion: Request) -> Response:
        """Formulario de búsqueda y, si hay consulta, sus resultados."""
        consulta = peticion.query_params.get("q", "").strip()
        modo = peticion.query_params.get("modo", "hibrido")
        resultados, error = [], ""
        if consulta:
            try:
                resultados = self._servicio.buscar(consulta, 15, modo if modo in ("hibrido", "palabras", "significado") else "hibrido")
            except ErrorVectores as fallo:
                error = str(fallo)
        return self._pagina(peticion, "buscar.html", consulta=consulta, modo=modo, resultados=resultados, error=error)

    async def ficha(self, peticion: Request) -> Response:
        """Ficha de un documento, en HTML.

        En la web se muestran también las fichas de documentos personales: la
        página solo la ve quien está en la VPN, y nada sale hacia fuera.
        """
        huella = self._huella(peticion)
        info = self._servicio.documento(huella) if huella else None
        if info is None:
            return self._no_encontrado(peticion)
        markdown = self._servicio.ficha(huella, para_fuera=False)
        html = self._markdown.render(self._sin_cabecera(markdown)) if markdown else ""
        return self._pagina(peticion, "ficha.html", info=info, html=html)

    async def original(self, peticion: Request) -> Response:
        """Descarga del fichero original, elegido por huella del inventario."""
        huella = self._huella(peticion)
        ruta = self._servicio.original(huella) if huella else None
        if ruta is None:
            return self._no_encontrado(peticion)
        return FileResponse(ruta, filename=ruta.name)

    async def preguntar(self, peticion: Request) -> Response:
        """Formulario de pregunta y respuesta con fuentes."""
        pregunta, local, resultado, error = "", False, None, ""
        if peticion.method == "POST":
            formulario = await peticion.form()
            pregunta = str(formulario.get("pregunta", "")).strip()
            local = formulario.get("local") == "si"
            if pregunta:
                try:
                    resultado = self._servicio.preguntar(pregunta, local)
                except (ErrorVectores, ErrorLlamada, ErrorSaldoAgotado) as fallo:
                    error = str(fallo)
        return self._pagina(
            peticion, "preguntar.html", pregunta=pregunta, local=local, resultado=resultado, error=error,
            respuesta_html=self._markdown.render(resultado.respuesta.texto) if resultado else "",
        )

    async def materias(self, peticion: Request) -> Response:
        """Índice por materias."""
        return self._pagina(peticion, "materias.html", materias=self._servicio.materias())

    async def propuestas(self, peticion: Request) -> Response:
        """Listado de propuestas de cursos y píldoras (fase 7)."""
        return self._pagina(peticion, "propuestas.html", propuestas=[p for p, _ in self._servicio.propuestas()])

    async def propuesta(self, peticion: Request) -> Response:
        """Una propuesta, en HTML."""
        clave = peticion.path_params.get("clave", "")
        encontrada = self._servicio.propuesta(clave) if _CLAVE_PROPUESTA.fullmatch(clave) else None
        if encontrada is None:
            return self._no_encontrado(peticion)
        propuesta, markdown = encontrada
        return self._pagina(peticion, "propuesta.html", propuesta=propuesta,
                            html=self._markdown.render(self._sin_cabecera(markdown)))

    def _pagina(self, peticion: Request, plantilla: str, **datos) -> HTMLResponse:
        """Renderiza una plantilla."""
        return self._plantillas.TemplateResponse(peticion, plantilla, datos)

    def _no_encontrado(self, peticion: Request) -> HTMLResponse:
        """Página 404."""
        respuesta = self._pagina(peticion, "buscar.html", consulta="", modo="hibrido", resultados=[],
                                 error="Ese documento no está en el fondo.")
        respuesta.status_code = 404
        return respuesta

    @staticmethod
    def _huella(peticion: Request) -> str | None:
        """Huella de la ruta, solo si tiene la forma exacta de una huella."""
        huella = peticion.path_params.get("huella", "")
        return huella if _HUELLA.fullmatch(huella) else None

    @staticmethod
    def _sin_cabecera(markdown: str) -> str:
        """Quita la cabecera YAML de la ficha: en pantalla ya va en la cabecera de la página."""
        if markdown.startswith("---\n"):
            fin = markdown.find("\n---", 4)
            if fin != -1:
                return markdown[fin + 4 :]
        return markdown
