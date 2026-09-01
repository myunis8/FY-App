"""Lista de materiales: un catálogo de productos/accesorios reusable entre
obras (peines, borneras, soportes, tornillería, cables, etc. -- las cosas
que no están en la lista de precios porque no se cobran por separado, pero
hay que comprarlas igual) más, por obra, cuántos de cada uno hacen falta.

El cómputo (cajas, térmicas, tablero, jabalina, metros de cable y caño) es
automático, a partir de los mismos datos que ya cargaron Circuitos, Tablero
y Routeo -- no hay nada nuevo que tipear para verlo. Sigue funcionando
aunque la obra esté en etapa preliminar: lo que depende de Routeo (cajas de
inspección, metros de cable/caño) simplemente no aparece hasta que se rutee
algo, en vez de fallar o inventar un número.

Cuando se actualiza el cómputo de una obra, cada renglón se intenta
matchear por nombre exacto contra el catálogo ya existente; si no matchea,
se crea uno nuevo ahí mismo -- así, obra tras obra, se usan siempre los
mismos nombres en vez de ir acumulando variantes parecidas.
"""
from __future__ import annotations
import json, math, heapq
from pathlib import Path
from . import config as cfgmod

ARCHIVO = "materiales.json"

CATEGORIAS = ["Accesorios de tablero", "Puesta a tierra", "Canalización externa",
              "Fijación y tornillería", "Cables y caños", "Otros"]

# catálogo de arranque: lo típico que no está en precios.py porque no se
# cobra por separado (es insumo, no un ítem de presupuesto), pero hay que
# comprarlo igual. Se puede ampliar, editar y reordenar desde el home.
SEMILLA = [
    ("Accesorios de tablero", "Peine para térmicas", "u"),
    ("Accesorios de tablero", "Conector para peine", "u"),
    ("Accesorios de tablero", "Riel DIN", "m"),
    ("Accesorios de tablero", "Bornera de paso", "u"),
    ("Puesta a tierra", "Bornera de tierra", "u"),
    ("Puesta a tierra", "Cable de PAT (jabalina a barra)", "m"),
    ("Canalización externa", "Soporte para caño externo", "u"),
    ("Canalización externa", "Soporte para corrugado", "u"),
    ("Canalización externa", "Curva/codo para caño externo", "u"),
    ("Fijación y tornillería", "Conector para caja", "u"),
    ("Fijación y tornillería", "Tornillo autoperforante", "u"),
    ("Fijación y tornillería", "Taco Fischer S6/S8", "u"),
]


def _ruta() -> Path:
    return cfgmod.DIR_CONFIG / ARCHIVO


def leer() -> dict:
    p = _ruta()
    if not p.exists():
        datos = {"actualizadoEl": 0, "items": [
            {"id": f"mt_{i+1:03d}", "categoria": cat, "item": it, "unidad": un,
             "link": "", "precioEstimado": None, "orden": i}
            for i, (cat, it, un) in enumerate(SEMILLA)]}
        guardar(datos)
        return datos
    try:
        datos = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"actualizadoEl": 0, "items": []}
    datos.setdefault("items", [])
    for i, it in enumerate(datos["items"]):
        it.setdefault("link", "")
        it.setdefault("precioEstimado", None)
        it.setdefault("orden", i)
    return datos


def guardar(datos: dict) -> dict:
    from .contrato import ahora
    datos["actualizadoEl"] = ahora()
    vistos = set()
    for i, it in enumerate(datos.get("items") or []):
        if not it.get("id") or it["id"] in vistos:
            it["id"] = f"mt_{ahora()}_{i}"
        vistos.add(it["id"])
        it.setdefault("orden", i)
        if it.get("precioEstimado") not in (None, ""):
            it["precioEstimado"] = float(it["precioEstimado"])
        else:
            it["precioEstimado"] = None
    cfgmod.DIR_CONFIG.mkdir(parents=True, exist_ok=True)
    _ruta().write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return datos


