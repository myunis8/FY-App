"""Canalización: caños (tramos) que conectan cajas (nodos) para cada circuito.

Primera etapa, deliberadamente acotada frente a la app de referencia que se
usó como base (canaliza.html, ~2700 líneas): acá está el modelo de datos,
colocar cajas, trazar tramos ortogonales entre ellas, y sugerir el diámetro
de caño según cuántos conductores entran. Quedan para una próxima entrega:
el DRC completo (cruces, protecciones fuera de norma, etc.), el sistema de
cableado de iluminación (retornos por conductor), y el PDF de cómputo y
cableado detallado — son módulos grandes en sí mismos, y prefiero
entregarlos probados en vez de apurados.

Las coordenadas de nodos y tramos se guardan en el mismo sistema que los
elementos del plano (puntos del PDF, no píxeles), para reusar el mismo
render de /plano.png?zoom=N y no duplicar una calibración aparte.
"""
from __future__ import annotations
from . import contrato as C

# caños corrugados como se comercializan en Argentina
DIAS = [
    {"id": "5/8", "lbl": '5/8"', "mm": 16},
    {"id": "3/4", "lbl": '3/4"', "mm": 19},
    {"id": "7/8", "lbl": '7/8"', "mm": 22},
    {"id": "1", "lbl": '1"', "mm": 25},
    {"id": "1 1/4", "lbl": '1 1/4"', "mm": 32},
]
DEF_DIA = "7/8"

# conductores que entran por caño según su sección (tabla de llenado)
CAP0 = {
    "5/8": {1.5: 3, 2.5: 2, 4: 2, 6: 1, 10: 1, 16: 0},
    "3/4": {1.5: 5, 2.5: 4, 4: 3, 6: 2, 10: 2, 16: 1},
    "7/8": {1.5: 7, 2.5: 6, 4: 4, 6: 3, 10: 2, 16: 2},
    "1": {1.5: 9, 2.5: 8, 4: 6, 6: 4, 10: 3, 16: 2},
    "1 1/4": {1.5: 14, 2.5: 12, 4: 9, 6: 7, 10: 5, 16: 4},
}
MAXPROT = {1.5: 10, 2.5: 20, 4: 25, 6: 32, 10: 40, 16: 63}

KINDS = {
    "tablero": {"n": "Tablero", "ab": "TS"},
    "oct": {"n": "Caja octogonal", "ab": "CO"},
    "rect": {"n": "Caja rectangular", "ab": "CR"},
    "medidor": {"n": "Medidor", "ab": "MD"},
    "jabalina": {"n": "Jabalina", "ab": "JB"},
    "insp": {"n": "Caja de inspección", "ab": "CI"},
}
# tablero/medidor/jabalina son puntos únicos: se ven siempre, sin importar el
# filtro de circuitos activo (a diferencia de oct/rect/insp, que sí se filtran)
SIEMPRE_VISIBLES = ("tablero", "medidor", "jabalina")

INSP_SIZES = {
    "15x15": {"label": "15×15 cm", "max": 6},
    "20x20": {"label": "20×20 cm", "max": 10},
    "30x30": {"label": "30×30 cm", "max": 16},
    "custom": {"label": "Personalizada", "max": 8},
}
INSP_DEFAULT = "20x20"

ROUTES = {"techo": "Por cielorraso", "directo": "Directo entre cajas"}

REGLAS_DEFAULT = {"maxOct": 6, "maxRect": 8, "longRun": 15, "waste": 10, "spare": 20}


def _canal(obra: dict) -> dict:
    c = obra.setdefault("canalizacion", {})
    c.setdefault("nodos", [])
    c.setdefault("tramos", [])
    c.setdefault("conductores", [])
    c.setdefault("reglas", dict(REGLAS_DEFAULT))
    return c


