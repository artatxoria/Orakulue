"""Asignación de una materia de una lista fija a partir del tema y el título.

El modelo describe el tema de cada ficha con sus palabras («Excel: funciones de
búsqueda y referencia», «BUSCARV y COINCIDIR en hojas de cálculo»…), y agrupar
por ese texto no agrupa nada. Una lista cerrada de materias, decidida por
palabras clave, da un índice navegable sin volver a llamar al modelo.
"""

import re
import unicodedata


class ClasificadorMaterias:
    """Decide la materia de una ficha."""

    #: Materias en orden de prioridad: gana la primera cuyas palabras aparezcan.
    #: Lo específico va antes que lo general («Power Query en Excel» es Power
    #: BI; «machine learning con Python» es IA).
    MATERIAS: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("Ciberseguridad", ("ciberseguridad", "seguridad informatica", "hacking", "pentest*", "metasploit",
                            "phishing", "gophish", "aircrack", "pfsense", "vulnerab*", "malware", "ataque*")),
        ("Inteligencia artificial", ("inteligencia artificial", "ia", "ai", "machine learning",
                                     "aprendizaje automatico", "aprendizaje profundo", "deep learning",
                                     "redes neuronales", "chatgpt", "copilot", "llm*", "ia generativa", "prompt*",
                                     "agente*", "rag", "adimen artifizial", "pln", "procesamiento del lenguaje",
                                     "notebooklm", "gemini", "claude", "ai act", "modelos de clasificacion", "accuracy")),
        ("Power BI y Power Query", ("power bi", "power query", "power pivot", "dax")),
        ("Datos, estadística y big data", ("big data", "ciencia de datos", "analisis de datos", "pandas",
                                           "matplotlib", "numpy", "talend", "etl", "business intelligence",
                                           "visualizacion de datos", "estadistic*", "regresion", "clustering",
                                           "componentes principales", "pca", "dendrograma*")),
        ("Bases de datos y SQL", ("sql", "mysql", "postgres*", "postgis", "base de datos", "bases de datos",
                                  "datu base*", "sqlite", "mongodb")),
        ("Excel y hojas de cálculo", ("excel", "hoja de calculo", "hojas de calculo", "kalkulu orri*",
                                      "tablas dinamicas", "taula dinamiko*", "calc")),
        ("Word y procesadores de texto", ("word", "procesador de texto*", "procesadores de texto*", "testu prozesadore*", "writer",
                                          "correspondencia")),
        ("PowerPoint y presentaciones", ("powerpoint", "presentacion*", "aurkezpen*", "impress", "diapositiva*")),
        ("Access", ("access",)),
        ("Python", ("python", "django", "tkinter", "flask")),
        ("Desarrollo web", ("html*", "css", "javascript", "bootstrap", "php", "laravel", "symfony", "node*",
                            "express", "react", "angular", "vue", "wordpress", "web", "xml", "xsd", "json")),
        ("Otros lenguajes de programación", ("java", "c++", "c#", "kotlin", "programacion", "algoritm*",
                                             "arduino", "bash", "shell")),
        ("SIG y cartografía", ("cartograf*", "qgis", "gis", "sig", "mapa*", "geograf*")),
        ("Soporte técnico, CPD e incidencias", ("cpd", "centro de proceso de datos", "incidencia*", "soporte",
                                                "helpdesk", "glpi", "raid", "hardware", "videowall", "escalado")),
        ("Sistemas, redes y virtualización", ("linux", "windows", "red", "redes", "servidor*", "docker",
                                              "virtualbox", "virtualizacion", "sistema operativo",
                                              "sistemas operativos", "sistema eragile*", "cloud", "nube", "aws",
                                              "azure")),
        ("LaTeX y edición técnica", ("latex", "tex")),
        ("Git y control de versiones", ("git", "github", "control de versiones")),
        ("Marketing digital y redes sociales", ("marketing", "redes sociales", "seo", "comercio electronico",
                                                "ecommerce", "sare sozial*", "linkedin", "contenido*",
                                                "calendario editorial", "audiovisual")),
        ("Empresa, emprendimiento y gestión", ("empresa*", "emprend*", "gestion de proyectos", "negocio*",
                                               "financ*", "contabilidad", "fiscal*", "iva", "impuesto*",
                                               "licitacion*", "plan de negocio")),
        ("Competencias digitales básicas", ("competencias digitales", "alfabetizacion digital",
                                            "informatica basica", "internet", "correo electronico", "ofimatica",
                                            "ordenador*", "productividad", "software libre")),
        ("Prevención de riesgos laborales", ("riesgos laborales", "prl", "ergonomi*")),
        ("Formación y docencia", ("formacion", "docencia", "didactica", "curso*",
                                  "certificado de profesionalidad", "prestakuntza", "ikastaro*")),
    )
    OTRAS = "Otras materias"

    def __init__(self) -> None:
        """Compila una expresión por materia.

        Cada palabra se busca completa («ia» no casa con «media»), salvo las
        que terminan en ``*``, que son raíces («financ*» casa con «financiero»).
        """
        def patron(palabra: str) -> str:
            if palabra.endswith("*"):
                return re.escape(palabra[:-1])
            return re.escape(palabra) + r"(?![a-z0-9])"

        self._patrones = [
            (materia, re.compile(r"(?<![a-z0-9])(?:" + "|".join(patron(p) for p in palabras) + r")"))
            for materia, palabras in self.MATERIAS
        ]

    def clasificar(self, tema: str, titulo: str) -> str:
        """Devuelve la materia de una ficha.

        Se mira primero el tema y, si no decide, el título.

        Args:
            tema: tema principal que escribió el modelo.
            titulo: título del documento.

        Returns:
            Una de las materias de ``MATERIAS`` u ``OTRAS``.
        """
        for texto in (tema, titulo):
            normalizado = self._normalizar(texto)
            for materia, patron in self._patrones:
                if patron.search(normalizado):
                    return materia
        return self.OTRAS

    @staticmethod
    def _normalizar(texto: str) -> str:
        """Minúsculas y sin tildes."""
        sin = unicodedata.normalize("NFKD", texto.lower())
        return "".join(c for c in sin if not unicodedata.combining(c))
