"""Modelo geométrico de un proyecto de Routeo, portado de web/canaliza.html.

Es el mismo modelo que arma `buildProjectData()` en el navegador (circuits,
nodes, runs, wires, pxPerM, z, rules). Acá se reimplementan -- con los mismos
nombres y la misma lógica que sus funciones JS equivalentes -- los cálculos que
el PDF necesita y que hasta ahora sólo vivían en el cliente: agrupamiento de
caños, longitudes, cruces, lista de conductores por caño y cómputo de
materiales.

El editor interactivo del plano sigue usando su copia en JS; ésta es la que
consume `app/pdf_routeo.py` para generar el PDF del lado del servidor, igual
que el resto de los módulos.
"""
from __future__ import annotations
import math

# caños corrugados como se comercializan en Argentina (== DIAS en canaliza.html)
DIAS = [
    {"id": "5/8", "lbl": '5/8"', "mm": 16},
    {"id": "3/4", "lbl": '3/4"', "mm": 19},
    {"id": "7/8", "lbl": '7/8"', "mm": 22},
    {"id": "1", "lbl": '1"', "mm": 25},
    {"id": "1 1/4", "lbl": '1 1/4"', "mm": 32},
]

CAP0 = {                                   # conductores por caño según sección
    "5/8":   {1.5: 3, 2.5: 2, 4: 2, 6: 1, 10: 1, 16: 0},
    "3/4":   {1.5: 5, 2.5: 4, 4: 3, 6: 2, 10: 2, 16: 1},
    "7/8":   {1.5: 7, 2.5: 6, 4: 4, 6: 3, 10: 2, 16: 2},
    "1":     {1.5: 9, 2.5: 8, 4: 6, 6: 4, 10: 3, 16: 2},
    "1 1/4": {1.5: 14, 2.5: 12, 4: 9, 6: 7, 10: 5, 16: 4},
}

Z0 = {"ceiling": 2.60, "tablero": 1.80, "luminaria": 2.60, "interruptor": 1.20,
      "toma": 0.30, "especial": 1.20, "paso": 2.60, "medidor": 1.50, "jabalina": 0}

RULES0 = {"maxOct": 4, "maxRect": 3, "longRun": 25, "waste": 10, "spare": 15}
INSP_MAX_DEFAULT = 10                       # caños en una caja de inspección (== INSP_SIZES 20x20)

CROSS_CLEARANCE_M = 0.08                    # separación mínima para "resuelto en altura"
# tolerancia (px del plano) para no marcar como cruce el empalme dentro de una
# caja compartida. En canaliza.html sale de snapRadius()*2, que depende del zoom
# de pantalla; acá se fija en un valor equivalente al de una vista típica.
SNAP_TOL_PX = 36.0

LIGHT_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

WIRE_COLOR_MAP = {
    "tomas":     ["Marrón (fase)", "Celeste (neutro)", "Verde-amarillo (tierra)"],
    "especial":  ["Marrón (fase)", "Celeste (neutro)", "Verde-amarillo (tierra)"],
    "exterior":  ["Marrón (fase)", "Celeste (neutro)", "Verde-amarillo (tierra)"],
    "acometida": ["Marrón (fase)", "Celeste (neutro)", "Verde-amarillo (tierra)"],
    "tierra":    ["Verde-amarillo (tierra)"],
}
WIRE_HEX = {
    "Marrón (fase)": "#7a4a25",
    "Celeste (neutro)": "#49a9d8",
    "Blanco (retorno simple)": "#e9e9e9",
    "Amarillo (retorno combinado)": "#e8c93a",
    "Verde-amarillo (tierra)": "#6a9a2e",
}
RS_SHADES = ["#e9e9e9", "#aeaeae", "#767676"]
RC_SHADES = ["#e8c93a", "#c79a2a", "#96701a"]

DEV_KIND = {"iluminacion": "Iluminación", "tomas": "Tomacorrientes", "especial": "Especial",
            "exterior": "Exterior", "acometida": "Acometida", "tierra": "Puesta a tierra"}


def dia_of(did):
    for d in DIAS:
        if d["id"] == did:
            return d
    return DIAS[2]


