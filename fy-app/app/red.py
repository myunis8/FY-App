"""Módulo Red: oferta de productos de datos/domótica por obra, y un plano de
red propio (mismo plano/escala que Routeo, canalización separada de
canalizacion.runs -- ver contrato.py).

Este archivo es lógica pura, sin acceso a disco: normalización de
obra["red"] vive en contrato.obra_vacia()/normalizar() (ese contrato ya
garantiza que una obra vieja sin "red" abre con {"ofertas":[],
"dispositivos":[],"tramos":[]}, y que ningún módulo borra claves que no
entiende).
"""
from __future__ import annotations
import math

TIPOS_DISPOSITIVO = {
    "entrada":    "Entrada de servicio / acometida de datos",
    "router":     "Router",
    "switch":     "Switch",
    "switch_poe": "Switch PoE",
    "ap":         "Access point",
    "mesh":       "Nodo mesh",
    "camara":     "Cámara",
    "nvr":        "NVR",
    "nas":        "NAS",
    "ups":        "UPS",
    "rack":       "Rack",
    "patchera":   "Patchera",
    "rj45":       "Boca RJ45",
    "sensor":     "Sensor inteligente",
    "hub":        "Hub domótico",
}
MEDIOS = {"exterior": "Exterior", "utp": "UTP", "fibra": "Fibra", "inalambrico": "Inalámbrico"}
MEDIOS_INALAMBRICOS = {"inalambrico"}
# estos dispositivos pueden vivir sólo de un tramo inalámbrico (mesh↔mesh,
# sensor↔hub): no se avisa "sin conexión" si no tienen ningún tramo cableado
TIPOS_PUEDEN_SER_INALAMBRICOS = {"mesh", "sensor"}

UTP_MAX_M = 90.0                              # canal permanente, límite habitual de cobre estructurado
CONSUMO_POE_DEFAULT_W = {"camara": 8.0, "ap": 12.0}   # si el dispositivo no cargó el propio a mano
SEPARACION_TOL_M = 0.15                       # "van pegados": tolerancia de distancia perpendicular
SEPARACION_MIN_M = 0.5                        # longitud mínima de solapamiento para contar como "coincide"


# --------------------------------------------------------------- oferta
def totales_oferta(ofertas: list[dict]) -> dict:
    """Total ofrecido, total aceptado y cantidad de rechazados -- el resumen
    que se muestra arriba de la pestaña Oferta."""
    def suma(items):
        return sum(float(o.get("precioUnitario") or 0) * float(o.get("cantidad") or 0) for o in items)
    rechazados = sum(1 for o in ofertas if o.get("estado") == "rechazado")
    return {
        "ofrecido": round(suma(ofertas), 2),
        "aceptado": round(suma([o for o in ofertas if o.get("estado") == "aceptado"]), 2),
        "rechazados": rechazados,
    }


def ofertas_aceptadas(red: dict) -> list[dict]:
    """Lo que realmente entra al presupuesto -- única fuente de verdad,
    ver presupuesto.totales()."""
    return [o for o in (red or {}).get("ofertas") or [] if o.get("estado") == "aceptado"]


# ------------------------------------------------------------ geometría
def _dist(a, b):
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


def tramo_len_px(t: dict) -> float:
    pts = t.get("puntos") or []
    return sum(_dist(pts[i - 1], pts[i]) for i in range(1, len(pts)))


def tramo_len_m(t: dict, px_por_m: float | None) -> float:
    """0 para tramos inalámbricos (no son canalización) o sin escala."""
    if not px_por_m or (t.get("medio") in MEDIOS_INALAMBRICOS):
        return 0.0
    return tramo_len_px(t) / px_por_m


def _orientacion(p1, p2):
    return "h" if abs(p2["x"] - p1["x"]) >= abs(p2["y"] - p1["y"]) else "v"


def _segmentos_coinciden(a1, a2, b1, b2, tol_px: float, min_px: float) -> bool:
    """Simplificación deliberada (ver propuesta al usuario): los dos tramos
    son ortogonales (misma convención que Routeo), así que alcanza con
    comparar orientación + distancia perpendicular entre líneas medias +
    solapamiento proyectado. No es una regla AEA puntual, es un aviso de
    "van pegados, revisá si comparten bandeja"."""
    if _orientacion(a1, a2) != _orientacion(b1, b2):
        return False
    if _orientacion(a1, a2) == "h":
        if abs((a1["y"] + a2["y"]) / 2 - (b1["y"] + b2["y"]) / 2) > tol_px:
            return False
        lo = max(min(a1["x"], a2["x"]), min(b1["x"], b2["x"]))
        hi = min(max(a1["x"], a2["x"]), max(b1["x"], b2["x"]))
    else:
        if abs((a1["x"] + a2["x"]) / 2 - (b1["x"] + b2["x"]) / 2) > tol_px:
            return False
        lo = max(min(a1["y"], a2["y"]), min(b1["y"], b2["y"]))
        hi = min(max(a1["y"], a2["y"]), max(b1["y"], b2["y"]))
    return (hi - lo) >= min_px


