"""PDF de Routeo generado en el servidor con PyMuPDF -- el mismo patrón que
pdf_presupuesto.py / pdf_materiales.py, en vez del jsPDF/canvas que se armaba
en el navegador.

Contenido (igual que antes, es un cambio de "quién genera el PDF", no de "qué
dice"): una hoja general con todos los circuitos sobre el plano y su leyenda,
una hoja de cableado detallado opcional, una hoja por circuito con su tabla de
tramos, y una hoja de cómputo de materiales.

El dibujo del plano (caños, cables, cajas, cruces, etiquetas) se reproduce acá
a partir de la geometría del proyecto -- ver app/canaliza_geom.py, que porta a
Python las funciones que en canaliza.html hacían drawScene/drawConduit/etc.

Trucos de escala portados de canaliza.html: en el canvas los anchos de línea y
los radios se escribían como `X/z` para que quedaran de tamaño constante en
papel independientemente del zoom. Acá `T.u` reproduce ese factor: cada `X`
(numerador de aquel `X/z`) se multiplica por `T.u` y las posiciones por `T.k`.
"""
from __future__ import annotations
import io
from datetime import datetime
import pymupdf
from . import config as cfgmod, almacen, canaliza_geom as cg
from .canaliza_geom import dia_of, dia_lbl, cond_width, offset_poly, DEV_KIND

NAVY = (0x16 / 255, 0x28 / 255, 0x3f / 255)
INK = (0x1c / 255, 0x27 / 255, 0x33 / 255)
MUTED = (0x5b / 255, 0x6b / 255, 0x7a / 255)
LINE = (0.80, 0.80, 0.80)
MARGEN = 34.0
ZOOM_PLANO = 3.0                       # las coords de nodes/runs están en px del plano a este zoom

FORMATOS = {"a4": (595.28, 841.89), "a3": (841.89, 1190.55), "letter": (612.0, 792.0)}


def _rgb(h):
    h = (h or "#000000").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255)
    except ValueError:
        return (0, 0, 0)


def _fmt(v, d=2):
    if v is None or v != v:
        return "—"
    return f"{v:.{d}f}"


def _page_size(fmt, ori):
    w, h = FORMATOS.get((fmt or "a4").lower(), FORMATOS["a4"])
    return (max(w, h), min(w, h)) if (ori or "landscape").lower().startswith("land") else (min(w, h), max(w, h))


# --------------------------------------------------------------- plano de fondo
def _plano_imagen(obra: dict):
    """Devuelve (png_bytes, base_w, base_h). Se embebe el plano como PNG ya
    comprimido (no un Pixmap crudo) para que el PDF quede liviano y siga
    liviano al concatenarlo en el informe general."""
    oid = (obra.get("obra") or {}).get("id")
    nombre = (obra.get("plano") or {}).get("archivo")
    ruta = almacen.ruta_plano(oid, nombre) if (oid and nombre) else None
    if ruta is None or not ruta.exists():
        return None
    doc = pymupdf.open(str(ruta))
    pg = doc[0]
    pt_w, pt_h = pg.rect.width, pg.rect.height
    rz = min(4.0, max(1.5, 2400.0 / max(pt_w, pt_h)))
    png = pg.get_pixmap(matrix=pymupdf.Matrix(rz, rz)).tobytes("png")
    doc.close()
    return png, pt_w * ZOOM_PLANO, pt_h * ZOOM_PLANO


class _T:
    """Mapeo px-del-plano -> puntos de la página. `k` escala posiciones; `u`
    escala anchos/radios/tipos. En canaliza.html esos se escribían `X/z` para
    quedar de tamaño de pantalla constante; en un PDF de escala fija lo natural
    es dibujar a la escala de la imagen, así que `u == k` (un poco realzado para
    que la anotación se lea sobre el plano)."""

    SCENE = 1.15

    def __init__(self, rect: pymupdf.Rect, base_w: float, base_h: float):
        self.k = min(rect.width / base_w, rect.height / base_h)
        self.ox = rect.x0 + (rect.width - base_w * self.k) / 2
        self.oy = rect.y0 + (rect.height - base_h * self.k) / 2
        self.u = self.k * self.SCENE
        self.rect = pymupdf.Rect(self.ox, self.oy, self.ox + base_w * self.k, self.oy + base_h * self.k)

    def p(self, pt):
        return pymupdf.Point(self.ox + pt["x"] * self.k, self.oy + pt["y"] * self.k)

    def pts(self, arr):
        return [self.p(q) for q in arr]


