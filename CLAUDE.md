# CLAUDE.md — FY Manager

## 1. IDENTIDAD DEL PROYECTO

Este repositorio contiene **FY Manager**, una aplicación de escritorio/local destinada a la gestión profesional de instalaciones eléctricas domiciliarias en Argentina.

El proyecto pertenece a **FY Tech Solutions**.

Repositorio principal:

https://github.com/myunis8/FY-App

El sistema está orientado principalmente a profesionales de instalaciones eléctricas y busca centralizar:

- gestión de obras
- extracción de elementos desde planos eléctricos
- revisión y corrección de elementos
- asignación de circuitos
- canalización / Routeo
- diseño de tableros eléctricos
- cálculo de materiales
- presupuestos
- generación de PDFs
- seguimiento futuro de cobros
- futuras automatizaciones relacionadas con instalaciones eléctricas

---

# 2. REGLA FUNDAMENTAL: RESPETAR EL PROYECTO EXISTENTE

Este proyecto está en desarrollo activo y contiene decisiones de arquitectura que deben considerarse intencionales.

NO asumir que una implementación diferente es mejor simplemente porque resulta más moderna, más elegante o más habitual.

Antes de modificar arquitectura, estructura de archivos, contrato de datos o comportamiento de módulos:

1. analizar cómo funciona actualmente;
2. identificar las dependencias;
3. evaluar compatibilidad con obras existentes;
4. explicar el problema;
5. proponer la modificación;
6. esperar confirmación si la modificación es importante.

No realizar refactorizaciones grandes como efecto secundario de una tarea pequeña.

---

# 3. FUENTE DE VERDAD

La fuente de verdad del código es el contenido actual del repositorio GitHub.

Siempre trabajar sobre la versión más reciente disponible del repositorio.

No asumir que una versión mencionada en una conversación anterior sigue siendo la actual.

Si existe una discrepancia entre:

- una conversación anterior;
- un ZIP anterior;
- documentación antigua;
- y el código actual del repositorio;

el código actual del repositorio tiene prioridad, salvo que el usuario indique explícitamente lo contrario.

Los archivos `README.md`, `RESUMEN-FY-APP.md`, `CHANGELOG.md` y `VERSIONING.md` contienen información adicional importante y deben consultarse cuando corresponda.

---

# 4. ARQUITECTURA ACTUAL

La aplicación utiliza actualmente:

- Backend: Python
- Servidor HTTP: `http.server`
- Frontend: HTML + JavaScript vanilla
- Sin framework frontend
- Sin build step frontend
- Aplicación modular
- Estado persistente por obra en `obra.json`
- Integración con GitHub para sincronización de obras
- Generación de PDFs desde Python
- Ejecutable Windows mediante PyInstaller

La estructura principal actual incluye:

```text
fy-app/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── server.py
│   ├── contrato.py
│   ├── almacen.py
│   ├── config.py
│   ├── extractor/
│   ├── extraccion.py
│   ├── vinculos.py
│   ├── tablero.py
│   ├── pdf_tablero.py
│   ├── precios.py
│   ├── presupuesto.py
│   ├── pdf_presupuesto.py
│   ├── canalizacion.py
│   ├── sync.py
│   └── github.py
│
├── web/
│   ├── index.html
│   ├── revisor.html
│   ├── circuitos.html
│   ├── tablero.html
│   ├── precios.html
│   ├── presupuesto.html
│   └── canaliza.html
│
├── obras.py
├── build.bat
├── requirements.txt
├── VERSIONING.md
├── CHANGELOG.md
└── README.md
```

No asumir que esta estructura permanecerá idéntica para siempre. Si cambia, actualizar la documentación correspondiente.

---

# 5. CONTRATO CENTRAL: obra.json

`obra.json` es una parte crítica de la arquitectura.

Una obra contiene el estado de los distintos módulos del sistema.

Los módulos pueden consumir y producir diferentes partes de este contrato.

## REGLA DE ORO

**Ningún módulo puede eliminar claves de `obra.json` que no comprende.**

Esto es fundamental para mantener compatibilidad entre módulos y versiones diferentes.

Un módulo debe modificar únicamente las partes del contrato que le corresponden.

Si un módulo recibe una obra que contiene información de otro módulo:

