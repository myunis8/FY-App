# Cambios

El formato es una línea por cambio, agrupadas por versión.
`contrato` indica la versión del esquema de `obra.json`.

## 0.26.0 — nueva hoja de esquema unifilar en el PDF de Tablero, y el PDF de Routeo genera bastante más rápido todavía

- **Nueva hoja "esquema unifilar" en el PDF de Tablero.** Además de
  conexionado y guía de tapa, ahora `generar()` agrega una tercera hoja con
  la topología eléctrica clásica: alimentación desde medidor → interruptor
  termomagnético general → diferencial → barra de fase/neutro → una térmica
  por circuito, con su descripción (la misma de Circuitos, unificada en la
  versión anterior), corriente y sección. La puesta a tierra se dibuja como
  una bajada aparte con el símbolo de jabalina, separada de las barras de
  fase/neutro (en una instalación TT es un sistema aparte).
  - No inventa datos que la app no tiene: no hay potencia estimada por
    circuito, tipo de sistema de puesta a tierra, resistencia de jabalina ni
    norma aplicada, porque hoy no se cargan en ningún lado. El día de
    mañana que se agreguen esos campos, esta hoja es el lugar natural para
    mostrarlos.
  - El alto de la página se calcula de antemano según cuántas líneas ocupa
    la descripción más larga de los circuitos, en vez de dejar una hoja de
    tamaño fijo con espacio de sobra o de menos.
  - Se agregan tres símbolos nuevos reutilizables (`_simbolo_interruptor`,
    `_simbolo_diferencial`, `_simbolo_tierra`) con el mismo lenguaje visual
    (colores, trazos) que ya usan las otras dos hojas.
  - Probado generando el PDF a mano con varias combinaciones (sin
    diferencial, tablero recién creado sin ningún circuito todavía, sin
    bornera de tierra, un tablero trifásico con 10 circuitos) y mirando
    cada resultado renderizado -- ninguna combinación rompe, todas quedan
    legibles. También probado de punta a punta contra un servidor real:
    crear una obra, cargar circuitos, crear un tablero, sincronizarlo y
    descargar el PDF por la misma ruta que ya usaba el botón "Exportar
    PDF" de Tablero (sin tocar ese botón).
- **El PDF de Routeo genera todavía más rápido.** Además del cálculo de
  cruces (ya arreglado en la versión anterior), se encontró un segundo
  cuello de botella real: **la foto del plano se volvía a reescalar entera
  en cada una de las hojas** del PDF (la general, la detallada, y una por
  cada circuito) -- con una foto de varios megapíxeles (como una foto
  sacada con el celular) reescalar de nuevo en cada hoja es caro, y
  `makePdf()` genera siempre a la misma resolución (6000 px), así que el
  resultado de reescalarla es idéntico en las N hojas.
  - `canaliza.html`: `planCanvas()` ahora reescala el fondo una sola vez
    (queda en caché mientras no cambie el plano) y lo reutiliza con un
    blit directo en el resto de las hojas, en vez de volver a resamplear
    la foto original cada vez. `drawScene()` recibe un flag nuevo
    (`skipBase`) para no dibujar el fondo cuando ya lo dibujó
    `planCanvas()` aparte -- no cambia en nada el comportamiento del
    editor en pantalla, que sigue llamando a `drawScene()` como siempre.
  - Medido con Puppeteer sobre el código ya parcheado, con una foto
    sintética de 3200×4200 con textura (no un color plano, para que el
    costo de reescalado sea representativo): 20 circuitos pasó de 13.1s a
    5.2s, otra mejora de ~2.5x encima de la del cálculo de cruces. Sumando
    las dos mejoras, un proyecto grande debería andar entre 5 y 6 veces
    más rápido que antes de estos dos cambios.

## 0.25.0 — la obra abierta ahora es una pantalla propia (con Volver a Home), "Tablero principal" a secas se borra solo, y el PDF de Routeo genera bastante más rápido

- **El detalle de una obra ya no es un modal, es una pantalla propia:
  `obra.html?obra=<id>`.** Antes, al hacer clic en una obra desde Home se
  abría una ventanita (overlay) con los módulos; entrar a cualquier módulo
  y tocar "Volver" te mandaba siempre al Home, obligando a volver a buscar
  la obra en la lista. Con muchas obras esto se vuelve tedioso.
  - Se creó `web/obra.html`, con el mismo contenido que antes vivía en el
    modal de `index.html` (resumen, plano, los 4 módulos, subir/bajar/
    borrar), pero como pantalla completa navegable por URL.
  - `index.html`: el clic en una tarjeta de obra ahora navega a
    `/obra.html?obra=<id>` en vez de abrir el modal. Se sacó todo el
    código del modal de detalle que quedó sin uso (`abrirDetalle`,
    `pintarBloques`, `pintarPlano`, etc. -- ahora viven en `obra.html`).
  - `circuitos.html`, `tablero.html`, `canaliza.html`, `presupuesto.html`:
    el botón "Volver" ahora manda a `/obra.html?obra=<OBRA_ID>` en vez de
    `/` (Home) -- así entrar y salir de un módulo no te saca del contexto
    de la obra que estás trabajando.
  - `revisor.html` también actualizado, aunque hoy sólo se llega ahí desde
    `obra.html` (antes el modal), no cambia el flujo real, sólo el destino
    del botón.
  - `precios.html` (la lista de precios global, no depende de una obra)
    sigue volviendo a Home, porque no tiene sentido "asociarla" a ninguna
    obra en particular.
  - Probado con Puppeteer contra un servidor real: Home → obra.html →
    cada uno de los 4 módulos → Volver, confirmando en cada paso que la
    URL es la esperada y que ninguna vuelve al Home salvo desde
    `obra.html` misma.
- **"Tablero principal" a secas (el que quedaba de antes de separar la
  semilla en monofásico/trifásico) ahora se borra solo.** No hay nada en
  el código que lo "reagregue" -- lo que pasaba es que si se borraba a
  mano en `precios.html` sin darse cuenta de guardar (o si quedaba en
  datos viejos), seguía apareciendo. Ahora `precios.py` tiene una lista
  chica de ítems puntuales obsoletos (por ahora sólo éste) que se eliminan
  solos cada vez que se lee la lista de precios, sin depender de acordarse
  de borrarlo a mano. Probado con una lista de precios armada a mano con
  el caso exacto: al levantar el servidor, desaparece; "Tablero principal
  monofásico/trifásico" (los que sí hay que tener) quedan intactos.
- **El PDF de Routeo genera ~2 a 2.4x más rápido cuando hay varios
  circuitos.** El motivo real: por cada hoja del PDF (la general, la de
  cableado detallado, y una por cada circuito tildado) se volvía a
  calcular `findCrossings()` -- que recorre TODOS los cruces de TODO el
  proyecto y cuesta del orden de tramos² -- aunque el resultado es
  exactamente el mismo para cualquier hoja de un mismo PDF. Con muchos
  circuitos, ese cálculo se repetía una vez por cada hoja en vez de una
  sola vez.
  - `canaliza.html`: `makePdf()` ahora calcula los cruces una sola vez al
    principio y se los pasa a `planCanvas()` en las 3 hojas que lo usan,
    en vez de que cada una los recalcule por su cuenta. `planCanvas()`
    sigue calculándolos ella misma si no se los pasan (para no romper
    ningún otro uso futuro).
  - No cambia el resultado visual del PDF -- es exactamente el mismo
    cálculo, sólo que se hace una vez en lugar de N veces.
  - Medido con Puppeteer sobre proyectos sintéticos (usando el hook
    `window.canalizaDebug` para inyectar circuitos/tramos y llamar
    `planCanvas()` real de este archivo, antes/después del cambio): con
    20 circuitos, 5.2s → 2.15s (2.41x); con 35 circuitos, 6.0s → 2.9s
    (2.07x). El resto del tiempo es dibujar y comprimir a PNG cada hoja a
    resolución alta (6000 px), que no se tocó -- si en algún momento hace
    falta exprimir más, ahí quedaría el próximo lugar para mirar, bajando
    la resolución de las hojas por circuito (que no necesitan tanto
    detalle como la hoja general) a cambio de algo de nitidez.

## 0.24.1 — categorías huérfanas en la lista de precios corregidas, y la descripción de circuito ahora se lee y edita también desde Tablero

- **Bug real encontrado: "Tomas" vs "Tomacorrientes"**. `precios.html` sólo
  pinta las categorías de la lista fija `CATEGORIAS`; cualquier ítem que
  tuviera guardada una categoría vieja o mal tipeada (como
  `"Tomacorrientes"`, en vez de `"Tomas"`) quedaba invisible ahí -- no se
  podía ver ni tocarle el precio. Pero el combobox de "agregar de la lista
  de precios" en `presupuesto.html` no filtra, así que ahí sí aparecía, como
  un grupo aparte llamado "Tomacorrientes". Resultado: la lista de tomas
  especiales existía y tenía precio, pero era imposible editarla desde
  `precios.html`, que es justo lo que se reportó.
  - `precios.py`: `_completar_faltantes()` ahora corrige la categoría de un
    ítem conocido (matcheado por nombre exacto contra la semilla) si quedó
    en un valor que ya no existe en `CATEGORIAS` -- sólo en ese caso, nunca
    si el usuario lo reclasificó a mano a otra categoría válida. Se probó
    con una lista de precios reconstruida a mano con el caso exacto
    reportado (`Tomacorriente común`, las 3 `Toma especial - ...` y los
    artefactos bajo `"Tomacorrientes"`/`"Puntos"` en vez de
    `"Tomas"`/`"Iluminación"`): al levantar el servidor se realinean solas.
  - `precios.html`: además, como defensa, ya **no oculta ninguna categoría**
    aunque no la reconozca -- la muestra al final con una etiqueta "SIN
    CATALOGAR" para poder reclasificarla con un clic, en vez de que vuelva a
    desaparecer en silencio si este bug se repite por otra vía.
  - Se agregó una etiqueta "POSIBLE DUPLICADO" junto a cualquier ítem cuyo
    nombre se repita exactamente en otro (por ejemplo, un `"Tablero
    principal"` suelto que quedó de antes de separar la lista en
    monofásico/trifásico) -- no se borra solo (regla de oro), pero ahora se
    nota para que se pueda borrar a mano.
  - El botón "Agregar ítem" de `precios.html` ya no acepta una categoría
    tipeada a mano que no matchee ninguna de la lista válida (eso es lo que
    generaba el problema en primer lugar) -- si no matchea, cae a "Otros".
  - `presupuesto.html`: el combobox de "agregar de la lista de precios"
    ahora agrupa en el mismo orden que `precios.html` (conocidas primero,
    en orden fijo), para que las dos pantallas se vean consistentes entre
    sí. Probado con Puppeteer: los mismos grupos, mismas cantidades, mismo
    orden en las dos pantallas.
  - Se confirmó que `presupuesto.sugerir_items()` (matching automático
    desde el plano) sigue sin avisos después del cambio -- el fix sólo
    toca `categoria`, nunca `item` (el nombre, que es lo que usa
    `EQUIVALENCIAS` para matchear).
