# Cambios

El formato es una línea por cambio, agrupadas por versión.
`contrato` indica la versión del esquema de `obra.json`.

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
