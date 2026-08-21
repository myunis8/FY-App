# Cambios

El formato es una línea por cambio, agrupadas por versión.
`contrato` indica la versión del esquema de `obra.json`.

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
