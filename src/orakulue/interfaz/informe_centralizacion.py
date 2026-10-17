"""Informe del simulacro de centralización, en Markdown y CSV.

Enseña lo que haría la fase 2 antes de hacerlo: cuánto se mueve, adónde, qué
se queda en su sitio y qué choques de nombre se han resuelto. El CSV lista
todas las operaciones, una por fila, en el orden en que se ejecutarían.
"""

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path

from orakulue.dominio.operacion import TipoOperacion
from orakulue.dominio.plan_centralizacion import PlanCentralizacion
from orakulue.infraestructura.configuracion_centralizacion import ConfiguracionCentralizacion
from orakulue.utilidades.formato import Formato


class InformeCentralizacion:
    """Compone el informe del simulacro."""

    MUESTRA = 30

    def __init__(
        self, plan: PlanCentralizacion, configuracion: ConfiguracionCentralizacion, nombre_csv: str
    ) -> None:
        """Reúne los datos.

        Args:
            plan: plan calculado.
            configuracion: fondo y zonas vivas.
            nombre_csv: nombre del CSV complementario, para citarlo.
        """
        self._plan = plan
        self._configuracion = configuracion
        self._personal = configuracion.personal
        self._nombre_csv = nombre_csv

    def escribir(self, ruta_md: Path, ruta_csv: Path) -> None:
        """Escribe el Markdown y el CSV.

        Args:
            ruta_md: fichero Markdown de destino.
            ruta_csv: fichero CSV de destino.
        """
        ruta_md.parent.mkdir(parents=True, exist_ok=True)
        ruta_md.write_text(self.componer(), encoding="utf-8")
        with ruta_csv.open("w", newline="", encoding="utf-8-sig") as fichero:
            escritor = csv.writer(fichero, delimiter=";")
            escritor.writerow(["orden", "operacion", "origen", "destino", "tamano_bytes", "huella"])
            for orden, o in enumerate(self._plan.operaciones, start=1):
                escritor.writerow([orden, o.tipo.value, o.origen, o.destino, o.tamano, o.huella])

    def componer(self) -> str:
        """Devuelve el informe Markdown completo."""
        return "\n\n".join(s for s in (
            self._cabecera(), self._cifras(), self._destinos(), self._zonas_vivas(),
            self._solo_enlazar(), self._renombrados(), self._muestra(),
        ) if s) + "\n"

    def _r(self, ruta: Path) -> str:
        """Ruta abreviada con ``~``."""
        return Formato.ruta(ruta, self._personal)

    def _cabecera(self) -> str:
        """Título y aviso de simulacro."""
        return (
            "# Orakulue — Simulacro de centralización\n\n"
            f"Generado el {datetime.now():%d/%m/%Y a las %H:%M}.\n\n"
            "**Simulacro: no se ha tocado nada.** Esto es lo que haría "
            "`orakulue centralizar --ejecutar`.\n\n"
            f"- Fondo: `{self._r(self._configuracion.carpeta_fondo)}`\n"
            f"- Copias retiradas (no se borran): `{self._r(self._configuracion.carpeta_retirados)}`\n"
            "- Cada operación queda registrada y el lote entero se puede deshacer con "
            "`orakulue deshacer --lote N`."
        )

    def _cifras(self) -> str:
        """Tabla de cifras del plan."""
        plan = self._plan
        filas = [
            ("Documentos que se llevan al fondo", Formato.cifra(plan.cuenta(TipoOperacion.MOVER)),
             Formato.tamano(plan.bytes_de(TipoOperacion.MOVER))),
            ("Copias que se retiran", Formato.cifra(plan.cuenta(TipoOperacion.RETIRAR)),
             Formato.tamano(plan.bytes_de(TipoOperacion.RETIRAR))),
            ("Enlaces que se crean", Formato.cifra(plan.cuenta(TipoOperacion.ENLAZAR)), ""),
            ("Ya estaban en el fondo", Formato.cifra(plan.ya_en_fondo), ""),
            ("Se quedan en su sitio (solo enlazar)", Formato.cifra(len(plan.en_su_sitio)), ""),
            ("Se quedan en zonas vivas", Formato.cifra(len(plan.en_zona_viva)), ""),
            ("Van al fondo y conservan una copia en zona viva",
             Formato.cifra(len(plan.duplicados_con_zona_viva)), ""),
            ("Renombrados por choque de nombre", Formato.cifra(len(plan.renombrados)), ""),
        ]
        tabla = "\n".join(f"| {a} | {b} | {c} |" for a, b, c in filas)
        return (
            "## 1. Cifras\n\n| | Documentos | Tamaño |\n|---|---:|---:|\n" + tabla + "\n\n"
            "El espacio no se libera al ejecutar: las copias retiradas se conservan hasta que "
            "decidas vaciar la carpeta de retirados."
        )

    def _destinos(self) -> str:
        """Cómo quedaría organizado el fondo."""
        fondo = self._configuracion.carpeta_fondo
        nivel1 = self._plan.por_destino(fondo, 1)
        nivel2 = self._plan.por_destino(fondo, 2)
        filas = []
        for carpeta, n in sorted(nivel1.items(), key=lambda par: (-par[1], str(par[0]))):
            nombre = "fondo/ (raíz)" if carpeta == Path(".") else f"fondo/{carpeta}"
            filas.append(f"| `{nombre}` | {Formato.cifra(n)} |")
            hijas = [(c, m) for c, m in nivel2.items() if c.parent == carpeta and c != carpeta]
            for hija, m in sorted(hijas, key=lambda par: -par[1])[:8]:
                filas.append(f"| &nbsp;&nbsp;`{hija.name}` | {Formato.cifra(m)} |")
        return (
            "## 2. Cómo quedaría el fondo\n\nOrganización provisional: conserva la estructura de "
            "origen. La fase 4 la sustituirá por una temática. Se muestran las 8 subcarpetas "
            "más grandes de cada una.\n\n| Carpeta | Documentos |\n|---|---:|\n" + "\n".join(filas)
        )

    def _zonas_vivas(self) -> str:
        """Qué se queda en su sitio por estar en zonas de trabajo activo."""
        if not self._configuracion.zonas_vivas:
            return ""
        cuenta = Counter()
        for ruta in self._plan.en_zona_viva:
            for zona in self._configuracion.zonas_vivas:
                if ruta.is_relative_to(zona):
                    cuenta[zona] += 1
                    break
        filas = "\n".join(
            f"| `{self._r(z)}` | {Formato.cifra(cuenta[z])} |" for z in self._configuracion.zonas_vivas
        )
        return (
            "## 3. Zonas vivas: no se tocan\n\nCarpetas de trabajo activo. Sus documentos siguen en "
            "el inventario, pero no se mueven ni se convierten en enlaces.\n\n"
            "| Zona | Documentos |\n|---|---:|\n" + filas
        )

    def _solo_enlazar(self) -> str:
        """Qué pasa fuera de las carpetas que van al fondo."""
        if not self._configuracion.carpetas_al_fondo:
            return ""
        fuera = [
            o for o in self._plan.operaciones
            if o.tipo is TipoOperacion.RETIRAR and not self._configuracion.va_al_fondo(o.origen)
        ]
        cuenta, bytes_ = Counter(), Counter()
        for operacion in fuera:
            carpeta = Formato.carpeta_resumida(operacion.origen, self._personal, 4)
            cuenta[carpeta] += 1
            bytes_[carpeta] += operacion.tamano
        filas = "\n".join(
            f"| `{self._r(c)}` | {Formato.cifra(n)} | {Formato.tamano(bytes_[c])} |"
            for c, n in cuenta.most_common(25)
        )
        al_fondo = ", ".join(f"`{self._r(c)}`" for c in self._configuracion.carpetas_al_fondo)
        return (
            "## 4. Solo enlazar: copias fuera del fondo\n\n"
            f"Al fondo solo van {al_fondo}. En el resto, cada documento se queda en su sitio "
            f"({Formato.cifra(len(self._plan.en_su_sitio))} documentos) y solo sus copias pasan "
            f"a ser enlaces: {Formato.cifra(len(fuera))} copias. Las 25 carpetas con más:\n\n"
            "| Carpeta | Copias que pasan a enlace | Tamaño |\n|---|---:|---:|\n" + filas
        )

    def _renombrados(self) -> str:
        """Destinos que chocaban y cómo se han resuelto."""
        if not self._plan.renombrados:
            return ""
        lista = "\n".join(
            f"- `{self._r(a)}` → `{b.name}`" for a, b in self._plan.renombrados[:50]
        )
        resto = len(self._plan.renombrados) - 50
        return (
            "## 5. Choques de nombre\n\nDos documentos distintos iban al mismo sitio del fondo; "
            "el segundo recibe un número.\n\n" + lista + (f"\n- … y {resto} más." if resto > 0 else "")
        )

    def _muestra(self) -> str:
        """Algunos traslados de ejemplo, para comprobar a ojo que tienen sentido."""
        traslados = [o for o in self._plan.operaciones if o.tipo is TipoOperacion.MOVER]
        paso = max(1, len(traslados) // self.MUESTRA)
        lista = "\n".join(
            f"- `{self._r(o.origen)}`\n  → `{self._r(o.destino)}`"
            for o in traslados[::paso][: self.MUESTRA]
        )
        return (
            f"## 6. Muestra de traslados\n\n{min(self.MUESTRA, len(traslados))} traslados "
            f"repartidos por todo el plan. La lista completa está en `{self._nombre_csv}`.\n\n" + lista
        )