- debe conservarla;
- no debe resetearla;
- no debe eliminarla;
- no debe reemplazarla por un estado vacío;
- no debe asumir que conoce todo el JSON.

Antes de cambiar `contrato.py`, estudiar cuidadosamente:

- `obra_vacia()`
- `normalizar()`
- `progreso()`
- todas las funciones que leen/escriben el contrato.

Los cambios al contrato son cambios de arquitectura y deben tratarse con especial cuidado.

---

# 6. COMPATIBILIDAD DE DATOS

Las obras existentes son datos reales y no deben romperse por introducir una funcionalidad nueva.

Cuando sea necesario agregar una nueva clave:

- agregarla de manera compatible;
- establecer un valor por defecto razonable;
- mantener las claves existentes;
- evitar migraciones destructivas.

Cuando sea necesario cambiar una estructura existente:

1. identificar obras antiguas potencialmente afectadas;
2. determinar si hace falta migración;
3. implementar la migración de forma explícita;
4. preservar la información existente.

Nunca eliminar silenciosamente información de una obra.

---

# 7. MÓDULOS ACTUALES

## Extractor de plano

Extrae elementos eléctricos desde planos PDF.

Incluye:

- símbolos;
- posiciones;
- calibración;
- elementos detectados;
- correcciones manuales.

No asumir que la extracción automática es perfecta.

El usuario puede corregir manualmente los elementos.

---

## Revisor

Permite revisar y corregir los elementos detectados por el extractor.

Las correcciones manuales del usuario tienen prioridad sobre las inferencias automáticas.

No implementar lógica que vuelva a sobrescribir automáticamente una corrección manual sin una razón explícita.

---

## Circuitos

Permite:

- crear circuitos;
- asignar elementos;
- visualizar elementos sobre el plano;
- definir información descriptiva del circuito.

El campo de notas/descripción del circuito puede ser utilizado posteriormente por otros módulos, por ejemplo tablero y documentación.

---

## Routeo / Canalización

`web/canaliza.html` corresponde a la aplicación integrada de canalización conocida visualmente como **Routeo**.

IMPORTANTE:

- el nombre visible es Routeo;
- los nombres internos `canaliza` / `canalizacion` se mantienen deliberadamente;
- no reimplementar Routeo desde cero;
- no reemplazarlo por otra solución sin una decisión explícita.

---

## Tablero eléctrico

El módulo de tablero incluye:

- dispositivos;
- térmicas;
- peines;
- conectores;
- cables;
- ruteo manual;
- posiciones;
- descripción por dispositivo;
- exportación PDF;
- guía de tapa.

### Conectores de peine

El sistema actual utiliza conectores de peine.

El concepto antiguo de `puente` fue eliminado.

Si aparece código o datos antiguos con:

```text
tipo: "puente"
```

no asumir que pertenece al modelo actual.

El sistema actual utiliza:

```text
tipo: "conectorPeine"
```

La polaridad del conector se determina automáticamente según la barra del peine que toca.

No agregar un selector manual de polaridad salvo que se solicite explícitamente.

---

## Presupuesto

El módulo de presupuesto utiliza:

- elementos de la obra;
- circuitos;
- lista de precios;
- cantidades;
- extras;
- opcionales;
- descuentos;
- información de la obra.

El presupuesto debe mantener consistencia con la lista de precios.

Si un elemento no tiene correspondencia con la lista de precios, debe hacerse visible para el usuario y no ocultarse silenciosamente.

---

## PDF

Los PDFs generados por el sistema son documentos finales destinados al uso profesional.

No considerar suficiente que un PDF "se genere sin excepción".

Debe verificarse:

- contenido;
- distribución;
- márgenes;
- textos;
- cortes de página;
- legibilidad;
- superposición;
- elementos gráficos;
- consistencia visual.

Cuando se modifique generación de PDF, realizar una prueba real y revisar visualmente el resultado cuando sea posible.

---

# 8. FRONTEND

El frontend utiliza HTML y JavaScript vanilla.

No introducir React, Vue, Angular, Svelte u otro framework salvo decisión explícita del usuario.

No agregar un sistema de build innecesario.

Preferir:

