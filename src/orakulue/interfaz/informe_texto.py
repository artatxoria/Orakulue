"""Informe de la fase 3: cobertura de la extracción, idiomas, casi duplicados y
documentos con datos personales.

Nunca escribe los datos personales encontrados: solo cuántos hay de cada tipo
y en qué documento, para que se pueda revisar a mano.
"""

from collections import Counter
from datetime import datetime
from pathlib import Path

from orakulue.dominio.grupo_casi_duplicados import GrupoCasiDuplicados
from orakulue.dominio.marca_datos_personales import MarcaDatosPersonales, NivelRiesgo
from orakulue.dominio.texto_extraido import EstadoExtraccion
from orakulue.utilidades.formato import Formato


class InformeTexto:
    """Compone el informe Markdown de la fase 3."""

    GRUPOS_DETALLADOS = 40
    _IDIOMAS = {"es": "Castellano", "eu": "Euskera", "en": "Inglés", "?": "Sin determinar"}

    def __init__(
        self,
        metadatos: list[tuple[str, EstadoExtraccion, int, str, str, str]],
        rutas: dict[str, list[Path]],
        grupos: list[GrupoCasiDuplicados],
        marcas: list[MarcaDatosPersonales],
        personal: Path,
    ) -> None:
        """Reúne los datos.

        Args:
            metadatos: (huella, estado, caracteres, extractor, idioma, mensaje).
            rutas: rutas de cada huella en el inventario.
            grupos: grupos de casi duplicados.
            marcas: marcas de datos personales.
            personal: directorio personal, para abreviar rutas.
        """
        self._metadatos = metadatos
        self._rutas = rutas
        self._grupos = grupos
        self._marcas = marcas
        self._personal = personal

    def escribir(self, ruta: Path) -> None:
        """Escribe el informe.

        Args:
            ruta: fichero de destino.
        """
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(self.componer(), encoding="utf-8")

    def componer(self) -> str:
        """Devuelve el informe completo."""
        return "\n\n".join(s for s in (
            "# Orakulue — Informe de texto\n\n"
            f"Generado el {datetime.now():%d/%m/%Y a las %H:%M}. Solo lectura: no se ha "
            "modificado ningún documento.",
            self._extraccion(), self._sin_texto(), self._idiomas(),
            self._casi_duplicados(), self._datos_personales(), self._errores(),
        ) if s) + "\n"

    def _ruta(self, huella: str) -> str:
        """Primera ruta de una huella, abreviada."""
        rutas = self._rutas.get(huella)
        return Formato.ruta(rutas[0], self._personal) if rutas else f"(huella {huella[:12]}…)"

    def _extraccion(self) -> str:
        """Cuántos contenidos se han leído y con qué resultado, por formato."""
        tabla: dict[str, Counter] = {}
        for huella, estado, *_ in self._metadatos:
            rutas = self._rutas.get(huella) or [Path("?")]
            formato = rutas[0].suffix.lower().lstrip(".") or "?"
            tabla.setdefault(formato, Counter())[estado] += 1
        estados = list(EstadoExtraccion)
        cabecera = "| Formato | " + " | ".join(e.value.capitalize() for e in estados) + " |"
        separador = "|---|" + "---:|" * len(estados)
        filas = [
            f"| {f} | " + " | ".join(Formato.cifra(c[e]) for e in estados) + " |"
            for f, c in sorted(tabla.items(), key=lambda par: -sum(par[1].values()))
        ]
        total = Counter(e for _, e, *_ in self._metadatos)
        resumen = ", ".join(f"{Formato.cifra(total[e])} {e.value}" for e in estados)
        return (
            f"## 1. Extracción\n\n{Formato.cifra(len(self._metadatos))} contenidos distintos: "
            f"{resumen}.\n\n" + "\n".join([cabecera, separador, *filas])
        )

    def _sin_texto(self) -> str:
        """Dónde están los documentos que necesitarán reconocimiento óptico."""
        huellas = [h for h, e, *_ in self._metadatos if e is EstadoExtraccion.SIN_TEXTO]
        if not huellas:
            return ""
        carpetas = Counter(
            Formato.carpeta_resumida(self._rutas[h][0], self._personal, 4)
            for h in huellas if self._rutas.get(h)
        )
        filas = "\n".join(
            f"| `{Formato.ruta(c, self._personal)}` | {Formato.cifra(n)} |"
            for c, n in carpetas.most_common(20)
        )
        return (
            "## 2. Sin capa de texto\n\n"
            f"{Formato.cifra(len(huellas))} documentos no tienen texto que leer: casi siempre son PDF "
            "escaneados. Necesitan reconocimiento óptico de caracteres (OCR), que no está "
            "instalado. Las 20 carpetas con más:\n\n| Carpeta | Documentos |\n|---|---:|\n" + filas
        )

    def _idiomas(self) -> str:
        """Reparto por idioma de los textos leídos."""
        idiomas = Counter(i for _, e, _, _, i, _ in self._metadatos if e is EstadoExtraccion.CORRECTA)
        filas = "\n".join(
            f"| {self._IDIOMAS.get(i, i)} | {Formato.cifra(n)} |" for i, n in idiomas.most_common()
        )
        return "## 3. Idiomas\n\n| Idioma | Documentos |\n|---|---:|\n" + filas

    def _casi_duplicados(self) -> str:
        """Grupos de documentos distintos con casi el mismo texto, en dos clases."""
        if not self._grupos:
            return "## 4. Casi duplicados\n\nNo se han encontrado."
        identicos = [g for g in self._grupos if g.casi_identicos]
        familias = [g for g in self._grupos if not g.casi_identicos]
        return "\n\n".join([
            "## 4. Casi duplicados\n\nDocumentos cuyos ficheros son distintos pero cuyo texto coincide "
            "en un 80 % o más. **No se ha cambiado nada.**",
            self._bloque_grupos(
                "4.1. Casi idénticos (95 % o más)", identicos,
                "Probablemente el mismo documento: en otro formato, con una errata corregida o "
                "regenerado. Aquí sí tiene sentido decidir cuál conservar.",
            ),
            self._bloque_grupos(
                "4.2. Familias de plantilla (80–95 %)", familias,
                "Documentos distintos hechos sobre el mismo modelo: una propuesta por cliente, un "
                "acta por empresa, los capítulos de una misma serie. No sobra ninguno; en la fase 4 "
                "bastará con una ficha por familia.",
            ),
        ])

    def _bloque_grupos(self, titulo: str, grupos: list[GrupoCasiDuplicados], explicacion: str) -> str:
        """Detalla una clase de grupos de casi duplicados."""
        miembros = sum(len(g.huellas) for g in grupos)
        bloques = [
            f"### {titulo}\n\n{Formato.cifra(len(grupos))} grupos con {Formato.cifra(miembros)} "
            f"documentos. {explicacion} Se detallan los {min(self.GRUPOS_DETALLADOS, len(grupos))} primeros."
        ]
        for numero, grupo in enumerate(grupos[: self.GRUPOS_DETALLADOS], start=1):
            lineas = "\n".join(f"- `{self._ruta(h)}`" for h in grupo.huellas)
            parecido = (
                f"{grupo.similitud_maxima:.0%}" if grupo.similitud_minima == grupo.similitud_maxima
                else f"{grupo.similitud_minima:.0%}–{grupo.similitud_maxima:.0%}"
            )
            bloques.append(f"#### {numero}. Parecido {parecido}\n\n{lineas}")
        return "\n\n".join(bloques)

    def _datos_personales(self) -> str:
        """Documentos con indicios, sin mostrar ningún dato."""
        niveles = Counter(m.nivel for m in self._marcas)
        resumen = "\n".join(
            f"| {n.value.capitalize()} | {Formato.cifra(niveles[n])} |" for n in NivelRiesgo
        )
        excluidas = sorted(
            (m for m in self._marcas if m.excluir_de_fichas),
            key=lambda m: (m.nivel is not NivelRiesgo.ALTO, self._ruta(m.huella)),
        )
        filas = "\n".join(
            f"| {m.nivel.value} | `{self._ruta(m.huella)}` | {m.identificadores} | {m.correos} | "
            f"{m.telefonos} | {m.rotulos} | {m.personas} |"
            for m in excluidas
        )
        return (
            "## 5. Datos personales\n\n"
            "Indicios en el texto, **sin mostrar ningún valor**. Los niveles medio y alto quedan "
            "excluidos de la fase 4 (no se enviarán a ningún servicio externo) hasta que se revisen.\n\n"
            "| Nivel | Documentos |\n|---|---:|\n" + resumen + "\n\n"
            "Criterio: **alto**, algún DNI, NIE o IBAN con dígito de control válido; **medio**, correos, "
            "teléfonos o nombres de persona concentrados en el texto, o un formulario personal "
            "rellenado; **bajo**, algún indicio suelto.\n\n"
            "| Nivel | Documento | DNI/NIE/IBAN | Correos | Teléfonos | Rótulos | Personas |\n"
            "|---|---|---:|---:|---:|---:|---:|\n" + filas
        )

    def _errores(self) -> str:
        """Documentos que no se han podido leer."""
        errores = [(h, m) for h, e, _, _, _, m in self._metadatos if e is EstadoExtraccion.ERROR]
        if not errores:
            return ""
        lista = "\n".join(f"- `{self._ruta(h)}`: {m}" for h, m in errores)
        return f"## 6. No se han podido leer\n\n{lista}"
