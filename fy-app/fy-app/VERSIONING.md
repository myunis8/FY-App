# Versionado de FY-App

Mientras el ciclo completo no esté probado de punta a punta, la versión se
mantiene por debajo de 1.0.0.

## Formato: `0.MINOR.PATCH`

- **MINOR** sube al agregar o rehacer un módulo completo (el extractor, el
  armado de circuitos, el presupuesto).
- **PATCH** sube con correcciones dentro de un módulo que ya existe.

No se usa versionado semántico estricto todavía porque el contrato de
`obra.json` puede seguir cambiando de forma incompatible entre versiones
`0.x` — eso es justamente lo que distingue el período pre-1.0. Los cambios
de forma del contrato se anotan en el CHANGELOG bajo cada versión.

## Cuándo pasa a 1.0.0

Cuando el ciclo completo funcione de punta a punta con una obra real:

1. Extraer un plano (o cargar a mano, si no hay plano).
2. Armar los circuitos y que la validación no marque errores.
3. Canalizar (módulo pendiente).
4. Presupuestar y entregar el PDF.
5. Marcar la obra como pagada y hacer seguimiento.

A partir de 1.0.0 sí rige semver: **MAJOR** para cambios que rompen el
contrato de `obra.json` o la estructura de datos en el repositorio, **MINOR**
para funcionalidad nueva compatible, **PATCH** para arreglos.

## Dónde vive la versión

- `app/__init__.py` → `__version__`, la única fuente de verdad.
- Se muestra en el tablero, en la cabecera (`/api/estado`).
- Cada entrada del `CHANGELOG.md` lleva el número de versión.

## Cómo se sube

Al cerrar un cambio: actualizar `__version__` en `app/__init__.py`, agregar la
entrada correspondiente arriba de todo en `CHANGELOG.md`. Cuando el proyecto
llegue a 1.0.0, conviene sumar tags de git (`git tag v1.0.0`) para poder volver
a una versión publicada.
