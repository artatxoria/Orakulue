"""Informe de la prueba comparativa de modelos y del presupuesto del fondo."""

import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from orakulue.aplicacion.estimador_coste import EstimadorCoste
from orakulue.aplicacion.prueba_comparativa import ResultadoModelo
from orakulue.aplicacion.seleccion_fichables import Fichable, ResultadoSeleccion
from orakulue.infraestructura.catalogo_tarifas import FECHA_TARIFAS, CatalogoTarifas
from orakulue.utilidades.formato import Formato


class InformePrueba:
    """Compone el informe Markdown de la prueba (simulacro o real)."""

    def __init__(
        self,
        seleccion: ResultadoSeleccion,
        muestra: list[Fichable],
        modelos: list[str],
        personal: Path,
        resultados: list[ResultadoModelo] | None = None,
        aviso: str = "",
    ) -> None:
        """Reúne los datos.

        Args:
            seleccion: resultado de la selección de fichables.
            muestra: documentos de la prueba.
            modelos: modelos comparados.
            personal: directorio personal, para abreviar rutas.
            resultados: resultados reales, o ``None`` en el simulacro.
            aviso: texto del aviso de saldo.
        """
        self._seleccion = seleccion
        self._muestra = muestra
        self._modelos = modelos
        self._personal = personal
        self._resultados = resultados
        self._aviso = aviso
        self._tarifas = CatalogoTarifas()
        self._estimador = EstimadorCoste()

    def escribir(self, ruta: Path) -> None:
        """Escribe el informe."""
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(self.componer(ruta.parent), encoding="utf-8")

    def componer(self, carpeta_informe: Path) -> str:
        """Devuelve el informe completo.

        Args:
            carpeta_informe: carpeta donde irá el informe, para que los enlaces
                a las fichas sean relativos y funcionen en Obsidian.
        """
        real = self._resultados is not None
        partes = [
            "# Orakulue — Prueba comparativa de modelos" + ("" if real else " (simulacro)"),
            f"Generado el {datetime.now():%d/%m/%Y a las %H:%M}. Tarifas del {FECHA_TARIFAS}.",
            "**Simulacro: no se ha llamado a ningún modelo ni se ha gastado nada.** Para hacer la "
            "prueba: `orakulue prueba-modelos --ejecutar`." if not real else "",
            self._seleccion_texto(),
            self._presupuesto(),
            self._muestra_texto(),
        ]
        if real:
            partes += [self._comparacion(carpeta_informe), self._errores()]
        if self._aviso:
            partes.append("## Saldo\n\n" + self._aviso.replace("\n", "\n\n"))
        return "\n\n".join(p for p in partes if p) + "\n"

    def _seleccion_texto(self) -> str:
        """Cuánto hay que fichar y qué se ha descartado."""
        s = self._seleccion
        return (
            f"## Qué se ficha\n\n- **{Formato.cifra(len(s.fichables))} fichas.**\n"
            f"- Fuera por datos personales en el texto: {Formato.cifra(s.por_datos_personales)}.\n"
            f"- Fuera por el nombre del fichero (notas, asistencia, listas…): {Formato.cifra(s.por_nombre)}.\n"
            f"- Representados por otra ficha de su familia de plantilla: {Formato.cifra(s.por_familia)}."
        )

    def _presupuesto(self) -> str:
        """Coste del fondo completo por modelo: estimado y, si hay prueba, medido."""
        filas = []
        medidos = {r.modelo: r for r in (self._resultados or [])}
        for modelo in self._modelos:
            tarifa = self._tarifas.de(modelo)
            estimado = self._estimador.estimar(self._seleccion.fichables, tarifa, por_lotes=True)
            fila = f"| {modelo} | {self._dolares(estimado)} |"
            if modelo in medidos and medidos[modelo].fichas:
                r = medidos[modelo]
                # La prueba es síncrona: por lotes costaría la mitad.
                por_ficha = r.coste / len(r.fichas) * tarifa.DESCUENTO_LOTES
                fila += f" {self._dolares(por_ficha * len(self._seleccion.fichables))} |"
            elif self._resultados is not None:
                fila += " — |"
            filas.append(fila)
        cabecera = "| Modelo | Estimado por longitud |"
        separador = "|---|---:|"
        if self._resultados is not None:
            cabecera += " Proyectado con la prueba |"
            separador += "---:|"
        return (
            "## Coste del fondo completo, por lotes (−50 %)\n\nEl estimado sale de la longitud de "
            "los textos y peca por exceso. El proyectado multiplica el coste medio por ficha medido "
            "en la prueba.\n\n" + "\n".join([cabecera, separador, *filas])
        )

    def _muestra_texto(self) -> str:
        """Documentos de la prueba y lo que costaría la prueba."""
        filas = "\n".join(
            f"| {n} | `{Formato.ruta(f.rutas[0], self._personal)}` | {f.idioma} | {Formato.cifra(f.caracteres)} |"
            for n, f in enumerate(self._muestra, start=1)
        )
        costes = ", ".join(
            f"{m}: {self._dolares(self._estimador.estimar(self._muestra, self._tarifas.de(m), por_lotes=False))}"
            for m in self._modelos
        )
        return (
            f"## Muestra ({len(self._muestra)} documentos)\n\nCoste estimado de la prueba (llamadas directas, "
            f"sin descuento): {costes}.\n\n| # | Documento | Idioma | Caracteres |\n|---:|---|---|---:|\n" + filas
        )

    def _comparacion(self, carpeta_informe: Path) -> str:
        """Tabla con un enlace a cada ficha, para leerlas una al lado de otra."""
        resultados = self._resultados or []
        resumen = "\n".join(
            f"| {r.modelo} | {len(r.fichas)} | {len(r.errores)} | {Formato.cifra(r.entrada)} | "
            f"{Formato.cifra(r.salida)} | {self._dolares(r.coste)} |"
            for r in resultados
        )
        cabecera = "| # | " + " | ".join(r.modelo for r in resultados) + " |"
        separador = "|---:|" + "---|" * len(resultados)
        filas = []
        for numero, fichable in enumerate(self._muestra, start=1):
            celdas = []
            for r in resultados:
                ficha = r.fichas.get(fichable.huella)
                celdas.append(
                    f"[ficha]({os.path.relpath(ficha, carpeta_informe)})" if ficha else "error"
                )
            filas.append(f"| {numero} | " + " | ".join(celdas) + " |")
        return (
            "## Resultado\n\n| Modelo | Fichas | Errores | Tokens de entrada | Tokens de salida | Coste |\n"
            "|---|---:|---:|---:|---:|---:|\n" + resumen + "\n\n### Fichas para comparar\n\nEl número es el "
            "de la tabla de la muestra.\n\n" + "\n".join([cabecera, separador, *filas])
        )

    def _errores(self) -> str:
        """Errores por modelo."""
        lineas = [
            f"- {r.modelo}, documento {self._numero(h)}: {mensaje}"
            for r in self._resultados or [] for h, mensaje in r.errores.items()
        ]
        return "## Errores\n\n" + "\n".join(lineas) if lineas else ""

    def _numero(self, huella: str) -> int:
        """Número de un documento en la muestra."""
        return next(n for n, f in enumerate(self._muestra, start=1) if f.huella == huella)

    @staticmethod
    def _dolares(cantidad: Decimal) -> str:
        """Dólares con coma decimal."""
        return f"{cantidad:.2f} $".replace(".", ",") if cantidad >= 1 else f"{cantidad:.4f} $".replace(".", ",")
