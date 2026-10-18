"""Exportación de una propuesta aceptada como borrador para Bibliotecario.

Bibliotecario produce el material de un curso a partir de su ``curso.yaml``
(ver ``ELABORACION-DE-CURSOS.md`` en ese proyecto). Una propuesta no es un
temario contratado, así que el borrador lo dice: cliente «propuesta propia» y
todos los apartados con ``origen: propio``. Si después llega un cliente con su
temario, ese temario manda.

El YAML se escribe a mano, con los valores como JSON (que es YAML válido),
para no añadir una dependencia por un solo fichero.
"""

import json
from pathlib import Path

from orakulue.dominio.propuesta import Propuesta
from orakulue.utilidades.formato import Formato


class ExportadorBibliotecario:
    """Escribe la carpeta de borrador de un curso."""

    def __init__(self, documentos: dict[str, tuple[str, Path]], personal: Path) -> None:
        """Prepara el exportador.

        Args:
            documentos: huella → (título, ruta), para la lista de fuentes.
            personal: directorio personal, para abreviar rutas.
        """
        self._documentos = documentos
        self._personal = personal

    def exportar(self, propuesta: Propuesta, carpeta: Path) -> Path:
        """Crea ``carpeta/<título>/`` con ``curso.yaml`` y ``fuentes.md``.

        Args:
            propuesta: propuesta aceptada.
            carpeta: carpeta donde se crean los borradores.

        Returns:
            Carpeta del borrador.
        """
        destino = carpeta / Formato.slug(propuesta.titulo, 60)
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "curso.yaml").write_text(self._yaml(propuesta), encoding="utf-8")
        (destino / "fuentes.md").write_text(self._fuentes(propuesta), encoding="utf-8")
        return destino

    def _yaml(self, propuesta: Propuesta) -> str:
        """Contenido de ``curso.yaml``."""
        d = propuesta.datos
        valor = lambda v: json.dumps(v, ensure_ascii=False)  # noqa: E731
        if propuesta.tipo == "curso":
            dirigido, objetivo, requisitos = d["publico_objetivo"], d["descripcion"], d["requisitos_previos"]
            modulos = [(m["titulo"], m["contenidos"]) for m in d["modulos"]]
        else:
            dirigido, objetivo, requisitos = d["destinatarios"], d["objetivo"], []
            modulos = [(propuesta.titulo, d["contenidos"])]
        lineas = [
            f"# Borrador generado por Orakulue a partir de la propuesta {propuesta.clave}.",
            "# NO es un temario contratado: todos los apartados son de origen propio.",
            "# Si llega un cliente con su temario, se sustituye por la transcripción literal.",
            'cliente: "propuesta propia"',
            'cliente_final: ""',
            "idioma: es",
            "ficha:",
            "  duracion_horas: null   # a decidir",
            f"  dirigido_a: {valor(dirigido)}",
            f"  requisitos_previos: {valor([Formato.slug(r, 40).lower() for r in requisitos])}",
            f"  objetivo_general: {valor(objetivo)}",
            "modulos:",
        ]
        for numero, (titulo, apartados) in enumerate(modulos, start=1):
            lineas += [f"  - numero: {numero}", f"    titulo: {valor(titulo)}", "    alternativa: false", "    apartados:"]
            for orden, apartado in enumerate(apartados, start=1):
                ident = f"{numero:02d}_{orden:02d}"
                fichero = f"unidad{numero:02d}/{ident}_{Formato.slug(apartado, 40).lower()}.tex"
                lineas += [f"      - id: {valor(ident)}", f"        titulo: {valor(apartado)}",
                           f"        fichero: {valor(fichero)}", "        origen: propio"]
        return "\n".join(lineas) + "\n"

    def _fuentes(self, propuesta: Propuesta) -> str:
        """Documentos del fondo en los que se apoya la propuesta."""
        lineas = [f"# Fuentes de «{propuesta.titulo}»", "",
                  "Documentos del fondo que respaldan la propuesta (los números son las citas de la propuesta):", ""]
        for numero, huella in enumerate(propuesta.fuentes, start=1):
            titulo, ruta = self._documentos.get(huella, (huella[:12], Path("?")))
            lineas.append(f"- [{numero}] {titulo} — `{Formato.ruta(ruta, self._personal)}`")
        if propuesta.datos.get("falta_por_preparar"):
            lineas += ["", "## Falta por preparar", ""] + [f"- {f}" for f in propuesta.datos["falta_por_preparar"]]
        return "\n".join(lineas) + "\n"