# ------------------------------------------------------------- cómputo
def computar_cajas(obra: dict) -> dict:
    """Cajas octogonales, rectangulares y de inspección: de lo que ya se
    extrajo o se agregó a mano en Routeo (`canalizacion.nodes`, que tiene
    el tipo exacto de caja de cada punto ruteado) -- es la fuente más fiel,
    porque ahí es donde de verdad se decide qué caja lleva cada punto.

    Si todavía no se ruteó nada, se aproxima con lo que ya hay en
    Circuitos (artefactos → octogonal, tomas/llaves/otros → rectangular),
    para que la obra preliminar también tenga un número, aclarando que es
    una aproximación."""
    canal = obra.get("canalizacion") or {}
    nodos = canal.get("nodes") or []
    if nodos:
        octogonales = sum(1 for n in nodos if n.get("kind") == "oct")
        rectangulares = sum(1 for n in nodos if n.get("kind") == "rect")
        inspeccion = sum(1 for n in nodos if n.get("kind") == "insp")
        return {"octogonales": octogonales, "rectangulares": rectangulares,
                "inspeccion": inspeccion, "fuente": "routeo"}
    elementos = obra.get("elementos") or []
    octogonales = sum(1 for e in elementos if e.get("tipo") == "artefacto")
    rectangulares = sum(1 for e in elementos if e.get("tipo") in ("toma", "llave", "otros"))
    return {"octogonales": octogonales, "rectangulares": rectangulares,
            "inspeccion": 0, "fuente": "aproximado"}


def computar_tableros(obra: dict) -> list[dict]:
    """Un renglón por tablero: bocas, niveles, y qué lleva adentro."""
    salida = []
    for t in obra.get("tableros") or []:
        dispositivos = t.get("dispositivos") or []
        general = next((d for d in dispositivos if d.get("tipo") == "termica" and d.get("rol") == "general"), None)
        diferencial = next((d for d in dispositivos if d.get("tipo") == "diferencial"), None)
        termicas = sum(1 for d in dispositivos if d.get("tipo") == "termica" and d.get("rol") != "general")
        protectores = sum(1 for d in dispositivos if d.get("tipo") == "protector")
        tierra = any(d.get("tipo") == "bornera" for d in dispositivos)
        salida.append({
            "id": t.get("id"), "nombre": t.get("nombre"), "fases": t.get("fases", 1),
            "bocas": t.get("bocas"), "niveles": t.get("pisos"),
            "general": bool(general), "diferencial": bool(diferencial),
            "termicas": termicas, "protectores": protectores, "jabalinaPAT": tierra,
        })
    return salida


def _fases_por_polos(polos) -> str:
    return "trifásica" if (polos or 2) >= 3 else "monofásica"


def computar_generales(obra: dict) -> list[dict]:
    """Protecciones de cabecera del tablero: interruptor general, interruptor
    diferencial y protector de tensión. Se agrupan por especificación entre
    TODOS los tableros de la obra, igual que computar_termicas() -- para
    comprar da lo mismo de qué tablero es cada una. No entran en
    computar_termicas() (que es sólo las seccionales, una por circuito)."""
    grupos: dict[tuple, dict] = {}
    for t in obra.get("tableros") or []:
        for d in t.get("dispositivos") or []:
            tipo, polos = d.get("tipo"), d.get("polos", 2)
            fases = _fases_por_polos(polos)
            if tipo == "termica" and d.get("rol") == "general":
                corr = d.get("corriente")
                etq = f"Interruptor general C{corr} {fases}" if corr else f"Interruptor general {fases}"
                clave = ("general", corr, polos)
            elif tipo == "diferencial":
                corr, sens = d.get("corriente"), d.get("sensibilidadMa")
                partes = ["Interruptor diferencial"]
                if corr:
                    partes.append(f"{corr} A")
                if sens:
                    partes.append(f"{sens} mA")
                partes.append(fases)
                etq = " ".join(partes)
                clave = ("diferencial", corr, sens, polos)
            elif tipo == "protector":
                etq = f"Protector de tensión {fases}"
                clave = ("protector", polos)
            else:
                continue
            g = grupos.setdefault(clave, {"tipo": clave[0], "etiqueta": etq, "cantidad": 0})
            g["cantidad"] += 1
    orden = {"general": 0, "diferencial": 1, "protector": 2}
    return sorted(grupos.values(), key=lambda g: (orden.get(g["tipo"], 9), g["etiqueta"]))


