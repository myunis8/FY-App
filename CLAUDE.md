# CLAUDE.md — FY Manager

## 1. IDENTIDAD DEL PROYECTO

Este repositorio contiene **FY Manager**, una aplicación destinada a la gestión profesional de instalaciones eléctricas en Argentina.

Proyecto de:

**FY Tech Solutions**

Repositorio:

https://github.com/myunis8/FY-App

FY Manager busca centralizar el flujo de trabajo de una instalación eléctrica:

```text
Plano eléctrico
      ↓
Extracción de elementos
      ↓
Revisión / corrección
      ↓
Circuitos
      ↓
Canalización / Routeo
      ↓
Tablero
      ↓
Materiales
      ↓
Presupuesto
      ↓
Documentación final
```

El proyecto está en desarrollo activo.

---

# 2. REGLA FUNDAMENTAL

Trabajá siempre sobre el estado ACTUAL del repositorio.

El código existente es la fuente de verdad.

No asumir que una implementación mencionada en conversaciones anteriores sigue siendo válida.

Antes de modificar código:

1. inspeccionar el código actual;
2. identificar las dependencias;
3. entender cómo funciona actualmente;
4. determinar el impacto del cambio;
5. modificar únicamente lo necesario.

No realizar refactorizaciones grandes como consecuencia secundaria de una tarea pequeña.

---

# 3. USO DE CLAUDE CODE

Este proyecto se desarrolla utilizando Claude Code directamente sobre el repositorio local.

Por lo tanto:

* modificar directamente los archivos del proyecto;
* NO devolver bloques de código para que el usuario los copie manualmente;
* NO generar archivos completos en la respuesta si ya fueron modificados en el workspace;
* NO generar ZIP salvo que el usuario lo solicite explícitamente;
* usar las herramientas disponibles para leer, modificar y verificar archivos;
* revisar siempre los cambios realizados mediante `git diff`;
* ejecutar pruebas relevantes después de modificar código.

El usuario debe poder revisar los cambios directamente en VS Code.

---

# 4. REGLA SOBRE GIT

Claude Code utiliza Git de forma autónoma en este proyecto.

## Puede hacer automáticamente

* `git status`
* `git diff`
* inspeccionar commits, archivos e historial
* preparar cambios
* ejecutar tests
* `git commit`
* `git push`

## Commit y push automáticos al terminar cada tarea

Orden permanente del usuario (dada el 2026-09-01):

> "quiero que commitees y pushees todo, y de ahora en mas siempre"

Por lo tanto, al terminar cada tarea:

1. revisar `git status` y `git diff`;
2. verificar que no haya credenciales ni debugging olvidado;
3. hacer `git commit` con un mensaje corto y claro en inglés;
4. hacer `git push` a la rama actual.

No hace falta que el usuario lo pida cada vez: ya está pedido de forma permanente.

Si aparecen en el working tree cambios ajenos a la tarea, incluirlos igual en el commit
(el usuario pidió "commitees y pushees todo") pero avisarlo en la respuesta.

Si `git push` falla (por ejemplo, la rama remota avanzó), informar el error y no forzar.

---

# 5. FLUJO NORMAL DE TRABAJO

Para cada nueva tarea:

## Paso 1 — Inspección

Primero entender el pedido.

Buscar en el código:

* archivos relacionados;
* funciones relacionadas;
* endpoints;
* componentes;
* estructuras de datos;
* estilos;
* lógica existente.

No comenzar modificando código sin haber inspeccionado el área afectada.

---

## Paso 2 — Plan

Antes de una modificación compleja, informar brevemente:

```text
Voy a modificar:

- archivo A
- archivo B

Motivo:

...

No se espera impacto en:

...
```

Para cambios triviales no es necesario realizar una explicación extensa.

---

## Paso 3 — Implementación

Modificar directamente los archivos.

Prioridades:

1. mínima modificación necesaria;
2. compatibilidad;
3. reutilización;
4. claridad;
5. mantenimiento futuro.

---

## Paso 4 — Verificación

Después de modificar:

1. revisar `git diff`;
2. verificar que no se hayan modificado archivos accidentalmente;
3. ejecutar las pruebas correspondientes;
4. corregir errores;
5. volver a revisar el diff.

---

## Paso 5 — Resultado

Al terminar informar:

* qué se hizo;
* archivos modificados;
* pruebas realizadas;
* problemas conocidos;
* si corresponde actualizar versión;
* el commit y push hechos (mensaje usado y rama).

No pegar nuevamente el código completo salvo que el usuario lo solicite.

---

# 6. NO SOBREREESCRIBIR

Una de las prioridades del proyecto es evitar modificaciones innecesarias.

