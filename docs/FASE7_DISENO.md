# Fase 7 — Diseño de las propuestas de cursos y píldoras

Propuesta para revisar **antes de programar**.

---

## 1. Qué se quiere

Pasar de «tengo mucho material» a **«esto es lo que podría ofrecer, y con qué
lo sostengo»**: una lista corta y razonada de cursos nuevos y de píldoras
formativas para empresas. Cada propuesta lleva el material del fondo que la
respalda, lo que ya está hecho (teoría, ejercicios) y **lo que falta por
preparar**.

No sustituye la decisión: la propone. Lo que se acepte pasa a Bibliotecario,
que es quien produce el material del curso.

## 2. De dónde se parte (comprobado)

| Pieza | Qué hay |
|---|---|
| Fichas de interés alto o medio | 1.120 (955 en castellano, 58 en euskera, 107 en inglés) |
| Ideas de curso dentro de esas fichas | unas 2.200 |
| Ideas de píldora | unas 2.200 |
| Oferta actual | Catálogos en LaTeX en `en_Elaboracion/Catálogo de cursos/` (empresas, euskera, subvencionada) |
| Buscador de la fase 5 | Para encontrar más material de apoyo de cada propuesta |

Cada ficha propone ideas mirando solo su documento, así que hay miles,
repetidas y desiguales. La fase 7 consiste en **juntarlas, contrastarlas con
el fondo y con la oferta actual, y quedarse con las mejores**.

## 3. El proceso, en cuatro pasos

### Paso 1 — Reunir y agrupar las ideas (local, gratis)

- Se leen las ideas de curso y de píldora de las fichas de interés alto y
  medio. Las de documentos con datos personales ya no tienen ficha.
- Cada idea se convierte en vector con `bge-m3`, como en la fase 5, y se
  **agrupan las parecidas**. «Tablas dinámicas para análisis comercial» y
  «Informes de ventas con tablas dinámicas» son la misma propuesta vista
  desde dos documentos.
- Cada grupo es una **propuesta candidata**, que reúne todos los documentos
  que la sugirieron.

### Paso 2 — Puntuar cada candidata (local, gratis)

Una puntuación sencilla y explicable, no una caja negra:

| Criterio | Por qué |
|---|---|
| **Respaldo**: cuántos documentos distintos la sugieren, y de qué interés | Una propuesta que sale de veinte documentos tiene material detrás; una que sale de uno, no |
| **Ejercicios disponibles** en esos documentos | Un curso sin ejercicios preparados cuesta mucho más de montar |
| **Vigencia**: proporción de material actual frente a desactualizado | Excel 2010 no sostiene un curso de 2027 |
| **Euskera**: si hay material en euskera | Es un valor diferencial de la oferta |
| **Ya en el catálogo** (penaliza) | Se compara con los títulos de los catálogos actuales; si ya lo ofreces, no es «nuevo» |

Sale una lista ordenada de candidatas, con el desglose de su puntuación para
que se vea por qué cada una está donde está.

### Paso 3 — Redactar las mejores (API de pago, poco volumen)

Para las mejores candidatas (por omisión, 20 cursos y 20 píldoras), un modelo
redacta la propuesta a partir de **las fichas de sus documentos de apoyo**,
más los pasajes que encuentre el buscador. La propuesta incluye:

- **título** y **a quién va dirigida**;
- **objetivo** y lo que sabrá hacer quien la curse;
- **temario por módulos o bloques**, en orden, sin horas ni sesiones (el
  reparto del tiempo lo decides tú);
- **qué ya existe en el fondo**: teoría y ejercicios, con el documento de
  cada cosa;
- **qué falta por preparar**;
- **en qué se diferencia** de lo que ya ofreces;
- para las píldoras: el **problema concreto de empresa** que resuelve.

Mismas reglas que en las fases anteriores: salida en JSON con esquema fijo,
convertida a Markdown; **nada de documentos con datos personales**;
simulacro con presupuesto antes de gastar; control de saldo según la norma 5.

### Paso 4 — Revisar y llevar a Bibliotecario (local)

- Las propuestas quedan en `~/Documentos/formakuntza/propuestas/`, una por
  fichero, con un índice ordenado por puntuación. Se leen en Obsidian, en la
  tablet y en la web, donde se añade una página «Propuestas».
- Una orden **exporta la propuesta aceptada como borrador para
  Bibliotecario**: una carpeta con su `curso.yaml`, con todos los apartados
  marcados `origen: propio`, porque nadie los ha contratado, y la lista de
  documentos fuente. Si luego llega un cliente con su temario, ese temario
  manda, como dicta `ELABORACION-DE-CURSOS.md`.

## 4. Coste

El volumen es pequeño: unas 40 propuestas, con unos 15.000 tokens de entrada
y 3.000 de salida cada una. Calculado con las tarifas de la fase 4:

| Modelo | Coste aproximado de las 40 |
|---|---:|
| Haiku 5.5 | ≈ 0,15 $ |
| Sonnet 5.5 | ≈ 2,50 $ |
| Opus 5.5 | ≈ 5 $ |

El simulacro dará la cifra exacta antes de gastar. Aquí, a diferencia de las
fichas, **la calidad pesa más que el precio**: son pocas llamadas, y cada
propuesta es un posible producto. Propuesta: **Sonnet 5.5**, con una prueba
previa de tres propuestas con Sonnet y Opus para comparar, igual que se hizo
con las fichas.

## 5. Lo que no hace

- No inventa material: lo que no está en el fondo aparece como «falta por
  preparar», no como contenido.
- No decide precios ni duraciones.
- No lee la bóveda de Obsidian (`Ezaugarriak`), que es el otro fondo de
  Bibliotecario. Sería una mejora posterior: muchas ideas nacen ahí.

## 6. Decisiones (18 de octubre de 2026)

1. **Modelo**: Sonnet 5.5, con una prueba previa de tres propuestas con Sonnet
   y Opus para comparar.
2. **Primera tanda**: 20 cursos y 20 píldoras.
3. **Píldoras SPRI**: por ahora, formato libre. Más adelante habrá
   seguramente un formato que seguir. Por eso **el esquema de la píldora va en
   su propio módulo**, separado del de los cursos: cuando llegue el formato,
   se cambia ese esquema y su plantilla, y se vuelve a redactar solo lo que
   haga falta, sin tocar el resto del proceso. Las propuestas guardan la
   respuesta completa del modelo, como las fichas, para poder rehacer el
   Markdown sin pagar.
4. **Oferta actual**: los catálogos de `Catálogo de cursos/` son la
   referencia.
