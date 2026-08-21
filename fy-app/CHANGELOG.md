# Cambios

El formato es una línea por cambio, agrupadas por versión.
`contrato` indica la versión del esquema de `obra.json`.

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
