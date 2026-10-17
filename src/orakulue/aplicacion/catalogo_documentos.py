"""Caso de uso: reunir de cada contenido lo que el buscador necesita mostrar.

Junta el inventario, las fichas y las marcas de datos personales en una sola
tabla en memoria, para que el buscador no dependa de cinco almacenes.
"""

from pathlib import Path

from orakulue.aplicacion.seleccion_fichables import SeleccionFichables
from orakulue.dominio.documento import Documento
from orakulue.dominio.info_documento import InfoDocumento
from orakulue.dominio.marca_datos_personales import MarcaDatosPersonales
from orakulue.utilidades.clasificador_materias import ClasificadorMaterias


class CatalogoDocumentos:
    """Construye la información de presentación de cada contenido."""

    def construir(
        self,
        documentos: list[Documento],
        fichas: list[tuple[Path, str, str, str, str]],
        huellas_fichas: dict[Path, str],
        marcas: dict[str, MarcaDatosPersonales],
    ) -> dict[str, InfoDocumento]:
        """Devuelve la información por huella.

        Un contenido cuenta como personal si la fase 3 lo marcó con nivel
        medio o alto, o si su nombre de fichero delata datos de personas
        (las mismas reglas que dejan fuera de las fichas).

        Args:
            documentos: inventario.
            fichas: (ruta, título, tipo, tema, interés) de cada ficha.
            huellas_fichas: ruta de ficha → huella del contenido.
            marcas: marcas de datos personales.

        Returns:
            Diccionario huella → ``InfoDocumento``.
        """
        rutas: dict[str, list[Path]] = {}
        for documento in documentos:
            if documento.huella:
                rutas.setdefault(documento.huella, []).append(documento.ruta)
        por_huella = {huellas_fichas[r]: (r, titulo, tema, interes)
                      for r, titulo, _tipo, tema, interes in fichas if r in huellas_fichas}
        materias, seleccion = ClasificadorMaterias(), SeleccionFichables()
        catalogo = {}
        for huella, lista in rutas.items():
            lista = sorted(lista)
            personal = (huella in marcas and marcas[huella].excluir_de_fichas) or seleccion.sensible_por_nombre(lista)
            if huella in por_huella:
                ruta_ficha, titulo, tema, interes = por_huella[huella]
                catalogo[huella] = InfoDocumento(
                    huella, tuple(lista), titulo, interes, materias.clasificar(tema, titulo), ruta_ficha, personal
                )
            else:
                catalogo[huella] = InfoDocumento(huella, tuple(lista), lista[0].stem, personal=personal)
        return catalogo