def dia_lbl(did):
    return dia_of(did)["lbl"]


def cond_width(section):
    s = section or 0
    if s >= 10:
        return 4.4
    if s >= 6:
        return 3.7
    if s >= 4:
        return 3.1
    if s >= 2.5:
        return 2.5
    return 1.4


def _dist(a, b):
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


def seg_intersect(p1, p2, p3, p4):
    d1x, d1y = p2["x"] - p1["x"], p2["y"] - p1["y"]
    d2x, d2y = p4["x"] - p3["x"], p4["y"] - p3["y"]
    denom = d1x * d2y - d1y * d2x
    if abs(denom) < 1e-9:
        return None
    t = ((p3["x"] - p1["x"]) * d2y - (p3["y"] - p1["y"]) * d2x) / denom
    u = ((p3["x"] - p1["x"]) * d1y - (p3["y"] - p1["y"]) * d1x) / denom
    if 0.03 < t < 0.97 and 0.03 < u < 0.97:
        return {"x": p1["x"] + t * d1x, "y": p1["y"] + t * d1y, "t": t, "u": u}
    return None


def path_fraction(pts, seg_idx, t):
    total = sum(_dist(pts[i - 1], pts[i]) for i in range(1, len(pts)))
    if total <= 0:
        return 0.0
    acc = sum(_dist(pts[i - 1], pts[i]) for i in range(1, seg_idx))
    acc += _dist(pts[seg_idx - 1], pts[seg_idx]) * t
    return acc / total


def offset_poly(pts, d):
    if not d:
        return pts
    out = []
    for i, p in enumerate(pts):
        a = pts[i - 1] if i > 0 else None
        b = pts[i + 1] if i < len(pts) - 1 else None
        nx = ny = 0.0
        if a:
            dx, dy = p["x"] - a["x"], p["y"] - a["y"]
            L = math.hypot(dx, dy) or 1
            nx += -dy / L
            ny += dx / L
        if b:
            dx, dy = b["x"] - p["x"], b["y"] - p["y"]
            L = math.hypot(dx, dy) or 1
            nx += -dy / L
            ny += dx / L
        L = math.hypot(nx, ny) or 1
        nx, ny = nx / L, ny / L
        out.append({"x": p["x"] + nx * d, "y": p["y"] + ny * d})
    return out


