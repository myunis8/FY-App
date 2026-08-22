# Cambios

El formato es una línea por cambio, agrupadas por versión.
`contrato` indica la versión del esquema de `obra.json`.

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
