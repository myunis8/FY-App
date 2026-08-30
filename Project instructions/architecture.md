# FY Manager

## Objetivo

FY Manager es una aplicación destinada a profesionales de instalaciones eléctricas.

El objetivo principal es permitir administrar:

- clientes
- obras
- presupuestos
- materiales
- planos
- documentación
- costos
- impresión de documentación

La aplicación debe priorizar:

- rapidez
- simplicidad
- facilidad de uso
- apariencia profesional

Nunca se deben implementar soluciones que compliquen innecesariamente la interfaz.

---

## Filosofía

Toda funcionalidad debe:

- reutilizar componentes existentes
- mantener consistencia visual
- evitar código duplicado
- minimizar dependencias

---

## Arquitectura

La aplicación está dividida en módulos.

Cada módulo debe ser independiente.

Los módulos comparten únicamente servicios comunes.

Ejemplos:

Clientes

↓

Obras

↓

Presupuestos

↓

Materiales

↓

PDF

↓

Configuración

---

## Diseño

Toda pantalla debe seguir el mismo estilo.

- colores consistentes
- botones consistentes
- tablas consistentes
- formularios consistentes

No crear estilos nuevos salvo necesidad.

---

## Rendimiento

Priorizar:

- componentes reutilizables

- lazy loading cuando corresponda

- evitar renders innecesarios

- evitar duplicación de datos

---

## Antes de modificar código

Siempre analizar:

1) impacto

2) archivos afectados

3) compatibilidad

4) posibilidad de reutilización