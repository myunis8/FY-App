# FY-App — Resumen para continuar en otro chat

Pegá este archivo entero al inicio de la conversación nueva, junto con el ZIP
del código (`fy-app.zip`, versión **0.20.0**). Con esto alcanza para que
Claude entienda el proyecto sin tener que re-leer todo el historial.

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
  tablero.py         motor del módulo de tablero eléctrico (dispositivos, cables, peines)
  pdf_tablero.py     exporta el tablero a PDF (conexionado + guía de tapa)
  precios.py         lista de precios con semilla y migración automática
  presupuesto.py     calcula cantidades desde los elementos, arma el presupuesto
  pdf_presupuesto.py genera el PDF de presupuesto (formato fijo, ver abajo)
  canalizacion.py    integración con Canaliza (ver más abajo) — muy chico a propósito
  sync.py, github.py otros

web/
  index.html         listado de obras + detalle con accesos a cada módulo
  revisor.html       revisión de elementos extraídos del plano
  circuitos.html     asignar elementos a circuitos, ver el plano con overlay
  tablero.html       editor visual del tablero (drag&drop, cableado, peines, caños)
  precios.html       lista de precios editable
  presupuesto.html   presupuesto final
  canaliza.html      app de canalización INTEGRADA tal cual (ver abajo) — NO reimplementar
