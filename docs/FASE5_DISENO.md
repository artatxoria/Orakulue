# Fase 5 — Diseño del buscador semántico

Propuesta para revisar **antes de programar**.

---

## 1. Qué se quiere poder hacer

- **Buscar**: «¿qué tengo sobre tablas dinámicas para gente que empieza?» y
  recibir los documentos más útiles, con su ficha, su interés formativo y el
  pasaje que responde.
- **Preguntar**: «¿cómo explicarías BUSCARV con un ejemplo de mis apuntes?» y
  recibir una respuesta redactada que **cita los documentos** de los que sale.

La fase 6 llevará esto a una página web por la VPN y a un conector para
Claude. Aquí se construye el motor y una orden de línea de comandos.

## 2. Qué se indexa

| Nivel | Qué | Cuántos | Para qué |
|---|---|---:|---|
| Ficha | Las fichas de la fase 4 (título, tema, resumen, teoría, ejercicios, ideas) | 1.628 | Encontrar **documentos**: una ficha resume el documento entero |
| Trozo | El texto de cada documento, en trozos de ~1.500 caracteres solapados | ~58.000 | Encontrar **pasajes** concretos y citar de dónde sale cada cosa |

- Se indexan los 2.201 contenidos con texto, no solo los que tienen ficha.
- Por documento se indexan como máximo 300.000 caracteres (un libro largo
  entero), y en las hojas de cálculo, 20.000: más allá son filas de datos que
  solo meten ruido.
- Los trozos respetan los párrafos: no se corta una frase por la mitad.
- Es **incremental por huella**, como todo lo anterior: un documento nuevo o
  cambiado se indexa; lo demás no se toca.

## 3. Cómo se busca: híbrido

Dos buscadores que se complementan, y una fusión de resultados.

| Buscador | Encuentra | Falla con |
|---|---|---|
| **Palabras** (FTS5, ya incluido en SQLite) | Términos exactos: «BUSCARV», «IFCT0049», «Power Query» | Sinónimos y otros idiomas: «buscar un valor en una tabla» no encuentra «BUSCARV» |
| **Significado** (vectores con `bge-m3`, en Ollama, en tu GPU) | Preguntas en lenguaje natural, sinónimos y **entre idiomas**: una pregunta en castellano encuentra apuntes en euskera | Códigos y nombres propios poco frecuentes |

Los dos rankings se combinan con **fusión por rango recíproco** (RRF): sencilla,
sin parámetros que ajustar y robusta. Los resultados se agrupan por documento,
y se muestran la ficha, la materia, el interés formativo y el mejor pasaje.

Comprobado en el PC de sobremesa: SQLite trae FTS5, y `bge-m3` da vectores de
1.024 dimensiones y ocupa 1,2 GB de los 8 GB de la tarjeta gráfica.

### Dónde se guardan los vectores

En un fichero NumPy junto a la base de datos (unos 120 MB en media precisión),
con búsqueda por fuerza bruta: con 60.000 vectores, multiplicar una matriz es
instantáneo. **No hace falta un servidor de vectores** (Qdrant, Chroma…): uno
más que arrancar, mantener y respaldar, sin ganancia a este tamaño. Si el fondo
creciera diez veces, se cambiaría la pieza de almacenamiento sin tocar lo demás.

Dependencia nueva: `numpy`.

## 4. Cómo se responde

1. Se buscan los mejores pasajes y fichas (búsqueda híbrida).
2. Se envían al modelo con la pregunta y la instrucción de responder **solo**
   con lo que hay en esos pasajes y de **citar cada afirmación** con su número.
3. La respuesta llega en castellano, con la lista de fuentes: ruta del
   documento y enlace a su ficha.

Si los pasajes no responden la pregunta, el modelo debe decirlo, no inventar.

### Con qué modelo (decidido)

| Opción | Calidad | Coste | Privacidad |
|---|---|---|---|
| **Haiku 5.5 por la API** | Buena, también en euskera | ~0,001 $ por pregunta | Los pasajes salen hacia Anthropic |
| **Modelo local** (`qwen2.5:7b`, ya instalado) | Bastante peor, sobre todo en euskera | 0 | Nada sale del PC |

**Decisión**: Haiku por defecto y la opción `--local` para preguntas sobre
material delicado. El control de gasto es el mismo de la fase 4: cada
pregunta se anota, y el saldo se avisa igual.

### Datos personales (decidido)

Los 329 documentos marcados con datos personales:

- **Decisión**: se indexan para la búsqueda **local** (te salen marcados como
  tales, y nada sale del PC), pero sus pasajes **nunca** se envían a la API al
  responder. Con `--local` sí se usan, porque no salen del equipo.

## 5. Cómo se sabe si busca bien

Antes de darlo por bueno, un **juego de preguntas de prueba**: unas 20
preguntas reales («ejercicios de consultas de acción en Access», «material en
euskera sobre funciones de Excel», «qué tengo de RAG»…), cada una con los
documentos que deberían salir. Se mide qué proporción aparece entre los diez
primeros con cada buscador por separado y con el híbrido. Así cualquier ajuste
posterior (tamaño de trozo, pesos) se juzga con datos.

Las preguntas las propongo yo a partir de las fichas, y tú corriges las que no
reflejen lo que buscarías de verdad.

## 6. Órdenes

```bash
uv run orakulue indexar                         # crea o actualiza el índice (local, gratis)
uv run orakulue buscar "tablas dinámicas para principiantes"
uv run orakulue preguntar "¿cómo explico BUSCARV con mis apuntes?"
uv run orakulue preguntar --local "…"          # sin salir del PC
uv run orakulue evaluar-busqueda                # juego de preguntas de prueba
```

`indexar` y `buscar` no cuestan nada. `preguntar` sin `--local` cuesta muy poco
y queda anotado en el control de gasto.