Si una función necesita cambiarse:

NO reescribir todo el archivo.

Si solamente se modifican unas líneas:

modificar solamente esas líneas.

No regenerar archivos que no necesitan cambios.

No cambiar formato, indentación o estructura de archivos sin necesidad.

Evitar cambios cosméticos mezclados con cambios funcionales.

---

# 7. ARQUITECTURA ACTUAL

El proyecto utiliza actualmente:

* Python;
* `http.server`;
* HTML;
* JavaScript vanilla;
* CSS;
* almacenamiento por obra;
* generación de PDFs;
* GitHub para sincronización;
* PyInstaller para distribución.

No introducir:

* React;
* Vue;
* Angular;
* Svelte;
* Flask;
* FastAPI;
* Django;

salvo decisión explícita del usuario.

No agregar un framework solamente por preferencia personal.

---

# 8. ESTRUCTURA PRINCIPAL

La estructura actual incluye:

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
├── requirements.txt
├── README.md
├── RESUMEN-FY-APP.md
├── CHANGELOG.md
└── VERSIONING.md
```

La estructura puede cambiar en el futuro.

Si cambia, respetar la estructura actual del repositorio.

---

# 9. obra.json — CONTRATO CENTRAL

`obra.json` es un componente crítico del sistema.

Representa el estado persistente de una obra.

Los diferentes módulos utilizan diferentes partes de ese estado.

## REGLA CRÍTICA

Un módulo NO debe eliminar información que pertenece a otro módulo.

Si un módulo no conoce una clave de `obra.json`:

DEBE CONSERVARLA.

Nunca:

* resetearla;
* eliminarla;
* reemplazarla por `{}`;
* reemplazarla por `[]`;
* sobrescribirla con un valor vacío.

Antes de modificar:

```text
app/contrato.py
```

analizar:

* `obra_vacia()`;
* `normalizar()`;
* `progreso()`;
* todas las funciones que leen y escriben el contrato.

Los cambios al contrato requieren especial cuidado.

---

# 10. COMPATIBILIDAD DE OBRAS

Las obras existentes son datos reales.

Una nueva versión del software no debe destruir información creada por versiones anteriores.

Cuando se agregue una nueva propiedad:

* proporcionar valor por defecto;
* mantener propiedades existentes;
* hacer el cambio compatible.

Si se necesita cambiar una estructura:

1. identificar versiones antiguas;
2. analizar compatibilidad;
3. implementar migración si corresponde;
4. preservar información.

Nunca realizar migraciones destructivas silenciosas.

---

# 11. EXTRACTOR

El extractor permite obtener elementos eléctricos desde planos PDF.

Puede trabajar con:

* símbolos;
* posiciones;
* calibración;
* elementos detectados;
* correcciones.

La extracción automática puede equivocarse.

Las correcciones manuales realizadas por el usuario tienen prioridad.

No sobrescribir automáticamente una corrección manual.

---

# 12. REVISOR

El revisor permite inspeccionar y corregir los elementos detectados.

Las modificaciones manuales del usuario deben considerarse intencionales.

Si una función automática vuelve a procesar los datos:

debe respetar las correcciones manuales existentes.

---

# 13. CIRCUITOS

El módulo de circuitos permite:

* crear circuitos;
* asignar elementos;
* visualizar circuitos;
* visualizar elementos sobre el plano;
* almacenar información descriptiva.

Los datos de circuitos pueden ser utilizados posteriormente por:

* tablero;
* presupuesto;
* materiales;
* documentación.

No cambiar el contrato de circuitos sin analizar sus consumidores.

---

# 14. ROUTEO / CANALIZACIÓN

El módulo:

```text
web/canaliza.html
```

corresponde visualmente a **Routeo**.

Internamente puede seguir utilizando nombres como:

```text
canaliza
canalizacion
```

Esto es intencional.

No renombrar todo el módulo simplemente para cambiar la terminología visual.

Routeo permite realizar el trazado de canalizaciones.

No reemplazar el módulo existente sin analizar primero su funcionamiento actual.

---

# 15. TABLERO

El módulo de tablero permite:

* dispositivos;
* térmicas;
* peines;
* conectores;
* cables;
* ruteo manual;
* posiciones;
* descripciones;
* PDF;
* guía de tapa.

## Conectores de peine

El modelo actual utiliza:

```text
conectorPeine
```

El concepto antiguo:

```text
puente
```

ya no corresponde al modelo actual.

No reintroducirlo.

La polaridad del conector se determina automáticamente según la barra del peine que toca.

No agregar selección manual de polaridad salvo solicitud explícita.

---

# 16. PRESUPUESTO

El presupuesto puede utilizar información de:

* obra;
* elementos;
* circuitos;
* precios;
* materiales;
* extras;
* opcionales;
* descuentos.

Los elementos sin correspondencia de precios no deben desaparecer silenciosamente.

Deben poder detectarse y corregirse.

---

# 17. PDF

Los PDFs son documentos profesionales.

No considerar suficiente que simplemente "se genere".

Verificar cuando corresponda:

* contenido;
* posiciones;
* márgenes;
* textos;
* tablas;
* saltos de página;
* superposición;
* legibilidad;
* consistencia visual.

Si el cambio es visual, generar y revisar el PDF real.

---

# 18. FRONTEND

El frontend utiliza HTML + JavaScript vanilla.

Antes de crear:

* una función;
* un componente;
* un estilo;
* una utilidad;

buscar primero si ya existe algo equivalente.

Reutilizar antes que duplicar.

Mantener:

* estilo visual;
* nombres;
* patrones;
* comportamiento.

No introducir frameworks frontend sin autorización.

---

# 19. BACKEND

El backend utiliza Python.

Mantener el diseño actual basado en `http.server`.

Evitar dependencias innecesarias.

Antes de agregar una dependencia:

1. verificar si la biblioteca estándar resuelve el problema;
2. evaluar impacto;
3. evaluar distribución con PyInstaller;
4. evaluar compatibilidad.

---

# 20. SEGURIDAD

Nunca incluir secretos en el repositorio.

Nunca guardar:

* tokens;
* passwords;
* API keys;
* credenciales;

en:

* código;
* HTML;
* JavaScript;
* PDFs;
* logs;
* commits;
* documentación.

La autenticación de GitHub debe permanecer del lado del backend.

---

# 21. GITHUB

El repositorio:

```text
myunis8/FY-App
```

contiene el código de FY Manager.

Las obras sincronizadas por el programa son otro concepto.

No mezclar:

```text
repositorio del programa
```

con:

```text
repositorios de obras
```

La protección contra conflictos mediante SHA debe conservarse.

No eliminar controles de concurrencia sin una razón explícita.

---

# 22. VERSIONADO

El proyecto utiliza versionado semántico.

La versión principal está definida en:

```text
app/__init__.py
```

Reglas:

PATCH:
correcciones y pequeños cambios compatibles.

MINOR:
nueva funcionalidad compatible.

MAJOR:
cambios incompatibles.

Antes de cambiar la versión analizar el tipo de modificación.

---

# 23. CHANGELOG

Los cambios relevantes deben registrarse en:

```text
CHANGELOG.md
```

No registrar cada modificación interna trivial.

Registrar:

* funcionalidades nuevas;
* cambios de comportamiento;
* correcciones importantes;
* cambios de arquitectura.

---

# 24. COMMITS

Los mensajes de commit deben ser:

* cortos;
* claros;
* en inglés.

Ejemplos:

```text
Add circuit descriptions
Fix PDF page overflow
Update budget calculation
Remove obsolete bridge logic
Improve panel rendering
```

No utilizar mensajes excesivamente largos.

El commit y el push son automáticos al terminar cada tarea (ver sección 4).

Antes de cada commit revisar:

```bash
git status
git diff
```

El commit prioriza los cambios relacionados con la tarea; si hay cambios
sueltos de otra cosa en el working tree, se incluyen igual (orden del usuario:
"commitees y pushees todo") y se avisa en la respuesta.

---

# 25. GIT DIFF

Antes de considerar terminada una tarea:

revisar siempre:

```bash
git diff
```

Buscar:

* cambios accidentales;
* archivos modificados sin relación;
* código duplicado;
* debugging olvidado;
* prints innecesarios;
* credenciales;
* cambios de formato masivos.

Si aparecen modificaciones ajenas a la tarea:

NO eliminarlas automáticamente.

Informar al usuario.

---

# 26. PRUEBAS

No considerar una tarea terminada simplemente porque el código "parece correcto".

Para backend:

* ejecutar el servidor;
* probar rutas;
* verificar respuestas;
* verificar persistencia.

Para frontend:

* abrir la página;
* probar interacción;
* probar formularios;
* revisar errores de consola;
* verificar estados.

Para PDFs:

* generar PDF;
* abrirlo;
* revisar contenido;
* revisar layout.

Para funcionalidades complejas:

usar pruebas automatizadas o navegador automatizado cuando estén disponibles.

---

# 27. BUGS

Cuando el usuario informa que una corrección no funcionó:

NO aplicar parches sucesivos a ciegas.

Primero:

1. reproducir;
2. observar;
3. identificar causa;
4. revisar datos;
5. revisar flujo;
6. corregir causa real.

No asumir que el diagnóstico anterior era correcto.

---

# 28. CAMBIOS DE ARQUITECTURA

Si una solicitud requiere:

* cambiar `obra.json`;
* cambiar el sistema de módulos;
* cambiar la persistencia;
* cambiar el servidor;
* cambiar el sistema de sincronización;
* introducir un framework;
* cambiar la arquitectura frontend;

primero explicar el impacto.

No implementar una modificación arquitectónica grande como parte de una solución rápida sin advertirlo.

---

# 29. AUTOMATIZACIÓN

Uno de los objetivos futuros de FY Manager es automatizar tareas de diseño y presupuestación.

La automatización debe ser:

* explicable;
* modificable;
* reversible;
* visible para el usuario.

El software debe asistir al profesional.

No ocultar decisiones importantes.

No asumir automáticamente que una decisión eléctrica es correcta si depende de información que el usuario no proporcionó.

---

# 30. CONTEXTO ELÉCTRICO

FY Manager está orientado a instalaciones eléctricas en Argentina.

Utilizar terminología habitual argentina.

Cuando corresponda utilizar criterios AEA.

No inventar requisitos normativos.

Distinguir entre:

* requisito normativo;
* buena práctica;
* decisión de diseño;
* simplificación del software.

Un cálculo automático debe dejar claro qué supuestos utiliza.

---

# 31. UX

FY Manager debe sentirse como una herramienta profesional.

Prioridades:

1. claridad;
2. rapidez;
3. consistencia;
4. confiabilidad;
5. facilidad de uso.

Evitar:

* modales innecesarios;
* pasos innecesarios;
* interfaces recargadas;
* animaciones decorativas;
* configuraciones difíciles de encontrar.

Las operaciones frecuentes deben requerir pocos pasos.

---

# 32. NO INVENTAR

Si falta información:

NO inventar.

Si no está claro:

* investigar en el código;
* revisar documentación;
* buscar usos existentes;
* preguntar al usuario si sigue siendo ambiguo.

Es preferible una pregunta breve a implementar una arquitectura incorrecta.

---

# 33. NO HACER REFACTORIZACIONES NO SOLICITADAS

Si el usuario pide:

> "agregar un botón"

no aprovechar la tarea para:

* reorganizar todo el frontend;
* renombrar archivos;
* cambiar arquitectura;
* reescribir CSS;
* cambiar el sistema de datos.

Si se detecta una mejora importante:

informarla por separado.

---

# 34. ZIP

El ZIP NO es el mecanismo normal de trabajo.

El desarrollo se realiza directamente sobre el repositorio local.

Sólo generar ZIP cuando:

* el usuario lo solicite;
* sea necesario distribuir una versión;
* sea necesario entregar una build.

Cuando se genere un ZIP:

1. verificar código;
2. actualizar versión si corresponde;
3. actualizar CHANGELOG;
4. generar ZIP;
5. descomprimirlo;
6. ejecutar la aplicación desde la copia;
7. verificar que funciona.

No incluir:

```text
.git/
__pycache__/
venv/
logs/
archivos temporales
```

salvo solicitud explícita.

---

# 35. RESPUESTAS DE CLAUDE CODE

Después de una tarea terminada, responder de forma concisa.

Formato recomendado:

```text
## Implementado

