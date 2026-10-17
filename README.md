# Orakulue

Inventario, deduplicación y consulta con IA de un fondo documental para
impartir cursos de formación. Esta es la **segunda versión**: la primera era
un chat sobre documentos subidos a Open WebUI y no resolvía lo importante.

## Propósito

Quien prepara cursos acumula manuales, apuntes, libros y ejercicios
descargados de muchos sitios, repartidos por el disco y a menudo repetidos con
otro nombre. Orakulue:

1. **Inventaría** todo el material y detecta los duplicados por su contenido,
   no por su nombre (fase 1, disponible).
2. **Lo centraliza** en una única carpeta, dejando enlaces simbólicos donde
   estaban las copias (fase 2, disponible).
3. **Extrae el texto** y detecta casi duplicados: versiones, el mismo
   documento en otro formato; marca los que tienen datos personales
   (fase 3, disponible).
4. **Escribe una ficha** por documento con la teoría, los ejercicios
   aprovechables y las ideas de curso (fase 4).
5. **Permite consultarlo con IA** desde cualquier dispositivo a través de una
   VPN (fases 5 y 6).

El plan completo está en [`docs/PLAN.md`](docs/PLAN.md).

## Requisitos

- Linux (probado en Debian 12).
- Python 3.11 o posterior.
- [uv](https://docs.astral.sh/uv/) para el entorno.

Las fases 1 a 3 no tienen dependencias de Python externas: usan solo la
biblioteca estándar. La fase 3 llama a estos programas del sistema (paquetes de
Debian `poppler-utils`, `catdoc` y `libreoffice`):

- `pdftotext`, para los PDF;
- `catdoc`, `xls2csv` y `catppt`, para los `.doc`, `.xls` y `.ppt` antiguos;
- `soffice`, solo para los RTF;
- `tesseract` (paquetes `tesseract-ocr`, `tesseract-ocr-spa` y
  `tesseract-ocr-eus`) y `pdftoppm`, para el OCR de los PDF escaneados.

Los formatos modernos (`.docx`, `.xlsx`, `.pptx`, `.odt`, `.ods`, `.odp`,
`.epub`) se leen directamente, sin programas externos.

## Instalación

```bash
git clone https://github.com/artatxoria/Orakulue.git
cd Orakulue
uv sync
cp configuracion/orakulue.ejemplo.toml configuracion/orakulue.toml
```

Edita `configuracion/orakulue.toml`: carpetas que se recorren, extensiones,
exclusiones, rutas preferidas para el original de cada duplicado y, en la
sección `[centralizacion]`, la carpeta del fondo y qué se lleva a ella.

## Uso

```bash
uv run orakulue inventariar
```

Recorre el disco, calcula la huella SHA-256 de cada documento y escribe en
`datos/informes/` dos ficheros con sello de fecha:

- `duplicados-AAAAMMDD-HHMM.md`: cifras, dónde está el material, qué carpetas
  se han saltado y los grupos de copias que más ocupan.
- `duplicados-AAAAMMDD-HHMM.csv`: todas las copias, una por fila, con el
  original propuesto marcado. Se abre directamente en LibreOffice.

**No mueve, renombra ni borra nada.** Las pasadas siguientes son
incrementales: solo se vuelven a leer los ficheros que han cambiado.

Para regenerar el informe sin recorrer el disco (por ejemplo, tras cambiar
`prioridad_original`):

```bash
uv run orakulue informe
```

### Centralizar en el fondo (fase 2)

```bash
uv run orakulue centralizar
```

**Simulacro**: calcula qué se haría y escribe
`datos/informes/centralizacion-simulacro-AAAAMMDD-HHMM.md` (y su CSV con todas
las operaciones), sin tocar el disco. Para cada contenido distinto:

- si hay una copia en `carpetas_al_fondo`, se mueve al fondo y deja un enlace
  simbólico en su sitio;
- fuera de esas carpetas rige el modo **solo enlazar**: el documento se queda
  donde está y solo sus copias se sustituyen por enlaces;
- las **zonas vivas** (carpetas de trabajo activo) no se tocan;
- las copias sobrantes **no se borran**: se apartan a `datos/retirados/`.

Cuando el simulacro esté revisado:

```bash
uv run orakulue inventariar              # el plan se calcula sobre el inventario
uv run orakulue centralizar --ejecutar
uv run orakulue inventariar              # actualiza el inventario con el fondo
```

Antes de cada movimiento se comprueba que el fichero no ha cambiado desde el
inventario, y antes de retirar una copia, que su huella sigue siendo la del
original. Ante el primer fallo, la ejecución se detiene. Cada ejecución es un
**lote** con todas sus operaciones registradas:

```bash
uv run orakulue lotes                    # lotes y estado de sus operaciones
uv run orakulue deshacer --lote 1        # devuelve el disco a como estaba
```

### Texto, casi duplicados y datos personales (fase 3)

```bash
uv run orakulue extraer      # extrae el texto de lo nuevo y analiza
uv run orakulue ocr          # reconoce los PDF escaneados (lento) y analiza
uv run orakulue analizar     # repite solo el análisis
```

Solo lee los documentos. El texto de cada contenido distinto se guarda en
`datos/textos/` (una vez por huella, aunque haya varias copias) y el informe
`datos/informes/texto-AAAAMMDD-HHMM.md` recoge:

- qué se ha podido leer, por formato, y qué no tiene capa de texto. Los PDF
  escaneados se leen con `ocr`: cada página se convierte en imagen y la lee
  Tesseract en castellano, euskera e inglés, hasta 60 páginas por documento.
  Cada PDF se intenta una sola vez;
- el idioma predominante de cada texto (castellano, euskera o inglés);
- los **casi duplicados**, separados en casi idénticos (95 % o más) y
  familias de plantilla (80–95 %);
- los documentos con **indicios de datos personales** (DNI, NIE o IBAN con
  dígito de control válido; correos o teléfonos densos; formularios
  rellenados). El informe solo da recuentos, nunca los valores. Los de nivel
  medio y alto quedan excluidos de la fase 4.

Pruebas:

```bash
uv run pytest
```

## Estructura de carpetas

```
Orakulue/
├── configuracion/          ejemplo de configuración (la real no se publica)
├── datos/                  inventario e informes (privado, fuera de git)
├── docs/                   plan del proyecto y artículos del blog
├── src/orakulue/
│   ├── dominio/            entidades: Documento, GrupoDuplicados…
│   ├── infraestructura/    disco, huellas, SQLite, configuración y
│   │                       extractores de texto
│   ├── aplicacion/         casos de uso: inventariar, detectar duplicados,
│   │                       planificar, ejecutar y deshacer la centralización
│   ├── interfaz/           línea de órdenes e informes Markdown y CSV
│   └── utilidades/         formato de cifras, tamaños y rutas
└── tests/                  pruebas con pytest
```

## Privacidad

El inventario y los informes contienen rutas del disco, que pueden revelar
nombres de clientes. Por eso `datos/` y la configuración real están en
`.gitignore` desde el primer commit.

## Nota sobre nombres

El código está escrito en castellano. Se mantienen en inglés solo los nombres
que impone Python o una herramienta: `__init__`, `__main__`, `README`,
`conftest`, `test_*` y las palabras reservadas.