- **Bug real encontrado: la descripción de un circuito no se veía desde
  Tablero**. El panel de detalle de una térmica en `tablero.html` mostraba
  únicamente `dispositivo.descripcion` (un campo propio del dispositivo),
  nunca `circuito.notas` (la descripción que se carga en Circuitos) -- por
  eso, al seleccionar una térmica cuyo circuito ya tenía descripción, el
  campo aparecía vacío, dando a entender que no había ninguna.
  - Ahora, si la térmica está atada a un circuito (`circuitoId`), el campo
    "Descripción" del panel de Tablero lee y edita directamente
    `circuito.notas` -- la misma clave que ya se editaba en Circuitos, sin
    un campo paralelo. Los dispositivos sin circuito (térmica general,
    diferencial, protector, bornera) siguen usando su propio
    `descripcion`, como ya funcionaba desde 0.24.0.
  - `contrato.py`: se agregó una migración chica y segura
    (`_consolidar_descripcion_dispositivos()`, corre en `normalizar()`, o
    sea en cada lectura/guardado) que, si un dispositivo viejo ya tenía su
    propia `descripcion` de antes de este cambio, la traslada a
    `circuito.notas` en vez de perderla (sin pisar una que el usuario ya
    haya cargado ahí).
  - `pdf_tablero.py`: la guía de tapa ahora usa la misma prioridad -- para
    un dispositivo con circuito, siempre `circuito.notas`, nunca el
    `descripcion` suelto del dispositivo -- para que PDF, Tablero y
    Circuitos muestren siempre lo mismo.
  - Probado con Puppeteer contra un servidor real: se creó un circuito con
    descripción ("Iluminación cocina"), se lo asignó a una térmica de
    tablero, y al seleccionarla en `tablero.html` el campo mostró el valor
    correcto con la etiqueta "Descripción del circuito (misma de
    Circuitos)". Se probó también el camino de edición (escribir en el
    campo desde Tablero) y se confirmó en `obra.json` que actualiza
    `circuito.notas`, no un campo aparte. Se generó el PDF del tablero, se
    renderizó con PyMuPDF y se miró: la guía de tapa muestra la descripción
    correcta debajo de la térmica.

## 0.24.0 — bug crítico de precios corregido (fallaba en silencio), descripción propia en protecciones, y aviso visible cuando falta un ítem

- **Sobre "de dónde salieron los precios"**: los valores de la semilla
  (`SEMILLA` en `precios.py`) son estimaciones de referencia que armé yo,
  no vienen de ninguna lista real ni de un proveedor -- son un punto de
  partida para no arrancar en $0, pensados para ajustarse a los precios
  reales de plaza. Esto ya estaba así desde el principio del proyecto, no
  cambió en esta entrega.