class Proyecto:
    """Envuelve el dict de `buildProjectData()` y expone los cálculos del PDF."""

    def __init__(self, proy: dict, ocultos=None):
        self.circuits = proy.get("circuits") or []
        self.nodes = proy.get("nodes") or []
        self.runs = proy.get("runs") or []
        self.wires = proy.get("wires") or []
        self.px_per_m = proy.get("pxPerM")
        self.base_name = proy.get("baseName") or "plano"
        self.z = {**Z0, **(proy.get("z") or {})}
        r = proy.get("rules") or {}
        self.rules = {**RULES0, **{k: v for k, v in r.items() if k != "cap"}}
        # las claves de sección llegan como string tras pasar por obra.json
        # ("1.5", "4", ...); se normalizan a float para poder indexar por c.section
        cap_src = r.get("cap") or CAP0
        self.cap = {d: {float(k): v for k, v in (row or {}).items()}
                    for d, row in cap_src.items()}
        self.hidden = set(ocultos or [])
        self._by_node = {n["id"]: n for n in self.nodes}
        self._by_circ = {c["id"]: c for c in self.circuits}
        # cuántos tramos "por cielorraso" llegan a cada nodo, para repartir la
        # bajada de esa caja (ver run_vert_m -- mismo criterio que runVert() en
        # canaliza.html y _run_vert_m() en materiales.py)
        self._grados_techo: dict = {}
        for rr in self.runs:
            if rr.get("route") == "directo":
                continue
            for k in ("a", "b"):
                nid = rr.get(k)
                if nid:
                    self._grados_techo[nid] = self._grados_techo.get(nid, 0) + 1

    # ---------------------------------------------------------------- básicos
    def node(self, nid):
        return self._by_node.get(nid)

    def circuit(self, cid):
        return self._by_circ.get(cid)

    def is_ci_visible(self, cid):
        return cid not in self.hidden

    def resolve_z(self, n):
        if not n:
            return self.z["ceiling"]
        if n.get("z") is not None and not n.get("zAuto"):
            return n["z"]
        k = n.get("kind")
        if k in ("tablero", "medidor", "jabalina"):
            return self.z[k]
        dev = n.get("device")
        return self.z[dev] if dev in self.z and self.z[dev] is not None else self.z["ceiling"]

    # ------------------------------------------------------------- longitudes
    def run_len_px(self, r):
        p = r.get("pts") or []
        return sum(_dist(p[i - 1], p[i]) for i in range(1, len(p)))

    def run_horiz_m(self, r):
        return self.run_len_px(r) / self.px_per_m if self.px_per_m else 0.0

    def run_vert_m(self, r):
        """MISMA LÓGICA QUE runVert() en canaliza.html y _run_vert_m() en
        materiales.py. "por cielorraso": la bajada de cada caja se reparte
        entre los tramos por cielorraso que llegan a ella, así una caja
        intermedia de una cadena al mismo nivel no cuenta su bajada una vez
        por tramo."""
        za = self.resolve_z(self.node(r.get("a")))
        zb = self.resolve_z(self.node(r.get("b")))
        if r.get("route") == "directo":
            return abs(za - zb)
        c = self.z["ceiling"]
        da = max(1, self._grados_techo.get(r.get("a"), 1))
        db = max(1, self._grados_techo.get(r.get("b"), 1))
        return max(0.0, c - za) / da + max(0.0, c - zb) / db

    def run_len_m(self, r):
        return (self.run_horiz_m(r) + self.run_vert_m(r)) if self.px_per_m else 0.0

    # ------------------------------------------------------- caños (grupos)
    @staticmethod
    def group_key(r):
        if r.get("share") is False or not r.get("a") or not r.get("b"):
            return "s:" + str(r.get("id"))
        ab = sorted([r["a"], r["b"]])
        return f"g:{ab[0]}|{ab[1]}:{r.get('route', 'techo')}"

    def cap_of(self, dia, sec):
        row = self.cap.get(dia)
        try:
            return int(row.get(float(sec), 0)) if row else 0
        except (TypeError, ValueError):
            return 0

    def fill_ratio(self, dia, runs):
        f = 0.0
        for r in runs:
            c = self.circuit(r.get("circuit"))
            if not c:
                continue
            cap = self.cap_of(dia, c.get("section"))
            if cap <= 0:
                return math.inf
            f += (r.get("cables") or 0) / cap
        return f

    def conduit_groups(self):
        m = {}
        for r in self.runs:
            k = self.group_key(r)
            g = m.get(k)
            if g is None:
                g = {"key": k, "runs": [], "dia": r.get("dia"), "a": r.get("a"),
                     "b": r.get("b"), "route": r.get("route")}
                m[k] = g
            g["runs"].append(r)
            if dia_of(r.get("dia"))["mm"] > dia_of(g["dia"])["mm"]:
                g["dia"] = r.get("dia")
        for g in m.values():
            g["horiz"] = max(self.run_horiz_m(r) for r in g["runs"])
            g["vert"] = max(self.run_vert_m(r) for r in g["runs"])
            g["len"] = g["horiz"] + g["vert"]
            g["cables"] = sum(r.get("cables") or 0 for r in g["runs"])
            g["fill"] = self.fill_ratio(g["dia"], g["runs"])
        return m

    # ------------------------------------------------------------- cruces
    def group_z_at_fraction(self, g, frac):
        if (g.get("route") or "techo") == "techo":
            return self.z["ceiling"]
        za = self.resolve_z(self.node(g.get("a")))
        zb = self.resolve_z(self.node(g.get("b")))
        return za + (zb - za) * frac

    def find_crossings(self):
        groups = [g for g in self.conduit_groups().values() if len(g["runs"][0].get("pts") or []) > 1]
        out = []
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                A, B = groups[i], groups[j]
                shared = [x for x in (A["a"], A["b"]) if x and (x == B["a"] or x == B["b"])]
                pa, pb = A["runs"][0]["pts"], B["runs"][0]["pts"]
                for x in range(1, len(pa)):
                    for y in range(1, len(pb)):
                        ip = seg_intersect(pa[x - 1], pa[x], pb[y - 1], pb[y])
                        if not ip:
                            continue
                        if shared:
                            near = any((self.node(nid) and _dist(self.node(nid), ip) < SNAP_TOL_PX)
                                       for nid in shared)
                            if near:
                                continue
                        zA = self.group_z_at_fraction(A, path_fraction(pa, x, ip["t"]))
                        zB = self.group_z_at_fraction(B, path_fraction(pb, y, ip["u"]))
                        diff = abs(zA - zB)
                        out.append({"a": A, "b": B, "pt": ip, "zA": zA, "zB": zB,
                                    "diff": diff, "safe": diff >= CROSS_CLEARANCE_M})
        return out

    # ------------------------------------------------------- conductores
    def wire_colors_for(self, c):
        base = WIRE_COLOR_MAP.get(c.get("kind"), [])
        return [base[i] if i < len(base) else f"Conductor {i + 1}" for i in range(c.get("cables") or 0)]

    @staticmethod
    def wire_code(w):
        k = w.get("kind")
        if k == "F":
            return "F"
        if k == "N":
            return "N"
        if k == "RS":
            return "RS-" + str(w.get("light"))
        if k == "RC":
            return "RC-" + str(w.get("light")) + str(w.get("branch"))
        return "?"

    def wire_shade_index(self, w):
        letras = sorted({x.get("light") for x in self.wires
                         if x.get("circuit") == w.get("circuit") and x.get("kind") == w.get("kind")})
        try:
            return max(0, letras.index(w.get("light")))
        except ValueError:
            return 0

    def wire_hex(self, w):
        k = w.get("kind")
        if k == "F":
            return WIRE_HEX["Marrón (fase)"]
        if k == "N":
            return WIRE_HEX["Celeste (neutro)"]
        if k == "RS":
            return RS_SHADES[min(self.wire_shade_index(w), len(RS_SHADES) - 1)]
        if k == "RC":
            return RC_SHADES[min(self.wire_shade_index(w), len(RC_SHADES) - 1)]
        return "#5b6470"

    def conduit_conductors(self, vis):
        items = []

        def order(w):
            if w.get("kind") == "F":
                return -2
            if w.get("kind") == "N":
                return -1
            li = LIGHT_LETTERS.find(w.get("light") or "")
            return li * 10 + (w.get("branch") if w.get("kind") == "RC" else 0.5)

        for r in vis:
            c = self.circuit(r.get("circuit"))
            if not c:
                continue
            if c.get("kind") == "iluminacion":
                ws = [w for w in self.wires
                      if w.get("circuit") == c["id"] and r.get("id") in (w.get("runIds") or [])]
                ws.sort(key=order)
                for w in ws:
                    items.append({"color": self.wire_hex(w), "section": c.get("section"),
                                  "code": self.wire_code(w), "circuit": c.get("name")})
            else:
                colors = self.wire_colors_for(c)
                for i in range(r.get("cables") or 0):
                    label = colors[i] if i < len(colors) else f"Conductor {i + 1}"
                    items.append({"color": WIRE_HEX.get(label, "#5b6470"), "section": c.get("section"),
                                  "code": label, "circuit": c.get("name")})
        return items

    # ------------------------------------------------------------- visibilidad
    def runs_at_node(self, nid):
        return [r for r in self.runs if r.get("a") == nid or r.get("b") == nid]

    def node_visible(self, n, only=None):
        if n.get("kind") in ("tablero", "medidor", "jabalina"):
            return True
        rs = self.runs_at_node(n["id"])
        if only:
            return any(r.get("circuit") == only for r in rs)
        if not rs:
            return True
        return any(self.is_ci_visible(r.get("circuit")) for r in rs)

    # ------------------------------------------------------------- DRC (errores)
    def node_max_conduits(self, n):
        k = n.get("kind")
        if k == "oct":
            return self.rules["maxOct"]
        if k == "rect":
            return self.rules["maxRect"]
        if k == "insp":
            return n.get("inspMax") or INSP_MAX_DEFAULT
        return None                                  # tablero/medidor/jabalina: sin límite

    def drc_error_targets(self):
        """Ids que el DRC del editor marca en ROJO sobre el dibujo (sólo los
        errores de nivel "e" que tienen un objeto en el plano): caño excedido
        en capacidad -> id del primer tramo del grupo; caja con más caños de
        los que admite -> id de la caja. Es el mismo criterio que `problems`
        en drawScene() de canaliza.html (no incluye avisos ni el texto del
        listado, que no va al PDF)."""
        malos = set()
        for g in self.conduit_groups().values():
            f = g["fill"]
            if f == math.inf or f > 1:
                malos.add(g["runs"][0].get("id"))
        for n in self.nodes:
            mx = self.node_max_conduits(n)
            if mx is not None:
                claves = {self.group_key(r) for r in self.runs_at_node(n["id"])}
                if len(claves) > mx:
                    malos.add(n["id"])
        malos.discard(None)
        return malos

    # ------------------------------------------------------------- cómputo
    def compute_bom(self):
        cable, cable_color, conduit = {}, {}, {}
        boxes = {"tablero": 0, "oct": 0, "rect": 0, "medidor": 0, "jabalina": 0, "insp": 0}
        boxes_insp, by_circuit = {}, []
        spare = self.rules["spare"] / 100.0
        waste = 1 + self.rules["waste"] / 100.0
        groups = self.conduit_groups()

        for n in self.nodes:
            k = n.get("kind")
            boxes[k] = boxes.get(k, 0) + 1
            if k == "insp":
                key = n.get("inspLabel") or "Sin medida especificada"
                boxes_insp[key] = boxes_insp.get(key, 0) + 1

        for g in groups.values():
            conduit[g["dia"]] = conduit.get(g["dia"], 0.0) + g["len"]

        for c in self.circuits:
            rs = [r for r in self.runs if r.get("circuit") == c["id"]]
            length = sum(self.run_len_m(r) for r in rs)
            vert = sum(self.run_vert_m(r) for r in rs)
            sec = c.get("section")
            cable_color.setdefault(sec, {})
            cab = 0.0

            if c.get("kind") == "iluminacion":
                wires = [w for w in self.wires if w.get("circuit") == c["id"] and (w.get("runIds") or [])]
                for w in wires:
                    wl = 0.0
                    for rid in w.get("runIds") or []:
                        run = next((x for x in self.runs if x.get("id") == rid), None)
                        if not run:
                            continue
                        ends = (1 if run.get("a") else 0) + (1 if run.get("b") else 0)
                        wl += self.run_len_m(run) + ends * spare
                    code = self.wire_code(w)
                    cable_color[sec][code] = cable_color[sec].get(code, 0.0) + wl
                    cab += wl
            else:
                colors = self.wire_colors_for(c)
                for r in rs:
                    L = self.run_len_m(r)
                    ends = (1 if r.get("a") else 0) + (1 if r.get("b") else 0)
                    per = L + ends * spare
                    cab += per * (r.get("cables") or 0)
                    for i in range(r.get("cables") or 0):
                        col = colors[i] if i < len(colors) else f"Conductor {i + 1}"
                        cable_color[sec][col] = cable_color[sec].get(col, 0.0) + per

            cable[sec] = cable.get(sec, 0.0) + cab
            by_circuit.append({"c": c, "runs": len(rs), "len": length, "vert": vert, "cab": cab})

        for k in cable:
            cable[k] *= waste
        for s in cable_color:
            for col in cable_color[s]:
                cable_color[s][col] *= waste

        shared = sum(1 for g in groups.values() if len(g["runs"]) > 1)
        return {
            "cable": cable, "cableColor": cable_color, "conduit": conduit,
            "boxes": boxes, "boxesInsp": boxes_insp, "byCircuit": by_circuit,
            "shared": shared, "nGroups": len(groups),
            "totalCable": sum(cable.values()), "totalConduit": sum(conduit.values()),
        }