# ------------------------------------------------------------------ DRC
def verificar(obra: dict, px_por_m: float | None) -> list[dict]:
    """Avisos del módulo Red -- mismo shape que el DRC de Routeo
    ({lvl, txt, target, cat}), para poder reusar el mismo patrón de modal
    clickeable que centra y resalta el elemento en el plano."""
    red = obra.get("red") or {}
    dispositivos = red.get("dispositivos") or []
    tramos = red.get("tramos") or []
    por_id = {d["id"]: d for d in dispositivos if d.get("id")}
    avisos: list[dict] = []

    def push(lvl, txt, target, cat):
        avisos.append({"lvl": lvl, "txt": txt, "target": target, "cat": cat})

    def nombre(d):
        return TIPOS_DISPOSITIVO.get(d.get("tipo"), d.get("tipo") or "Dispositivo")

    # 1) recorrido entrada -> router
    entradas = [d["id"] for d in dispositivos if d.get("tipo") == "entrada"]
    routers = [d["id"] for d in dispositivos if d.get("tipo") == "router"]
    adj: dict[str, list[str]] = {}
    for t in tramos:
        a, b = t.get("desde"), t.get("hasta")
        if a and b:
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
    if entradas and routers:
        vistos, cola = set(entradas), list(entradas)
        while cola:
            n = cola.pop()
            for v in adj.get(n, []):
                if v not in vistos:
                    vistos.add(v)
                    cola.append(v)
        if not any(r in vistos for r in routers):
            push("e", "No hay un recorrido de red desde la entrada de servicio hasta el router.",
                 routers[0], "conectividad")
    elif routers and not entradas:
        push("w", "No hay ninguna entrada de servicio exterior ubicada en el plano.",
             routers[0], "conectividad")
    elif entradas and not routers:
        push("w", "No hay ningún router ubicado en el plano.", entradas[0], "conectividad")

    # 2) dispositivos cableados sin conexión
    conectados = set()
    for t in tramos:
        if t.get("desde"):
            conectados.add(t["desde"])
        if t.get("hasta"):
            conectados.add(t["hasta"])
    for d in dispositivos:
        if d.get("tipo") in TIPOS_PUEDEN_SER_INALAMBRICOS:
            continue
        if d["id"] not in conectados:
            push("w", f"{nombre(d)} sin ningún tramo conectado a la red.", d["id"], "conectividad")

    # 3) UTP > 90 m
    for t in tramos:
        if t.get("medio") == "utp":
            L = tramo_len_m(t, px_por_m)
            if L > UTP_MAX_M:
                push("w", f"Tramo UTP de {L:.1f} m supera los {UTP_MAX_M:.0f} m de un canal "
                     "permanente de cobre estructurado.", t.get("desde"), "utp")

    # 4) presupuesto PoE por switch
    for d in dispositivos:
        if d.get("tipo") != "switch_poe" or not d.get("poeW"):
            continue
        consumo = 0.0
        for t in tramos:
            if t.get("desde") != d["id"] and t.get("hasta") != d["id"]:
                continue
            otro_id = t["hasta"] if t.get("desde") == d["id"] else t.get("desde")
            otro = por_id.get(otro_id)
            if not otro:
                continue
            w = otro.get("consumoPoeW")
            if w is None:
                w = CONSUMO_POE_DEFAULT_W.get(otro.get("tipo"), 0.0)
            consumo += w or 0.0
        if consumo > d["poeW"]:
            push("e", f"Switch PoE: {consumo:.0f} W conectados superan los {d['poeW']:.0f} W "
                 "disponibles.", d["id"], "poe")

    # 5) separación datos/energía (ver propuesta: simplificación geométrica,
    # no una regla AEA puntual -- sólo avisa "revisá esto", no certifica nada)
    canal_runs = (obra.get("canalizacion") or {}).get("runs") or []
    if px_por_m and canal_runs:
        tol_px = SEPARACION_TOL_M * px_por_m
        min_px = SEPARACION_MIN_M * px_por_m
        for t in tramos:
            if t.get("medio") in MEDIOS_INALAMBRICOS:
                continue
            pts = t.get("puntos") or []
            encontrado = False
            for i in range(1, len(pts)):
                if encontrado:
                    break
                for r in canal_runs:
                    rp = r.get("pts") or []
                    for j in range(1, len(rp)):
                        if _segmentos_coinciden(pts[i - 1], pts[i], rp[j - 1], rp[j], tol_px, min_px):
                            push("w", "Un tramo de red corre pegado a un caño de energía -- "
                                 "no deberían compartir bandeja/caño.", t.get("desde"), "separacion")
                            encontrado = True
                            break
                    if encontrado:
                        break
    return avisos
