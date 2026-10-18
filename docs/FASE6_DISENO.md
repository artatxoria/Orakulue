# Fase 6 — Diseño del acceso remoto: web por la VPN y conector para Claude

Propuesta para revisar **antes de programar**.

---

## 1. Lo que hay

| Pieza | Estado |
|---|---|
| VPN WireGuard de servicios web (`wg0`) | En marcha. PC de sobremesa `10.8.0.5`, tablet `10.8.0.3`, móvil `10.8.0.2` (dado de alta para el CRM) |
| Cortafuegos del PC (`/etc/nftables.conf`) | Política *drop*; en `wg0` solo están abiertos el 22000 (Syncthing) y el 8000 |
| Puerto 8000 en `10.8.0.5` | **Ocupado por el CRM** (`crm_formacin-puerta-vpn-1`) |
| Buscador de la fase 5 | Funciona en la línea de órdenes del PC |

Condición de partida: **el fondo vive en el PC de sobremesa**. Si el PC está
apagado, no hay acceso. Ver el punto 6.

## 2. La web por la VPN

### Qué se puede hacer

- **Buscar**, con los mismos resultados que `orakulue buscar`: título, materia,
  interés, pasaje y variantes.
- **Leer la ficha** de cada resultado, con su Markdown convertido a HTML.
- **Abrir el original**: descargar el PDF o el Word para leerlo o anotarlo en
  la tablet.
- **Preguntar**, con la misma respuesta citada de `orakulue preguntar`. Al lado
  se muestra lo que ha costado y una casilla «sin salir del PC» que equivale
  a `--local`.
- **Índice por materias**, el mismo de `_indice.md`, navegable.

Pensada para la pantalla de la tablet y del móvil: una sola columna, letra
legible y nada que dependa de Internet (ni tipografías ni bibliotecas
externas), porque se usa por la VPN.

### Cómo se sirve

- Escucha **solo en `10.8.0.5`**, la dirección de la VPN, como Syncthing. Desde
  la red de casa o desde Internet no se ve.
- Puerto propio: **8010**. Hay que abrirlo en el cortafuegos del PC, solo en
  `wg0`, con una línea más en `/etc/nftables.conf`. Es un paso tuyo, porque
  necesita `sudo`.
- **Sin contraseña: basta la VPN** (decidido). Se asume este riesgo: En la
  VPN también está servicios web. Si alguna vez se comprometiera ese
  servidor, sin contraseña tendría acceso directo al fondo y a los documentos
  originales. Para acotarlo, la web solo escucha en `10.8.0.5`, el
  cortafuegos solo abre el puerto en `wg0`, y no hay nada que permita
  escribir ni borrar: solo se lee. Añadir contraseña más adelante sería un
  cambio pequeño.
- Arranca como **servicio de usuario de systemd**, igual que Syncthing: se
  levanta solo al encender el PC.
- Solo descarga **documentos del inventario**, pedidos por su huella; nunca una
  ruta que venga en la petición. Así no se puede pedir `/etc/passwd` ni ningún
  fichero fuera del fondo.

### Con qué se programa

Python, como el resto, con **Starlette y Uvicorn**: un servidor web pequeño,
moderno y sin magia, que basta para cinco páginas. Para pasar las fichas a
HTML, **markdown-it-py**. Las plantillas, con **Jinja2**. Son tres dependencias
nuevas, todas pequeñas y muy usadas.

La lógica no se duplica: la web llama a las mismas clases que la línea de
órdenes (Buscador, Respondedor, AvisoSaldo…).

## 3. El conector para Claude (MCP)

Un servidor **MCP** (Model Context Protocol) permite que Claude use Orakulue
como herramienta. Pides «prepárame un curso de Excel avanzado con lo que tengo
en el fondo», y Claude busca, lee las fichas y los pasajes que le hacen falta y
redacta el curso.

### Herramientas que ofrece

