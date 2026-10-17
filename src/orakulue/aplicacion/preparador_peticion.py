"""Caso de uso: preparar lo que se envía al modelo para fichar un documento.

Decide qué parte del texto se envía y redacta las instrucciones. Las
instrucciones son idénticas en todas las peticiones, para que la caché del
proveedor las reaproveche.
"""

from pathlib import Path

from orakulue.dominio.peticion import Peticion

#: Instrucciones comunes. No llevan nada variable (ni fechas ni rutas): un solo
#: carácter distinto invalidaría la caché.
INSTRUCCIONES = """\
Eres documentalista de un formador de informática y competencias digitales que \
trabaja en Euskadi, en castellano y en euskera, para empresas, personas \
trabajadoras y personas desempleadas. Tiene miles de documentos guardados \
(manuales, libros, apuntes, ejercicios, presentaciones, normativa, propuestas) y \
no tiene tiempo de leerlos. Tu trabajo es leer uno y escribir su ficha.

La ficha sirve para decidir rápido si el documento le sirve para preparar \
formación, ahora o más adelante, y qué puede sacar de él.

Criterios:
- Básate solo en el texto que recibes. No inventes páginas, apartados ni \
contenidos que no aparezcan. En «donde» indica el apartado, el tema o la página \
solo si el texto lo deja claro; si no, déjalo vacío.
- Del documento puede llegarte solo una parte (principio, centro y final), \
señalada con marcas de corte. Descríbelo entero hasta donde permita lo que ves y \
dilo en «observaciones» si la parte que falta impide valorar algo.
- La ficha se escribe en castellano aunque el documento esté en euskera o en \
inglés. El título se conserva en su idioma original.
- «interes»: alto si sirve casi tal cual para impartir o preparar formación; \
medio si aporta teoría o ejercicios aprovechables con trabajo; bajo si aporta \
poco; ninguno si no es material formativo (facturas, contratos, trámites, \
correspondencia). Si es «ninguno», deja vacías las listas de teoría, ejercicios \
e ideas.
- «vigencia»: marca «desactualizado» si se basa en versiones antiguas de un \
programa o en normativa superada, y explica por qué.
- Ideas de curso: propuestas concretas que este documento ayudaría a impartir, \
con destinatarios y lo que aprenderían. Ideas de píldora: formaciones cortas y \
prácticas para empresas (del tipo que financia SPRI), con un objetivo concreto. \
No propongas duraciones, horas ni sesiones.
- No copies en la ficha nombres de personas particulares, DNI, correos, \
teléfonos ni ningún otro dato personal que aparezca en el texto.
- Sé concreto y breve. Mejor tres conceptos bien elegidos que veinte genéricos.
"""


class PreparadorPeticion:
    """Compone la petición de un documento."""

    PRINCIPIO = 24_000
    CENTRO = 8_000
    FINAL = 8_000

    def preparar(self, huella: str, ruta: Path, texto: str, idioma: str) -> Peticion:
        """Prepara la petición.

        Args:
            huella: huella del contenido.
            ruta: una de sus rutas; el nombre del fichero y de su carpeta ayudan
                a entender de qué va (p. ej. «Excel avanzado/ejercicio3.xlsx»).
            texto: texto extraído.
            idioma: idioma detectado en la fase 3.

        Returns:
            La petición.
        """
        fragmento, recortado = self._fragmento(texto)
        mensaje = (
            f"Fichero: {ruta.parent.name}/{ruta.name}\n"
            f"Formato: {ruta.suffix.lower().lstrip('.')}\n"
            f"Idioma detectado: {idioma}\n"
            f"Longitud total del texto: {len(texto)} caracteres"
            f"{' (se envía solo una parte)' if recortado else ''}\n\n"
            f"<documento>\n{fragmento}\n</documento>\n\nEscribe la ficha de este documento."
        )
        return Peticion(huella, mensaje, len(fragmento), recortado)

    def _fragmento(self, texto: str) -> tuple[str, bool]:
        """Elige qué parte del texto se envía.

        Los documentos cortos van enteros. De los largos se envía el principio
        (portada, índice, primeros capítulos), un trozo del centro y otro del
        final: así la ficha no describe solo el arranque de un libro.
        """
        maximo = self.PRINCIPIO + self.CENTRO + self.FINAL
        if len(texto) <= maximo:
            return texto, False
        mitad = len(texto) // 2
        centro = texto[mitad - self.CENTRO // 2 : mitad + self.CENTRO // 2]
        return (
            f"{texto[: self.PRINCIPIO]}\n\n[… corte: se omite parte del documento …]\n\n"
            f"{centro}\n\n[… corte: se omite parte del documento …]\n\n{texto[-self.FINAL :]}",
            True,
        )