def _stroke(pg, pts, color, width, *, dash=None, close=False, opacity=1.0):
    if len(pts) < 2:
        return
    sh = pg.new_shape()
    sh.draw_polyline(pts)
    sh.finish(color=color, width=max(0.05, width), dashes=dash, closePath=close,
              lineCap=1, lineJoin=1, stroke_opacity=opacity)
    sh.commit()


def _poly_pts(pts):
    return [{"x": p.x, "y": p.y} for p in pts]


# --------------------------------------------------------------- dibujo del plano
def _draw_conduit(pg, T, P, grp, bad, vis, detailed):
    base = T.pts(grp["runs"][0]["pts"])
    if len(base) < 2:
        return
    u = T.u
    if detailed:
        items = P.conduit_conductors(vis)
        n = max(len(items), 1)
        max_w = max((cond_width(it["section"]) for it in items), default=1.4)
        pipe_w = min(26, 9 + n * (max_w + 0.6))
        _stroke(pg, base, (1, 1, 1), (pipe_w + 4) * u, opacity=0.9)
        _stroke(pg, base, _rgb("#b3261e") if bad else _rgb("#9aa4ad"), (pipe_w + 1.2 if bad else pipe_w) * u)
        _stroke(pg, base, (1, 1, 1), (pipe_w - 2.6) * u)
        sp = min(5.6, (pipe_w - 2.5) / n)
        for i, it in enumerate(items):
            off = (i - (n - 1) / 2) * sp if n > 1 else 0
            pts = T.pts(offset_poly(_poly_pts(base), off * u))
            w = cond_width(it["section"])
            _stroke(pg, pts, (15 / 255, 18 / 255, 20 / 255), (w + 1.1) * u, opacity=0.6)
            _stroke(pg, pts, _rgb(it["color"]), w * u)
        return

    _stroke(pg, base, (1, 1, 1), 11 * u, opacity=0.9)
    _stroke(pg, base, _rgb("#b3261e") if bad else _rgb("#9aa4ad"), (8.5 if bad else 7.5) * u)
    _stroke(pg, base, (1, 1, 1), 5.5 * u)
    n = len(grp["runs"])
    for i, r in enumerate(grp["runs"]):
        if r not in vis:
            continue
        c = P.circuit(r.get("circuit"))
        if not c:
            continue
        off = (i - (n - 1) / 2) * 3.4 if n > 1 else 0
        pts = T.pts(offset_poly(_poly_pts(base), off * u))
        dash = f"[{9 * u} {6 * u}] 0" if c.get("dash") else None
        _stroke(pg, pts, _rgb(c.get("color")), (2.2 if n > 1 else 2.8) * u, dash=dash)


def _draw_device(pg, T, dev, cx, cy, R, color):
    u = T.u
    seg = []
    if dev == "luminaria":
        seg = [((-R * .5, -R * .5), (R * .5, R * .5)), ((R * .5, -R * .5), (-R * .5, R * .5))]
    elif dev == "interruptor":
        seg = [((-R * .45, R * .35), (R * .45, -R * .4))]
    elif dev == "toma":
        seg = [((-R * .42, 0), (R * .42, 0))]
    elif dev == "especial":
        seg = [((-R * .15, -R * .5), (-R * .45, R * .05)), ((-R * .45, R * .05), (R * .05, R * .05)),
               ((R * .05, R * .05), (-R * .1, R * .5))]
    for (ax, ay), (bx, by) in seg:
        _stroke(pg, [pymupdf.Point(cx + ax, cy + ay), pymupdf.Point(cx + bx, cy + by)], color, 1.6 * u)


