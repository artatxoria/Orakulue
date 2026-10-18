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
   aprovechables y las ideas de curso (fase 4, disponible).
5. **Permite buscar y preguntar** al fondo, citando las fuentes (fase 5,
   disponible), y hacerlo desde cualquier dispositivo a través de una VPN o
   desde Claude (fase 6, disponible).
6. **Propone cursos y píldoras nuevos** a partir de lo que hay en el fondo,
   con los documentos que sostienen cada propuesta (fase 7, disponible).

El plan completo está en [`docs/PLAN.md`](docs/PLAN.md).

## Requisitos

- Linux (probado en Debian 12).
- Python 3.11 o posterior.
- [uv](https://docs.astral.sh/uv/) para el entorno.

Las fases 1 a 3 no tienen dependencias de Python externas: usan solo la
biblioteca estándar. La fase 4 usa el SDK de Anthropic (`anthropic`) y la 5,
`numpy`; los dos los instala `uv sync`. La fase 5 necesita además
[Ollama](https://ollama.com) con el modelo de vectores `bge-m3` (y
`qwen2.5:7b-instruct` para las respuestas locales). La fase 3 llama a estos programas del sistema (paquetes de
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

### Fichas con IA (fase 4)

Necesita una clave de la API de Anthropic en la variable
`CLAVE_API_ANTHROPIC_ORAKULUE`, exportada o escrita en un fichero `.env` en la
raíz del proyecto (excluido de git; conviene `chmod 600 .env`). En la sección
`[fichas]` de la configuración se declara el saldo de la cuenta, que el
proveedor no publica, para poder estimar lo que queda.

```bash
uv run orakulue prueba-modelos             # simulacro: muestra y presupuesto
uv run orakulue prueba-modelos --ejecutar  # ficha la muestra con varios modelos
uv run orakulue fichar                     # simulacro: fichas pendientes y coste
uv run orakulue fichar --ejecutar          # ficha el fondo por lotes
```

- Una ficha por contenido distinto; de cada familia de plantilla, una sola.
- Quedan fuera los documentos con datos personales (fase 3); los que, por el
  nombre del fichero, son notas, asistencias, listas de alumnos o papeles
  económicos y administrativos (extractos, facturas, contratos, vida
  laboral…), y todo lo que esté dentro de `rutas_personales` de `[fichas]`.
- Si las reglas se endurecen después de fichar,
  `uv run orakulue retirar-fichas-personales` aparta (sin borrar) las fichas
  que ya no deberían estar a la vista, a `datos/fichas_retiradas`.
- La respuesta del modelo es JSON con un esquema fijo; el programa la
  convierte en Markdown con cabecera YAML, en la carpeta `carpeta` de
  `[fichas]`. Las fichas sin interés formativo van a `_sin_interes/`, y
  `_indice.md` las agrupa por interés y materia para Obsidian.
- **Control de gasto**: cada llamada se anota con su coste según la tarifa.
  Al terminar se avisa de lo gastado, del saldo estimado y de cuántas
  ejecuciones más aguanta. El aviso nunca para nada; solo corta la falta
  real de saldo, que se reconoce por el texto del error y nombra la clave.
- **Reanudable**: una ficha hecha no se vuelve a pedir, y un lote enviado sin
  recoger se recoge antes de enviar otro.

### Buscar y preguntar (fase 5)

```bash
uv run orakulue indexar                       # índice local y gratuito, incremental
uv run orakulue buscar "tablas dinámicas para principiantes"
uv run orakulue buscar --modo palabras "IFCT0049"
uv run orakulue preguntar "¿cómo explico BUSCARV con mis apuntes?"
uv run orakulue preguntar --local "…"        # sin salir del equipo
uv run orakulue evaluar-busqueda              # mide el buscador
```

- Se indexan las fichas y el texto de cada documento en trozos de ~1.500
  caracteres. Los vectores se calculan con `bge-m3` en Ollama y se guardan en
  la misma base SQLite, junto a un índice de palabras FTS5.
- La búsqueda es **híbrida**: por palabras (términos exactos, códigos) y por
  significado (sinónimos, preguntas en lenguaje natural, entre idiomas),
  combinadas con fusión por rango recíproco. Es local y gratuita.
- `preguntar` envía los mejores pasajes a Haiku 5.5 con la orden de usar solo
  eso y citar cada afirmación. Los documentos con datos personales salen en la
  búsqueda marcados, pero sus pasajes **nunca** se envían a la API; con
  `--local` se usan, porque no salen del equipo. El gasto se anota como en la
  fase 4.
- `evaluar-busqueda` pasa un juego de preguntas con sus documentos esperados
  (`datos/evaluacion/preguntas.toml`, privado) y mide el acierto en los diez
  primeros de cada modo de búsqueda.

### Web por la VPN y conector para Claude (fase 6)

```bash
uv run orakulue servir                 # web en 10.8.0.5:8010 (solo la VPN)
uv run orakulue conector-mcp           # conector para Claude (lo arranca Claude)
```

- **Web**: buscar, leer fichas, descargar los originales, preguntar y ver el
  índice por materias, desde la tablet o el móvil conectados a la VPN. Escucha
  solo en la dirección de la VPN y es de solo lectura. Solo descarga
  documentos del inventario, pedidos por su huella. Para que arranque sola:
  `docs/systemd/orakulue-web.service` (servicio de usuario). Hay que abrir el
  puerto en el cortafuegos solo para la interfaz de la VPN.
- **Conector MCP** para Claude Code y la app de escritorio en el mismo
  equipo, por stdio: herramientas `buscar`, `leer_ficha`, `leer_pasajes` y
  `materias`. Ejemplo de configuración en `docs/mcp/ejemplo.mcp.json`. Lo que
  devuelve llega a Anthropic, así que de los documentos con datos personales
  solo da el título y el aviso, nunca su contenido.

### Propuestas de cursos y píldoras (fase 7)

```bash
uv run orakulue candidatas                     # reúne y puntúa las ideas (local)
uv run orakulue prueba-propuestas --ejecutar   # compara modelos con unas pocas
uv run orakulue proponer                       # simulacro de la tanda y su coste
uv run orakulue proponer --ejecutar            # redacta la tanda
uv run orakulue exportar-propuesta <clave>     # borrador para Bibliotecario
```

- Las ideas de curso y de píldora de las fichas se agrupan por significado y
  se puntúan con criterios explicables: respaldo (cuántos documentos y de qué
  interés), ejercicios disponibles, vigencia, material en euskera y relación
  con el catálogo actual, que se lee de sus ficheros LaTeX. Lo que ya se
  ofrece baja en la lista y se indica con qué curso coincide.
- Al elegir la tanda se funden las candidatas casi iguales.
- La propuesta de curso sigue los apartados del catálogo. La duración queda
  «a decidir». Cita los documentos fuente y separa lo que ya existe de lo que
  falta por preparar. La de píldora tiene su propio esquema y su plantilla,
  para adaptarla a un formato concreto cuando haga falta.
- Las propuestas se guardan en la carpeta `carpeta` de `[propuestas]`, con un
  índice, y se ven también en la web. La exportación crea un `curso.yaml` de
  borrador, con todos los apartados `origen: propio`, y una lista de fuentes.

Pruebas:

```bash
uv run pytest
```

## Estructura de carpetas

```
Orakulue/
├── configuracion/          ejemplo de configuración (la real no se publica)
├── datos/                  inventario e informes (privado, fuera de git)
├── docs/                   plan, diseños de fases, servicio systemd, ejemplo
│                           del conector MCP y artículos del blog
├── src/orakulue/
│   ├── dominio/            entidades: Documento, GrupoDuplicados…
│   ├── infraestructura/    disco, huellas, SQLite, configuración y
│   │                       extractores de texto
│   ├── aplicacion/         casos de uso: inventariar, detectar duplicados,
│   │                       planificar, ejecutar y deshacer la centralización
│   ├── interfaz/           línea de órdenes, informes, web y conector MCP
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