| Herramienta | Qué hace |
|---|---|
| `buscar` | Búsqueda híbrida; devuelve títulos, materias, interés, huella y pasaje |
| `leer_ficha` | La ficha completa de un documento |
| `leer_pasajes` | Los mejores pasajes de un documento para una consulta |
| `materias` | El índice por materias, con cuántas fichas hay de cada una |

No hay herramienta «preguntar». Quien redacta la respuesta es el propio
Claude, y pasar por Haiku sería pagar dos veces por lo mismo.

### Datos personales

Todo lo que el conector devuelve **llega a Anthropic**, igual que lo que se
envía a la API. Se aplica la misma regla de la fase 5: los documentos con datos
personales pueden aparecer en los resultados, marcados y con su título, pero
**su texto y su ficha no se devuelven nunca**.

### Dónde funciona: una limitación importante

| Dónde usas Claude | ¿Funciona? | Por qué |
|---|---|---|
| **Claude Code y la app de escritorio en el PC de sobremesa** | **Sí** | El conector corre en el propio PC y Claude lo arranca directamente (transporte *stdio*). Nada nuevo se expone en la red |
| La app de Claude en el móvil o en claude.ai | **No, tal cual** | Esos conectores los llaman los servidores de Anthropic desde Internet, y Orakulue solo es accesible dentro de la VPN |

Para el móvil, la web del punto 2 cubre buscar, leer y preguntar. Abrir el
conector a Internet, publicándolo a través del Traefik de servicios web con
autenticación, es posible, pero expone el fondo fuera de la VPN. **Decidido:
ahora solo el conector local**; lo de Internet, si llega a hacer falta, irá en
una fase aparte y con su propia revisión de seguridad.

Con qué se programa: el **SDK oficial de MCP para Python** (`mcp`), que es lo
que piden Claude Code y la app de escritorio.

## 4. Lo que tendrás que hacer tú (llegado el momento, de uno en uno)

1. Abrir el puerto 8010 en `wg0` en el cortafuegos del PC (una línea en
   `/etc/nftables.conf`). Para aplicarlo en vivo es preferible
   `sudo nft add rule inet firewall input iifname "wg0" tcp dport 8010 accept`
   a recargar el fichero entero, que duplica las reglas ya cargadas (sin
   efecto práctico, pero deja la tabla desordenada hasta el próximo arranque).
2. ~~Dar de alta el móvil en la VPN.~~ **No hace falta**: el móvil ya estaba
   en la VPN (`10.8.0.2`) desde que se montó el acceso al CRM. Basta con
   activar el túnel en la aplicación WireGuard (el Xiaomi lo corta cuando no
   se usa) y escribir la dirección con `http://` delante.
3. Añadir el conector a Claude Code y a la app de escritorio. Lo puedo dejar
   escrito en la configuración del proyecto, y solo tendrás que aprobarlo.

## 5. Pruebas

- **Seguridad**: la web no responde sin sesión, una ruta inventada no descarga
  nada fuera del inventario, y ni la web ni el conector devuelven el texto de
  un documento personal.
- **Funcionamiento**: búsqueda, ficha, descarga y pregunta, con el cliente de
  pruebas de Starlette, sin levantar el servidor y sin gastar (con la API
  simulada).
- **Conector**: las cuatro herramientas, llamadas como las llamaría Claude.

## 6. Cuando el PC está apagado

No hay acceso: el índice, los textos y los originales están en el PC. Hay dos
alternativas, y ninguna es para ahora:

- **Encendido remoto** (*Wake-on-LAN*). Con el PC apagado su VPN tampoco
  está, así que no se le puede despertar desde servicios web directamente:
  haría falta otro aparato siempre encendido en la red de casa (el router, si
  lo permite, o una placa pequeña) que reciba la orden y lo despierte.
- **Copia del índice en servicios web**, solo para buscar. Duplicaría
  documentos privados en el servidor, en contra del criterio de la fase 4.
