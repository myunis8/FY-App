# FY-App — Resumen para continuar en otro chat

Pegá este archivo entero al inicio de la conversación nueva, junto con el ZIP
del código (`fy-app.zip`, versión **0.24.0**). Con esto alcanza para que
Claude entienda el proyecto sin tener que re-leer todo el historial.

## Reglas permanentes de este proyecto (mantener siempre, en toda entrega)

1. **El ZIP se entrega sin carpeta contenedora**: todos los archivos sueltos
   en la raíz del zip (`zip -r fy-app.zip .` desde adentro de la carpeta del
   proyecto), nunca con todo adentro de una carpeta `fy-app/`.
2. **Los comandos de git van siempre en inglés y lo más resumidos posible**:
   un solo `git commit -m "..."` corto en inglés describiendo el cambio, más
   `git add -A` y `git push`. Nunca en español, nunca un mensaje largo.
3. **Versionado semántico** (`app/__init__.py`, `__version__`): PATCH para
   correcciones y ajustes chicos, MINOR para funcionalidad nueva. Cada
   entrega suma una entrada nueva arriba de todo en `CHANGELOG.md`,
   explicando qué se rompió, por qué, y cómo se probó — no sólo qué se
   cambió.
4. **Regla de oro del contrato de datos**: ningún módulo borra claves de
   `obra.json` que no entiende, para que una versión vieja no destruya datos
   de una nueva.
5. **Testeo real, siempre, antes de dar algo por terminado**: levantar el
   servidor de verdad (`nohup python3 obras.py PUERTO &` con `sleep 4` antes
   de pegarle, todo en el mismo bloque de bash — el proceso muere entre
   llamadas separadas de la herramienta), probar contra la API real, y para
   PDF generados, renderizarlos con PyMuPDF y **mirarlos** con la
   herramienta `view`, no sólo confiar en que no tiraron excepción. Para
   páginas interactivas (tablero.html, canaliza.html), usar Puppeteer
   (hay un Chromium real disponible en
   `/home/claude/.cache/puppeteer/chrome/linux-131.0.6778.204/chrome-linux64/chrome`,
   y el paquete `puppeteer` en
   `/home/claude/.npm-global/lib/node_modules/@mermaid-js/mermaid-cli/node_modules/puppeteer`)
   para clickear de verdad, no simular.
6. **Verificar siempre desde un ZIP recién descomprimido** en `/tmp`, no
   desde la carpeta de trabajo — varias veces algo funcionaba en el árbol de
   trabajo pero fallaba empaquetado. El flujo estándar de cada entrega es:
   hacer el cambio → probar en el árbol de trabajo → bump de versión →
   actualizar CHANGELOG → empaquetar → descomprimir en una carpeta nueva de
   `/tmp` → correr el smoke test final ahí, contra un servidor real → recién
   ahí `present_files` y entregar.
7. Cuando algo "parece que ya debería funcionar" pero el usuario dice que
   sigue mal: no asumir que es el mismo bug de la vuelta anterior ni parchear
   a ciegas. Reproducir el caso exacto, mirar la imagen/PDF que mande, y
   recién ahí diagnosticar. Varias veces en este proyecto la causa real
   resultó ser otra cosa de lo que parecía a primera vista (ver CHANGELOG
   0.21.3, 0.23.2, 0.24.0 como ejemplos).

## Qué es

Sistema modular de gestión de instalaciones eléctricas domiciliarias
(normativa argentina, AEA), organizado por obra. Backend Python puro
(`http.server`, sin frameworks) + frontend HTML/JS vanilla (sin build step,
un archivo por módulo). Todo el estado de una obra vive en un único
`obra.json` por proyecto, con un contrato de claves fijo que **nunca se
borra** aunque un módulo no las entienda (regla de oro documentada en
`app/contrato.py`).

## Estructura de archivos