- funciones pequeñas;
- componentes reutilizables cuando corresponda;
- CSS existente;
- patrones ya utilizados en el proyecto;
- APIs existentes.

Antes de crear una nueva función utilitaria, buscar si ya existe una equivalente.

Antes de crear un nuevo componente visual, buscar si existe uno reutilizable.

---

# 9. BACKEND

El backend utiliza Python y `http.server`.

No introducir Flask, FastAPI, Django u otro framework salvo decisión explícita.

Mantener las dependencias externas al mínimo.

Antes de agregar una dependencia:

1. determinar si realmente es necesaria;
2. comprobar si puede resolverse con la biblioteca estándar;
3. evaluar impacto sobre el ejecutable;
4. evaluar impacto sobre instalaciones existentes.

---

# 10. SEGURIDAD

El token de GitHub utilizado por la aplicación es información sensible.

Nunca:

- incluir tokens en el código;
- incluir tokens en el frontend;
- incluir tokens en HTML;
- incluir tokens en JavaScript;
- incluir tokens en PDFs;
- incluir tokens en logs;
- incluir tokens en commits;
- incluir tokens en archivos entregados;
- inventar tokens.

La comunicación con GitHub debe realizarse desde Python/backend.

---

# 11. GITHUB Y SINCRONIZACIÓN DE OBRAS

El código del programa y los datos de las obras son conceptos diferentes.

El repositorio del código `FY-App` contiene el programa.

Las obras se sincronizan con otro repositorio configurado por el usuario.

No mezclar ambos conceptos.

La sincronización de obras utiliza mecanismos de control mediante SHA para evitar sobrescribir cambios realizados por otra persona.

No eliminar ni debilitar esta protección sin una razón explícita.

---

# 12. VERSIONADO

El proyecto utiliza versionado semántico.

La versión se encuentra en:

```text
app/__init__.py
```

Reglas generales:

- PATCH: corrección de bugs, pequeños ajustes o cambios internos sin nueva funcionalidad significativa.
- MINOR: nueva funcionalidad compatible.
- MAJOR: cambios incompatibles importantes.

Cada entrega que modifique funcionalidad debe evaluar si corresponde incrementar la versión.

No incrementar MAJOR arbitrariamente.

---

# 13. CHANGELOG

Toda entrega relevante debe actualizar:

```text
CHANGELOG.md
```

La nueva entrada debe colocarse arriba de las anteriores.

No limitarse a enumerar archivos modificados.

Explicar:

- qué cambió;
- por qué;
- qué comportamiento se modificó;
- cómo se probó;
- cualquier limitación conocida.

---

# 14. ESTILO DE COMMITS

Los commits deben estar en inglés.

Deben ser cortos y claros.

Preferir:

```text
Add circuit descriptions
Fix PDF page overflow
Change panel connector rendering
Remove obsolete bridge logic
Update budget calculation
```

Evitar:

```text
feat: agregar una funcionalidad nueva para...
```

salvo que el usuario solicite explícitamente Conventional Commits.

El comando esperado normalmente es:

```bash
git add -A
git commit -m "Short English description"
git push
```

No generar mensajes de commit largos.

---

# 15. REGLAS PARA IMPLEMENTAR CAMBIOS

Cuando el usuario solicite una modificación:

## Paso 1 — Entender

Determinar exactamente:

- qué quiere cambiar;
- qué comportamiento espera;
- qué parte del sistema está involucrada.

Si la solicitud es ambigua y puede producir comportamientos diferentes, preguntar antes de implementar.

---

## Paso 2 — Investigar

Buscar primero en el código existente:

- funciones relacionadas;
- endpoints;
- estructuras de datos;
- componentes;
- estilos;
- generación de PDF;
- código similar.

No comenzar a escribir código inmediatamente.

---

## Paso 3 — Impacto

Determinar:

- archivos afectados;
- módulos afectados;
- impacto sobre `obra.json`;
- impacto sobre obras existentes;
- impacto sobre PDFs;
- impacto sobre frontend;
- impacto sobre backend.

---

## Paso 4 — Implementación

Modificar únicamente lo necesario.

No reescribir archivos enteros si solamente se modifican algunas funciones.

No realizar refactorizaciones no solicitadas como parte de una tarea.

---

