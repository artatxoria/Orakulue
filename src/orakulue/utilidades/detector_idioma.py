"""Detección aproximada del idioma de un texto: castellano, euskera o inglés.

Basta con contar palabras muy frecuentes de cada idioma. Es tosco, pero para
distinguir estos tres idiomas, tan distintos entre sí, sobra; y no añade
ninguna dependencia ni modelo.
"""

import re


class DetectorIdioma:
    """Decide el idioma predominante de un texto."""

    _PALABRAS = {
        "es": {"el", "la", "los", "las", "de", "del", "que", "y", "en", "un", "una", "por",
               "con", "para", "es", "se", "no", "al", "lo", "como", "más", "pero", "sus"},
        "eu": {"eta", "da", "ez", "bat", "du", "dira", "dute", "ere", "edo", "bere", "honek",
               "hau", "baina", "dago", "izan", "behar", "egin", "beste", "nola", "zer", "ditu"},
        "en": {"the", "and", "of", "to", "in", "is", "that", "for", "it", "with", "as", "on",
               "are", "this", "be", "by", "or", "from", "an", "you", "can", "which"},
    }

    #: Palabras que se miran como máximo; el principio del texto es suficiente.
    MUESTRA = 20_000
    #: Proporción mínima de palabras frecuentes para dar un veredicto.
    UMBRAL = 0.08

    def detectar(self, texto: str) -> str:
        """Devuelve el código del idioma predominante.

        Args:
            texto: texto que se va a analizar.

        Returns:
            ``es``, ``eu``, ``en`` o ``?`` si no hay suficientes indicios
            (texto corto, tablas de números, código fuente…).
        """
        palabras = re.findall(r"[a-záéíóúñü]+", texto[: self.MUESTRA * 8].lower())[: self.MUESTRA]
        if len(palabras) < 30:
            return "?"
        puntos = {
            idioma: sum(1 for p in palabras if p in frecuentes)
            for idioma, frecuentes in self._PALABRAS.items()
        }
        idioma, mejor = max(puntos.items(), key=lambda par: par[1])
        return idioma if mejor / len(palabras) >= self.UMBRAL else "?"
