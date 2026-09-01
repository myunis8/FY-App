# FY Manager

Servidor local en Python + interfaz HTML. Cada obra es un `obra.json` que se
guarda en este equipo y se espeja en un repositorio privado de GitHub.

## Probar sin compilar

```
python obras.py
```

Levanta el servidor en un puerto libre y abre el navegador solo.
Para salir, cerrá la ventana de la consola.

## Compilar el .exe

Doble clic en `build.bat`. Queda en `dist\FY Manager.exe`, un archivo
único que no necesita instalación ni Python en la máquina donde corre.

## Preparar el repositorio (una sola vez)

1. En GitHub: **New repository** → nombre `obras` → **Private** → Create.
2. Perfil → Settings → Developer settings → **Personal access tokens** →
   Fine-grained tokens → Generate new token.
   - Repository access: **Only select repositories** → `obras`
   - Permissions → Repository permissions → **Contents: Read and write**
   - Vencimiento: el que prefieras (anotá la fecha, hay que renovarlo).
3. En la app: **Configuración** → pegá `usuario/obras` y el token →
   **Probar acceso** → **Guardar**.

> **Si "Probar acceso" dice que podés leer pero no escribir**, al token le falta
> `Contents: Read and write`. En GitHub, editá el token, cambiá el permiso,
> guardá y **volvé a pegarlo en la app** (al cambiar permisos el valor no
> cambia, pero conviene confirmar que estás usando el token correcto).
>
> El botón escribe un archivo mínimo en `.obras-app/conexion.json` del
> repositorio. Es la única forma confiable de verificar: GitHub informa tu rol
> como dueño del repositorio, no los permisos del token, así que un token de
> sólo lectura sobre tu propio repo igual aparenta poder escribir.

Para quien sólo consulta: el mismo procedimiento pero con
**Contents: Read-only**. La app detecta el permiso real y le oculta las
acciones de escritura.

## Dónde quedan las cosas

| Qué | Dónde |
|---|---|
| Obras | `%LOCALAPPDATA%\FY Manager\obras\<id>\` |
| Configuración y token | `%APPDATA%\FY Manager\config.json` |
| Plano PDF | junto a la obra, como archivo aparte (nunca dentro del JSON) |
| En el repositorio | `obras/<id>/obra.json` y `obras/<id>/resumen.json` |

El token **nunca** se empaqueta en el `.exe` ni viaja al navegador: el pedido a
GitHub lo hace Python.

## Cómo evita pisar trabajo

Al bajar o subir una obra se guarda el `sha` del archivo. Antes de subir, la app
compara ese `sha` con el que hay en el repositorio. Si no coinciden, alguien
escribió en el medio: no pisa nada y avisa, con la opción de forzar.

No hay ningún archivo compartido entre obras, así que dos personas trabajando
en obras distintas nunca chocan.

## Versionado

El código va en un repositorio **distinto** al de las obras: uno es el programa,
el otro son los datos. Mezclarlos hace que cada guardado de una obra ensucie el
historial del código.

```
git init
git add .
git commit -m "Add local server, obra.json contract and PDF extractor"
git branch -M main
git remote add origin https://github.com/USUARIO/obras-app.git
git push -u origin main
```

Los mensajes de commit van en inglés, en imperativo y en una línea:
`Add ...`, `Fix ...`, `Change ...`, `Remove ...`.

## Estructura

```
app/
  config.py     rutas de datos y configuración del usuario
  contrato.py   obra.json v1: creación, normalización, resumen derivado
  almacen.py    lectura y escritura en disco
  github.py     cliente de la API (sin dependencias externas)
  sync.py       bajar el espejo, traer y subir obras
  server.py     servidor local y API
  main.py       arranque
web/
  index.html    tablero
```

## Qué falta

Los módulos se enchufan sobre este esqueleto, cada uno declarando qué bloques
del contrato consume y cuáles produce:

1. **Extractor** — lee el PDF y llena `plano` y `elementos`. *(hecho)*
2. **Circuitos** — se seleccionan por zona sobre el plano y llena `circuitos`. *(hecho)*
3. **Precios y presupuesto** — lista global congelable por obra, extras,
   opcionales, descuentos y PDF con logo y marca de agua. *(hecho)*
4. **Tablero** — presets de gabinete, distribución automática y arrastre
   gráfico de térmicas por riel. *(hecho, falta el dibujo del conexionado)*
3. **Validador** — función pura `validar(obra)`, llena `validacion`.
4. **Canalización** — `canaliza.html` adaptado al contrato.
5. **Cómputo** — deriva `computo` desde `canalizacion` y `circuitos`.
6. **Presupuesto** — `presupuestos-app.html` adaptado al contrato.

Regla de oro: ningún módulo borra claves que no entiende, para que una versión
vieja no destruya datos de una nueva.

## Backlog / a futuro

- **PDF consolidado de entrega**: un solo PDF que junte routeo (canalización),
  tablero (conexionado + guía de tapa) y presupuesto (materiales), pensado
  para entregarle una sola pieza al cliente en vez de varios archivos
  sueltos. Debería armarse de forma que sea fácil sumarle más secciones
  cuando aparezcan módulos nuevos (por ejemplo, automatizaciones) sin tener
  que rehacer el armado cada vez — cada módulo aporta su(s) página(s) ya
  generadas y esto sólo las concatena con una portada/índice.

<!-- push test: 2026-09-01 -->

