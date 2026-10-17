"""Informe de duplicados en Markdown, para revisar antes de mover nada.

Está pensado para leerse de arriba abajo: primero las cifras, después dónde
está el material, qué se ha dejado fuera y, por último, los grupos de copias.
La lista completa de copias va en el CSV que lo acompaña.
"""

from collections import Counter
from datetime import datetime
from pathlib import Path

from orakulue.aplicacion.detector_duplicados import DetectorDuplicados
from orakulue.dominio.carpeta_omitida import MotivoOmision
from orakulue.dominio.documento import Documento
from orakulue.dominio.grupo_duplicados import GrupoDuplicados
from orakulue.dominio.resumen_inventario import ResumenInventario
from orakulue.utilidades.formato import Formato


class InformeDuplicados:
    """Compone el informe Markdown de la fase 1."""

    # Niveles de carpeta bajo el directorio personal para agrupar el material.
    NIVELES_CARPETA = 3
    # Grupos que se detallan en el Markdown; el resto está en el CSV.
    GRUPOS_DETALLADOS = 40
    # Parejas de carpetas que más copias comparten.
    PAREJAS_MOSTRADAS = 25
    # Omisiones muy numerosas y poco interesantes: se cuentan, no se listan.
    MOTIVOS_SOLO_CONTADOS = {MotivoOmision.OCULTA, MotivoOmision.NOMBRE_EXCLUIDO}

    def __init__(
        self,
        documentos: list[Documento],
        grupos: list[GrupoDuplicados],
        detector: DetectorDuplicados,
        resumen: ResumenInventario | None,
        personal: Path,
        nombre_csv: str,
    ) -> None:
        """Reúne los datos del informe.

        Args:
            documentos: todo el inventario.
            grupos: grupos de duplicados ya ordenados.
            detector: para saber qué copia se propone como original.
            resumen: resumen de la pasada recién hecha, o ``None`` si el
                informe se genera sin inventariar.
            personal: directorio personal, para abreviar rutas.
            nombre_csv: nombre del CSV complementario, para citarlo.
        """
        self._documentos = documentos
        self._grupos = grupos
        self._detector = detector
        self._resumen = resumen
        self._personal = personal
        self._nombre_csv = nombre_csv
        self._originales = {g.huella: detector.original_propuesto(g) for g in grupos}

    def componer(self) -> str:
        """Devuelve el informe completo como texto Markdown."""
        secciones = [
            self._cabecera(),
            self._cifras(),
            self._por_carpeta(),
            self._parejas(),
            self._omitidas(),
            self._grupos_detallados(),
            self._errores(),
        ]
        return "\n\n".join(s for s in secciones if s) + "\n"

    def escribir(self, ruta: Path) -> None:
        """Escribe el informe en disco.

        Args:
            ruta: fichero de destino; su carpeta se crea si falta.
        """
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(self.componer(), encoding="utf-8")

    # --- Secciones ---------------------------------------------------------

    def _cabecera(self) -> str:
        """Título, fecha y advertencia de que no se ha tocado nada."""
        return (
            "# Orakulue — Informe de duplicados exactos\n\n"
            f"Generado el {datetime.now():%d/%m/%Y a las %H:%M}.\n\n"
            "**Este informe no ha movido, renombrado ni borrado nada.** Es la base "
            "para decidir la fase 2 (centralización en `fondo/` y enlaces simbólicos).\n\n"
            "«Duplicado exacto» significa mismo contenido byte a byte, se llame como "
            "se llame cada fichero. Las versiones distintas de un documento o el mismo "
            "texto en otro formato no aparecen aquí: se tratan en la fase 3."
        )

    def _cifras(self) -> str:
        """Tabla con las cifras globales."""
        total = sum(d.tamano for d in self._documentos)
        sobrantes = sum(g.copias_sobrantes for g in self._grupos)
        recuperable = sum(g.espacio_recuperable for g in self._grupos)
        sin_huella = sum(1 for d in self._documentos if d.huella is None)
        filas = [
            ("Documentos inventariados", Formato.cifra(len(self._documentos))),
            ("Tamaño total", Formato.tamano(total)),
            ("Documentos distintos", Formato.cifra(len(self._documentos) - sobrantes - sin_huella)),
            ("Grupos de duplicados", Formato.cifra(len(self._grupos))),
            ("Copias sobrantes", Formato.cifra(sobrantes)),
            ("Espacio recuperable", Formato.tamano(recuperable)),
            ("Sin huella (ilegibles)", Formato.cifra(sin_huella)),
        ]
        if self._resumen:
            filas += [
                ("Huellas calculadas en esta pasada", Formato.cifra(self._resumen.huellas_calculadas)),
                ("Huellas reaprovechadas", Formato.cifra(self._resumen.huellas_reutilizadas)),
                ("Leído del disco", Formato.tamano(self._resumen.bytes_leidos)),
                ("Ya no estaban desde la pasada anterior", Formato.cifra(self._resumen.desaparecidos)),
            ]
        tabla = "\n".join(f"| {nombre} | {valor} |" for nombre, valor in filas)
        return f"## 1. Cifras\n\n| | |\n|---|---:|\n{tabla}"

    def _por_carpeta(self) -> str:
        """Dónde está el material y cuánto de cada carpeta es copia."""
        copias = self._rutas_copia()
        documentos = Counter()
        bytes_ = Counter()
        repetidos = Counter()
        for documento in self._documentos:
            carpeta = Formato.carpeta_resumida(documento.ruta, self._personal, self.NIVELES_CARPETA)
            documentos[carpeta] += 1
            bytes_[carpeta] += documento.tamano
            if documento.ruta in copias:
                repetidos[carpeta] += 1
        filas = "\n".join(
            f"| `{Formato.ruta(c, self._personal)}` | {Formato.cifra(n)} | "
            f"{Formato.tamano(bytes_[c])} | {Formato.cifra(repetidos[c])} |"
            for c, n in documentos.most_common()
        )
        return (
            "## 2. Dónde está el material\n\n"
            f"Agrupado a {self.NIVELES_CARPETA} niveles bajo el directorio personal. "
            "«Copias» son los ficheros que pasarían a ser enlace si se acepta el "
            "original propuesto. **Revisa esta lista para confirmar el criterio**: "
            "cualquier carpeta que no sea documentación de formación debe añadirse a "
            "`rutas_excluidas` antes de la fase 2.\n\n"
            "| Carpeta | Documentos | Tamaño | Copias |\n|---|---:|---:|---:|\n" + filas
        )

    def _parejas(self) -> str:
        """Qué carpetas se copian entre sí, para entender de dónde salen las copias."""
        parejas = Counter()
        for grupo in self._grupos:
            original = self._originales[grupo.huella]
            carpeta_original = Formato.carpeta_resumida(original, self._personal, 4)
            for documento in grupo.documentos:
                if documento.ruta != original:
                    carpeta_copia = Formato.carpeta_resumida(documento.ruta, self._personal, 4)
                    parejas[(carpeta_copia, carpeta_original)] += 1
        if not parejas:
            return ""
        filas = "\n".join(
            f"| `{Formato.ruta(c, self._personal)}` | `{Formato.ruta(o, self._personal)}` | {n} |"
            for (c, o), n in parejas.most_common(self.PAREJAS_MOSTRADAS)
        )
        return (
            "## 3. De dónde salen las copias\n\n"
            f"Las {self.PAREJAS_MOSTRADAS} parejas de carpetas (a 4 niveles) que más "
            "copias comparten. Una carpeta que aparece mucho como «copia» suele ser una "
            "descarga repetida o una copia de seguridad manual.\n\n"
            "| La copia está en | El original propuesto está en | Copias |\n|---|---|---:|\n"
            + filas
        )

    def _omitidas(self) -> str:
        """Carpetas que no se han recorrido, agrupadas por motivo."""
        if not self._resumen or not self._resumen.carpetas_omitidas:
            return ""
        por_motivo: dict[MotivoOmision, list[Path]] = {}
        for omitida in self._resumen.carpetas_omitidas:
            por_motivo.setdefault(omitida.motivo, []).append(omitida.ruta)
        bloques = ["## 4. Carpetas que no se han recorrido"]
        for motivo in MotivoOmision:
            rutas = por_motivo.get(motivo)
            if not rutas:
                continue
            if motivo in self.MOTIVOS_SOLO_CONTADOS:
                bloques.append(f"- **{motivo.value[0].upper()}{motivo.value[1:]}:** {Formato.cifra(len(rutas))} carpetas.")
                continue
            lista = "\n".join(f"  - `{Formato.ruta(r, self._personal)}`" for r in sorted(rutas))
            bloques.append(f"- **{motivo.value[0].upper()}{motivo.value[1:]}** ({len(rutas)}):\n{lista}")
        return "\n\n".join(bloques)

    def _grupos_detallados(self) -> str:
        """Los grupos que más espacio ocupan, con el original propuesto marcado."""
        if not self._grupos:
            return "## 5. Grupos de duplicados\n\nNo hay duplicados exactos."
        bloques = [
            "## 5. Grupos de duplicados que más ocupan\n\n"
            f"Los {min(self.GRUPOS_DETALLADOS, len(self._grupos))} primeros de "
            f"{Formato.cifra(len(self._grupos))}. La lista completa está en "
            f"`{self._nombre_csv}`. **★** marca el original propuesto; el criterio es: "
            "primero lo que ya está en `fondo/` o en `formakuntza`, después la ruta "
            "menos profunda y, a igualdad, la copia más antigua."
        ]
        for numero, grupo in enumerate(self._grupos[: self.GRUPOS_DETALLADOS], start=1):
            original = self._originales[grupo.huella]
            lineas = "\n".join(
                f"- {'★' if d.ruta == original else '　'} `{Formato.ruta(d.ruta, self._personal)}`"
                for d in grupo.documentos
            )
            bloques.append(
                f"### {numero}. {grupo.documentos[0].ruta.name}\n\n"
                f"{len(grupo.documentos)} copias de {Formato.tamano(grupo.tamano)} · "
                f"recuperable {Formato.tamano(grupo.espacio_recuperable)} · "
                f"huella `{grupo.huella[:12]}…`\n\n{lineas}"
            )
        return "\n\n".join(bloques)

    def _errores(self) -> str:
        """Ficheros que no se han podido leer."""
        if not self._resumen or not self._resumen.errores:
            return ""
        lista = "\n".join(
            f"- `{Formato.ruta(r, self._personal)}`: {m}" for r, m in self._resumen.errores
        )
        return f"## 6. Ficheros que no se han podido leer\n\n{lista}"

    def _rutas_copia(self) -> set[Path]:
        """Rutas de todas las copias que no son el original propuesto."""
        return {
            d.ruta
            for g in self._grupos
            for d in g.documentos
            if d.ruta != self._originales[g.huella]
        }
