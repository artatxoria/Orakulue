"""Entidad GrupoCasiDuplicados: contenidos distintos con casi el mismo texto."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GrupoCasiDuplicados:
    """Documentos cuyo texto es casi igual aunque sus ficheros no lo sean.

    Casos típicos: el mismo documento en PDF y en Word, una versión con una
    errata corregida, o el mismo PDF regenerado con otros metadatos.

    Atributos:
        huellas: huellas de los contenidos del grupo, al menos dos.
        similitud_minima: el parecido más bajo entre dos miembros enlazados.
        similitud_maxima: el más alto.
    """

    huellas: tuple[str, ...]
    similitud_minima: float
    similitud_maxima: float

    #: A partir de aquí, todos los miembros son casi el mismo documento.
    UMBRAL_IDENTICOS = 0.95

    @property
    def casi_identicos(self) -> bool:
        """Si el grupo es el mismo documento con cambios mínimos.

        Por debajo del umbral, lo normal es una **familia de plantilla**:
        documentos distintos hechos sobre el mismo modelo (una propuesta por
        cliente, un acta por empresa), que comparten la mayor parte del texto.
        """
        return self.similitud_minima >= self.UMBRAL_IDENTICOS