- **Bug crítico real, encontrado y corregido**: `sugerir_items()` armaba el
  presupuesto buscando cada ítem por nombre EXACTO contra la lista de
  precios, y si no encontraba ninguno de los nombres esperados, **omitía
  esa línea en silencio** -- sin ningún aviso. Si alguien borraba o
  renombraba un ítem crítico en la lista de precios (o el nombre no
  coincidía letra por letra, que es justo lo que pasó con "Tomacorriente
  doble" en la entrega anterior: en el mapeo decía sólo "Tomacorriente
  doble" pero el nombre real en la lista es "Tomacorriente doble (dos bocas
  en una caja)"), esa cantidad detectada en el plano desaparecía del
  presupuesto sin que nadie lo notara. Ahora `sugerir_items()` devuelve
  también una lista de avisos, y Presupuesto los muestra en un cartel bien
  visible arriba de todo ("Falta este ítem en la lista de precios: ...").
  Probado el caso exacto que se reportó: con la lista de precios real,
  ahora matchea bien y no hay avisos; con un ítem sacado a propósito de la
  lista, aparece el aviso en vez de desaparecer la línea.
- **El cómputo de "toma común" ahora prioriza "Tomacorriente doble"**: en
  una instalación real la boca que se extrae del plano como toma
  "genérica" casi siempre es una caja con tomacorriente doble, no uno
  simple -- se corrigió el mapeo para que tome ese precio primero,
  cayendo a "Tomacorriente común" sólo si "Tomacorriente doble" no
  existiera en la lista.
- **Descripción propia en térmica general, diferencial, protector y
  bornera de tierra**: nuevo campo en el panel de cada dispositivo del
  Tablero (no sólo en los circuitos), para casos como "Térmica general",
  "Diferencial principal 40A", "Puesta a tierra", que no están atados a un
  circuito. La guía de tapa del PDF usa esta descripción propia cuando
  existe, y si no, cae a la del circuito asignado (como antes).

## 0.23.5 — descripción de circuito en varios renglones y en negrita en la guía de tapa, térmicas más separadas ahí, y más variedad de tomas en la lista de precios

- **La descripción de circuito ya no se corta**: en vez de truncar a una
  sola línea corta, `_texto_multilinea()` la envuelve en hasta 3 renglones
  (con "…" si de verdad no entra en esas 3). Se ve en negrita y bastante más
  grande que antes -- es lo más importante de esta hoja, según se pidió.
- **Térmicas más separadas, sólo en la guía de tapa**: esta hoja no tiene
  cables que necesiten espacio para pasar por atrás (esa es la razón por la
  que se separaron en la hoja de conexionado), así que se le dio su propia
  escala horizontal, un 45% más ancha entre térmica y térmica, pensada
  puntualmente para darle lugar a la descripción. La hoja de conexionado no
  se tocó.
- **Más variedad en "Tomas"** en la lista de precios: tomacorriente doble,
  con tapa IP44 (exterior/húmedo), con protección para niños, USB + 220V, y
  trifásica industrial. Se revisó primero cómo Presupuesto matchea los
  nombres extraídos del plano contra la lista (por nombre exacto, ver
  `EQUIVALENCIAS` en `presupuesto.py`) antes de tocar nada — los 4 nombres
  de los que depende ese cómputo automático ("Tomacorriente común" y las 3
  "Toma especial - ...") quedaron intactos; lo nuevo son ítems adicionales
  para elegir a mano desde el combobox de Presupuesto, no reemplazos.
  Probado: el cómputo automático desde elementos del plano sigue resolviendo
  cantidades y precios correctamente después del agregado.

## 0.23.4 — conectores alineados y siempre borrables, descripción por circuito, y la guía de tapa emula el tablero real

- **Conector de fase alineado con el de neutro**: el cuerpo de cualquier
  conector ahora se apoya siempre a la misma altura (tomando la barra de
  arriba, neutro, como referencia) — antes cada uno colgaba de su propia
  barra, y como la de fase está más abajo, quedaban a distinta altura. La
  patita hacia la barra de fase es un poco más larga, pero el cuerpo queda
  parejo con el de neutro.
- **Causa real de "a veces no puedo borrar un conector", encontrada**: los
  cables se dibujaban (y eran clickeables) *después* que los conectores, y
  el área de clic de un cable es bastante ancha (14px, para que sea fácil
  tocarlo) y sigue todo su recorrido -- como un cable siempre arranca justo
  en el terminal de un conector, esa franja ancha tapaba el clic del
  conector exactamente en los casos en que más importa: cuando el conector
  ya tiene un cable enganchado, que es el uso normal. Se invirtió el orden:
  ahora los conectores (y los peines) se dibujan después de los cables, así
  su marca más chica y precisa gana el clic en ese punto exacto. El cable
  se sigue pudiendo clickear en cualquier otro tramo de su largo. Probado
  justo con ese caso (conector con un cable ya enganchado): antes no se
  podía seleccionar para borrar, ahora sí.
- **Descripción por circuito**: nuevo campo en Circuitos ("ej: Iluminación
  cocina"), debajo de la sección/protección de cada uno. Se guarda en el
  campo `notas` que ya existía en el modelo de datos pero nunca se mostraba
  en ningún lado.
- **La guía de tapa del PDF de Tablero ahora muestra esa descripción como
  etiqueta** debajo de cada térmica, y **tiene un enmarcado tipo gabinete
  real** (marco grueso con tornillos en las cuatro esquinas), para que la
  hoja se sienta como el tablero físico y no sólo un diagrama. Las
  etiquetas se acotan al ancho de su propia térmica para no superponerse
  con la del vecino cuando están pegadas (el caso más común).

## 0.23.3 — polaridad automática (nada de elegirla a mano), y "carga" bien entendida: el cuerpo siempre va arriba del peine

- **Bug real encontrado**: el selector de polaridad (fase/neutro) que se
  agregó en la entrega anterior nunca se conectó a nada -- el clic sobre la
  barra del peine ya traía la polaridad correcta (de qué barra se tocó),
  pero el código seguía leyendo el valor del selector en vez de usarla. Por
  eso un conector colocado sobre la barra de neutro salía igual marrón.
  **Se sacó el selector por completo**: la polaridad ahora es automática,
  la decide sola la barra que se toque (celeste sobre neutro, marrón sobre
  fase) -- ya no hay nada que elegir a mano para eso.
- **"Carga superior/lateral" estaba mal entendida**: no es de dónde se
  monta el cuerpo del conector (siempre arriba del peine, nunca al
  costado) -- es hacia dónde sale el cable real desde ese cuerpo: derecho
  hacia arriba (carga superior) o hacia el costado (carga lateral). Se
  corrigió la geometría en el editor y en el PDF: el cuerpo se apoya
  siempre en el mismo lugar sobre la barra; sólo cambia la patita que sale
  de él.
- Probado en navegador real y en el PDF: un conector tocando la barra de
  neutro sale celeste solo, sin elegir nada; uno con carga lateral y otro
  con carga superior sobre el mismo peine muestran ambos cuerpos montados
  igual, con la patita saliendo para el costado o para arriba según
  corresponda.

## 0.23.2 — la causa real de "fase/neutro/tierra siempre superpuestos" encontrada y corregida, y el conector vuelve a tener diseño de dispositivo

- **Causa real de la superposición, encontrada**: la separación en carriles
  que ya existía (0.22.0) excluía a propósito el primer y el último tramo de
  cada cable, para no mover los extremos de su terminal exacta. Pero el
  caso MÁS COMÚN de todos -- varios conductores (fase, neutro, tierra) que
  salen del MISMO punto de origen (una entrada de caño) hacia destinos
  distintos -- comparte justamente ESE primer tramo entero. Al excluirlo,
  ese caso nunca se separaba: quedaban exactamente uno encima del otro
  durante todo el tramo compartido, tal como se ve en el PDF adjuntado.
  Ahora se consideran todos los tramos, incluidos el primero y el último —
  se acepta que el extremo quede a un par de puntos del centro exacto de la
  terminal (el propio dibujo de la terminal ya lo disimula) a cambio de que
  los conductores dejen de superponerse. Corregido en el PDF y, de paso,
  agregado por primera vez del lado del editor web (`separarParalelos()` en
  JS, calcada de `_separar_paralelos()` en Python) -- no existía ahí
  todavía, aunque el editor a veces disimulaba mejor la superposición.
  Probado con el caso exacto (fase y neutro bajando del mismo caño de
  entrada al mismo dispositivo): antes, una encima de la otra; ahora, dos
  líneas paralelas separadas desde justo debajo del punto de entrada, en
  los dos lugares.
- **El conector vuelve a tener diseño de dispositivo**: la simplificación de
  la entrega anterior (un círculo liso) sacó de más — quedaba prolijo de a
  uno, pero abstracto, sin parecerse a una pieza real, y además varios
  cerca uno del otro se veían como un amontonamiento de puntitos. Se
  rediseñó como un cuerpo rectangular sólido con un tornillo simple en el
  medio (como una bornera real), manteniendo la corrección de fondo (nada
  de relleno transparente ni capas superpuestas que dejen ver un nodo de
  más) pero sin perder el aspecto de pieza reconocible.

## 0.23.1 — selectores en vez de escribir a mano, borrado por selección + Delete, conector rediseñado limpio, y saltos de cruce más chicos

- **Elegir fase/neutro y carga superior/lateral ahora es con dos selectores**
  al lado del botón "Conector de peine" — no hay que escribir nada a mano.
  Quedan visibles mientras la herramienta está activa, y se pueden cambiar
  entre un conector y el siguiente sin reabrir nada.
- **Borrar una conexión (peine o conector) es: clic para seleccionarla,
  Delete para borrarla** — sacado el cartel de confirmación en el momento,
  mismo criterio que ya se usaba para los cables. La conexión seleccionada
  se resalta (el peine con un borde de color; el conector con un anillo).
- **Causa del "nodo de más" en el conector, encontrada y corregida**: el
  diseño anterior dibujaba un círculo sólido *debajo* del ícono, y como el
  cuerpo del ícono tenía relleno semi-transparente (para que se note el
  color sin tapar del todo), ese círculo se veía transparentar por encima,
  pareciendo un nodo extra flotando sobre el dibujo. El conector se rediseñó
  completo: un solo círculo sólido del color de la polaridad con una ranura
  blanca simple — sin capas superpuestas, sin partes de más.
- **Saltos de cruce más chicos** (de 5pt a 2.6pt de radio, en el editor y en
  el PDF): antes, cuando varios cables corrían casi pegados y cada uno
  cruzaba la misma línea, sus saltos se amontonaban en una mancha borrosa.
  Con saltos más chicos, cada cruce queda limpio y distinguible aunque haya
  varios juntos. Se revisó a fondo la lógica de qué cable salta y cuál seguí
  derecho (`_calcular_saltos`/`calcularSaltos`): sólo uno de los dos salta
  por cada cruce puntual, nunca los dos a la vez — lo que se veía "feo" era
  el tamaño acumulado de varios saltos reales y correctos, muy juntos; con
  el tamaño reducido, ese amontonamiento deja de notarse.
- Probado en navegador real: conector creado con los selectores (sin ningún
  `prompt()`), clic + Delete lo borra sin cartel, diseño limpio confirmado
  visualmente. Reproducido un cruce con 5 cables paralelos sobre la misma
  línea (como en la foto): cada uno muestra su propio salto, chico y nítido,
  sin amontonarse.

## 0.23.0 — conectores de peine rediseñados de cero (libres, con cable a mano), y más espacio entre térmicas

- **Se eliminó el sistema de "conector al piso siguiente" (puente)** por
  completo -- `crear_puente`, su endpoint, su dibujo, todo. En su lugar,
  **conector de peine** (`conectorPeine`): se apoya sobre un peine, en la
  posición exacta donde el usuario haga clic a lo largo de la barra (ya no
  se centra solo), de dos tipos según de dónde entra el cable real (foto de
  referencia del usuario): **superior** (patita hacia arriba) o **lateral**
  (patita hacia el costado). El color del cuerpo ya sigue siendo el de la
  polaridad (marrón fase / celeste neutro).
- **El conector queda como un extremo más de la herramienta de "Cable"
  normal**: desde su patita se traza a mano el conductor hacia donde haga
  falta (otro conector en otro peine, una térmica, un caño...), con la
  misma libertad de ruteo (puntos intermedios incluidos) que cualquier otro
  cable -- ya no es un trazo recto y fijo calculado solo por la app.
- **Más espacio entre térmicas**: el margen a los costados de cada una casi
  se duplicó (de ~9% a ~16% de la celda por lado), tanto en el editor como
  en el PDF, para que el hueco por donde se ve pasar un cable sea más claro.
- **Importante — no hay migración automática**: un tablero que ya tuviera
  conectores del sistema viejo los va a mostrar rotos (el nuevo renderizador
  espera campos distintos). Hay que borrarlos y volver a colocarlos con el
  conector nuevo; los peines, térmicas y demás cableado no se ven afectados.
- Probado en navegador real: conector superior de fase colocado fuera del
  centro del peine (en el punto exacto donde se clickeó), conector lateral
  de neutro en otro piso, y un cable trazado a mano desde un conector hacia
  el peine con la herramienta genérica -- confirmado también en el PDF
  generado con el mismo tablero, coherente con lo que se ve en el editor.

## 0.22.1 — los conectores al piso siguiente ahora se anclan de verdad a los peines, coloreados por polaridad, y las térmicas se separan para ver por dónde corren los cables

- **Causa del "desconectado"**: el conector (puente) arrancaba desde un punto
  flotante debajo de la fila de térmicas del piso de origen, y su posición
  X no necesariamente coincidía con el ancho real del peine de destino —
  visualmente parecía salir de la nada y terminar en la nada.
- **`crear_puente` rediseñado** (`app/tablero.py`): ahora exige un peine ya
  puesto en el piso de origen y otro en el de destino (ya no acepta una
  posición libre). La posición se calcula sola, del centro de cada peine.
  Si falta alguno, avisa en vez de dejar algo mal puesto.
- **Geometría corregida** (`web/tablero.html` y `app/pdf_tablero.py`): el
  conector arranca exactamente sobre la barra del peine de origen y termina
  exactamente sobre la del peine de destino, atravesando en el medio la fila
  de térmicas del piso de origen.
- **"Pasa por atrás" gratis**: la app ya dibuja las térmicas encima del
  cableado (para taparlo a propósito); al extender el conector para que
  cruce toda la fila, automáticamente queda tapado detrás de cada térmica y
  reaparece en los huecos, sin necesitar lógica nueva.
- **Huecos reales entre térmicas**: se agregó un margen visible a los
  costados de cada térmica (antes ocupaban la celda entera, pegadas unas a
  otras) tanto en el editor como en el PDF, para que el efecto anterior
  tenga dónde asomar.
- **Color por polaridad**: el cuerpo del conector (antes blanco con borde
  oscuro) ahora se pinta con el color de fase (marrón) o neutro (celeste).
  Cuando fase y neutro bajan entre el mismo par de peines quedaban
  exactamente superpuestas la mayor parte del recorrido — se separaron unos
  px al costado para poder distinguirlas.
- El nodo/terminal para conectar un cable ya existía (`data-con-click` +
  `lado`/`polaridad`); con la geometría corregida ahora queda en el lugar
  correcto para engancharle un cable hacia otro conector.
- Probado en navegador real y en el PDF con el mismo tablero (peines de
  distinto ancho en cada piso): ambos extremos quedan pegados a su peine,
  fase y neutro se distinguen, y el cable se ve pasar por el hueco entre las
  dos térmicas del medio. Sin regresiones en el cableado de la bornera PAT
  ni en la separación de cables paralelos ya arregladas antes.

## 0.22.0 — cables del tablero separados en carriles, y vista previa de PDF en Tablero, Presupuesto y Routeo

- **Cables que comparten corredor ya no se dibujan encima uno del otro**:
  cuando varios cables corren un tramo por el mismo lugar (misma coordenada,
  rangos que se superponen — típico en el corredor entre pisos, donde el
  orden de entrada de los circuitos no coincide con el orden de las
  térmicas), `_separar_paralelos()` los corre en paralelo en carriles
  parejos. Sólo desplaza los tramos "del medio" de cada cable, nunca el
  primero ni el último, así los extremos siguen enganchando exacto en cada
  terminal. Probado reproduciendo el patrón real (8 circuitos con orden de
  entrada distinto al de las térmicas): antes era una maraña ilegible, ahora
  cada cable se puede seguir individualmente. No afecta el caso simple (sin
  cables superpuestos), que se ve exactamente igual que antes.
- **Vista previa antes de descargar, en los tres lugares donde se genera un
  PDF** (Tablero, Presupuesto, Routeo): se arma el PDF y se muestra en un
  visor adentro de la app; recién ahí aparece "Descargar…", que usa el
  selector nativo de ubicación del sistema operativo cuando el navegador lo
  soporta (Chrome/Edge), y si no, la descarga común. Tablero y Presupuesto
  ahora piden el PDF al servidor como archivo en memoria en vez de navegar
  directo a la URL; Routeo arma el PDF en el navegador (como ya hacía) y
  ahora lo muestra antes de guardarlo, sin pedir nada al servidor. Probado
  en los tres módulos: el visor abre con el PDF correcto y el cierre limpia
  la memoria usada.
- Quedó anotado en el README, como backlog, el pedido de un PDF consolidado
  de entrega (routeo + tablero + materiales, con lugar para módulos futuros
  como automatizaciones) para encarar más adelante.

## 0.21.3 — la causa real del PDF de tablero cortado, y una red de seguridad para que no vuelva a pasar

- **Causa real encontrada**: no era (sólo) la bornera. Cuando el usuario
  endereza un cable a mano en el editor interactivo (arrastra un punto
  intermedio para esquivar otro cable), ese punto se guarda en los píxeles
  de ESE editor — que usa una escala mucho más grande (`celda=64`) pensada
  para clickear cómodo con el mouse. El generador del PDF usaba esos mismos
  números tal cual, pero su propia escala es `celda=34`. Resultado: cualquier
  cable con un tramo enderezado a mano terminaba dibujado muy lejos de donde
  correspondía — a veces bien afuera de la hoja, cortando todo lo que
  estuviera después. Esto explica por qué el arreglo anterior (la bornera)
  no alcanzó: era un bug real, pero no el único, y no el más frecuente en un
  tablero con varios cables que se cruzan y hay que acomodar a mano.
- **`_ruta_a_pdf()`**: convierte cada punto de ruta manual de píxeles del
  editor a la posición lógica que representa (boca en X; piso + fracción en
  Y) y lo reconstruye con la geometría propia de esta hoja. Probado con un
  cable enderezado a mitad de la fila del General: en el PDF aparece
  exactamente ahí, no desplazado.
- **Red de seguridad, además de la corrección**: after de armar la hoja,
  ahora se mide dónde termina *todo* lo que realmente se va a dibujar
  (dispositivos, peines, puentes, cables con sus rutas ya convertidas) y si
  algo cae más allá de lo pensado, la hoja se agranda para que entre —
  nunca más se corta contenido, así aparezca en el futuro algún caso no
  contemplado. Probado a propósito con un punto absurdo (5000,5000): la
  hoja creció para cubrirlo en vez de cortarlo. En el caso normal (sin
  ningún error) esto no agranda nada — se probó que la hoja da exactamente
  el mismo tamaño que antes.
- Nota: la "guía de tapa" (página 2) comparte la geometría con la de
  conexionado, así que si algún cable puntual estira la hoja de
  conexionado, la de tapa queda con el mismo tamaño (un poco más de margen
  en blanco alrededor de las térmicas) — no afecta la corrección, sólo el
  ajuste fino en ese caso puntual.

## 0.21.2 — PDF de tablero cortado por el borde (bornera PAT), "Volver" en Tablero, y combobox de precios en Presupuesto

- **Bug encontrado y corregido: el PDF de conexionado del tablero salía
  cortado por la derecha** cuando había una bornera de tierra (PAT) con
  cables en más de un terminal. Causa: `_punto_endpoint()` en
  `pdf_tablero.py` calculaba la posición de cada terminal de la bornera
  igual que en una térmica común (el número de terminal se sumaba como
  desplazamiento *horizontal*, una celda entera por terminal) — pero la
  bornera dibuja sus 6 terminales apilados *verticalmente*, todos en el
  mismo X (ver `_bornera()`). El resultado: un cable al 2º, 3º... terminal
  de la PAT se calculaba varias celdas a la derecha de donde está el
  dispositivo, y como el ancho de la hoja (`_Geom.ancho`) no contempla ese
  corrimiento, el tablero entero quedaba cortado a partir de ahí. Se
  corrigió replicando la geometría real de la bornera (mismo X, Y por fila).
  Reproducido con un tablero de prueba con la misma composición que el
  reportado (general + diferencial + protector DPS + PAT, TUG1/TUG2/IUG1/IUG2,
  TUE1-4, cables a los 6 terminales de la PAT) y confirmado que el PDF sale
  completo, sin cortes.
- **"Volver" en Tablero** llevaba a Circuitos; ahora va al listado de obras,
  igual que en Revisor y Circuitos.
- **Combobox de precios en Presupuesto**: en "Extras y adicionales" ahora se
  puede elegir un ítem ya cargado en la lista de precios (agrupado por
  categoría, con el precio vigente visible antes de elegir) en vez de
  tipearlo de cero. Se agrega con nombre, unidad y precio ya completos. El
  botón "+ Personalizado" se mantiene para lo que no está en la lista.

## 0.21.1 — retornos que comparten caño ya se distinguen por color, hojas de tomas con conductores reales, y más resolución para digital

- **Retornos múltiples por el mismo caño, ahora distinguibles**: si dos o
  más luces con retorno simple (o dos o más combinadas) comparten un caño,
  antes se dibujaban del mismo color y eran indistinguibles a simple vista.
  Ahora cada una toma un tono de una escala: retorno simple blanco → gris
  medio → gris oscuro; combinada amarillo → mostaza → ocre oscuro (hasta 3
  tonos, alcanza para cualquier instalación normal; de haber una 4ª se
  repite el tono más oscuro). El orden lo da la letra de la luz dentro del
  circuito, así que la primera luz agregada mantiene siempre el tono
  original (blanco/amarillo). Fase, neutro y tierra no cambian. Probado:
  luz A → blanco (`#e9e9e9`), luz B → gris medio (`#aeaeae`).
- **Las hojas de circuito de tomas/especiales ahora muestran sus
  conductores reales** (fase/neutro/tierra) dentro del caño, igual que ya
  pasaba en la hoja general y en las de iluminación — antes esto sólo se
  activaba para circuitos de iluminación (`detailed:true` estaba
  condicionado a `c.kind==="iluminacion"`, sin razón para excluir al resto).
  Probado renderizando la hoja de un circuito de tomas: se ven los 3
  conductores de colores dentro del caño.
- **Más resolución, pensado para digital** (esta app es para pantalla, no
  para imprimir): la imagen base del plano pasa de calibrarse a `zoom=2` a
  `zoom=3` (más nítida al hacer zoom, tanto en el editor como en el PDF);
  las hojas del PDF suben de `res:3200/4800` a `res:6000` parejo en todas, y
  la hoja general pasa de JPEG a PNG (sin pérdida) igual que ya hacían las
  hojas detalladas — evita el "corrimiento" de color de JPEG en líneas
  finas al hacer zoom. De paso se corrigió que el `zoom=2` de la URL del
  plano estaba hardcodeado por separado en `server.py` y en
  `canalizacion.py` (`ZOOM_PLANO`); ahora `server.py` lee el valor de
  `canalizacion.py`, una sola fuente de verdad.
- Se agregaron `planCanvas`, `wireHex` y `conduitConductors` a
  `window.canalizaDebug` (sólo lectura), para poder inspeccionar el
  render exacto que va a un PDF sin tener que generar el PDF completo.

## 0.21.0 — Routeo: ortogonalidad real, reasignación de circuito con sync a Circuitos, autoguardado al servidor, y limpieza de la UI integrada

Se renombra el módulo a **Routeo** en todo lo visible (título, tarjeta en
`index.html`, encabezado del PDF). Internamente sigue siendo
`canalizacion.py` / `obra.canalizacion` / `/canaliza.html` — cambiar eso
implicaría tocar rutas, `almacen.py` y el contrato de `obra.json` sin
ningún beneficio para el usuario, así que se dejó igual a propósito.

- **Ortogonalidad real, incluso con cajas fuera de grilla**: `orthoPoint()`
  calculaba el punto exacto respecto al anterior pero después
  `snapToGrid()` redondeaba los dos ejes, así que un tramo que arrancaba de
  una caja extraída (casi nunca cae justo en la grilla) terminaba en
  diagonal. Ahora el eje que coincide con el punto anterior queda siempre
  exacto; sólo el otro eje se redondea. Además, al cerrar un tramo contra
  una caja que no queda alineada con el último punto, se inserta solo el
  codo a 90° que hace falta (`draftHopTo()`), tanto al confirmar el clic
  como en la vista previa mientras se mueve el mouse. Probado con dos cajas
  fuera de grilla (T1 y T2, separadas 40×40 px) conectadas directo y con un
  punto intermedio a mano alzada: todos los tramos dieron ortogonales, con
  los extremos exactos sobre las cajas.
- **Las cajas extraídas ya no se pueden arrastrar** — su posición es la
  real relevada en el módulo Plano, no un punto libre para reacomodar.
- **Reasignar el circuito de una caja, con sync real a Circuitos**: el panel
  de cada caja tiene ahora un selector de "Circuito". Al cambiarlo, el color
  del borde, la etiqueta y el resaltado se actualizan en vivo (se resuelven
  contra `S.circuits` por `circuitId`, no quedan horneados en el nodo). Al
  guardar (manual o automático), el servidor aplica la reasignación sobre
  `obra.circuitos` — saca el elemento del circuito viejo y lo agrega al
  nuevo — así el módulo de Circuitos refleja el cambio. Probado de punta a
  punta: reasignada una llave sin circuito a IUG1 en Routeo, confirmado por
  API que `obra.circuitos["IUG1"].elementos` la incluye, sin tocar el botón
  Guardar (llegó por el autoguardado).
- **Autoguardado real contra el servidor**: Canaliza ya autoguardaba en
  `localStorage` del navegador en cada cambio (debounce de 900ms); ahora ese
  mismo disparador también guarda en la obra (`window.fyGuardarAuto`, un
  único hook agregado a `doAutosave()`, sin tocar su lógica de guardado
  local). El guardado manual pasa a llamarse simplemente "Guardar".
- **Botón "Reiniciar"**: borra todos los tramos y el cableado ya trazados;
  las cajas y los circuitos quedan igual. Probado: de 1 tramo pasa a 0, las
  4 cajas y los 2 circuitos no se tocan.
- **Botón "Volver"**, mismo criterio que el resto de los módulos (vuelve a
  `/`).
- **Resaltado de cajas por circuito activo mientras se rutea**: con la
  herramienta "Tramo de caño" activa, las cajas que pertenecen al circuito
  seleccionado se destacan con un halo de su color. Verificado por muestreo
  de píxeles: el halo da exactamente el color hex del circuito activo, y no
  aparece en cajas de otro circuito.
- **Limpieza de la UI integrada**: se ocultan "Abrir plano", "Guardar
  proyecto", "Abrir proyecto", "Nuevo proyecto" y "Calibrar" (top y en la
  lista de herramientas) — el plano, los circuitos y la escala los maneja el
  resto de la app. Si todavía no hay plano extraído, el cartel vacío ya no
  ofrece subir uno a mano: indica que hay que extraerlo en el módulo Plano.
  Si la escala no está calibrada, el chip existente ("Sin escala") queda
  como única leyenda — no se agregó nada nuevo ahí, sólo se sacó el botón
  para recalibrar a mano.
- Se agregó `window.canalizaDebug` (sólo lectura: `S`, `activeCi`, `ciById`,
  `nodeById`, `findNode`) para poder inspeccionar el estado desde la consola
  del navegador sin exportar todo el proyecto — útil para depurar a futuro.

## 0.20.4 — circuitos también se completan en proyectos guardados, mismo color que en Circuitos, y color por circuito en cada caja

- Mismo patrón de bug que las cajas en la 0.20.3: si el proyecto guardado
  tenía `circuits: []` (de antes de existir `circuitos_para_canaliza`),
  quedaba así para siempre y bloqueaba "Tramo de caño" con *"Creá al menos
  un circuito antes de dibujar"*. `mergeCircuitosExtraidos()` ahora completa
  los circuitos faltantes en cada apertura, igual que ya se hacía con las
  cajas — sin pisar uno que el usuario ya haya editado acá.
- La paleta de colores de `circuitos_para_canaliza()` era propia y no
  coincidía con la de Circuitos. Ahora usa exactamente `COLORES` de
  `circuitos.html`, mismo índice por posición — mismo color en los dos
  módulos.
- Cada caja extraída ahora lleva `ringColor` con el color de su circuito
  (calculado igual que `colorDe()`), y el borde de la caja se pinta con ese
  color en vez del negro por defecto — un solo `if` aditivo en el dibujo del
  nodo, sin tocar nada más de Canaliza; si una caja no tiene circuito
  asignado, se ve como antes.
- Probado en navegador real reproduciendo ambos bugs juntos (circuitos vacíos
  + plano ok): confirmado que ya no aparece la alerta al trazar y que las
  cajas se ven con el color de su circuito.

## 0.20.3 — las cajas seguían sin aparecer si ya había un proyecto guardado, y ahora se ve el circuito de cada una sin hacer clic

- El self-heal de la 0.20.2 completaba plano y escala en un proyecto ya
  guardado, pero **no** las cajas — si ese guardado venía de antes de la
  0.20.1 (sin `nodes`), seguían sin aparecer. Ahora `mergeCajasExtraidas()`
  agrega, cada vez que se abre el módulo, las cajas ya extraídas que todavía
  no estén en el proyecto guardado (por id) — nunca pisa ni borra una que ya
  esté, así que lo que el usuario ya movió, editó o borró a propósito queda
  intacto. Se probó reproduciendo exactamente el caso (proyecto guardado con
  plano y circuitos ok pero 0 cajas) y confirmando en navegador real que las
  4 cajas de la obra de prueba aparecen solas.
- El circuito de cada caja ahora se ve directo en la etiqueta sobre el plano
  (ej. `A·IUG1`, `T1·TUG1`), no sólo al hacer clic — la nota interna
  (`Circuito: ...`) se mantiene además, para cuando se abre el panel de
  edición de la caja.

## 0.20.2 — el plano no se abría si ya había un proyecto de Canaliza guardado sin él

- **Causa**: el arranque de la 0.20.1 (plano/circuitos/cajas traídos solos)
  sólo corre la primera vez que se abre el módulo, cuando todavía no hay
  `canalizacion` guardada en la obra. Si en algún momento anterior se guardó
  un proyecto sin plano (por ejemplo, guardando antes de que este puente
  supiera pasarlo), esa foto vieja queda fija para siempre y tapa cualquier
  mejora posterior — el plano nunca vuelve a aparecer aunque la obra sí lo
  tenga.
- **Arreglo**: al cargar un proyecto ya guardado, si le falta el plano
  (`baseSrc`) o la escala (`pxPerM`) y la obra sí los tiene, se completan
  esos dos campos antes de importar. No se toca nada más del proyecto
  guardado — nodos, tramos y cableado ya hechos quedan intactos.
- Reproducido a propósito (un proyecto guardado con `baseSrc: null`) y
  confirmado en navegador real que ahora sí carga el plano y la escala.

## 0.20.1 — las cajas ya extraídas vuelven a aparecer solas en Canaliza

- **Corrección de fondo, quedó pendiente en el 0.20.0**: al pasar a guardar el
  proyecto tal cual lo produce `buildProjectData()` de Canaliza, se llevó
  puesta sin querer la traducción de elementos a `nodes` que sí existía en el
  0.19.1 (con el modelo de datos propio, ya descartado). Resultado: primera
  vez que se abría Canaliza para una obra, sólo llegaban el plano y los
  circuitos — las cajas (artefactos, tomas, llaves) ya extraídas y asignadas
  a un circuito en el resto de la app había que volver a marcarlas a mano.
- **`nodos_para_canaliza(obra)`** en `app/canalizacion.py`: traduce cada
  elemento ya extraído a un nodo de Canaliza (caja octogonal para artefactos,
  rectangular para tomas y llaves), en la posición real sobre el mismo
  `plano.png?zoom=2` que Canaliza usa de fondo (`posicionPdfPt * zoom`), con
  la letra ya asignada en el plano como etiqueta cuando existe, y una nota
  con el circuito al que ya pertenece (buscado por pertenencia en
  `circuito.elementos`, que es la fuente real — el campo `circuitoId` del
  elemento es legado, se conserva por la regla de no borrar claves pero no lo
  actualiza nada). Sólo se usa la primera vez que se abre el módulo, igual
  que `circuitos_para_canaliza()` — después manda el proyecto guardado.
- **`pxpermetro_para_canaliza(obra)`**: de paso, la escala que ya calibró el
  extractor (`plano.escala.ptPorMetro`) se manda convertida a `pxPerM`, así
  tampoco hace falta volver a calibrar a mano marcando dos puntos.
- `GET /api/obras/{id}/canalizacion` devuelve ahora también `nodos` y
  `pxPerM`. El puente en `canaliza.html` (el script chico, no el de Canaliza)
  los suma a lo que ya cargaba de circuitos y plano.
- Probado de punta a punta con un navegador real (Puppeteer): servidor real,
  obra de prueba con plano + 4 elementos + 2 circuitos, `canaliza.html`
  abierto tal cual lo abriría el usuario — las 4 cajas aparecen en su lugar
  exacto sobre el plano, con la escala ya calibrada (56.7 px/m) y sin haber
  tocado nada a mano.

## 0.20.0 — Canaliza integrada tal cual, no reimplementada

- **Cambio de estrategia, a pedido explícito**: el intento anterior
  reimplementaba la app de referencia y perdía todas sus funcionalidades
  (DRC, cableado de iluminación, PDF multi-hoja). Ahora se integra la app
  real (`canaliza.html`, ~2770 líneas) tal cual, con sólo tres agregados
  puntuales que se pidieron hacer en la otra conversación donde se armó:
  `window.canalizaExportar`/`window.canalizaImportar` expuestos desde el
  cierre del script, y una bandera para saltear el diálogo de autoguardado
  del navegador cuando corre integrada. El resto del archivo no se tocó.
- **`app/canalizacion.py` rehecho** de un modelo de datos propio (nodos,
  tramos) a algo mucho más simple: leer y guardar el proyecto tal cual lo
  produce la propia `buildProjectData()` de Canaliza, sin capa de traducción
  intermedia que mantener sincronizada.
- Los circuitos ya definidos en el módulo de Circuitos se traducen una sola
  vez al formato que espera Canaliza (`circuitos_para_canaliza()`) y viajan
  como punto de partida la primera vez que se abre el módulo — después, el
  proyecto guardado manda.
- Dos endpoints nuevos, reemplazando a los seis anteriores:
  `GET /api/obras/{id}/canalizacion` (proyecto guardado, o si es la primera
  vez, circuitos traducidos + URL del plano) y
  `POST /api/obras/{id}/canalizacion` (guarda el proyecto tal cual).
- Botón "Guardar en la obra" agregado a la barra de Canaliza, junto a los
  suyos propios de guardar/abrir como archivo — no reemplaza esos, se suma.
- Probado contra el servidor real: primera carga con circuitos traducidos
  correctamente (IUG→iluminación, TUG→tomas, con sección real), guardado y
  relectura del proyecto intactos.

## 0.19.1 — las cajas ya extraídas aparecen solas en canalización

- **Corrección de fondo**: las cajas octogonales y rectangulares ya se
  extraen del plano y se asignan a un circuito en el módulo de Circuitos —
  no tenía sentido pedir que se recrearan acá. Ahora aparecen solas (con
  línea punteada, del color de su circuito) apenas se abre canalización, y
  sirven directo como extremo de un tramo sin agregar nada.
- Sólo se agrega a mano lo que de verdad no viene de la extracción: el
  tablero, por dónde entra la acometida (medidor), la jabalina, y cajas de
  paso (octogonales o de inspección) para rutear entre cajas ya existentes.
- Un elemento extraído no se puede borrar desde este módulo (avisa y manda a
  Circuitos, que es donde corresponde editarlo).
- Se encontró y corrigió un bug propio de precedencia de operadores en el
  panel lateral: el aviso de "todavía no agregaste nada a mano" no se
  mostraba nunca, porque el `||` de reserva quedaba pegado a toda la
  concatenación en vez de sólo al resultado de la lista.
- Probado contra el servidor real: un elemento simulado como "ya extraído y
  asignado a un circuito" quedó disponible para trazar un tramo sin haber
  sido agregado manualmente.

## 0.19.0 — primera etapa de canalización

- **Nuevo módulo: Canalización** (`web/canaliza.html`, `app/canalizacion.py`).
  Primera etapa, apoyada en la app de referencia que se pasó como base
  (~2700 líneas) pero deliberadamente acotada: colocar cajas (tablero,
  octogonal, rectangular, medidor, jabalina, de inspección) sobre el mismo
  plano ya calibrado del resto de la app, y trazar tramos de caño —siempre
  ortogonales— entre dos cajas, asignados a un circuito ya existente. El
  diámetro de caño se sugiere solo, con la misma tabla de llenado real de la
  app de referencia (validada caso por caso: 3 conductores de 1,5mm² dan
  5/8", 6 dan 7/8", una mezcla de 2,5mm²+16mm² da 3/4").
  Borrar una caja borra en cascada los tramos que quedarían con una sola
  punta — probado contra el servidor real.
- **Pendiente, con honestidad**: el DRC completo (cruces de caños, cajas con
  más conductores de los que soportan, protecciones fuera de norma), el
  sistema de cableado de iluminación (retornos por conductor), el cálculo de
  longitudes reales, y la exportación a PDF con las hojas de cableado
  detallado y cómputo de materiales — son módulos grandes en sí mismos, y
  siguiendo la misma disciplina de todo este proyecto, se entregan probados
  en una próxima etapa en vez de apurados ahora.

## 0.18.1 — arreglado el recorte del PDF del tablero

- **Encontrado con el PDF real que mandaste, no con el texto extraído** (que
  se lee en cualquier orden y no muestra el problema real): el ancho de la
  hoja se calculaba con la cantidad nominal de bocas del tablero
  (`bocasPorPiso`), no con lo que hay de verdad colocado. Si un dispositivo
  quedaba más allá de ese ancho nominal —por ejemplo si el tablero se achicó
  después de ubicar térmicas—, la hoja lo recortaba justo en el borde.
- Ahora el ancho se calcula sobre el máximo real entre lo nominal y la
  posición + polos de cada dispositivo colocado. Reproducido el escenario
  exacto (bocasPorPiso=6 con una bornera en la posición 8) y confirmado con
  el render: antes se cortaba, ahora la hoja crece y se ve completa.

## 0.18.0 — el PDF del tablero rehecho con detalle real, y ajustes finos

- **El PDF del tablero, rehecho de fondo**: la entrega anterior lo simplificó
  demasiado (rectángulos lisos), justo lo contrario de lo pedido. Ahora usa
  el mismo lenguaje visual que el editor interactivo — tornillos con cruz o
  más, ventana con el nombre del circuito, teclas de la térmica, Δ y botón de
  test del diferencial, display del protector, terminales de la bornera — y
  el mismo ruteo de cables en escuadra con salto donde dos se cruzan (antes
  eran líneas rectas cruzándose sin ningún criterio).
- En el camino se encontró un bug de verdad: `insert_textbox` no dibuja nada
  si la caja es más angosta que el texto (fallaba en silencio), por eso las
  ventanas de las térmicas se veían vacías en el primer intento. Se cambió
  por un centrado manual con `insert_text` que siempre dibuja.
- **Marca de agua, otra vez ajustada**: 4,5% quedó casi invisible ahora que
  la opacidad se aplica de verdad (antes el bug del parámetro la dejaba
  siempre opaca, así que un número bajo no se notaba). 12% es un punto medio
  genuinamente visible. Además, en vez de "piso" o "techo" —que se rompían
  cada vez que cambiaba el default—, ahora se detecta si el valor guardado es
  uno de mis propios defaults de una entrega anterior (8, 14, 16, 4.5) y en
  ese caso se reemplaza por el vigente; un valor puesto a mano por el usuario
  se respeta tal cual.
- **Agregar ítem a la lista de precios, corregido**: si no había una
  categoría elegida en el filtro (que por defecto dice "Todas"), el ítem
  nuevo caía en "Otros" sin avisar — parecía que el botón no hacía nada.
  Ahora pregunta la categoría si hace falta, y confirma con un aviso.

## 0.17.0 — exportar el tablero a PDF, y el bug de fondo de la marca de agua

- **Exportar el tablero a PDF**, con dos páginas: una de conexionado a color
  con fondo claro (térmicas, peines, conectores y cables — estos últimos en
  línea recta, no en escuadra con saltos: es una versión simplificada del
  editor interactivo, no una réplica pixel a pixel), y otra de "tapa puesta"
  con sólo las térmicas y su etiqueta (circuito + corriente), pensada para
  imprimir y pegar como guía adentro del tablero real.
- **Encontrado el motivo real de que la marca de agua nunca se viera
  translúcida de verdad, en ninguna entrega anterior**: en esta versión de
  PyMuPDF, el parámetro `alpha=` de `insert_image()` no es opacidad — es sólo
  un flag de rendimiento sobre si la imagen tiene o no canal alfa propio.
  Nunca hizo nada. La única forma real de bajar la opacidad es armar un
  graphics state con `/ca` y aplicarlo a mano en el content stream, que es
  justo lo que hacía el PDF de referencia. Ahora se hace así, y quedó
  confirmado a ojo: antes se veía opaca a pesar del alpha bajo, ahora se ve
  genuinamente tenue.
- Marca de agua más grande (80% del ancho) y más translúcida (4,5%) que la
  referencia, a pedido explícito — con techo incondicional, para que ningún
  valor guardado de una entrega anterior la haga más visible de lo pedido.
- **Corregida la leyenda del pie del presupuesto**: tenía un salto de línea
  a mano justo en medio de la oración ("...por inflación u" / "otras..."),
  heredado sin querer del PDF de referencia. Ahora es un solo texto corrido
  que ajusta de línea donde corresponde por ancho, no a mitad de una idea.
- **La migración de precios ahora también corrige, no sólo agrega**: si un
  ítem ya existía pero con precio en $0 (de una semilla vieja, antes de
  cargar precios reales), se actualiza al precio de la semilla actual. Antes
  sólo se agregaban los que faltaban del todo, así que un ítem ya presente
  con $0 se veía igual de "no cargado" aunque el código ya lo tuviera resuelto.

## 0.16.0 — nodos alineados a los pines, formato de presupuesto fijo, tomas corregidas

- **Nodo y cable ahora coinciden exacto**: el nodo se dibujaba fuera del
  cuerpo de la térmica, y el cable conectaba al borde de la fila, no al
  tornillo real dibujado adentro del esquema. Los dos puntos quedaban a unos
  24px de distancia entre sí. Se unificó todo en una sola constante
  (`MARGEN_PIN`), verificado con Node: nodo y punto de conexión dan
  exactamente las mismas coordenadas.
- **La grilla ahora sí es submúltiplo de la distancia entre pines**: había un
  padding de ±2/4px en el ancho de cada térmica que rompía la alineación con
  la grilla. Se sacó ese padding (el margen visual entre térmicas se pasó
  adentro del propio dibujo SVG, sin tocar la posición de los tornillos) y
  ahora la distancia entre pines da exactamente 64px — múltiplo limpio de la
  grilla por defecto (8px).
- **Entradas de circuito intercaladas**: cada entrada de caño alterna su
  altura con la siguiente, simulando cómo entran los caños en la realidad
  (unos más adelante, otros más atrás) tal como en la foto de referencia.
- **Formato de presupuesto fijo**, leído directamente del PDF de referencia
  con PyMuPDF (no estimado a ojo desde una captura): marca de agua al 7% de
  opacidad, cuadrada, centrada exacta (antes estaba mucho más grande y más
  visible que lo pedido); logo de 46×46pt arriba a la derecha. Se agrupan los
  ítems por categoría (Puntos, Tomas, Iluminación, Tableros, Puesta a tierra)
  con tabla propia por categoría, subtotal y TOTAL GENERAL, igual que la
  referencia. Probado generando el mismo presupuesto de ejemplo: el total dio
  exactamente $2.709.156,00, idéntico al original.
- **Arreglado el motivo real de "faltan los tomas"**: `toma_heladera` y
  `toma_lavarropas` son subtipos que el extractor sí genera, pero
  `presupuesto.py` no los reconocía y cualquier toma de ese tipo caía
  silenciosamente en "Tomacorriente común" en vez de su categoría especial.

## 0.15.0 — el cableado se robaba los clics, y precios que se autocompletan

- **Arreglado: rutear un cable cerca de otro seleccionaba el otro** en vez de
  colocar el punto donde correspondía. La causa: el trazo invisible de 14px
  que agregué para poder seleccionar y borrar un cable quedaba clicable
  siempre, incluso mientras se estaba trazando uno nuevo. Ahora sólo
  intercepta el clic en modo "mover" (sin ninguna herramienta de cableado
  activa) — mientras se rutea, todo cable existente deja pasar el clic de
  largo.
- **Precios reales cargados en la semilla**, con los valores de la lista que
  se pasó: Punto de luz $19.363, Punto combinado $20.842, Tomacorriente común
  $24.525, las tres tomas especiales a $34.525, Boca combinada $24.525,
  artefactos a $29.715, los cuatro tableros, PAT $162.585, conexión al medidor
  $200.000, Flotante a 220V $100.000. "Flotante a 24V" quedó en $0 porque no
  se veía su valor en la imagen que se pasó — hay que cargarlo a mano.
- **Migración automática de la lista de precios**: la misma clase de problema
  que ya había aparecido con la marca de agua — un archivo ya guardado en
  disco de antes de agregar un ítem nuevo a la semilla nunca lo recibía solo.
  Ahora, al leer la lista, se completan automáticamente los ítems que falten
  respecto de la semilla actual, sin tocar ni reordenar los que ya estaban
  (incluidos los precios que se hubieran editado a mano). Probado: un archivo
  con sólo 3 ítems y un precio editado a mano (Punto de luz a $50.000) pasó a
  17 ítems, conservando ese $50.000 intacto y sin duplicar nada en una
  segunda lectura.

## 0.14.0 — conectores independientes, deshacer/rehacer, grilla, y arreglos

- **El conector vuelve a ser de un solo conductor**, no un par fase+neutro
  forzado: se elige la polaridad al activar la herramienta, y cada uno se
  coloca donde haga falta — uno de fase acá, uno de neutro allá, sin que
  tengan que ir pegados.
- **Deshacer / rehacer con atajos de teclado** (Ctrl+Z, Ctrl+Y o Ctrl+Shift+Z),
  con botones ↶↷ en la cabecera. Se encontró y corrigió un bug real de lógica
  antes de entregarlo: el historial guardaba el estado anterior al cambio en
  vez del nuevo, así que quedaba siempre un paso atrasado — el primer
  "deshacer" saltaba dos pasos de una, y el estado más reciente se perdía sin
  que "rehacer" pudiera traerlo de vuelta. Se corrigió y se verificó paso a
  paso con Node: 3 ediciones, deshacer x3, rehacer x3, cada valor exacto y sin
  saltos ni pérdidas; también se probó el recorte a 60 pasos de historial.
- **Ahora se puede borrar un tramo de cable ya conectado**: antes sólo los dos
  círculos de las puntas (3.5px) eran clicables, y si estaban pegados a una
  térmica quedaban tapados. Se agregó un trazo invisible de 14px a lo largo
  de todo el cable, así que cualquier parte visible se puede tocar para
  seleccionarlo y borrarlo con Delete.
- **Grilla configurable** para rutear cables (editable por tablero, 8px por
  defecto), con snap aplicado tanto al punto que se toca como a la vista
  previa en vivo.
- Las flechas ◀▶ para reordenar las bocas de caño ya funcionaban; se les puso
  un fondo circular porque el problema real era que no se notaban, perdidas
  entre el resto de los elementos.
- **Marca de agua, arreglada de fondo**: el problema real de la entrega
  anterior era que el valor de opacidad ya guardado en disco (8) nunca caía
  al nuevo valor por defecto, porque en Python `8 or 16` da 8, no 16. Ahora el
  piso de opacidad es incondicional (16% mínimo, sin importar lo guardado) y
  el tamaño subió a 86% del ancho de la hoja.

## 0.13.0 — ruteo vertical primero, conector con polaridad, marca de agua corregida

- **El cable ahora sale recto en vertical y recién al final dobla**, no al
  revés. Todo nodo de este tablero (un tramo de caño, el polo de un
  dispositivo, el propio conector) sale físicamente en vertical; salir
  doblando en horizontal justo al lado del nodo era lo que se sentía raro.
- **El conector entre pisos, mejorado de fondo**: antes era una sola línea
  gris sin polaridad, y crearlo exigía tocar un punto vacío exacto en la
  banda (impreciso). Ahora:
  - Lleva fase y neutro por separado, con sus propios nodos arriba y abajo,
    igual que un peine.
  - Es un extremo válido de cable: se puede cablear un peine a un conector,
    un conector a otro conector, siempre con la misma verificación de
    cortocircuito que todo lo demás.
  - Se puede anclar tocando un peine ya puesto (usa su centro exacto), en vez
    de sólo aceptar un click a ciegas en la banda vacía.
- **Marca de agua corregida**: se forzaba a un recuadro cuadrado, así que
  cualquier logo que no fuera 1:1 quedaba deformado. Ahora se lee la
  proporción real de la imagen y se respeta. También bastante más grande
  (74% del ancho de la hoja) y algo más visible por defecto (14% en vez de
  8%), pensado para logos con trazo fino como el que se probó.
- Validado con Node (el ruteo) y contra el servidor real (conector con
  polaridad, cortocircuito entre dos conectores, proporción del logo real
  preservada 2051×1576 → 1.30).

## 0.12.0 — ruteo en vivo, saltos de cruce, y arreglo del desconecte en los caños

- **Ruteo en vivo, como un diseñador de PCB**: desde el último punto puesto,
  el tramo en escuadra ahora sigue al mouse en tiempo real hasta el próximo
  click, en vez de recién mostrar el resultado una vez confirmado. Se
  actualiza en un overlay aparte, sin repintar todo el gabinete, para que
  sea fluido.
- **Arreglado el desconecte en los caños**: el tramo grueso (fase/neutro/
  tierra) y el cable fino que salía de ahí usaban dos cálculos de posición
  distintos que no coincidían — por eso el cable parecía nacer de la nada.
  Ahora comparten un único cálculo (`puntaDeStub`) y quedan pegados siempre.
- **Salto esquemático en los cruces**: cuando dos cables se cruzan en un
  punto (uno horizontal, otro vertical, de dos cables distintos), el más
  nuevo de los dos dibuja un saltito en arco por encima, como en un esquema
  eléctrico de mano. Sólo salta cruces puntuales — dos tramos paralelos
  superpuestos no generan ningún salto, porque ahí no hay forma de dibujarlo
  sin que deje de verse.
- Verificado con Node: dos cables perpendiculares generan exactamente un
  salto en el más nuevo y ninguno en el más viejo; dos tramos paralelos
  solapados no generan salto.

## 0.11.0 — caños sin límite fijo, cables ortogonales, Escape y Delete

- **Se saca el concepto de "N bocas fijas"**: ahora se van agregando entradas
  una por una (Acometida, Jabalina, o cualquier circuito ya creado), tantas
  como haga falta por el mismo lado — más de un circuito puede entrar por
  arriba o por abajo sin ningún tope artificial. Cada entrada se puede mover
  de izquierda a derecha con las flechitas ◀▶, y editarse o eliminarse
  tocándola de nuevo.
- **Cables siempre ortogonales**: ya no hay líneas inclinadas. Cualquier
  segmento entre dos puntos (el origen, un punto intermedio que se toque, o
  el destino) se dibuja en escuadra — horizontal y después vertical — tanto
  en el cable final como en la vista previa mientras se traza.
- **Escape vuelve a la herramienta Mover**, sea cual sea la que esté activa.
- **Seleccionar y borrar un cable con Delete**: tocar un cable ya no lo borra
  al toque — lo selecciona (se resalta punteado en cobre) y recién se quita
  al apretar Delete o Backspace. Escape también lo deselecciona.

## 0.10.1 — el cableado se tapaba con todo, no sólo con las térmicas

- **Encontrado el error real**: al poner el cableado "por detrás" en 0.10.0,
  quedó detrás del fondo decorativo del riel y de las bandas también (que no
  son térmicas, son sólo el dibujo de fondo) — por eso no se veía nada, no se
  podía clickear para editar, y los peines desaparecían. Ahora el orden es:
  primero el fondo decorativo, después el cableado (ya visible), y al final
  las térmicas — que son lo único que debe taparlo, y sólo donde están
  paradas.
- Esto también arregla la edición: antes el riel entero (todo su rectángulo)
  interceptaba el clic así estuviera vacío. Ahora sólo el cuerpo real de una
  térmica lo hace; en cualquier zona sin térmica, el clic llega al cable o al
  peine que está debajo.
- **Corregido el cable gris**: el color por polaridad se calculaba y se
  guardaba en el cable (fase/neutro/tierra) desde la entrega anterior, pero
  el dibujo nunca lo usaba — seguía con el color viejo. Ahora toma
  `cable.polaridad` directo.
- Verificado con Node armando un tablero completo (general, caño de
  acometida, un peine, un cable) y comprobando que el color, la posición de
  la térmica y el trazo del peine dan los valores esperados.

## 0.10.0 — polaridad, cortocircuito, y cableado siempre por detrás

- **Verificación de cortocircuito**: antes de crear cualquier cable se
  compara la polaridad de los dos extremos (fase, neutro o tierra) y se
  rechaza si no coinciden — "Eso conecta fase con neutro: es un
  cortocircuito." Aplica a caños, peines y nodos de dispositivo por igual.
- **Colores por polaridad en todos lados**: los nodos de cada polo se pintan
  marrón (fase), celeste (neutro) o verde (tierra) según la convención "el de
  la izquierda es fase". Ya no hay que adivinar cuál es cuál.
- **Tramos de cable en cada boca de caño**: al asignar una boca aparece un
  pedazo corto de cable por cada conductor que trae — marrón y celeste para
  acometida o un circuito común, más uno verde si el circuito es TUG o TUE
  (que necesitan tierra además de fase y neutro). La jabalina es un solo
  tramo verde. Cada tramo termina en su propio nodo: de ahí se cablea, no
  del caño en sí.
- **El cableado pasa siempre por detrás**: se pintan primero los cables,
  peines y conectores, y recién después los rieles y las térmicas — así una
  térmica nunca queda tapada por un cable. El cable se ve en los huecos entre
  pisos y en el canal lateral, y desaparece donde el gabinete lo tapa, como en
  una instalación real. Si se prefiere ver el recorrido completo siempre,
  conviene rutearlo a mano por el canal (con la herramienta de puntos
  intermedios) en vez de ir directo.
- Circuitos IUG/IUE/ACU/OCE siguen sin el conductor de tierra extra, tal como
  se pidió; si se quiere sumarlo también a ACU se puede extender igual que
  con TUG/TUE.

## 0.9.0 — nodos por polo, ruta libre, y selector de bocas por botones

- **Un nodo por polo, no uno por lado**: una térmica bipolar ahora tiene 2
  nodos arriba y 2 abajo (uno por polo), igual el diferencial y el protector.
  La bornera de tierra tiene sus terminales de costado, no arriba/abajo. Esto
  es lo que hacía falta para conectar en serie de verdad: el polo de fase
  puede ir a un lado y el de neutro a otro, sin que se estorben.
- **El peine ya no "tapa" el nodo**: como cada polo tiene su propio nodo, el
  punto donde el peine engancha una térmica sigue disponible para cablear
  otra cosa desde ahí mismo, sin nada especial que hacer.
- **Ruteo libre**: un cable ya no va siempre en línea recta por el canal
  lateral. Con la herramienta activa, después de tocar el primer extremo se
  pueden tocar tantos puntos intermedios como se quiera antes de tocar el
  segundo extremo, y el cable sigue exactamente esa ruta.
- **Selector de bocas de caño por botones**, no por texto: tocar una boca abre
  una lista con Acometida, Jabalina, y cada circuito ya creado, para elegir
  con un clic en vez de escribir el nombre.
- **Conector rediseñado** a partir de la foto de referencia: cuerpo con
  tornillo en cruz y lengüeta de contacto, en vez del rectángulo simple
  anterior.
- Validado de punta a punta: dos cables al mismo lado de una térmica pero a
  polos distintos (0 y 1) conviven sin problema; un polo fuera de rango se
  rechaza; una ruta con puntos intermedios se guarda y se puede reconstruir.

## 0.8.0 — bocas de caño fijas, y conexión en serie real

- **Bocas de caño en vez de posición libre**: como en la foto de referencia
  (los caños en corte que entran al gabinete), ahora son una cantidad fija
  —elegible, 1 a 12, por separado arriba y abajo— y se toca cada boca para
  decidir qué entra: acometida, un circuito puntual, o la jabalina. Tocar una
  boca ya asignada permite cambiarla sin duplicar el agujero.
- **Conexión en serie de verdad**: el problema de fondo era que sólo se podía
  cablear de un caño a una térmica directo. Ahora cada dispositivo tiene dos
  nodos (arriba y abajo, visibles con la herramienta "Cable / serie" activa) y
  un cable conecta *cualquier* combinación de caño, peine, o nodo de un
  dispositivo. Así se arma la cadena real: acometida → térmica general
  (que corta todo) → diferencial → peine → cada térmica del circuito.
  Un peine también puede ser el destino de un cable, para alimentarlo desde
  el diferencial en vez de asumir que siempre nace de la nada.
- Corregido un bug de origen propio encontrado en las pruebas: los ids se
  generaban con el milisegundo del reloj y podían repetirse si se creaban
  varios objetos en la misma corrida. Ahora usan un identificador realmente
  único.
- Validado de punta a punta contra el servidor real: boca fuera de rango,
  reasignar una boca sin romper los cables que ya dependían de ella (mismo id,
  se actualiza en el lugar), y la cadena completa caño → general → diferencial
  con sus tres tramos intactos.

## 0.7.0 — caños de entrada/salida y cableado por canal lateral

- **La etiqueta del circuito ahora se lee**: se movió adentro de la térmica, a
  la ventana donde normalmente iría la marca del fabricante, en negrita.
  Antes quedaba afuera del dibujo y se recortaba.
- **Protector corregido**: ya no mostraba una corriente en A como si fuera un
  amperímetro. Ahora tiene un display estilo 7 segmentos con la tensión de
  referencia ("220" + "V"), editable desde el panel de detalle.
- **Peine con fase y neutro diferenciados**: dos barras, marrón (fase, siempre
  la del polo izquierdo) y celeste (neutro), cada una con sus propios pines a
  la columna que corresponde. Un tripolar sin neutro sólo tiene barra de fase.
- **Sistema de caños**: una franja arriba de todo y otra abajo de todo del
  gabinete, donde se colocan los puntos de entrada/salida — acometida,
  cada circuito, la jabalina — con su símbolo de caño en corte.
- **Cable desde caño**: herramienta de dos clics que conecta un caño con la
  térmica (o la bornera, o la general) que corresponde.
- **El cable nunca cruza por encima de otra térmica**: viaja por un canal
  lateral reservado a la izquierda del gabinete hasta la altura del piso de
  destino, y recién ahí se mete hacia el dispositivo. No es literalmente "por
  detrás" del riel (en un esquema 2D de arriba, eso lo volvería invisible) —
  es la alternativa que mantiene el cable siempre visible y nunca superpuesto
  con ninguna térmica. Si preferís que directamente desaparezca detrás de los
  pisos intermedios, se puede ofrecer como variante en una próxima entrega.
- Probado de punta a punta contra el servidor real: caño, cable, borrado en
  cascada del caño con su cable, y rechazo de tipo de caño inválido.

## 0.6.0 — conexionado con peines y conectores

- **Mucho más alto en Y**, como se pidió: cada piso pasa de 108px a un riel de
  150px, más dos bandas de cableado de 78px arriba y abajo (llegada y salida).
- **El peine deja de ser un simple interruptor visual** y pasa a ser un objeto
  real: herramienta "Peine" → tocás la primera térmica del tramo, tocás la
  última, y el peine las une en paralelo. Se dibuja en la banda superior, con
  pines bajando a cada térmica alcanzada, tal como en la foto de referencia.
- **Conector entre pisos**, la pieza de la foto: herramienta "Conector al piso
  siguiente" → tocás la banda de salida de un piso, tocás la banda de llegada
  del piso de abajo, y se dibuja el puente que baja el bus. Sólo se permite al
  piso inmediatamente siguiente, como corresponde físicamente.
- Tocar un peine o un conector ya puesto permite borrarlo (con confirmación).
- Validado con Node: la geometría dio las coordenadas esperadas (el peine
  queda en la banda superior con pines hasta el riel; el puente recorre
  exactamente la altura de un piso completo, de banda inferior a banda
  superior del siguiente) y las llamadas reales a la API crean, rechazan y
  validan peines y conectores como corresponde.
- Se retira el selector "peine / individual" por riel de la versión anterior:
  quedó reemplazado por este sistema.

## 0.5.2 — causa real del bug de las térmicas, y esquemas nuevos

- **Encontrada la causa de fondo** de que las térmicas de los circuitos no
  aparecieran: los circuitos armados antes de crear el tablero quedan con
  `tableroId` vacío, y sincronizar sólo buscaba circuitos ya vinculados. Ahora,
  si la obra tiene un único tablero (el caso normal), sincronizar **reclama**
  los circuitos sueltos automáticamente y les asigna ese tablero. Probado de
  punta a punta contra el servidor.
- **Corrección de bocas**: quedó bien esta vez — 12 bocas por piso, una
  térmica bipolar ocupa 2.
- Dibujo esquemático rehecho a partir de las cinco referencias: térmica con
  tornillos en cruz arriba y en más abajo, diferencial con botón T de test y
  ventana indicadora, protector con display y botonera, bornera con tornillos
  en tres grupos, riel DIN con las ranuras típicas de fondo en cada piso. Sin
  ninguna marca de fábrica — sólo contorno, la corriente ("C16", "40A/30mA") y
  el circuito.
- Validado el SVG generado con Node antes de entregar (no sólo mirado a ojo).

## 0.5.1 — correcciones del tablero

- **Corrección de concepto**: una boca es el ancho de una llave monopolar (no
  usada, prohibida). Una térmica bipolar ocupa 2 bocas. Un riel de 12 bocas
  entran 6 térmicas — no 6 bocas como estaba antes. Los presets pasan a 12,
  24, 36, 48 y 72 bocas, todos con 12 bocas por piso.
- **Nada se coloca solo.** La térmica general, el diferencial, la bornera de
  tierra y las térmicas de cada circuito nacen en una **bandeja**, afuera del
  gabinete. El usuario los arrastra al riel. Esto también corrige el aporte de
  que las térmicas de circuitos creados antes "no aparecían": ahora siempre
  están visibles en la bandeja hasta que se colocan, en vez de quedar
  invisibles si no encontraban lugar solas.
- **Dibujo esquemático** de cada dispositivo (contorno, llaves, sin marca de
  ninguna fábrica): térmica con "C" + corriente, diferencial con Δ y botón de
  test, bornera con símbolo de tierra, protector con indicador. Debajo de cada
  térmica de circuito, su nombre.
- Tablero más grande (bocas de 64px, antes 42) y con más aire.
- **Entrada arriba/abajo** ahora es una flecha visible sobre o bajo cada
  dispositivo colocado, más un selector explícito en el panel de detalle al
  tocar un dispositivo (antes sólo existía como ícono chico, poco visible).
- **Cableado — primera versión**: cada riel elige "peine" o "conectores
  individuales" y se dibuja en consecuencia (una barra continua o tramos
  cortos entre térmicas vecinas). Pendiente para una próxima entrega: el
  conexionado punto a punto con la canalización real del plano.
- Agregar dispositivos sueltos (térmica, diferencial, bornera, protector) con
  un clic, y quitarlos del tablero con confirmación.

## 0.5.0 — tablero, y arreglo de fondo en circuitos

- **Lista de precios** actualizada a las categorías reales: Puntos, Tomas,
  Iluminación, Tableros, Puesta a tierra, Trabajos adicionales (aparte) y
  Automatizaciones (aparte). Orden manual por categoría con flechas, como en
  la app anterior.
- **Arreglo de fondo en circuitos**: la familia de un elemento ya no depende
  sólo de si es artefacto o toma — se afina por subtipo. Antes una
  preinstalación de A.A. (que para el extractor también es "toma") podía
  colarse en un TUG al sombrear una zona, sin ningún aviso. Ahora las familias
  son `luz`, `tomas_general`, `tomas_especial`, `tomas_aa` y `tomas_otro`, y
  mezclar familias en un circuito es **error**, no advertencia.
- **Modo Individual** en circuitos: un clic agrega o saca un elemento del
  circuito activo al toque, sin pasar por el lote. El modo Zona sigue para
  sombrear rangos.
- **Deshacer / rehacer** en circuitos (Ctrl+Z / Ctrl+Y), sobre altas, bajas y
  movimientos entre circuitos.
- **Módulo de tablero** (`web/tablero.html`): presets de gabinete (8 a 36
  bocas) o a medida, con distribución automática en pisos; general y
  diferencial por defecto (25 A / 40 A, editables), bornera de tierra de riel
  DIN, protector de sobretensión opcional del tamaño de una térmica.
  Una térmica por circuito, dimensionada según su protección y la cantidad de
  polos que corresponde (mono 2P, trifásico 3P o 4P según corte neutro).
  Distribución arrastrando con el mouse sobre el riel, con validación de
  superposición y de espacio excedido en tiempo real.
- Los circuitos ahora se asignan a un tablero (`circuitos.tableroId`), y desde
  ahí "Sincronizar circuitos" agrega o quita térmicas automáticamente.
- **Pendiente para una próxima entrega**: el conexionado gráfico completo
  (peine, conectores, guirnaldas, entrada de caños arriba/abajo dibujada) —
  por ahora cada dispositivo guarda de qué lado se alimenta, pero el dibujo
  del cableado en sí todavía no está.

## 0.4.0 — precios y presupuesto

- Lista de precios global (`web/precios.html`), editable por categoría, con
  ajuste porcentual masivo.
- Al presupuestar, los precios se **congelan dentro de la obra**: actualizar la
  lista después no mueve un presupuesto ya armado. Si algún ítem congelado
  cambió de precio en la lista vigente, se muestra la variación para decidir
  si conviene reajustar.
- Módulo de presupuesto (`web/presupuesto.html`): cantidades sugeridas desde
  los elementos del plano, extras y adicionales, ítems marcables como
  opcionales (se muestran aparte y no suman al total), descuento por
  porcentaje o por monto fijo, y precio final para redondear (queda registrado
  como "ajuste").
- Logo y marca de agua configurables desde Configuración, con vista previa.
  La marca de agua se puede regular en opacidad.
- Generador de PDF del presupuesto (PyMuPDF, sin dependencias nuevas): logo,
  datos de la empresa, tabla de trabajos, extras, opcionales y totales.
- Se agrega `VERSIONING.md`: versión `0.MINOR.PATCH` hasta que el ciclo
  completo (extraer, circuitos, canalización, presupuesto, seguimiento)
  funcione de punta a punta, momento en que pasa a `1.0.0` con semver estricto.
  La versión ahora se muestra en la cabecera del tablero.

## 0.3.1

- El armado de circuitos pasa a hacerse sobre el plano: se sombrea una zona con
  el mouse y quedan marcados los elementos que correspondan al tipo de circuito
  activo (iluminación o tomas). Shift suma a lo ya marcado.
- Cada circuito muestra su color en el plano, y los elementos sin asignar quedan
  en gris.
- Valores por defecto por tipo: IUG 1,5 mm² / 10 A, TUG y TUE 2,5 mm² / 16 A,
  ACU 2,5 mm² / 20 A.
- Aviso nuevo cuando un circuito mezcla familias (una tecla dentro de un TUG).
- Las obras sin plano siguen usando la lista.

## 0.3.0 — circuitos

- Módulo de circuitos: agrupar elementos en IUG, TUG, IUE, TUE, ACU y OCE,
  con sección y protección por circuito.
- Chequeos: elementos sin circuito, elementos en dos circuitos, circuito vacío,
  máximo de bocas por tipo, sección mínima y protección contra sección.
- Obras sin plano, para reparaciones y trabajos chicos: los elementos se cargan
  a mano desde circuitos.
- Corrige la leyenda "alimentación / extractor", que se partía en dos y hacía
  saltar un falso aviso de caja faltante.

## 0.2.1

- Corrige el desfase de los elementos en planos apaisados: el visor fijaba el
  sistema de coordenadas antes de conocer el tamaño real de la hoja.
- Los vínculos entre artefactos y teclas pasan a un módulo único (`vinculos.py`)
  y se recalculan en vivo: al colocar una caja a mano, los avisos de "letra sin
  artefacto" y "tecla sin artefacto" desaparecen solos.
- Al colocar un artefacto o una tecla a mano se pide la letra.
- "Agregar caja" permite elegir el tipo.

## 0.2.0 — FY-App

- La app pasa a llamarse FY-App; los datos guardados con el nombre anterior se
  mudan solos al arrancar.
- Se quita la detección automática de ambientes: era poco confiable y el
  agrupamiento lo hace el usuario en el módulo de circuitos. Sale OpenCV como
  dependencia.
- Las leyendas sin caja dibujada pasan a ser error `caja_faltante`, con botón
  para colocar la caja en el plano.
- Calibración manual de escala marcando dos puntos e ingresando la medida.
- El extractor corre solo al abrir el revisor por primera vez.
- "Fuerza" pasa a llamarse "Otros".

## 0.1.0 — esqueleto y extractor

- Servidor local en Python con interfaz HTML, sin dependencias para el núcleo.
- Contrato `obra.json` v1: bloques por módulo, ids estables, regla de no borrar
  claves desconocidas.
- Tablero con resumen por obra, filtros y la vía de progreso.
- Sincronización con repositorio privado de GitHub, una carpeta por obra.
- Verificación de acceso escribiendo un archivo de prueba.
- Carga del plano en PDF, guardado como archivo aparte.
- Extractor: escala, punto de referencia, artefactos, tomas, teclas,
  circuitos y combinados.
- Revisor visual con corrección manual y marca de revisado.