- ...
- ...

## Archivos modificados

- ...
- ...

## Pruebas

- ...
- ...

## Commit y push

`Add ...` — pusheado a `main`
```

No pegar nuevamente el contenido completo de los archivos modificados.

El usuario puede ver los cambios directamente en VS Code.

---

# 36. REGLA ESPECIAL PARA TAREAS COMPLEJAS

Si una tarea tiene muchas partes:

no intentar resolver todo de una vez sin validar.

Dividir en etapas.

Por ejemplo:

```text
1. Backend
2. Contrato de datos
3. Frontend
4. Persistencia
5. PDF
6. Pruebas
```

Después de cada etapa verificar que no se haya roto funcionalidad existente.

---

# 37. OBJETIVO DEL PROYECTO

El objetivo final es que FY Manager permita gestionar de forma integrada:

```text
PLANO
 ↓
EXTRACCIÓN
 ↓
REVISIÓN
 ↓
CIRCUITOS
 ↓
ROUTEO
 ↓
TABLERO
 ↓
MATERIALES
 ↓
PRESUPUESTO
 ↓
DOCUMENTACIÓN
```

manteniendo:

* datos consistentes;
* trazabilidad;
* control profesional;
* compatibilidad;
* facilidad de uso;
* arquitectura mantenible.

La prioridad no es agregar funcionalidades rápidamente.

La prioridad es construir una base sólida que permita agregar funcionalidades sin romper las existentes.