```
app/
  __init__.py        __version__ (subir en cada entrega)
  main.py, obras.py  arranque del servidor
  server.py          todas las rutas HTTP (GET/POST/PUT/DELETE), un solo archivo
  contrato.py        obra_vacia(), normalizar(), progreso() — el esquema de obra.json
  almacen.py         leer/guardar/borrar obra en disco
  config.py          config global de la app (logo, marca de agua, usuario)
  extractor/         extracción de elementos desde el plano PDF (símbolos, calibración)
  extraccion.py      orquesta el extractor
  vinculos.py        valida elementos <-> circuitos
  tablero.py         motor del módulo de tablero eléctrico (dispositivos, peines, conectores, cables)
  pdf_tablero.py     exporta el tablero a PDF (conexionado + guía de tapa)
  precios.py         lista de precios con semilla y migración automática
  presupuesto.py     calcula cantidades desde los elementos, arma el presupuesto
  pdf_presupuesto.py genera el PDF de presupuesto (formato fijo, ver abajo)
  canalizacion.py    integración con Canaliza/Routeo (ver más abajo) — muy chico a propósito
  sync.py, github.py otros

web/
  index.html         listado de obras + detalle con accesos a cada módulo; ahí vive
                      también la vista previa de PDF de Presupuesto (ver más abajo)
  revisor.html        revisión de elementos extraídos del plano
  circuitos.html      asignar elementos a circuitos, ver el plano con overlay, descripción
                      de cada circuito (campo "notas", ver abajo)
  tablero.html         editor visual del tablero (drag&drop, peines, conectores, cables
                      libres, descripción por dispositivo)
  precios.html        lista de precios editable
  presupuesto.html    presupuesto final, con aviso visible si algo no matchea contra la
                      lista de precios
  canaliza.html       app de canalización/Routeo INTEGRADA tal cual (ver abajo) — NO
                      reimplementar; nombre visible "Routeo", nombre interno de archivo
                      y rutas siguen siendo "canaliza"/"canalizacion" a propósito
```

