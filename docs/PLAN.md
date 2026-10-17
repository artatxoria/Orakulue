# 07 — Plan de Orakulue (segunda versión)

Documento de planificación. Cuando arranque el proyecto se traslada a
`Orakulue/docs/` y desde allí se mantiene.

---

## 1. Qué problema resuelve

Juan reúne documentación aprovechable para impartir cursos: unos 4.400
documentos (6,8 GB) repartidos por el disco, con el grueso en
`~/Documentos/formakuntza/errekurtsoak` (2.659) y `~/Documentos/lana/empresas`
(770). No hay tiempo para estudiarlos uno a uno, y al descargar sin revisar se
acumulan copias.

Orakulue v2 tiene que:

1. **Inventariar** todo el material y detectar los duplicados, también los
   que tienen nombres distintos.
2. **Centralizarlo** en `~/Documentos/formakuntza/fondo/`, bien organizado,
   dejando enlaces simbólicos en los sitios de antes.
3. **Leer cada documento una vez** y guardar una ficha: teoría, ejercicios
   aprovechables, propuestas de cursos nuevos y de píldoras para SPRI.
4. **Permitir consultarlo con IA** desde cualquier dispositivo, a través de la
   VPN de servicios web, con el sistema corriendo en el PC de sobremesa.

### Por qué falló la primera versión

Orakulue v1 era un Open WebUI con documentos subidos: un chat, nada más. No
quitaba duplicados ni producía nada que se pudiera leer sin la IA delante. La
v2 invierte el orden: primero orden y fichas legibles; la conversación con la
IA va encima, al final.

## 2. Decisiones tomadas

| Asunto | Decisión |
|---|---|
| Dónde corre | PC de sobremesa con Debian. Nada en servicios web salvo la VPN |
| Lenguaje | Python, orientado a objetos (lectura de PDF y Office, huellas, SQLite, SDK de las API de IA) |
| Almacén central | `~/Documentos/formakuntza/fondo/` |
| Duplicados | Enlace simbólico al original en cada ubicación antigua |
| Fichas | API de pago (Claude u otra más económica), con control de gasto según la norma 5 |
| Nombre | Orakulue, segunda versión |
| Publicación | Repositorio en GitHub, portfolio y una serie de artículos en el blog de bidedigitala |

## 3. Fases

Cada fase deja algo útil por sí sola, aunque no se llegue a la siguiente.
Cada fase cierra con su artículo del blog.

### Fase 1 — Inventario y huellas

- Recorrido de las carpetas acordadas. Por cada fichero: ruta, tamaño, fecha
  y **huella SHA-256 del contenido**.
- La huella no depende del nombre: dos ficheros con el mismo contenido tienen
  la misma huella aunque se llamen distinto. Así salen los duplicados exactos.
- Todo se guarda en una base SQLite. **No se mueve ni se borra nada.**
- Entregable: informe de duplicados exactos agrupados, con el espacio que
  se recuperaría.

### Fase 2 — Centralización y enlaces

- Juan revisa y aprueba el informe de la fase 1.
- Cada documento único pasa a `fondo/`, con una organización provisional
  sacada de las carpetas de origen (`errekurtsoak` ya está clasificado por
  materias: Python, Access, bases de datos, libros…).
- En la ubicación antigua de cada fichero, y en la de cada copia, queda un
  enlace simbólico al original.
- Mover dentro del mismo disco es renombrar: no se copia nada y es inmediato.
- **Registro de cada operación** para poder deshacerla entera.
- Exclusiones: carpeta de Syncthing (`para_revisar`, la tablet no entiende
  enlaces), repositorios git, `anaconda3`, `Plantillas`, lo personal
  (`etxea`, `Facturación`).

### Fase 3 — Extracción de texto y casi duplicados

- Texto de cada documento: `pdftotext`, `pandoc`, y lectura del texto de las
  imágenes para los PDF escaneados.