```

Salida siempre en `/mnt/user-data/outputs/fy-app.zip`.

## Estado de los módulos

| # | Módulo | Estado |
|---|---|---|
| 1 | Extractor de plano | ✓ Hecho |
| 2 | Revisor + correcciones | ✓ Hecho |
| 3 | Circuitos sobre el plano | ✓ Hecho |
| 4 | Precios y presupuesto + PDF | ✓ Hecho |
| 5 | Tablero eléctrico (editor + export PDF) | ✓ Hecho |
| 6 | Canalización | ✓ Integrada (app externa real, ver abajo) |
| 7 | Seguimiento de cobro | Pendiente, no empezado |

## Lo más importante: el módulo de Canalización es una app AJENA integrada, no código mío

Esto es crítico para no repetir un error grande que ya cometí una vez.

`web/canaliza.html` es una app completa (~2770 líneas) que el usuario ya
tenía funcionando en otro proyecto/conversación: planificador de
canalización con dibujo sobre plano, cálculo de diámetro de caño (tabla de
llenado AEA), DRC (cruces de caños, cajas sobrecargadas, protecciones fuera
de norma), sistema de cableado de iluminación (trazar qué conductor lógico
pasa por cada tramo), y exportación a PDF multi-hoja (general, por circuito,
cableado detallado con colores, cómputo de materiales). Todo esto **ya
funciona** dentro de ese archivo, probado y usado por el usuario.

**Error que cometí y no hay que repetir**: en un primer intento reescribí
esa funcionalidad desde cero dentro de mi propio modelo de datos,
"simplificándola" — perdiendo el DRC, el cableado y el PDF multi-hoja. El
usuario lo rechazó explícitamente ("no me gusta, perdió todas sus
funcionalidades, no quiero iterar de nuevo 20 veces").

**Solución correcta, ya aplicada**: integrar el archivo real tal cual, con
sólo tres agregados quirúrgicos (pedidos y hechos en la conversación
original donde se armó esa app, no acá):
```js
// expuesto al final del IIFE principal:
window.canalizaExportar = buildProjectData;   // serializa el estado actual
window.canalizaImportar = applyProjectData;   // carga un estado (incluye imagen de fondo)
// y en boot(): si window.CANALIZA_SIN_AUTOSAVE es true, no pregunta por el
// autoguardado del navegador, y dispara el evento 'canaliza-listo' cuando terminó
```
Sobre eso, `web/canaliza.html` tiene un segundo `<script>` (agregado por mí,
ANTES del script principal de ~2770 líneas) que:
- pone `window.CANALIZA_SIN_AUTOSAVE = true`
- escucha `'canaliza-listo'`, y ahí: `GET /api/obras/{id}/canalizacion` — si
  ya hay un proyecto guardado lo carga tal cual; si es la primera vez, arma
  un objeto con los circuitos ya definidos en el módulo de Circuitos
  (traducidos a su formato) + la URL del plano, y lo importa
- agrega un botón "💾 Guardar en la obra" que llama `canalizaExportar()` y
  hace `POST /api/obras/{id}/canalizacion` con el resultado tal cual

`app/canalizacion.py` es deliberadamente mínimo: sólo `leer_proyecto()`,
`guardar_proyecto()` (el proyecto se guarda tal cual, sin transformarlo) y
`circuitos_para_canaliza()` (traduce IUG/TUG/TUE/ACU/OCE de esta app al
`kind` que espera Canaliza). **No hay que agregarle un modelo de datos
propio** — la app integrada ya tiene el suyo, completo y probado.

`obra.json.canalizacion` guarda exactamente lo que produce la propia
`buildProjectData()` de Canaliza (`{v, baseName, baseSrc, pxPerM, circuits,
nodes, runs, wires, viewGroups, hiddenCircuits, grid, rules, z, counters,
savedAt}`) — no un esquema mío.

**Pendiente de esto**: sólo probar la integración en un navegador real
(clics reales, no sólo llamadas a la API) — si hay Puppeteer disponible,
usarlo. La lógica de fetch/import/export ya se probó a nivel API y funciona,
pero nunca se vio la app corriendo de punta a punta en un navegador.

## Convenciones que cuesta recordar y conviene tener a mano

- **Testeo real, siempre**: antes de dar algo por terminado, levantar el
  servidor de verdad (`nohup python3 obras.py PUERTO &`, con `sleep 4` antes
  de pegarle — arrancar y pegarle en el mismo bloque de bash, si no el
  proceso muere entre llamadas separadas de la herramienta), probar contra
  la API real, y para archivos generados (PDF), renderizarlos con PyMuPDF y
  **mirarlos** con la herramienta `view`, no sólo confiar en que no tiraron
  excepción.
- **Verificar siempre desde un ZIP recién descomprimido** en `/tmp`, no
  desde la carpeta de trabajo — varias veces algo funcionaba en el árbol de
  trabajo pero fallaba empaquetado.
- **PyMuPDF 1.28.x**: el parámetro `alpha=` de `insert_image()` NO es
  opacidad — es sólo un flag interno sobre si la imagen tiene canal alfa.
  Para opacidad real: `pg._set_opacity(CA=1, ca=valor)` devuelve un nombre
  de graphics state, pero `insert_image()` no lo aplica solo — hay que
  editar el content stream a mano después (buscar el último `q\n` que
  insertó `insert_image()` e insertarle `/{nombre} gs\n` justo después,
  después `doc.update_stream(pg.get_contents()[0], nuevo_contenido)`).
- **`insert_textbox` de PyMuPDF falla en silencio** si la caja es más
  angosta que el texto — no lanza excepción, simplemente no dibuja nada.
  Para etiquetas cortas en espacios ajustados, mejor centrar a mano con
  `insert_text` + `get_text_length()`.
- **Defaults que cambian con el tiempo chocan con config ya guardada en
  disco**: si guardás un valor default en `config.json` y en una entrega
  posterior cambiás ese default en el código, un usuario que ya tenga el
  valor viejo persistido nunca ve el nuevo default. Ya pasó tres veces con
  la opacidad de la marca de agua. Antes de fijar un límite tipo
  piso/techo, pensar si no conviene detectar "esto es uno de mis propios
  defaults viejos" y reemplazarlo, en vez de acotar el valor guardado.
- **Migraciones de listas (como precios) deben corregir, no sólo agregar**:
  un ítem que ya existe con precio en `$0` de una semilla vieja se ve igual
  de "no cargado" que uno que directamente falta. Migrar tiene que cubrir
  los dos casos.
- **No reinventar algo que el usuario ya trajo funcionando de otro lado**
  (ver el caso de Canaliza arriba). Si trae una app/archivo externo pidiendo
  "integrar" o "usar como base", la primera pregunta es si conviene anexarla
  tal cual con un puente de datos fino, antes de reimplementarla.
- **Los tramos/cables siempre ortogonales**, nunca diagonales, en todos los
  módulos con dibujo (tablero, canalización). Convención ya establecida, no
  hay que preguntarla de nuevo.
- El **transcript completo** de todo lo hecho hasta ahora (con el detalle
  turno a turno) sigue existiendo en el sistema de archivos de la sesión
  anterior — si en algún momento hace falta un detalle muy específico de
  *cómo* se resolvió algo que este resumen no cubre, se puede pedir. Pero
  para el 95% de los casos, este resumen + el código ya alcanza.

## Cómo seguir

Al empezar la conversación nueva:
1. Subir este `.md` + `fy-app.zip`.
2. Pedirle a Claude que descomprima el zip, revise `CHANGELOG.md` completo
   (versión 0.20.0) para el detalle turno a turno de decisiones ya tomadas,
   y arranque desde ahí.
3. Próximos pasos naturales, en orden de lo que probablemente se pida:
   - Probar Canaliza en un navegador real (no sólo API).
   - Empezar el módulo de Seguimiento de cobro (todavía sin arrancar).
   - Lo que el usuario pida sobre la marcha.