def computar_termicas(obra: dict) -> list[dict]:
    """Agrupa las térmicas de TODOS los tableros de la obra por corriente y
    polos (2 polos = monofásica, 3 o más = trifásica) -- para comprar da lo
    mismo de qué tablero es cada una. La curva no se pregunta en ningún
    lado de la app todavía: siempre es C, que es la que se usa en la
    práctica para circuitos residenciales, así que se etiqueta "C{A}"."""
    grupos: dict[tuple, int] = {}
    for t in obra.get("tableros") or []:
        for d in t.get("dispositivos") or []:
            if d.get("tipo") != "termica" or d.get("rol") == "general" or not d.get("corriente"):
                continue
            clave = (d.get("corriente"), d.get("polos", 2))
            grupos[clave] = grupos.get(clave, 0) + 1
    salida = []
    for (corriente, polos), cant in sorted(grupos.items(), key=lambda kv: (kv[0][1], kv[0][0] or 0)):
        fases = "trifásica" if polos >= 3 else "monofásica"
        salida.append({"corriente": corriente, "polos": polos, "fases": fases,
                       "etiqueta": f"Térmica C{corriente} {fases}", "cantidad": cant})
    return salida


def computar_jabalina(obra: dict):
    """Una jabalina + su caja de inspección por cada tablero con bornera de
    tierra. Sección y largo son el estándar AEA para instalaciones
    residenciales (jabalina copperweld 5/8" x 2,40 m) -- hoy no hay ningún
    campo para cargar uno distinto obra por obra; si en algún momento se
    agrega, éste es el lugar natural para leerlo en vez de este default."""
    cantidad = sum(1 for t in obra.get("tableros") or []
                   for d in (t.get("dispositivos") or []) if d.get("tipo") == "bornera")
    if not cantidad:
        return None
    return {"cantidad": cantidad, "seccion": "5/8\"", "largo": "2,40 m"}


def _resolve_z(nodo, z_cfg):
    if not nodo:
        return z_cfg.get("ceiling", 2.4)
    if nodo.get("z") is not None and not nodo.get("zAuto"):
        return nodo["z"]
    kind = nodo.get("kind")
    if kind == "tablero":
        return z_cfg.get("tablero", 1.5)
    if kind == "medidor":
        return z_cfg.get("medidor", 1.5)
    if kind == "jabalina":
        return z_cfg.get("jabalina", 0.3)
    device = nodo.get("device")
    if device and z_cfg.get(device) is not None:
        return z_cfg[device]
    return z_cfg.get("ceiling", 2.4)


def _run_horiz_m(run, px_por_m):
    pts = run.get("pts") or []
    total = 0.0
    for i in range(1, len(pts)):
        a, b = pts[i - 1], pts[i]
        total += math.hypot(b["x"] - a["x"], b["y"] - a["y"])
    return total / px_por_m if px_por_m else 0.0


def _run_vert_m(run, nodos_por_id, z_cfg):
    za = _resolve_z(nodos_por_id.get(run.get("a")), z_cfg)
    zb = _resolve_z(nodos_por_id.get(run.get("b")), z_cfg)
    if run.get("route") == "directo":
        return abs(za - zb)
    techo = z_cfg.get("ceiling", 2.4)
    return max(0.0, techo - za) + max(0.0, techo - zb)


def _grupo_de_cano(run):
    """Misma agrupación que usa Routeo (ver groupKey() en canaliza.html):
    dos tramos que van entre las mismas dos cajas, por el mismo tipo de
    recorrido, comparten un único caño físico -- si no se agruparan, ese
    caño se contaría una vez por cada cable que lleva adentro."""
    if run.get("share") is False or not run.get("a") or not run.get("b"):
        return "s:" + str(run.get("id"))
    ab = sorted([run["a"], run["b"]])
    return f"g:{ab[0]}|{ab[1]}:{run.get('route','techo')}"