## Paso 5 — Verificación

Probar el comportamiento real.

No considerar terminada una modificación simplemente porque:

- compila;
- Python no genera excepción;
- JavaScript no muestra errores inmediatos.

Siempre que sea posible probar la funcionalidad real.

---

# 16. BUGS

Cuando el usuario informa que algo sigue funcionando mal después de una corrección:

NO asumir que el diagnóstico anterior era correcto.

NO aplicar otro parche sobre el mismo lugar automáticamente.

Primero:

1. reproducir el problema;
2. identificar el caso exacto;
3. analizar el flujo;
4. revisar el estado real de los datos;
5. revisar el resultado visual si corresponde;
6. determinar la causa;
7. recién entonces modificar el código.

Si el usuario proporciona una imagen, PDF o ejemplo concreto, utilizarlo como evidencia del comportamiento real.

---

# 17. PRUEBAS

El estándar de prueba debe ser lo más cercano posible al uso real.

Para cambios de backend:

- levantar el servidor;
- probar las rutas reales;
- verificar respuestas;
- verificar que los datos persistan correctamente.

Para cambios de frontend:

- cargar la página real;
- interactuar con ella;
- probar clicks;
- probar formularios;
- verificar estados;
- verificar errores de consola.

Para páginas interactivas complejas:

- preferir pruebas reales con navegador automatizado cuando esté disponible;
- no asumir que una función funciona sólo porque el código parece correcto.

Para PDFs:

- generar el PDF;
- abrir/renderizar el resultado;
- revisar visualmente cuando el cambio sea gráfico o de layout.

---

# 18. PRUEBA DEL ZIP

Cuando sea necesario generar un ZIP para entregar el proyecto:

1. realizar primero las pruebas sobre el árbol de trabajo;
2. actualizar versión;
3. actualizar CHANGELOG;
4. generar el ZIP;
5. descomprimir el ZIP en una ubicación limpia;
6. ejecutar las pruebas desde esa copia;
7. corregir cualquier problema que sólo aparezca en el paquete;
8. entregar únicamente después de superar la prueba final.

Nunca asumir que el árbol de desarrollo y el ZIP son equivalentes.

---

# 19. REGLA DE ENTREGA

El objetivo es minimizar el código innecesariamente generado.

### Si el cambio es pequeño

NO generar un ZIP completo.

Entregar:

1. resumen;
2. archivos modificados;
3. contenido completo de cada archivo modificado;
4. instrucciones especiales si existen;
5. commit sugerido.

### Si el cambio es grande

Se puede generar un ZIP.

Generar ZIP cuando:

- se crean muchos archivos;
- cambia significativamente la estructura;
- se realizan modificaciones en gran parte del proyecto;
- el usuario lo solicita explícitamente.

El ZIP debe contener el proyecto directamente en su raíz.

NO crear:

```text
fy-app/fy-app/...
```

Debe ser:

```text
fy-app.zip
├── app/
├── web/
├── obras.py
├── requirements.txt
└── ...
```

---

# 20. NO REPETIR CÓDIGO SIN NECESIDAD

Una de las prioridades del proyecto es reducir respuestas innecesariamente grandes.

Si sólo cambian:

```text
app/server.py
web/index.html
```

no volver a generar:

```text
app/tablero.py
app/presupuesto.py
...
```

No entregar archivos que no fueron modificados.

No repetir código completo en explicaciones si no es necesario.

---

# 21. COMUNICACIÓN CON EL USUARIO

El usuario es el desarrollador responsable del proyecto.

No ocultar decisiones técnicas importantes.

Cuando exista una decisión de arquitectura relevante:

- explicar brevemente el problema;
- explicar la solución propuesta;
- explicar las consecuencias.

Evitar explicaciones innecesariamente largas para cambios simples.

Priorizar respuestas prácticas.

---

# 22. TERMINOLOGÍA ELÉCTRICA

El software está orientado al contexto argentino.

Utilizar terminología habitual en Argentina y referencias AEA cuando corresponda.

No asumir automáticamente normas estadounidenses.

Usar unidades del sistema métrico:

- V
- A
- W
- kW
- mm²
- m
- Ω

No utilizar AWG salvo que sea solicitado.