Salida siempre en `/mnt/user-data/outputs/fy-app.zip`, **sin carpeta
contenedora** (ver regla permanente #1).

## Estado de los módulos

| # | Módulo | Estado |
|---|---|---|
| 1 | Extractor de plano | ✓ Hecho |
| 2 | Revisor + correcciones | ✓ Hecho |
| 3 | Circuitos sobre el plano + descripción por circuito | ✓ Hecho |
| 4 | Precios y presupuesto + PDF + aviso de ítems faltantes | ✓ Hecho |
| 5 | Tablero eléctrico (editor + export PDF, conectores de peine, descripción por dispositivo) | ✓ Hecho |
| 6 | Routeo (canalización) | ✓ Integrada (app externa real, ver abajo) |
| 7 | Seguimiento de cobro | Pendiente, no empezado |

## Backlog conocido (a futuro, no urgente)

- **PDF consolidado de entrega**: un solo PDF que junte Routeo + Tablero +
  Presupuesto (materiales), con lugar para sumar módulos futuros (por
  ejemplo automatizaciones) sin rehacer el armado cada vez. Ya está anotado
  también en el `README.md` del propio proyecto.
- Vista previa de PDF: ya implementada en Tablero, Presupuesto y Routeo
  (ver detalle en la sección correspondiente más abajo). Si se agregan
  nuevos lugares que generen PDF, seguir el mismo patrón.

## Rediseño de Tablero: peines y conectores (importante, no confundir con versiones viejas)

El sistema de "conector al piso siguiente" (puente) que existía antes se
**eliminó por completo** y se reemplazó por **conectores de peine**. Si en
algún momento aparece código o datos viejos con `tipo: "puente"`, son
incompatibles con el sistema actual — no hay migración automática.

- Un **conector de peine** (`tipo: "conectorPeine"`) se apoya siempre
  **arriba** de la barra del peine (nunca al costado) — lo que cambia con la
  **carga** es hacia dónde sale el cable real desde el cuerpo: derecho hacia
  arriba (`carga: "superior"`) o hacia el costado (`carga: "lateral"`).
- La **polaridad es automática**: la decide sola la barra que se toque al
  crearlo (celeste sobre neutro, marrón sobre fase) — no hay ningún selector
  para elegirla a mano.
- La **posición a lo largo del peine** la elige el usuario con el clic (no
  se centra sola).
- El conector queda como un extremo más de la herramienta de "Cable"
  normal: desde su patita se traza a mano el cable hacia donde haga falta
  (otro conector en otro peine, una térmica, un caño), con la misma
  libertad de ruteo (puntos intermedios incluidos) que cualquier otro cable.
- Selección y borrado: **clic para seleccionar, tecla Delete para borrar**
  (mismo criterio que los cables) — no hay cartel de confirmación en el
  momento. Los cables se dibujan (y son clickeables) *antes* que los
  conectores/peines a propósito, para que el área de clic ancha de un cable
  no le robe el clic a un conector que ya tiene un cable enganchado.
- Diseño visual: cuerpo rectangular sólido tipo bornera real, con un
  tornillo simple en el medio, coloreado según polaridad — sin capas
  transparentes ni círculos superpuestos que dejen ver un "nodo" de más.
- **Separación en carriles** (`_separar_paralelos()` en PDF,
  `separarParalelos()` en el editor web, ambas ya implementadas y
  equivalentes): cuando varios cables comparten un corredor —el caso más
  común es fase/neutro/tierra saliendo del mismo caño de entrada hacia
  destinos distintos, que comparten justo el primer tramo— se corren en
  paralelo unos px en vez de superponerse. Se consideran TODOS los tramos
  de cada cable, incluido el primero y el último (se acepta un pequeño
  desvío en el extremo, disimulado por el propio dibujo de la terminal).
- **Térmicas separadas con huecos reales** (margen a los costados de cada
  una, en vez de ocupar la celda entera) tanto en el editor como en el PDF
  de conexionado, para que un cable que pasa por atrás de una térmica se
  vea asomar en el hueco con la de al lado — "pasa por atrás" funciona
  gratis porque la app ya dibuja las térmicas encima del cableado.
- **Guía de tapa** (segunda hoja del PDF): tiene su propia escala horizontal
  más ancha que la hoja de conexionado (no necesita espacio para cables), un
  enmarcado tipo gabinete real (marco + tornillos en las esquinas), y
  muestra la **descripción** de cada dispositivo como etiqueta en negrita,
  envuelta en varios renglones (nunca truncada a una sola línea corta). La
  descripción sale del campo propio del dispositivo (`d.descripcion`,
  editable en el panel de cada uno en el editor) o, si no tiene, de la
  descripción del circuito asignado (`circuito.notas`, editable en
  Circuitos).
- Saltos de cruce entre cables (donde uno "pasa por encima" de otro sin
  conectarse): tamaño reducido (2.6pt de radio, antes 5pt) para que no se
  amontonen en una mancha borrosa cuando varios cables paralelos cruzan la
  misma línea.

## Presupuesto: cómo funciona el matching contra la lista de precios (crítico, leer antes de tocar)

`app/presupuesto.py` tiene una tabla `EQUIVALENCIAS` que mapea categorías
calculadas desde el plano (`toma_comun`, `toma_aa`, `punto_simple`, etc.) a
una lista de nombres candidatos, buscados por **nombre exacto** (con
paréntesis y todo) contra `app/precios.py`. El primero que exista gana.

**Ya pasó un bug real por esto**: un nombre en `EQUIVALENCIAS` no coincidía
letra por letra con el nombre real en la lista de precios, y la línea
entera desaparecía del presupuesto **en silencio**, sin ningún aviso. Se
corrigió así:
- `sugerir_items()` ahora devuelve `(items, avisos)` — una tupla, no sólo la
  lista. Si algo detectado en el plano no tiene ítem correspondiente en la
  lista de precios, se agrega un aviso en texto plano en vez de omitirse.
- Esos avisos se guardan en `obra["presupuesto"]["avisosPrecios"]` y se
  muestran en un cartel bien visible arriba de todo en `presupuesto.html`
  (`#aviso-faltantes`, distinto del `#aviso-precios` que ya existía para
  "cambiaron los precios desde que congelaste").
- **Si se agrega o renombra un ítem en la lista de precios que EQUIVALENCIAS
  usa, hay que probar de verdad que sigue matcheando** (llamar
  `presupuesto.sugerir_items()` con datos de prueba y mirar que no aparezcan
  avisos), no asumirlo por el nombre.
- Los precios de la semilla (`SEMILLA` en `precios.py`) son estimaciones de
  referencia inventadas como punto de partida, no vienen de ningún
  proveedor real — el usuario los va ajustando a precios de plaza.

## Vista previa de PDF (Tablero, Presupuesto, Routeo)

Los tres lugares que generan un PDF muestran una vista previa en un iframe
adentro de la app antes de descargar, con un botón "Descargar…" que usa
`window.showSaveFilePicker` (deja elegir dónde guardar) cuando el navegador
lo soporta, y si no, la descarga común. Tablero y Presupuesto piden el PDF
al servidor como blob (`fetch` + `.blob()`), no navegando directo a la URL.
Routeo arma el PDF enteramente en el navegador con jsPDF (recurso bloqueado
en el sandbox de pruebas de Claude por la red restringida — es una
limitación del entorno de pruebas, no de la app real) y lo muestra igual
antes de guardarlo, sin pedir nada al servidor.

## Lo más importante: el módulo de Routeo (canaliza.html) es una app AJENA integrada, no código mío

Esto es crítico para no repetir un error grande que ya se cometió una vez
(documentado en detalle en `CHANGELOG.md`, buscar "Canaliza integrada tal
cual, no reimplementada"). En resumen: `web/canaliza.html` es una app
completa (~2900 líneas) que el usuario ya tenía funcionando en otro
proyecto, con DRC, cableado de iluminación, exportación a PDF multi-hoja,
etc. **No hay que reimplementar ni "simplificar" esa funcionalidad** — ya
se intentó una vez y se perdió todo. La integración correcta (ya hecha) es
un puente de datos fino: un segundo `<script>` chico al principio del
archivo, antes del script principal de ~2900 líneas, que:
- carga sola el plano, los circuitos y las cajas ya extraídas la primera
  vez que se abre (y completa lo que falte en aperturas siguientes, sin
  pisar nada que el usuario ya haya editado — ver `mergeCajasExtraidas()` /
  `mergeCircuitosExtraidos()`),
- traduce los elementos del plano (artefactos, tomas, llaves) a nodos de
  Canaliza con su posición real y el color de su circuito,
  (`app/canalizacion.py`: `nodos_para_canaliza()`, `circuitos_para_canaliza()`),
- convierte las rutas manuales del editor de Tablero (celda=64px) a la
  escala del PDF (celda=34pt) — nunca son intercambiables directo
  (`_ruta_a_pdf()` en `pdf_tablero.py` resuelve el mismo problema para
  el módulo de Tablero, no confundir los dos "editor vs PDF" de módulos
  distintos).
- Nombre visible renombrado a **"Routeo"** en todos los lugares que lo
  muestra el usuario (título, tarjeta en index.html, encabezado del PDF) —
  el nombre interno de archivos, rutas de API, y claves de `obra.json`
  siguen siendo "canaliza"/"canalizacion" a propósito, para no arriesgar
  romper nada sin necesidad.

## Convenciones que cuesta recordar y conviene tener a mano

- **PyMuPDF 1.28.x**: el parámetro `alpha=` de `insert_image()` NO es
  opacidad — es sólo un flag interno sobre si la imagen tiene canal alfa.
  `insert_textbox` falla en silencio si la caja es más angosta que el
  texto — por eso `_texto_centrado()`/`_texto_multilinea()` en
  `pdf_tablero.py` centran a mano con `insert_text`, que siempre dibuja.
- **Defaults que cambian con el tiempo chocan con config ya guardada en
  disco**: antes de fijar un límite tipo piso/techo, pensar si no conviene
  detectar "esto es uno de mis propios defaults viejos" y reemplazarlo, en
  vez de acotar el valor guardado.
- **Migraciones de listas (como precios) deben corregir, no sólo agregar**:
  un ítem que ya existe con precio en $0 de una semilla vieja se ve igual
  de "no cargado" que uno que directamente falta. `_completar_faltantes()`
  en `precios.py` ya cubre los dos casos — mirarla antes de tocar la
  semilla.
- **No reinventar algo que el usuario ya trajo funcionando de otro lado**
  (ver el caso de Routeo arriba). Si trae una app/archivo externo pidiendo
  "integrar" o "usar como base", la primera pregunta es si conviene anexarla
  tal cual con un puente de datos fino, antes de reimplementarla.
- **Los tramos/cables siempre ortogonales**, nunca diagonales, en todos los
  módulos con dibujo (Tablero, Routeo). El ortogonal es "vertical primero".
  Cuando un tramo conecta con un extremo fuera de grilla (una caja
  extraída, por ejemplo), el eje que coincide con el punto anterior queda
  SIEMPRE exacto, nunca se redondea a la grilla — si no, dejaba de ser
  realmente recto (bug real ya corregido, ver CHANGELOG 0.20.2/0.21.3).
- **Coordenadas de dos sistemas nunca son intercambiables directo**: el
  editor interactivo de Tablero usa una escala mucho más grande
  (`celda=64px`) que el PDF (`celda=34pt`), pensada para que sea cómodo
  clickear con el mouse. Cualquier punto guardado en píxeles de un editor
  tiene que convertirse explícitamente antes de usarse en el otro sistema
  (ver `_ruta_a_pdf()`).
- El **transcript completo** de todo lo hecho hasta ahora (con el detalle
  turno a turno) sigue existiendo en el sistema de archivos de la sesión
  anterior — si en algún momento hace falta un detalle muy específico de
  *cómo* se resolvió algo que este resumen no cubre, se puede pedir. Pero
  para el 95% de los casos, este resumen + el código + el `CHANGELOG.md`
  completo ya alcanzan.

## Cómo seguir

Al empezar la conversación nueva:
1. Subir este `.md` + `fy-app.zip`.
2. Pedirle a Claude que descomprima el zip, revise `CHANGELOG.md` completo
   (versión 0.24.0) para el detalle turno a turno de decisiones ya tomadas,
   y arranque desde ahí.
3. Próximos pasos naturales, en orden de lo que probablemente se pida:
   - Seguir puliendo Tablero/Routeo sobre la marcha, a medida que se prueban
     casos reales más complejos.
   - Empezar el módulo de Seguimiento de cobro (todavía sin arrancar).
   - El PDF consolidado del backlog, si se vuelve prioritario.
   - Lo que el usuario pida sobre la marcha.
