# Fase 4 — Diseño de las fichas

Propuesta para revisar **antes de programar**. Tarifas tomadas de la tabla de
modelos de Anthropic del 6 de octubre de 2026; se vuelven a comprobar en su
página de precios antes de la primera ejecución.

---

## 1. Qué se ficha

| Criterio | Decisión propuesta |
|---|---|
| Unidad | Una ficha por **contenido distinto** (huella), no por fichero |
| Familias de plantilla | Una sola ficha por familia, que enumera a todos sus miembros |
| Datos personales | Los de nivel medio y alto **no se envían** |
| Sin texto o ilegibles | No se fichan |
| Alcance | **Todo el inventario**, esté donde esté: lo que interesa es si sirve para formar, no dónde está guardado |
| Interés formativo | Lo valora el modelo: alto, medio, bajo o ninguno. Si es «ninguno» (un contrato, una factura), la ficha es mínima, con el motivo, y va a `fichas/_sin_interes/` |

Son **1.724 contenidos**: 1.326 de `formakuntza`, 397 de `lana` y 1 suelto.

## 2. Qué se envía de cada documento

Los textos van de unos pocos párrafos a libros enteros (mediana: 6.500
caracteres; uno de cada diez pasa de 138.000). No se envía el libro entero:

- los primeros **24.000 caracteres** (portada, índice y primeros capítulos);
- **8.000** del centro y **8.000** del final, para que la ficha no describa
  solo el arranque.

Unos 40.000 caracteres como máximo por documento. Todo el corpus son unos
**25 millones de caracteres**, entre 7 y 9 millones de tokens según el idioma.
Los documentos cortos van enteros.

## 3. La ficha

El modelo devuelve **JSON con un esquema fijo** (salida estructurada), y el
programa lo convierte en Markdown. Así todas las fichas tienen el mismo
formato y una respuesta incompleta se detecta antes de guardarla.

Cabecera YAML (para buscar y filtrar en Obsidian):

```yaml
titulo:          # título real del documento, no el nombre del fichero
tipo:            # manual, libro, apuntes, ejercicios, presentación, examen,
                 # plantilla, normativa, propuesta, otro
tema:            # tema principal (p. ej. «Excel — tablas dinámicas»)
temas: []        # temas secundarios
nivel:           # iniciación, intermedio, avanzado
idioma:          # es, eu, en
publico:         # a quién va dirigido
vigencia:        # actual / desactualizado (p. ej. «Excel 2010») y por qué
interes:         # interés formativo: alto, medio, bajo, ninguno
aprovechable:    # alto, medio, bajo
huella:
rutas: []        # dónde está en el disco
familia: []      # otros documentos de su familia de plantilla, si los hay
```

Cuerpo:

1. **Resumen**, en pocas líneas.
2. **Teoría que contiene**: los conceptos, en viñetas, con el apartado o la
   página donde están cuando se pueda.
3. **Ejercicios aprovechables**: qué ejercicio, qué practica, si trae solución.
4. **Ideas de curso**: título, a quién va dirigido y qué aprendería.
5. **Ideas de píldora para SPRI**: título y objetivo concreto.
6. **Observaciones**: calidad, carencias, si conviene combinarlo con otro.

Sin reparto de horas ni de sesiones: eso lo decides tú.

Las fichas se guardan en `~/Documentos/formakuntza/fichas/`, una por fichero
`.md`. Se leen en Obsidian y en la tablet, sin la IA delante. Esa carpeta no
entra en el inventario, porque el `.md` no está entre las extensiones.

## 4. Control de gasto (norma 5)

Igual que en el CRM, con estas piezas:

- **Clave propia**: `CLAVE_API_ANTHROPIC_ORAKULUE`, distinta de la del CRM.
  Con una clave por aplicación, el gasto de una no falsea la estimación de la
  otra, y cuando falle el error dice qué clave es.
- **Saldo declarado** en la configuración privada: lo pones tú, porque el
  proveedor no lo publica.
- **Registro de consumo** en la base de datos: por llamada, los tokens de
  entrada, de salida y de caché, y el coste calculado con la tarifa.
- **Presupuesto previo**: como en la fase 2, la orden hace por defecto un
  **simulacro** que cuenta lo que se va a enviar y da el coste estimado. No se
  gasta nada hasta pasar `--ejecutar`.
- **Aviso al terminar**, en castellano: lo gastado en esta ejecución, el
  acumulado, el saldo estimado y cuántas ejecuciones como esta aguanta.
  Recuerda que es una estimación y remite al panel de Anthropic.
- **El aviso nunca para nada.** Lo único que corta es el error real del
  proveedor.
- **Falta de saldo**: se reconoce por el **texto** del mensaje del proveedor,
  nunca por el código HTTP. El error dice que se ha agotado el saldo de la
  clave `CLAVE_API_ANTHROPIC_ORAKULUE`. Ante la duda, se trata como un error
  normal.
- **Reanudable**: cada ficha guardada no se vuelve a pedir. Si algo corta a
  mitad, se continúa donde se quedó y no se paga dos veces.

## 5. Modelo

### Coste estimado del fondo completo (1.724 fichas)

Supuestos: unos 10 millones de tokens de entrada (texto más instrucciones) y
unos 3 millones de salida (ficha y razonamiento, con esfuerzo bajo).

| Modelo | Normal | Por lotes (−50 %) |
|---|---:|---:|
| Claude Haiku 5.5 (0,10 / 0,50 $ por millón) | ≈ 2,50 $ | **≈ 1,25 $** |
| Claude Sonnet 5.5 (2 / 10 $) | ≈ 50 $ | ≈ 25 $ |
| Claude Opus 5.5 (4 / 20 $) | ≈ 100 $ | ≈ 50 $ |

Son órdenes de magnitud, no presupuestos. El presupuesto exacto lo dará el
simulacro, contando el texto real.

La **API por lotes** (Message Batches) cuesta la mitad. A cambio, las
respuestas no llegan al momento, sino en algún momento dentro de un plazo
máximo de 24 horas. Para fichar todo el fondo no importa.

### Otros proveedores

Con Haiku 5.5 el fondo entero cuesta un par de dólares. Un proveedor más
barato ahorraría céntimos y obligaría a:

- abrir otra cuenta y otra clave;
- rehacer el control de saldo, que ya existe para Anthropic en el CRM;
- enviar material de clientes a un proveedor con otras condiciones de
  tratamiento de datos.

No compensa.

### Decisión: prueba con los tres modelos

1. **Prueba comparativa**: 20 documentos variados (castellano y euskera; un
   libro, un manual, ejercicios, una presentación, una hoja de cálculo),
   fichados con los tres modelos. Coste total de la prueba: alrededor de un
   dólar. Tú comparas las fichas una al lado de otra.
2. Con el modelo elegido, el **fondo completo por lotes**.

Mi hipótesis, que la prueba confirmará o no: **Haiku 5.5** basta para resumir,
clasificar y localizar ejercicios. **Sonnet 5.5** puede notarse en el euskera y
en la calidad de las ideas de curso. Si la diferencia está solo en las ideas,
caben las dos cosas: Haiku para las fichas y Sonnet, más adelante, para la
fase 7 (propuestas de cursos), que trabaja sobre muchas menos peticiones.

## 6. Lo que tendrás que hacer tú (llegado el momento, de uno en uno)

1. Crear una clave en el panel de Anthropic para Orakulue.
2. Guardarla en la variable de entorno `CLAVE_API_ANTHROPIC_ORAKULUE`.
3. Declarar el saldo disponible en la configuración privada.