No convertir automáticamente conceptos eléctricos argentinos a terminología estadounidense.

Cuando una decisión eléctrica dependa de una norma, distinguir claramente entre:

- requisito normativo;
- buena práctica;
- decisión de diseño del software.

No inventar requisitos de la AEA.

---

# 23. AUTOMATIZACIÓN

El objetivo futuro del proyecto incluye automatizar parte del trabajo de diseño y presupuestación de instalaciones eléctricas.

Actualmente algunas decisiones todavía son manuales.

No implementar automatización "inteligente" simplemente por parecer conveniente.

Una automatización debe:

- ser explicable;
- permitir modificación manual;
- no ocultar las decisiones tomadas;
- permitir al usuario corregir resultados.

La aplicación debe asistir al profesional, no quitarle control.

---

# 24. DISEÑO UX

La aplicación debe sentirse como una herramienta profesional de trabajo.

Prioridades:

1. claridad;
2. rapidez;
3. consistencia;
4. información útil;
5. apariencia profesional.

Evitar:

- interfaces excesivamente recargadas;
- modales innecesarios;
- confirmaciones constantes;
- animaciones decorativas;
- pasos innecesarios;
- configuraciones difíciles de encontrar.

Cuando exista una acción frecuente, intentar minimizar la cantidad de clicks.

---

# 25. PRESERVACIÓN DE FUNCIONALIDAD

Antes de modificar una función existente preguntarse:

- ¿quién la utiliza?
- ¿qué datos recibe?
- ¿qué devuelve?
- ¿qué otras páginas dependen de ella?
- ¿qué obras existentes dependen de su comportamiento?

No romper comportamiento existente para resolver una funcionalidad nueva.

Si una modificación necesariamente cambia comportamiento anterior, indicarlo explícitamente.

---

# 26. NO INVENTAR

Si falta información sobre:

- estructura;
- comportamiento;
- reglas de negocio;
- contrato de datos;
- intención del usuario;

no inventar una solución definitiva.

Investigar primero.

Si no es posible determinarlo, explicar la incertidumbre y preguntar.

---

# 27. DOCUMENTACIÓN

Cuando una modificación cambia una decisión arquitectónica importante, actualizar la documentación correspondiente.

No llenar documentación con información redundante.

Mantenerla útil y concisa.

La documentación no debe convertirse en una copia del código.

---

# 28. ESTADO ACTUAL CONOCIDO

Los módulos principales actualmente implementados incluyen:

1. Extractor de plano — implementado.
2. Revisor y correcciones — implementado.
3. Circuitos sobre plano — implementado.
4. Precios y presupuesto — implementado.
5. PDF de presupuesto — implementado.
6. Tablero eléctrico — implementado.
7. PDF de tablero — implementado.
8. Routeo / canalización — integrado.
9. Seguimiento de cobro — pendiente.

Existe como backlog futuro la generación de un PDF consolidado que pueda reunir:

- Routeo;
- tablero;
- presupuesto;
- futuros módulos.

Ese PDF debe diseñarse de manera modular para permitir incorporar nuevas secciones posteriormente.

---

# 29. PRIORIDAD DE DECISIONES

Cuando haya conflicto entre instrucciones, utilizar este orden:

1. solicitud explícita actual del usuario;
2. código actual del repositorio;
3. contrato de `obra.json`;
4. reglas de este archivo;
5. documentación histórica;
6. suposiciones propias.

Nunca utilizar una decisión antigua de una conversación para contradecir el código actual sin verificar primero.

---

# 30. OBJETIVO FINAL

FY Manager debe evolucionar hacia una herramienta profesional que permita pasar desde:

```text
Plano eléctrico
      ↓
Extracción de elementos
      ↓
Revisión
      ↓
Circuitos
      ↓
Canalización / Routeo
      ↓
Tablero
      ↓
Cómputo de materiales
      ↓
Presupuesto
      ↓
Documentación final
```

manteniendo en todo momento:

- trazabilidad;
- control del profesional;
- datos consistentes;
- compatibilidad entre versiones;
- interfaz simple;
- documentación profesional.

La prioridad no es agregar funcionalidades rápidamente.

La prioridad es construir una base sólida sobre la cual puedan agregarse funcionalidades sin romper las anteriores.