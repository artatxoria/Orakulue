"""Nombres de pila frecuentes en castellano y en euskera.

Sirven para reconocer nombres de persona: en el texto («Ane Etxeberria»,
«JUAN PÉREZ») y en el nombre de los ficheros («lopez_irene.docx»), que es como
suelen llamarse las entregas de alumnos. La lista es corta a propósito, para no
confundir con nombres de persona términos como «Power Query».
"""

import re
import unicodedata


class NombresDePila:
    """Lista de nombres de pila y comprobaciones sobre ella."""

    TODOS = frozenset(("Juan José Antonio Manuel Francisco Javier David Daniel Carlos Jesús Alejandro Miguel Rafael Pedro "
    "Pablo Ángel Sergio Fernando Jorge Luis Alberto Álvaro Adrián Diego Raúl Iván Rubén Óscar Andrés "
    "Enrique Ramón Víctor Mario Roberto Hugo Marcos Héctor Alfonso Jaime Ignacio Gonzalo Eduardo "
    "Santiago Alfredo Ricardo Joaquín Emilio Asier Iker Jon Mikel Unai Aitor Gorka Ander Xabier Eneko "
    "Ibai Jokin Urko Julen Oier Imanol Iñaki Koldo Josu Aritz Beñat Markel Gaizka Ekaitz Hodei Eder "
    "Igor Endika Ion Joseba Kepa Patxi Txema Iñigo Haritz Andoni Aimar Mattin "
    "María Carmen Ana Isabel Laura Lucía Marta Cristina Paula Elena Sara Raquel Pilar Rosa Teresa "
    "Silvia Patricia Beatriz Andrea Irene Julia Alba Sandra Mónica Nuria Eva Sonia Rocío Natalia "
    "Claudia Inés Lorena Verónica Esther Alicia Yolanda Susana Lourdes Montserrat Rebeca Ángela "
    "Noelia Miriam Vanesa Marina Carla Begoña Nerea Ainhoa Amaia Leire Ane Maialen Itziar Idoia Miren "
    "Arantza Edurne Garazi Uxue Irati June Naroa Olatz Izaskun Iratxe Maider Estibaliz Nekane Ainara "
    "Aitziber Elixabete Eider Haizea Oihane Jone Libe Lide Nahia Saioa Zuriñe Maite Arrate Agurne"
        " Pamela Urko Jose Josefa Manuela Francisca Antonia Dolores Josefina Mercedes "
        "Concepción Encarnación Rosario Amparo Inmaculada Asunción Milagros Esperanza Gloria Margarita "
        "Victoria Fátima Lidia Diana Tamara Olga Alejandra Daniela Valeria Sofía Martina Lola Emma Nora "
        "Paola Gabriela Carolina Adriana Ariadna Judith Celia Aurora Ainara Erika Jessica Melanie "
        "Fernanda Ximena Camila Valentina Mariana Luciana Florencia Agustina Antonella Romina Yesica "
        "Gustavo Rodrigo Esteban Gabriel Samuel Nicolás Matías Sebastián Felipe Martín Tomás Lucas "
        "Mateo Leo Bruno Marc Pau Pol Oriol Jordi Xavier Joan Iago Iker Aitzol Iñaki Ibon Peio Kepa "
        "Gorka Jon Unai Julen Eneko Asier Iban Xabat Aratz Oinatz Ekain Telmo Eñaut Gaizka Mikel "
        "Agustín Arturo Benjamín César Cristian Christian Darío Elías Emilio Ernesto Federico Fermín "
        "Fidel Gerardo Germán Gilberto Guillermo Horacio Ismael Joel Jonathan Julián Julio Leonardo "
        "Lorenzo Marcelo Mariano Mauricio Maximiliano Moisés Nelson Octavio Omar Orlando Patricio "
        "Ramiro Raimundo Renato Ricardo Rolando Salvador Saúl Silvio Teodoro Ulises Valentín Wilson "
        "Xabier Yeray Aimar Anartz Beñat Hugo Izan Oier Ekhi Mattin Markel Aitor Ander Eder Endika"
    ).split())

    _NORMALIZADOS = frozenset(
        "".join(c for c in unicodedata.normalize("NFKD", n.lower()) if not unicodedata.combining(c))
        for n in TODOS
    )

    @classmethod
    def en_nombre_de_fichero(cls, nombre: str) -> bool:
        """Indica si un nombre de fichero parece el de una persona.

        Se trocea por guiones, espacios, cifras y mayúsculas intermedias
        («SanchezVidal_Marta» → sanchez, vidal, marta). Cuenta si alguna pieza
        es un nombre de pila y hay al menos otra pieza (el apellido): un
        fichero que se llama solo «Mario» no basta.

        Args:
            nombre: nombre del fichero sin extensión.

        Returns:
            ``True`` si parece el nombre de una persona.
        """
        separado = re.sub(r"(?<=[a-záéíóúñ])(?=[A-ZÁÉÍÓÚÑ])", " ", nombre)
        sin_tildes = "".join(
            c for c in unicodedata.normalize("NFKD", separado.lower()) if not unicodedata.combining(c)
        )
        piezas = [p for p in re.split(r"[^a-z]+", sin_tildes) if len(p) >= 2]
        return len(piezas) >= 2 and any(p in cls._NORMALIZADOS for p in piezas)
