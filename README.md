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
   estaban las copias (fase 2).
3. **Extrae el texto** y detecta casi duplicados: versiones, el mismo
   documento en otro formato (fase 3).
4. **Escribe una ficha** por documento con la teoría, los ejercicios
   aprovechables y las ideas de curso (fase 4).
5. **Permite consultarlo con IA** desde cualquier dispositivo a través de una
   VPN (fases 5 y 6).

El plan completo está en [`docs/PLAN.md`](docs/PLAN.md).

## Requisitos

- Linux (probado en Debian 12).
- Python 3.11 o posterior.
- [uv](https://docs.astral.sh/uv/) para el entorno.

La fase 1 no tiene dependencias externas: usa solo la biblioteca estándar.

## Instalación

```bash
git clone https://github.com/artatxoria/Orakulue.git
cd Orakulue
uv sync
cp configuracion/orakulue.ejemplo.toml configuracion/orakulue.toml
```

Edita `configuracion/orakulue.toml`: carpetas que se recorren, extensiones,
exclusiones y rutas preferidas para el original de cada duplicado.

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

Pruebas:

```bash
uv run pytest
```

## Estructura de carpetas

```
Orakulue/
├── configuracion/          ejemplo de configuración (la real no se publica)
├── datos/                  inventario e informes (privado, fuera de git)
├── docs/                   plan del proyecto
├── src/orakulue/
│   ├── dominio/            entidades: Documento, GrupoDuplicados…
│   ├── infraestructura/    disco, huellas, SQLite, configuración
│   ├── aplicacion/         casos de uso: Inventariador, DetectorDuplicados
│   ├── interfaz/           línea de órdenes, informe Markdown y CSV
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
