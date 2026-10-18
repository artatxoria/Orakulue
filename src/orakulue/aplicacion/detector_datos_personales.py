"""Caso de uso: buscar indicios de datos personales en el texto.

Complementa las exclusiones por carpeta de la fase 1: por el nombre de una
carpeta no siempre se sabe si contiene entregas de alumnos. El objetivo es
que ningún documento con datos personales llegue a un servicio externo en la
fase 4.

Se prefiere pecar de prudente con los identificadores (DNI, NIE, IBAN), pero
solo cuentan si su dígito de control es válido: así los números inventados de
un ejercicio de Excel casi nunca disparan la alarma.
"""

import re

from orakulue.utilidades.nombres_de_pila import NombresDePila

from orakulue.dominio.marca_datos_personales import MarcaDatosPersonales, NivelRiesgo

_LETRAS_DNI = "TRWAGMYFPDXBNJZSQVHLCKE"

_DNI = re.compile(r"\b(\d{8})[ -]?([A-Z])\b")
_NIE = re.compile(r"\b([XYZ])[ -]?(\d{7})[ -]?([A-Z])\b")
_IBAN = re.compile(r"\bES(\d{2})[ ]?((?:\d{4}[ ]?){5})\b")
_CORREO = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_TELEFONO = re.compile(r"(?<![\d.,])(?:\+34[ ]?)?([6789]\d{2})[ .]?(\d{3})[ .]?(\d{3})(?![\d.,])")
_ROTULOS = re.compile(
    r"nombre y apellidos|apellidos\s*:|d\.?\s?n\.?\s?i\.?\s*:|fecha de nacimiento|"
    r"firma del (?:alumno|alumna|participante|trabajador)|n\.?º de (?:la )?seguridad social|"
    r"calificaci[oó]n final|izen-abizenak|jaiotze-data",
    re.IGNORECASE,
)
_NOMBRES_DE_PILA = sorted(NombresDePila.TODOS)
_APELLIDO = r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+|[A-ZÁÉÍÓÚÑ]{2,}"
_PERSONA = re.compile(
    r"\b(?:" + "|".join(sorted({n for n in _NOMBRES_DE_PILA} | {n.upper() for n in _NOMBRES_DE_PILA},
                                key=len, reverse=True))
    + r")(?:\s+(?:" + _APELLIDO + r")){1,3}\b"
)

# Dominios que aparecen en los ejemplos de los manuales y no son de nadie.
_DOMINIOS_DE_EJEMPLO = ("example.", "ejemplo.", "dominio.", "empresa.", "test.", "correo.", "midominio.")


class DetectorDatosPersonales:
    """Cuenta indicios de datos personales y asigna un nivel de riesgo."""

    #: Caracteres por contacto por debajo de los cuales los correos y
    #: teléfonos son «densos». Una lista de alumnos o un formulario tienen un
    #: contacto cada pocas líneas; un libro con los correos de sus autores y
    #: de la editorial, uno cada muchas páginas, y no es un dato personal que
    #: proteger.
    CARACTERES_POR_CONTACTO = 2_000
    #: Un texto más corto que esto con tres contactos ya es sospechoso.
    TEXTO_CORTO = 20_000
    #: Caracteres por nombre de persona por debajo de los cuales hay «muchos».
    CARACTERES_POR_PERSONA = 3_000

    def analizar(self, huella: str, texto: str) -> MarcaDatosPersonales:
        """Analiza un texto.

        Args:
            huella: huella del contenido.
            texto: su texto.

        Returns:
            La marca con los recuentos y el nivel.
        """
        identificadores = len(self._dnis(texto) | self._nies(texto) | self._ibans(texto))
        correos = len({
            c.lower() for c in _CORREO.findall(texto)
            if not any(d in c.lower().split("@", 1)[1] for d in _DOMINIOS_DE_EJEMPLO)
        })
        telefonos = len({"".join(m) for m in _TELEFONO.findall(texto)})
        rotulos = len(_ROTULOS.findall(texto))
        personas = len({m.group(0).lower() for m in _PERSONA.finditer(texto)})

        contactos = correos + telefonos
        densos = contactos >= 3 and (
            len(texto) < self.TEXTO_CORTO or len(texto) / contactos < self.CARACTERES_POR_CONTACTO
        )
        # Lo mismo con los nombres: una lista de alumnos tiene muchos en poco
        # texto; un libro que cita a sus autores, pocos en mucho texto.
        muchas_personas = personas >= 5 and (
            len(texto) < self.TEXTO_CORTO or len(texto) / personas < self.CARACTERES_POR_PERSONA
        )
        if identificadores:
            nivel = NivelRiesgo.ALTO
        elif densos or muchas_personas or (rotulos >= 2 and contactos >= 1) or (rotulos >= 1 and personas >= 3):
            nivel = NivelRiesgo.MEDIO
        elif correos or telefonos or rotulos:
            nivel = NivelRiesgo.BAJO
        else:
            nivel = NivelRiesgo.NINGUNO
        return MarcaDatosPersonales(huella, nivel, identificadores, correos, telefonos, rotulos, personas)

    @staticmethod
    def _dnis(texto: str) -> set[str]:
        """DNI con letra de control correcta."""
        return {n + l for n, l in _DNI.findall(texto) if _LETRAS_DNI[int(n) % 23] == l}

    @staticmethod
    def _nies(texto: str) -> set[str]:
        """NIE con letra de control correcta (X=0, Y=1, Z=2 delante del número)."""
        return {
            p + n + l for p, n, l in _NIE.findall(texto)
            if _LETRAS_DNI[int(str("XYZ".index(p)) + n) % 23] == l
        }

    @staticmethod
    def _ibans(texto: str) -> set[str]:
        """IBAN españoles cuyo control módulo 97 es correcto."""
        validos = set()
        for control, cuenta in _IBAN.findall(texto):
            digitos = cuenta.replace(" ", "")
            # Se pasa «ES» al final como 1428 (E=14, S=28) y se comprueba el resto.
            if int(digitos + "1428" + control) % 97 == 1:
                validos.add(control + digitos)
        return validos