def _draw_node(pg, T, P, n):
    u, R = T.u, 10 * T.u
    ctr = T.p(n)
    cx, cy = ctr.x, ctr.y
    ci = P.circuit(n.get("circuitId")) if n.get("circuitId") else None
    stroke = _rgb(ci["color"]) if ci else (15 / 255, 18 / 255, 20 / 255)
    kind = n.get("kind")
    sh = pg.new_shape()
    if kind == "tablero":
        sh.draw_rect(pymupdf.Rect(cx - R * 1.25, cy - R, cx + R * 1.25, cy + R))
        sh.finish(color=stroke, fill=(1, 1, 1), width=2 * u)
        sh.commit()
        for i in range(3):
            x = cx - R * .7 + i * R * .7
            _stroke(pg, [pymupdf.Point(x, cy - R * .55), pymupdf.Point(x, cy + R * .55)], stroke, 2 * u)
        return
    if kind == "medidor":
        sh.draw_circle(ctr, R * 1.15)
        sh.finish(color=stroke, fill=(1, 1, 1), width=2 * u)
        sh.commit()
        _stroke(pg, [ctr, pymupdf.Point(cx - R * .55, cy - R * .35)], stroke, 2 * u)
        return
    if kind == "jabalina":
        _stroke(pg, [pymupdf.Point(cx, cy - R * 1.15), pymupdf.Point(cx, cy + R * .05)], stroke, 2 * u)
        for w, yy in ((.85, .05), (.55, .45), (.25, .85)):
            _stroke(pg, [pymupdf.Point(cx - R * w, cy + R * yy), pymupdf.Point(cx + R * w, cy + R * yy)], stroke, 2 * u)
        return
    if kind == "insp":
        sh.draw_rect(pymupdf.Rect(cx - R * 1.15, cy - R * 1.15, cx + R * 1.15, cy + R * 1.15))
        sh.finish(color=stroke, fill=(1, 1, 1), width=2 * u)
        sh.commit()
        _stroke(pg, [pymupdf.Point(cx - R * .75, cy - R * .75), pymupdf.Point(cx + R * .75, cy + R * .75)], stroke, 2 * u)
        _stroke(pg, [pymupdf.Point(cx + R * .75, cy - R * .75), pymupdf.Point(cx - R * .75, cy + R * .75)], stroke, 2 * u)
        return
    if kind == "oct":
        import math
        poly = []
        for i in range(8):
            a = math.pi / 8 + i * math.pi / 4
            poly.append(pymupdf.Point(cx + math.cos(a) * R * 1.15, cy + math.sin(a) * R * 1.15))
        sh.draw_polyline(poly + [poly[0]])
        sh.finish(color=stroke, fill=(1, 1, 1), width=2 * u, closePath=True)
        sh.commit()
        _draw_device(pg, T, n.get("device"), cx, cy, R, stroke)
        return
    # rectangular (default)
    sh.draw_rect(pymupdf.Rect(cx - R, cy - R * .78, cx + R, cy + R * .78))
    sh.finish(color=stroke, fill=(1, 1, 1), width=2 * u)
    sh.commit()
    _draw_device(pg, T, n.get("device"), cx, cy, R, stroke)


def _draw_crossing(pg, T, cr):
    u = T.u
    ctr = T.p(cr["pt"])
    cx, cy = ctr.x, ctr.y
    if cr["safe"]:
        s = 8 * u
        tri = [pymupdf.Point(cx, cy - s), pymupdf.Point(cx + s * .87, cy + s * .62),
               pymupdf.Point(cx - s * .87, cy + s * .62)]
        sh = pg.new_shape()
        sh.draw_polyline(tri + [tri[0]])
        sh.finish(color=_rgb("#8a6100"), fill=(1, 1, 1), width=2 * u, closePath=True)
        sh.commit()
        _stroke(pg, [pymupdf.Point(cx, cy - s * .32), pymupdf.Point(cx, cy + s * .18)], _rgb("#8a6100"), 1.8 * u)
    else:
        s = 7.5 * u
        _stroke(pg, [pymupdf.Point(cx - s, cy - s), pymupdf.Point(cx + s, cy + s)], _rgb("#b3261e"), 2.6 * u)
        _stroke(pg, [pymupdf.Point(cx + s, cy - s), pymupdf.Point(cx - s, cy + s)], _rgb("#b3261e"), 2.6 * u)