def agregar_nodo(obra: dict, kind: str, x: float, y: float, label: str = "",
                 device: str | None = None, insp_size: str | None = None) -> tuple[dict | None, str]:
    if kind not in KINDS:
        return None, "Ese tipo de caja no existe."
    canal = _canal(obra)
    nodo = {"id": C.nuevo_id(), "kind": kind, "x": x, "y": y, "label": label,
           "device": device, "note": ""}
    if kind == "insp":
        nodo["inspSize"] = insp_size or INSP_DEFAULT
        nodo["inspLabel"] = INSP_SIZES.get(nodo["inspSize"], INSP_SIZES[INSP_DEFAULT])["label"]
        nodo["inspMax"] = INSP_SIZES.get(nodo["inspSize"], INSP_SIZES[INSP_DEFAULT])["max"]
    canal["nodos"].append(nodo)
    return nodo, ""


def mover_nodo(obra: dict, nodo_id: str, x: float, y: float) -> bool:
    canal = _canal(obra)
    n = next((x for x in canal["nodos"] if x["id"] == nodo_id), None)
    if n is None:
        return False
    n["x"], n["y"] = x, y
    return True


def eliminar_nodo(obra: dict, nodo_id: str) -> bool:
    canal = _canal(obra)
    n = len(canal["nodos"])
    canal["nodos"] = [x for x in canal["nodos"] if x["id"] != nodo_id]
    # los tramos que llegaban a esta caja quedan huérfanos de un lado: se
    # eliminan también, porque un caño sin las dos puntas no representa nada
    canal["tramos"] = [t for t in canal["tramos"] if t["a"] != nodo_id and t["b"] != nodo_id]
    return len(canal["nodos"]) < n


def sugerir_diametro(cantidad_por_seccion: dict[float, int]) -> str:
    """La sección más chica que entra sin pasarse de la tabla de llenado,
    para todas las secciones de conductor mezcladas en ese caño a la vez."""
    for dia in DIAS:
        tabla = CAP0[dia["id"]]
        ok = True
        for seccion, cant in cantidad_por_seccion.items():
            cap = tabla.get(seccion, 0)
            if cap <= 0 or cant > cap:
                ok = False
                break
        if ok:
            return dia["id"]
    return DIAS[-1]["id"]


def _existe_como_extremo(obra: dict, node_id: str) -> bool:
    """Un extremo de tramo puede ser una caja agregada a mano en este módulo
    (tablero, medidor, jabalina, caja de paso) o un elemento que ya viene del
    plano extraído (luminaria, toma, llave) — no hay que recrearlo acá."""
    canal = _canal(obra)
    if any(n["id"] == node_id for n in canal["nodos"]):
        return True
    if any(e["id"] == node_id for e in obra.get("elementos") or []):
        return True
    return False


def agregar_tramo(obra: dict, circuito_id: str, a: str, b: str, pts: list[dict],
                  route: str = "directo", cables: int = 2,
                  seccion: float = 1.5) -> tuple[dict | None, str]:
    canal = _canal(obra)
    if not _existe_como_extremo(obra, a):
        return None, "La caja de origen no existe."
    if not _existe_como_extremo(obra, b):
        return None, "La caja de destino no existe."
    if route not in ROUTES:
        return None, "Ese recorrido no existe."
    dia = sugerir_diametro({seccion: cables})
    tramo = {"id": C.nuevo_id(), "circuito": circuito_id, "a": a, "b": b,
            "pts": pts, "route": route, "dia": dia, "cables": cables,
            "seccion": seccion, "note": ""}
    canal["tramos"].append(tramo)
    return tramo, ""


def eliminar_tramo(obra: dict, tramo_id: str) -> bool:
    canal = _canal(obra)
    n = len(canal["tramos"])
    canal["tramos"] = [t for t in canal["tramos"] if t["id"] != tramo_id]
    return len(canal["tramos"]) < n


def longitud_m(tramo: dict, pt_por_metro: float) -> float:
    pts = tramo.get("pts") or []
    total = 0.0
    for i in range(len(pts) - 1):
        dx = pts[i + 1]["x"] - pts[i]["x"]
        dy = pts[i + 1]["y"] - pts[i]["y"]
        total += (dx * dx + dy * dy) ** 0.5
    return total / pt_por_metro if pt_por_metro else 0.0