def computar_canalizacion(obra: dict) -> dict:
    """Metros estimados de cable (por sección) y de caño (por diámetro),
    calculados con la misma lógica de Routeo (largo horizontal + bajadas,
    caños compartidos contados una sola vez) -- pero es una estimación:
    no reemplaza el cómputo detallado que arma el propio módulo Routeo."""
    canal = obra.get("canalizacion") or {}
    runs = canal.get("runs") or []
    px_por_m = canal.get("pxPerM")
    if not runs or not px_por_m:
        return {"disponible": False, "cablePorSeccion": {}, "canoPorDiametro": {},
                "totalCableM": 0.0, "totalCanoM": 0.0}
    nodos_por_id = {n["id"]: n for n in canal.get("nodes") or []}
    circuitos_por_id = {c["id"]: c for c in canal.get("circuits") or []}
    z_cfg = canal.get("z") or {}

    cable_por_seccion: dict = {}
    total_cable = 0.0
    for r in runs:
        c = circuitos_por_id.get(r.get("circuit")) or {}
        seccion = c.get("section") or 0
        largo = _run_horiz_m(r, px_por_m) + _run_vert_m(r, nodos_por_id, z_cfg)
        metros = largo * (r.get("cables") or 1)
        cable_por_seccion[seccion] = cable_por_seccion.get(seccion, 0.0) + metros
        total_cable += metros

    grupos: dict = {}
    for r in runs:
        grupos.setdefault(_grupo_de_cano(r), []).append(r)
    cano_por_diametro: dict = {}
    total_cano = 0.0
    for tramos in grupos.values():
        horiz = max((_run_horiz_m(r, px_por_m) for r in tramos), default=0.0)
        vert = max((_run_vert_m(r, nodos_por_id, z_cfg) for r in tramos), default=0.0)
        largo = horiz + vert
        dia = tramos[0].get("dia") or "sin especificar"
        cano_por_diametro[dia] = cano_por_diametro.get(dia, 0.0) + largo
        total_cano += largo

    return {
        "disponible": True,
        "cablePorSeccion": {k: round(v, 1) for k, v in cable_por_seccion.items()},
        "canoPorDiametro": {k: round(v, 1) for k, v in cano_por_diametro.items()},
        "totalCableM": round(total_cable, 1),
        "totalCanoM": round(total_cano, 1),
    }


def _dijkstra(adj: dict, inicio: str) -> dict:
    dist = {inicio: 0.0}
    cola = [(0.0, inicio)]
    while cola:
        d, u = heapq.heappop(cola)
        if d > dist.get(u, math.inf):
            continue
        for v, w in adj.get(u, {}).items():
            nd = d + w
            if nd < dist.get(v, math.inf):
                dist[v] = nd
                heapq.heappush(cola, (nd, v))
    return dist


def computar_verificaciones(obra: dict) -> dict:
    """Por circuito: la distancia más larga desde el tablero hasta el punto
    más alejado, siguiendo la canalización ya trazada en Routeo (tramo
    horizontal + bajadas, misma cuenta que computar_canalizacion). Es el dato
    de entrada para estimar la caída de tensión y fijar un límite de consumo;
    por ahora sólo informa la distancia, la sección y la protección de cada
    circuito, sin calcular la caída.

    Si hay más de un tablero, se toma la distancia al más cercano. Si un
    circuito tiene tramos pero ninguno llega a un tablero por la
    canalización, se informa igual con distancia nula."""
    canal = obra.get("canalizacion") or {}
    runs = canal.get("runs") or []
    px_por_m = canal.get("pxPerM")
    tablero_ids = {n["id"] for n in canal.get("nodes") or [] if n.get("kind") == "tablero"}
    if not runs or not px_por_m or not tablero_ids:
        return {"disponible": False, "circuitos": []}

    nodos_por_id = {n["id"]: n for n in canal.get("nodes") or []}
    z_cfg = canal.get("z") or {}
    runs_por_circuito: dict = {}
    for r in runs:
        runs_por_circuito.setdefault(r.get("circuit"), []).append(r)

    salida = []
    for c in canal.get("circuits") or []:
        tramos = runs_por_circuito.get(c.get("id")) or []
        if not tramos:
            continue
        adj: dict = {}
        for r in tramos:
            a, b = r.get("a"), r.get("b")
            if not a or not b:
                continue
            largo = _run_horiz_m(r, px_por_m) + _run_vert_m(r, nodos_por_id, z_cfg)
            for x, y in ((a, b), (b, a)):
                if largo < adj.setdefault(x, {}).get(y, math.inf):
                    adj[x][y] = largo
        inicios = [t for t in tablero_ids if t in adj]
        fila = {"id": c.get("id"), "nombre": c.get("name") or c.get("id"),
                "seccionMm2": c.get("section"), "proteccionA": c.get("prot") or None}
        if not inicios:
            salida.append({**fila, "distanciaM": None, "conectadoATablero": False})
            continue
        FUENTE = "\x00src"
        for t in inicios:
            adj.setdefault(FUENTE, {})[t] = 0.0
            adj.setdefault(t, {})[FUENTE] = 0.0
        dist = _dijkstra(adj, FUENTE)
        dist.pop(FUENTE, None)
        d_max = max((v for v in dist.values() if v < math.inf), default=0.0)
        salida.append({**fila, "distanciaM": round(d_max, 1), "conectadoATablero": True})
    return {"disponible": True, "circuitos": salida}