def _label(pg, T, x, y, text, fs):
    fs = max(4.6, fs)
    w = pymupdf.get_text_length(text, fontname="helv", fontsize=fs)
    pg.draw_rect(pymupdf.Rect(x - 1.5, y - fs, x + w + 1.5, y + 2), color=None,
                 fill=(1, 1, 1), fill_opacity=0.9)
    pg.insert_text((x, y), text, fontsize=fs, fontname="helv", color=(15 / 255, 18 / 255, 20 / 255))


def _draw_scene(pg, T, P, *, only=None, detailed=False, labels=True, lens=True, crossings=None):
    groups = P.conduit_groups()
    for grp in groups.values():
        relevant = (any(r.get("circuit") == only for r in grp["runs"]) if only
                    else any(P.is_ci_visible(r.get("circuit")) for r in grp["runs"]))
        if not relevant:
            continue
        if only and detailed:
            vis = list(grp["runs"])
        elif only:
            vis = [r for r in grp["runs"] if r.get("circuit") == only]
        else:
            vis = [r for r in grp["runs"] if P.is_ci_visible(r.get("circuit"))]
        if not vis:
            continue
        _draw_conduit(pg, T, P, grp, False, vis, detailed)

    # etiquetas del caño (horizontales, con fondo -- ver nota del módulo)
    if lens and P.px_per_m:
        for grp in groups.values():
            if only:
                vis = [r for r in grp["runs"] if r.get("circuit") == only]
            else:
                vis = [r for r in grp["runs"] if P.is_ci_visible(r.get("circuit"))]
            if not vis:
                continue
            pnts = grp["runs"][0].get("pts") or []
            if len(pnts) < 2:
                continue
            mid = pnts[len(pnts) // 2]
            shown = vis if only else grp["runs"]
            cab = sum(r.get("cables") or 0 for r in shown)
            txt = f'{_fmt(grp["len"])} m · {dia_lbl(grp["dia"])} · {cab} cond.'
            if grp["vert"] > 0.01:
                txt += f'  (h {_fmt(grp["horiz"])} + v {_fmt(grp["vert"])})'
            m = T.p(mid)
            _label(pg, T, m.x, m.y - 4 * T.u, txt, 11 * T.u)

    for n in P.nodes:
        if not P.node_visible(n, only):
            continue
        _draw_node(pg, T, P, n)
        if labels:
            ci = P.circuit(n.get("circuitId")) if n.get("circuitId") else None
            t = (n.get("label") or "") + (f' · {ci["name"]}' if ci else "")
            c = T.p(n)
            _label(pg, T, c.x + 14 * T.u, c.y - 10 * T.u, t, 11 * T.u)

    for cr in (crossings if crossings is not None else P.find_crossings()):
        if only and not any(r.get("circuit") == only for r in cr["a"]["runs"]) \
                and not any(r.get("circuit") == only for r in cr["b"]["runs"]):
            continue
        _draw_crossing(pg, T, cr)


# ------------------------------------------------------------------ hojas
def _header(pg, W, titulo, sub):
    pg.insert_text((MARGEN, MARGEN + 12), titulo, fontsize=13, fontname="hebo", color=NAVY)
    if sub:
        tw = pymupdf.get_text_length(sub, fontname="helv", fontsize=8.5)
        pg.insert_text((W - MARGEN - tw, MARGEN + 12), sub, fontsize=8.5, fontname="helv", color=MUTED)
    pg.draw_line((MARGEN, MARGEN + 20), (W - MARGEN, MARGEN + 20), color=LINE, width=0.6)
    return MARGEN + 32


def _footer(pg, W, H, base_name, etiqueta):
    fecha = datetime.now().strftime("%d/%m/%Y")
    pg.insert_text((MARGEN, H - 16), f"{base_name}  ·  {fecha}", fontsize=7.5, fontname="helv", color=MUTED)
    tw = pymupdf.get_text_length(etiqueta, fontname="helv", fontsize=7.5)
    pg.insert_text((W - MARGEN - tw, H - 16), etiqueta, fontsize=7.5, fontname="helv", color=MUTED)


def _plan_page(doc, W, H, titulo, sub, plano_png, base_w, base_h, alto_reserva, draw_fn):
    pg = doc.new_page(width=W, height=H)
    y0 = _header(pg, W, titulo, sub)
    rect = pymupdf.Rect(MARGEN, y0 + 4, W - MARGEN, H - alto_reserva)
    T = _T(rect, base_w, base_h)
    pg.insert_image(T.rect, stream=plano_png)
    draw_fn(pg, T)
    return pg, T


def _legend_circuitos(pg, W, y, circuits):
    pg.insert_text((MARGEN, y), "Referencias", fontsize=8.5, fontname="hebo", color=NAVY)
    y += 12
    x = MARGEN
    for c in circuits:
        pg.draw_line((x, y - 3), (x + 14, y - 3), color=_rgb(c.get("color")), width=2.4)
        t = f'{c.get("name")}  {c.get("section")}mm² · {c.get("prot")}A'
        pg.insert_text((x + 18, y), t, fontsize=8, fontname="helv", color=INK)
        x += 24 + pymupdf.get_text_length(t, fontname="helv", fontsize=8)
        if x > W - MARGEN - 90:
            x = MARGEN
            y += 12
    return y


def generar(obra: dict, proyecto: dict, hojas: dict, *, formato="a4",
            orientacion="landscape", ocultos=None) -> bytes:
    plano = _plano_imagen(obra)
    if plano is None:
        raise ValueError("Esta obra no tiene un plano cargado en Routeo.")
    plano_png, base_w, base_h = plano
    P = cg.Proyecto(proyecto, ocultos=ocultos)
    W, H = _page_size(formato, orientacion)
    base_name = P.base_name
    crossings = P.find_crossings()
    doc = pymupdf.open()
    hojas = hojas or {}

    if hojas.get("general", True):
        sub = f"{_fmt(P.px_per_m, 1)} px/m" if P.px_per_m else "sin escala"
        pg, _ = _plan_page(doc, W, H, "Routeo — todos los circuitos", sub, plano_png, base_w, base_h,
                           88, lambda p, T: _draw_scene(p, T, P, labels=True, lens=False, crossings=crossings))
        _legend_circuitos(pg, W, H - 74, [c for c in P.circuits if P.is_ci_visible(c["id"])])
        _footer(pg, W, H, base_name, "Hoja general")

    if hojas.get("detallado"):
        pg, _ = _plan_page(doc, W, H, "Cableado detallado — todos los circuitos",
                           "cables reales dentro de cada caño", plano_png, base_w, base_h, 78,
                           lambda p, T: _draw_scene(p, T, P, labels=False, lens=False, detailed=True,
                                                    crossings=crossings))
        y = H - 66
        pg.insert_text((MARGEN, y), "Cómo leer los caños", fontsize=8.5, fontname="hebo", color=NAVY)
        pg.insert_textbox(pymupdf.Rect(MARGEN, y + 4, W - MARGEN, y + 30),
                          "Cada línea de color adentro del caño es un conductor; cuanto más gruesa, "
                          "mayor la sección. Marrón = fase, celeste = neutro, verde-amarillo = tierra; "
                          "blanco/gris = retorno simple, amarillo/ocre = combinada.",
                          fontsize=7.5, fontname="helv", color=INK, lineheight=1.3)
        _footer(pg, W, H, base_name, "Cableado detallado")

    for cid in (hojas.get("circuitos") or []):
        c = P.circuit(cid)
        if not c:
            continue
        rs = [r for r in P.runs if r.get("circuit") == cid]
        length = sum(P.run_len_m(r) for r in rs)
        vert = sum(P.run_vert_m(r) for r in rs)
        cab = sum(P.run_len_m(r) * (r.get("cables") or 0) for r in rs)
        sub = DEV_KIND.get(c.get("kind"), c.get("kind")) + (f' — {c["detail"]}' if c.get("detail") else "")
        pg, _ = _plan_page(doc, W, H, f'Circuito {c.get("name")}', sub, plano_png, base_w, base_h, 96,
                           lambda p, T, _cid=cid: _draw_scene(p, T, P, only=_cid, labels=True, lens=False,
                                                              detailed=True, crossings=crossings))
        y = H - 84
        celdas = [("Sección", f'{c.get("section")} mm²'), ("Protección", f'{c.get("prot")} A'),
                  ("Tramos", str(len(rs))), ("Horizontal", f'{_fmt(length - vert, 1)} m'),
                  ("Vertical", f'{_fmt(vert, 1)} m'), ("Cable", f'{_fmt(cab, 1)} m')]
        x = MARGEN
        for k, v in celdas:
            pg.insert_text((x, y), k, fontsize=7, fontname="helv", color=MUTED)
            pg.insert_text((x, y + 10), v, fontsize=9, fontname="hebo", color=INK)
            x += max(70, pymupdf.get_text_length(v, fontname="helv", fontsize=9) + 34)
        y += 24
        if rs:
            pg.draw_line((MARGEN, y - 6), (W - MARGEN, y - 6), color=LINE, width=0.4)
            cols = [MARGEN, MARGEN + 150, MARGEN + 210, MARGEN + 260, MARGEN + 320, MARGEN + 380, MARGEN + 445]
            for i, hcol in enumerate(["Tramo", "Caño", "Cond.", "Horiz.", "Vert.", "Total", "Cable"]):
                pg.insert_text((cols[i], y), hcol, fontsize=7, fontname="hebo", color=MUTED)
            y += 11
            gall = P.conduit_groups()
            for r in rs:
                if y > H - 24:
                    break
                a, b = P.node(r.get("a")), P.node(r.get("b"))
                g = gall.get(P.group_key(r))
                sh = "  (compartido)" if g and len(g["runs"]) > 1 else ""
                vals = [f'{(a or {}).get("label", "libre")} → {(b or {}).get("label", "libre")}{sh}',
                        dia_lbl(r.get("dia")), str(r.get("cables")), _fmt(P.run_horiz_m(r)),
                        _fmt(P.run_vert_m(r)), f'{_fmt(P.run_len_m(r))} m',
                        f'{_fmt(P.run_len_m(r) * (r.get("cables") or 0))} m']
                for i, v in enumerate(vals):
                    pg.insert_text((cols[i], y), v, fontsize=7, fontname="helv", color=INK)
                y += 10
        _footer(pg, W, H, base_name, f'Circuito {c.get("name")}')

    if hojas.get("bom"):
        _hoja_bom(doc, W, H, P, base_name)

    out = io.BytesIO()
    doc.save(out, deflate=True)
    doc.close()
    return out.getvalue()


def _hoja_bom(doc, W, H, P, base_name):
    b = P.compute_bom()
    pg = doc.new_page(width=W, height=H)
    sub = f'escala {_fmt(P.px_per_m, 1)} px/m' if P.px_per_m else "sin escala"
    y0 = _header(pg, W, "Cómputo de materiales", sub)
    col2 = W / 2 + 6
    y = y0 + 6

    pg.insert_text((MARGEN, y), "Cable por sección", fontsize=9, fontname="hebo", color=NAVY)
    y += 12
    cs = sorted((k for k, v in b["cable"].items() if v > 0), key=lambda x: float(x))
    for s in cs:
        pg.insert_text((MARGEN, y), f"{s} mm²", fontsize=8, fontname="helv", color=INK)
        pg.insert_text((MARGEN + 90, y), f'{_fmt(b["cable"][s], 1)} m', fontsize=8, fontname="hebo", color=INK)
        y += 11
        for col in sorted((b["cableColor"].get(s) or {})):
            pg.insert_text((MARGEN + 8, y), col, fontsize=7, fontname="helv", color=MUTED)
            pg.insert_text((MARGEN + 90, y), f'{_fmt(b["cableColor"][s][col], 1)} m', fontsize=7, fontname="helv", color=MUTED)
            y += 9
    pg.insert_text((MARGEN, y + 2), "Total cable", fontsize=8, fontname="hebo", color=INK)
    pg.insert_text((MARGEN + 90, y + 2), f'{_fmt(b["totalCable"], 1)} m', fontsize=8, fontname="hebo", color=INK)

    y2 = y0 + 6
    pg.insert_text((col2, y2), "Caño corrugado", fontsize=9, fontname="hebo", color=NAVY)
    y2 += 12
    ds = sorted((k for k, v in b["conduit"].items() if v > 0), key=lambda x: dia_of(x)["mm"])
    for d in ds:
        pg.insert_text((col2, y2), f'{dia_lbl(d)}  ({dia_of(d)["mm"]} mm)', fontsize=8, fontname="helv", color=INK)
        pg.insert_text((col2 + 90, y2), f'{_fmt(b["conduit"][d], 1)} m', fontsize=8, fontname="hebo", color=INK)
        y2 += 11
    pg.insert_text((col2, y2 + 2), "Total caño", fontsize=8, fontname="hebo", color=INK)
    pg.insert_text((col2 + 90, y2 + 2), f'{_fmt(b["totalConduit"], 1)} m', fontsize=8, fontname="hebo", color=INK)

    y = max(y, y2) + 26
    pg.insert_text((MARGEN, y), "Cajas", fontsize=9, fontname="hebo", color=NAVY)
    y += 12
    filas = [("Octogonales", b["boxes"].get("oct", 0)), ("Rectangulares", b["boxes"].get("rect", 0)),
             ("Tableros", b["boxes"].get("tablero", 0))]
    if b["boxes"].get("medidor"):
        filas.append(("Medidores", b["boxes"]["medidor"]))
    if b["boxes"].get("jabalina"):
        filas.append(("Jabalinas", b["boxes"]["jabalina"]))
    if b["boxes"].get("insp"):
        filas.append(("De inspección", b["boxes"]["insp"]))
    for k, v in filas:
        pg.insert_text((MARGEN, y), k, fontsize=8, fontname="helv", color=INK)
        pg.insert_text((MARGEN + 90, y), str(v), fontsize=8, fontname="hebo", color=INK)
        y += 11

    y += 12
    pg.insert_text((MARGEN, y), "Resumen por circuito", fontsize=9, fontname="hebo", color=NAVY)
    y += 12
    cols = [MARGEN, MARGEN + 120, MARGEN + 180, MARGEN + 230, MARGEN + 300, MARGEN + 370, MARGEN + 440]
    for i, hcol in enumerate(["Circuito", "Sección", "Protec.", "Tramos", "Recorrido", "Cable", "Tipo"]):
        pg.insert_text((cols[i], y), hcol, fontsize=7, fontname="hebo", color=MUTED)
    y += 11
    for r in b["byCircuit"]:
        if y > H - 60:
            break
        c = r["c"]
        vals = [c.get("name"), f'{c.get("section")} mm²', f'{c.get("prot")} A', str(r["runs"]),
                f'{_fmt(r["len"], 1)} m', f'{_fmt(r["cab"], 1)} m', DEV_KIND.get(c.get("kind"), c.get("kind"))]
        for i, v in enumerate(vals):
            pg.insert_text((cols[i], y), v, fontsize=7, fontname="helv", color=INK)
        y += 10

    nota = (f'Cálculo con {P.rules["waste"]}% de desperdicio, {P.rules["spare"]} cm de reserva por '
            f'conexión y bajadas verticales sobre cielorraso de {_fmt(P.z["ceiling"])} m.')
    if b["shared"]:
        nota += f'  {b["shared"]} caño(s) compartido(s) computados una sola vez.'
    pg.insert_textbox(pymupdf.Rect(MARGEN, H - 34, W - MARGEN, H - 18), nota,
                      fontsize=7, fontname="helv", color=MUTED, lineheight=1.3)
    _footer(pg, W, H, base_name, "Cómputo")
