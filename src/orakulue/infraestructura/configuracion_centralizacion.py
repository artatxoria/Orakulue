"""Parámetros de la fase 2: dónde está el fondo y qué se lleva a él.

Se separa de ``Configuracion`` porque solo la usan la planificación y la
ejecución de la centralización, y así cada parte puede probarse por su lado.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ConfiguracionCentralizacion:
    """Criterios para llevar los documentos al fondo.

    Atributos:
        carpeta_fondo: carpeta única donde acabará cada documento.
        carpeta_retirados: adonde van las copias sobrantes en lugar de
            borrarse. Debe estar en el mismo disco que los documentos para
            que retirarlas sea un simple cambio de nombre.
        zonas_vivas: carpetas de trabajo activo (cursos en elaboración,
            proyectos de software). Sus documentos se inventarían pero no se
            mueven ni se sustituyen por enlaces: un programa que regenera un
            PDF o lo guarda escribiendo un fichero nuevo rompería el enlace.
        correspondencias: pares (carpeta de origen, subcarpeta del fondo) que
            deciden la organización provisional. Gana la carpeta de origen
            más concreta. Un destino vacío significa la raíz del fondo.
        destino_por_defecto: subcarpeta del fondo para lo que no encaja en
            ninguna correspondencia; dentro se conserva la ruta relativa al
            directorio personal.
        personal: directorio personal, base de ``destino_por_defecto``.
        carpetas_al_fondo: únicas carpetas cuyos documentos se llevan al
            fondo. Fuera de ellas rige el modo «solo enlazar»: los documentos
            se quedan donde están y solo sus copias se sustituyen por enlaces.
            Sirve para que la documentación administrativa o de clientes no se
            mezcle con el material de formación. Vacía = todo va al fondo.
    """

    carpeta_fondo: Path
    carpeta_retirados: Path
    zonas_vivas: tuple[Path, ...]
    correspondencias: tuple[tuple[Path, str], ...]
    destino_por_defecto: str
    personal: Path
    carpetas_al_fondo: tuple[Path, ...] = ()

    def en_zona_viva(self, ruta: Path) -> bool:
        """Indica si un documento está en una zona de trabajo activo.

        Args:
            ruta: ruta absoluta del documento.

        Returns:
            ``True`` si cuelga de alguna zona viva.
        """
        return any(ruta.is_relative_to(z) for z in self.zonas_vivas)

    def va_al_fondo(self, ruta: Path) -> bool:
        """Indica si un documento puede llevarse al fondo.

        Args:
            ruta: ruta absoluta del documento.

        Returns:
            ``True`` si está en una de ``carpetas_al_fondo`` (o si esa lista
            está vacía) o ya está en el fondo; ``False`` si está en zona de
            «solo enlazar».
        """
        if not self.carpetas_al_fondo or ruta.is_relative_to(self.carpeta_fondo):
            return True
        return any(ruta.is_relative_to(c) for c in self.carpetas_al_fondo)

    def destino_en_fondo(self, ruta: Path) -> Path:
        """Calcula dónde iría un documento dentro del fondo.

        La organización es provisional: conserva la estructura de carpetas de
        origen, que en los recursos de formación ya va por materias. La fase 4
        la sustituirá por una organización temática.

        Args:
            ruta: ruta absoluta del documento.

        Returns:
            Ruta absoluta de destino, sin comprobar si ya existe.
        """
        if ruta.is_relative_to(self.carpeta_fondo):
            return ruta
        candidatas = [(o, d) for o, d in self.correspondencias if ruta.is_relative_to(o)]
        if candidatas:
            # La más concreta es la de más componentes en la ruta.
            origen, destino = max(candidatas, key=lambda par: len(par[0].parts))
            return self.carpeta_fondo / destino / ruta.relative_to(origen)
        if ruta.is_relative_to(self.personal):
            return self.carpeta_fondo / self.destino_por_defecto / ruta.relative_to(self.personal)
        return self.carpeta_fondo / self.destino_por_defecto / ruta.relative_to(ruta.anchor)