# --------------------------------------------------- auto-matcheo con la obra
def _renglones_computados(obra: dict) -> list:
    """(categoria, nombre, unidad, cantidad) de todo lo que sale solo del
    resto de la app -- la fuente de verdad para lo que se agrega a
    materiales.extras al actualizar el cómputo de una obra."""
    renglones = []
    cajas = computar_cajas(obra)
    if cajas["octogonales"]:
        renglones.append(("Otros", "Caja octogonal", "u", cajas["octogonales"]))
    if cajas["rectangulares"]:
        renglones.append(("Otros", "Caja rectangular", "u", cajas["rectangulares"]))
    if cajas["inspeccion"]:
        renglones.append(("Canalización externa", "Caja de inspección", "u", cajas["inspeccion"]))
    for gen in computar_generales(obra):
        renglones.append(("Accesorios de tablero", gen["etiqueta"], "u", gen["cantidad"]))
    for term in computar_termicas(obra):
        renglones.append(("Accesorios de tablero", term["etiqueta"], "u", term["cantidad"]))
    jaba = computar_jabalina(obra)
    if jaba:
        renglones.append(("Puesta a tierra", f'Jabalina {jaba["seccion"]} x {jaba["largo"]}',
                          "u", jaba["cantidad"]))
        renglones.append(("Puesta a tierra", "Caja de inspección para jabalina", "u", jaba["cantidad"]))
    canal = computar_canalizacion(obra)
    for seccion, metros in canal["cablePorSeccion"].items():
        if metros > 0:
            renglones.append(("Cables y caños", f"Cable {seccion} mm² (estimado)", "m", metros))
    for dia, metros in canal["canoPorDiametro"].items():
        if metros > 0:
            renglones.append(("Cables y caños", f"Caño {dia} (estimado)", "m", metros))
    for t in computar_tableros(obra):
        if t["bocas"]:
            renglones.append(("Accesorios de tablero",
                              f'Tablero de {t["bocas"]} bocas, {t["niveles"] or 1} nivel(es)', "u", 1))
    return renglones


def actualizar_computo_obra(obra: dict, materiales_obra: dict) -> dict:
    """Recalcula los renglones automáticos y los deja en
    materiales_obra["extras"], matcheando por nombre exacto contra el
    catálogo (y creando ahí lo que falte) -- sin tocar los renglones que el
    usuario haya agregado a mano, que no tienen origen "computo"."""
    catalogo = leer()
    por_nombre = {it["item"].strip().lower(): it for it in catalogo["items"]}
    cambio_catalogo = False
    from .contrato import ahora
    orden_max = max((it.get("orden", -1) for it in catalogo["items"]), default=-1)

    extras_computados = []
    for categoria, nombre, unidad, cantidad in _renglones_computados(obra):
        clave = nombre.strip().lower()
        existente = por_nombre.get(clave)
        if existente is None:
            orden_max += 1
            existente = {"id": f"mt_{ahora()}_{len(catalogo['items'])}", "categoria": categoria,
                        "item": nombre, "unidad": unidad, "link": "", "precioEstimado": None,
                        "orden": orden_max}
            catalogo["items"].append(existente)
            por_nombre[clave] = existente
            cambio_catalogo = True
        extras_computados.append({
            "id": f"me_auto_{existente['id']}", "catalogoId": existente["id"],
            "item": existente["item"], "categoria": existente["categoria"],
            "unidad": existente["unidad"], "cantidad": cantidad, "origen": "computo",
        })
    if cambio_catalogo:
        guardar(catalogo)

    extras_manuales = [e for e in (materiales_obra.get("extras") or []) if e.get("origen") != "computo"]
    materiales_obra["extras"] = extras_manuales + extras_computados
    return materiales_obra