- **Casi duplicados**: el mismo documento en PDF y en Word, una versión
  revisada, o el mismo PDF descargado de dos sitios con distintos metadatos.
  La huella no los iguala; el texto sí. Se comparan por similitud del texto.
- Los casi duplicados **no se sustituyen por enlaces**: son ficheros distintos.
  Se informa y Juan decide.

### Fase 4 — Fichas y organización temática

- Una ficha en Markdown por documento: tema, nivel, resumen de la teoría,
  ejercicios aprovechables, ideas de curso o de píldora SPRI y ruta del
  original. Legible en Obsidian y en la tablet sin IA.
- Escritas por una API de pago. La elección del proveedor se hace al llegar
  aquí, con las tarifas de ese momento.
- Control de gasto según la norma 5: estimación propia del saldo, aviso en
  castellano con lo gastado, lo que queda y cuántas ejecuciones más aguanta;
  error de falta de saldo identificando la clave; el aviso nunca detiene el
  trabajo.
- **Datos personales**: los trabajos, exámenes resueltos, certificados y CV de
  alumnos no se envían a ninguna API. En la fase 1 se excluyeron por carpeta
  los casos claros (prácticas FCT); el resto se marca en la fase 3 con
  detección sobre el texto, y lo marcado se queda fuera de las fichas.
- Con los temas de las fichas se reorganiza `fondo/` de forma definitiva. El
  programa actualiza los enlaces, porque sabe dónde está cada uno.

### Fase 5 — Buscador semántico y consulta con IA

- Vectores con `bge-m3` en local (ya instalado en Ollama) sobre fichas y texto.
- Consulta en lenguaje natural con respuesta que cita los documentos de origen.

### Fase 6 — Acceso desde cualquier sitio

- Interfaz web en el PC de sobremesa, escuchando solo en la VPN
  (`10.8.0.5`), igual que Syncthing.
- Conector MCP para poder pedir a Claude, por ejemplo, «prepárame un curso
  de Excel avanzado con lo que hay en el fondo».

### Fase 7 — Producción

- Propuestas de cursos nuevos y de píldoras SPRI generadas a partir del fondo,
  con referencia a los documentos que las sostienen.

## 4. Publicación

### GitHub y portfolio

El repositorio es público, así que **nunca entra en él**:

- los documentos ni las fichas;
- la base del inventario (las rutas dan nombres de clientes de
  `lana/empresas`);
- claves de API ni configuración real (solo un ejemplo de configuración).

Esto se fija en el `.gitignore` desde el primer commit.

### Artículos del blog

- Categoría: **Orakulue**. Un artículo por fase.
- Contenido: qué se hace, qué problema resuelve, problemas y retos
  encontrados, soluciones aplicadas y posibles mejoras. Código solo cuando
  haga falta para entender algo; el resto está en GitHub.
- Formato del blog de bidedigitala: Markdown en `src/content/blog/{es,eu}/`,
  con su pareja en euskera enlazada por `tkey`. Los 22 artículos publicados
  hasta ahora tienen las dos versiones.
- Sin nombres de clientes ni rutas que los revelen.

## 5. Decisiones del 17 de octubre de 2026

1. **Orakulue v1** renombrada a `proyectos/Orakulue_v1/`, intacta. La v2 se
   crea en `proyectos/Orakulue/`. El contenedor parado `Orakulue-UI` apunta
   todavía a la ruta antigua; no se arranca.
2. **Artículos en castellano y euskera**, como todos los del blog. Claude
   redacta las dos versiones y Juan revisa la de euskera.
3. **Alcance del inventario: todo el directorio personal**, cualquier carpeta
   con documentación útil (`formakuntza`, `lana/empresas`, `Descargas`, el
   resto de `lana`…). Tras la organización, cada documento existe en una sola
   ubicación, `fondo/`. Se excluye lo que no es documentación de formación o
   no admite enlaces: Syncthing, repositorios git, `anaconda3`, `Plantillas`,
   cachés, `etxea` y `Facturación`. La fase 1 entrega también la lista de
   carpetas encontradas para confirmar el criterio antes de mover nada.
