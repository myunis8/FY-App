"""Exporta el tablero a PDF: una vista de conexionado a color (fondo claro
para que los cables se vean) y una vista de "tapa puesta" con etiquetas de
cada térmica, para pegar como referencia adentro del tablero real.

El detalle de cada dispositivo (tornillos, ventana del circuito, Δ del
diferencial, display del protector, terminales de la bornera) replica el
mismo lenguaje visual que ya se usa en el editor interactivo, y el cableado
usa el mismo ruteo en escuadra con saltos donde dos cables se cruzan.
"""
from __future__ import annotations
import io
import pymupdf

ANCHO, ALTO = 1000, 700               # apaisado, se ajusta según el tablero
MARGEN = 34

# geometría del editor interactivo (web/tablero.html) -- deliberadamente MUCHO
# más grande que la de esta hoja (celda=34 acá vs. 64 ahí) para que sea cómodo
# clickear con el mouse. Un punto de "ruta" manual (cuando el usuario endereza
# un cable a mano) se guarda en esos píxeles de pantalla, no en los puntos de
# esta hoja -- si se usan tal cual, un cable puede terminar dibujado bien
# afuera de la página entera. Hay que convertirlos, nunca copiarlos directo.
CANAL_WEB = 46
CELDA_WEB = 64
FRANJA_CANO_WEB = 58
ALTURA_PISO_WEB = 78 + 150 + 78 + 22   # BANDA + ALTO_DISP + BANDA + MARGEN_PISO, ahí
NAVY = (0x16/255, 0x28/255, 0x3f/255)
TRAZO = (0x33/255, 0x50/255, 0x6e/255)
GRIS = (0x5b/255, 0x6b/255, 0x7a/255)
BLANCO = (1, 1, 1)
FONDO_HOJA = (0.985, 0.985, 0.975)
FONDO_RIEL = (0.85, 0.88, 0.88)
COLOR_POLARIDAD = {"fase": (0x8a/255, 0x5a/255, 0x2b/255),
                   "neutro": (0x2b/255, 0x6c/255, 0xa3/255),
                   "tierra": (0x2f/255, 0x7d/255, 0x5c/255)}
COLOR_ROL = {"diferencial": (0x6a/255, 0x3d/255, 0x9a/255),
            "protector": (0xb3/255, 0x43/255, 0x2f/255),
            "tierra": (0x5b/255, 0x6b/255, 0x7a/255)}


def _hex(h):
    h = (h or "5b6b7a").lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))


def _texto_centrado(pg, cx, cy_base, texto, fontsize, color, negrita=True, fuente_max=None):
    """insert_textbox falla en silencio si la caja es más angosta que el
    texto — pasó con las ventanas de las térmicas. Esto centra a mano con
    insert_text, que siempre dibuja, ajustando el tamaño si no entra."""
    if not texto:
        return
    fname = "hebo" if negrita else "helv"
    fs = fontsize
    ancho_max = fuente_max
    if ancho_max:
        while fs > 5 and pymupdf.get_text_length(texto, fontname=fname, fontsize=fs) > ancho_max:
            fs -= 0.5
    w = pymupdf.get_text_length(texto, fontname=fname, fontsize=fs)
    pg.insert_text((cx - w / 2, cy_base), texto, fontsize=fs, fontname=fname, color=color)


def _color_familia(d):
    if d.get("rol") == "general":
        return NAVY
    return _hex(d.get("color")) if d.get("color") else GRIS


# ---------------------------------------------------------------- tornillos
def _tornillo(pg, cx, cy, r, cruz):
    pg.draw_circle((cx, cy), r, color=TRAZO, fill=BLANCO, width=0.9)
    k = r * 0.55
    if cruz:
        pg.draw_line((cx - k, cy - k), (cx + k, cy + k), color=TRAZO, width=0.9)
        pg.draw_line((cx - k, cy + k), (cx + k, cy - k), color=TRAZO, width=0.9)
    else:
        pg.draw_line((cx - k, cy), (cx + k, cy), color=TRAZO, width=0.9)
        pg.draw_line((cx, cy - k), (cx, cy + k), color=TRAZO, width=0.9)


# ---------------------------------------------------------------- dispositivos
def _termica(pg, x0, y0, w, h, d, circuito):
    color = _color_familia(d)
    r = min(w / max(d["polos"], 1), h) * 0.15
    pg.draw_rect(pymupdf.Rect(x0 + 2, y0, x0 + w - 2, y0 + h), color=color, fill=BLANCO, width=1.4,
                radius=0.10)
    for i in range(d["polos"]):
        cx = x0 + (i + 0.5) * w / d["polos"]
        _tornillo(pg, cx, y0 + h * 0.14, r, cruz=True)
        _tornillo(pg, cx, y0 + h * 0.87, r, cruz=False)
    pg.draw_rect(pymupdf.Rect(x0 + w * 0.1, y0 + h * 0.23, x0 + w * 0.9, y0 + h * 0.4),
                color=TRAZO, fill=None, width=0.8, radius=0.08)
    if circuito:
        _texto_centrado(pg, x0 + w/2, y0 + h*0.35, circuito[:14], min(w*0.13, 9), TRAZO,
                        fuente_max=w*0.82)
    pg.draw_rect(pymupdf.Rect(x0 + w * 0.22, y0 + h * 0.44, x0 + w * 0.78, y0 + h * 0.5),
                color=TRAZO, width=0.7, radius=0.15)
    pg.draw_rect(pymupdf.Rect(x0 + w * 0.28, y0 + h * 0.51, x0 + w * 0.44, y0 + h * 0.62),
                color=TRAZO, width=0.7)
    pg.draw_rect(pymupdf.Rect(x0 + w * 0.56, y0 + h * 0.51, x0 + w * 0.72, y0 + h * 0.62),
                color=TRAZO, width=0.7)
    _texto_centrado(pg, x0 + w/2, y0 + h*0.84, f'C{d.get("corriente","")}', min(w*0.2, 12), TRAZO,
                    fuente_max=w*0.85)


def _diferencial(pg, x0, y0, w, h, d, circuito):
    r = min(w / max(d["polos"], 1), h) * 0.12
    pg.draw_rect(pymupdf.Rect(x0 + 2, y0, x0 + w - 2, y0 + h), color=COLOR_ROL["diferencial"],
                fill=BLANCO, width=1.4, radius=0.10)
    for i in range(d["polos"]):
        cx = x0 + (i + 0.5) * w / d["polos"]
        _tornillo(pg, cx, y0 + h * 0.1, r, cruz=False)
        _tornillo(pg, cx, y0 + h * 0.9, r, cruz=False)
    pg.draw_rect(pymupdf.Rect(x0 + w * 0.12, y0 + h * 0.28, x0 + w * 0.42, y0 + h * 0.58),
                color=TRAZO, width=0.8)
    _texto_centrado(pg, x0 + w*0.27, y0 + h*0.48, "T", min(w*0.2, 12), TRAZO)
    pg.draw_rect(pymupdf.Rect(x0 + w * 0.52, y0 + h * 0.3, x0 + w * 0.86, y0 + h * 0.42),
                color=None, fill=COLOR_ROL["diferencial"], radius=0.2)
    pg.insert_text((x0 + w * 0.14, y0 + h * 0.2), "Δ", fontsize=9, color=TRAZO)
    _texto_centrado(pg, x0 + w/2, y0 + h*0.72, f'{d.get("corriente","")}A {d.get("sensibilidadMa","")}mA',
                    min(w*0.11, 8), TRAZO, fuente_max=w*0.9)
    if circuito:
        _texto_centrado(pg, x0 + w/2, y0 + h*0.87, circuito[:14], 7, GRIS, negrita=False, fuente_max=w*0.9)


def _protector(pg, x0, y0, w, h, d, circuito):
    r = min(w, h) * 0.1
    pg.draw_rect(pymupdf.Rect(x0 + 2, y0, x0 + w - 2, y0 + h), color=COLOR_ROL["protector"],
                fill=BLANCO, width=1.4, radius=0.10)
    for cx in (x0 + w * 0.28, x0 + w * 0.72):
        for cy in (y0 + h * 0.1, y0 + h * 0.9):
            _tornillo(pg, cx, cy, r, cruz=False)
    pg.draw_rect(pymupdf.Rect(x0 + w * 0.28, y0 + h * 0.24, x0 + w * 0.86, y0 + h * 0.46),
                color=TRAZO, fill=(0.93, 0.97, 0.94), width=0.8, radius=0.1)
    _texto_centrado(pg, x0 + w*0.57, y0 + h*0.38, f'{d.get("tensionV",220)}V', min(w*0.15, 10),
                    (0x1c/255, 0x6b/255, 0x3a/255), fuente_max=w*0.5)
    _texto_centrado(pg, x0 + w/2, y0 + h*0.77, "DPS", 8, TRAZO)
    if circuito:
        _texto_centrado(pg, x0 + w/2, y0 + h*0.9, circuito[:14], 6.8, GRIS, negrita=False, fuente_max=w*0.9)


def _bornera(pg, x0, y0, w, h, d):
    pg.draw_rect(pymupdf.Rect(x0 + 2, y0, x0 + w - 2, y0 + h), color=COLOR_ROL["tierra"],
                fill=BLANCO, width=1.4, radius=0.08)
    filas = 6
    alto_fila = h * 0.84 / filas
    y_ini = y0 + h * 0.06
    for i in range(filas):
        cy = y_ini + alto_fila * (i + 0.5)
        pg.draw_rect(pymupdf.Rect(x0 + w * 0.26, cy - alto_fila * 0.32, x0 + w * 0.74,
                                 cy + alto_fila * 0.32), color=TRAZO, width=0.6, radius=0.4)
        pg.draw_circle((x0 + w / 2, cy), alto_fila * 0.16, color=TRAZO, width=0.5)
    pg.insert_text((x0 + w * 0.4, y0 + h - 3), "PAT", fontsize=6, color=TRAZO)


def _dibujar_dispositivo(pg, x0, y0, w, h, d, circuito):
    if d["tipo"] == "diferencial":
        _diferencial(pg, x0, y0, w, h, d, circuito)
    elif d["tipo"] == "protector":
        _protector(pg, x0, y0, w, h, d, circuito)
    elif d["tipo"] == "bornera":
        _bornera(pg, x0, y0, w, h, d)
    else:
        _termica(pg, x0, y0, w, h, d, circuito or ("General" if d.get("rol") == "general" else ""))


def _ruta_a_pdf(g: "_Geom", t: dict, ruta: list) -> list:
    """Los puntos de una ruta trazada a mano en el editor vienen en píxeles
    de ESE lienzo (celda=64, franjas más altas). Se convierten a la posición
    lógica que representan (boca en X; piso + fracción dentro de la fila en
    Y) y se reconstruyen con la geometría de ESTA hoja -- nunca se usan
    directo, porque las dos escalas no tienen nada que ver entre sí."""
    if not ruta:
        return []
    pisos = max(t.get("pisos", 1), 1)
    out = []
    for p in ruta:
        x, y = p[0], p[1]
        posicion = (x - CANAL_WEB) / CELDA_WEB
        piso = max(0, min(pisos - 1, int((y - FRANJA_CANO_WEB) // ALTURA_PISO_WEB)))
        frac = (y - (FRANJA_CANO_WEB + piso * ALTURA_PISO_WEB)) / ALTURA_PISO_WEB
        out.append((g.x(posicion), g.y_piso(piso) + frac * (g.altura_piso - g.franja)))
    return out


# ---------------------------------------------------------------- geometría
class _Geom:
    def __init__(self, t: dict):
        self.t = t
        self.celda = 34
        self.alto_disp = 58
        self.banda = 30
        self.franja = 34
        self.margen_piso = 20
        self.altura_piso = self.franja + self.banda + self.alto_disp + self.banda + self.margen_piso
        # el ancho nominal (bocasPorPiso) puede quedar chico frente a lo que
        # de verdad está colocado —por ejemplo si el tablero se achicó
        # después de ubicar térmicas—, y eso recortaba la hoja en el borde.
        # Nunca hay que confiar sólo en el número declarado.
        boca_maxima = t.get("bocasPorPiso", 0)
        for d in t.get("dispositivos") or []:
            if d.get("piso") is not None and d.get("posicion") is not None:
                boca_maxima = max(boca_maxima, d["posicion"] + d["polos"])
        self.ancho = MARGEN * 2 + boca_maxima * self.celda
        self.alto = MARGEN * 2 + t["pisos"] * self.altura_piso - self.margen_piso + self.franja
        # red de seguridad: además de los dispositivos, se mide TODO lo que
        # realmente se va a dibujar (peines, puentes, cables -- incluidas sus
        # rutas a mano) y si algo cae más allá de lo que da boca_maxima, se
        # agranda la hoja para que entre. Así, aunque en el futuro aparezca
        # un cálculo de posición con error en algún tipo de conexión que
        # todavía no se encontró, el resultado es una hoja más grande, nunca
        # un tablero cortado en el borde.
        max_x, max_y = self.ancho, self.alto
        for con in t.get("conexiones") or []:
            if con["tipo"] == "peine":
                max_x = max(max_x, self.x(con["hasta"] + 1) + MARGEN)
            elif con["tipo"] == "puente":
                max_x = max(max_x, self.x(con["x"] + 1) + MARGEN)
        for cable in t.get("cables") or []:
            pts = [p for p in (_punto_endpoint(self, t, cable.get("origen")),
                               _punto_endpoint(self, t, cable.get("destino"))) if p]
            pts += _ruta_a_pdf(self, t, cable.get("ruta") or [])
            for (px, py) in pts:
                max_x = max(max_x, px + MARGEN)
                max_y = max(max_y, py + MARGEN)
        self.ancho, self.alto = max_x, max_y

    def x(self, posicion: float) -> float:
        return MARGEN + posicion * self.celda

    def y_piso(self, piso: int) -> float:
        return MARGEN + self.franja + piso * (self.altura_piso - self.franja)

    def y_riel(self, piso: int) -> float:
        return self.y_piso(piso) + self.banda


def _nombre_circuito(obra, circuito_id):
    if not circuito_id:
        return None
    c = next((x for x in obra.get("circuitos") or [] if x["id"] == circuito_id), None)
    return c.get("nombre") if c else None


# ---------------------------------------------------------------- cableado
def _ortogonalizar(pts):
    out = [pts[0]]
    for i in range(1, len(pts)):
        x0, y0 = out[-1]
        x1, y1 = pts[i]
        if x0 != x1 and y0 != y1:
            out.append((x0, y1))          # vertical primero, igual que en la web
        out.append((x1, y1))
    return out


def _segmentos(pts):
    segs = []
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        if x0 == x1 and y0 == y1:
            continue
        segs.append((x0, y0, x1, y1, y0 == y1))
    return segs


def _cruce(a, b):
    if a[4] == b[4]:
        return None
    h, v = (a, b) if a[4] else (b, a)
    hx0, hx1 = min(h[0], h[2]), max(h[0], h[2])
    vy0, vy1 = min(v[1], v[3]), max(v[1], v[3])
    m = 3
    if vy0 + m < h[1] < vy1 - m and hx0 + m < v[0] < hx1 - m:
        return (v[0], h[1])
    return None


LANE_SPACING = 2.6   # separación entre cables que comparten corredor, en pt


def _separar_paralelos(cables_con_pts):
    """Cuando varios cables corren un tramo por el mismo corredor (misma
    coordenada, rangos que se superponen) quedan dibujados exactamente uno
    encima del otro y no se puede seguir ninguno. Sólo se desplazan los
    tramos "del medio" de cada cable (ni el primero ni el último) -- así los
    extremos siguen enganchando exacto en cada terminal, y como el ortogonal
    alterna dirección en cada tramo, correr un tramo del medio nunca le
    genera un quiebre raro al tramo vecino: sólo lo alarga o acorta.
    Modifica `pts` (listas mutables) en el lugar."""
    entradas = []   # (cable_idx, seg_idx, 'h'|'v', coordenada, r0, r1)
    for ci, (_cid, pts, _cable) in enumerate(cables_con_pts):
        for si in range(1, len(pts) - 2):        # tramo del medio: pts[si] -> pts[si+1]
            x0, y0 = pts[si]
            x1, y1 = pts[si + 1]
            if y0 == y1 and x0 != x1:
                entradas.append((ci, si, "h", round(y0, 2), min(x0, x1), max(x0, x1)))
            elif x0 == x1 and y0 != y1:
                entradas.append((ci, si, "v", round(x0, 2), min(y0, y1), max(y0, y1)))

    padre = list(range(len(entradas)))

    def raiz(i):
        while padre[i] != i:
            padre[i] = padre[padre[i]]
            i = padre[i]
        return i

    def unir(i, j):
        ri, rj = raiz(i), raiz(j)
        if ri != rj:
            padre[ri] = rj

    por_corredor = {}
    for i, e in enumerate(entradas):
        por_corredor.setdefault((e[2], e[3]), []).append(i)
    for grupo in por_corredor.values():
        grupo.sort(key=lambda i: entradas[i][4])
        for a in range(len(grupo)):
            for b in range(a + 1, len(grupo)):
                i, j = grupo[a], grupo[b]
                if entradas[i][5] > entradas[j][4]:      # los rangos se superponen
                    unir(i, j)

    clusters = {}
    for i in range(len(entradas)):
        clusters.setdefault(raiz(i), []).append(i)

    for miembros in clusters.values():
        if len(miembros) < 2:
            continue
        miembros.sort(key=lambda i: cables_con_pts[entradas[i][0]][0])   # orden estable, por id de cable
        k = len(miembros)
        for lane, i in enumerate(miembros):
            ci, si, orient = entradas[i][0], entradas[i][1], entradas[i][2]
            off = (lane - (k - 1) / 2) * LANE_SPACING
            pts = cables_con_pts[ci][1]
            if orient == "h":
                pts[si][1] += off
                pts[si + 1][1] += off
            else:
                pts[si][0] += off
                pts[si + 1][0] += off


def _calcular_saltos(cables_con_pts):
    saltos = {}
    for i in range(len(cables_con_pts)):
        for j in range(i + 1, len(cables_con_pts)):
            for sa in _segmentos(cables_con_pts[i][1]):
                for sb in _segmentos(cables_con_pts[j][1]):
                    p = _cruce(sa, sb)
                    if p:
                        saltos.setdefault(cables_con_pts[j][0], []).append(p)
    return saltos


def _dibujar_cable(pg, pts, saltos, color):
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        horiz = y0 == y1
        en_tramo = [p for p in (saltos or []) if
                   (horiz and abs(p[1] - y0) < 0.6 and min(x0, x1) + 3 < p[0] < max(x0, x1) - 3) or
                   (not horiz and abs(p[0] - x0) < 0.6 and min(y0, y1) + 3 < p[1] < max(y0, y1) - 3)]
        en_tramo.sort(key=lambda p: p[0] if horiz else p[1], reverse=(x1 < x0 if horiz else y1 < y0))
        cur = (x0, y0)
        for (sx, sy) in en_tramo:
            if horiz:
                d = 1 if x1 > x0 else -1
                antes, despues = (sx - d * 4, y0), (sx + d * 4, y0)
                pico = (sx, y0 - 5)
            else:
                d = 1 if y1 > y0 else -1
                antes, despues = (x0, sy - d * 4), (x0, sy + d * 4)
                pico = (x0 + 5, sy)
            pg.draw_line(cur, antes, color=color, width=1.3)
            pg.draw_curve(antes, pico, despues, color=color, width=1.3)
            cur = despues
        pg.draw_line(cur, (x1, y1), color=color, width=1.3)


def _punto_endpoint(g: _Geom, t: dict, ep: dict):
    if not ep:
        return None
    if ep["tipo"] == "dispositivo":
        d = next((x for x in t["dispositivos"] if x["id"] == ep["id"]), None)
        if d is None or d.get("piso") is None:
            return None
        if d["tipo"] == "bornera":
            # la PAT es una bornera vertical de 6 terminales apilados en Y,
            # todos en el mismo X (ver _bornera) -- no es "arriba/abajo" con
            # el polo como desplazamiento en X, como sí pasa con las
            # térmicas. Tratarla igual corría el punto varias celdas afuera
            # del dispositivo (y a veces afuera de la hoja entera).
            x0, w = g.x(d["posicion"]), d["polos"] * g.celda - 2
            y0, h = g.y_riel(d["piso"]) + 2, g.alto_disp - 4
            filas = 6
            alto_fila = h * 0.84 / filas
            polo = ep.get("polo", 0) or 0
            return (x0 + w / 2, y0 + h * 0.06 + alto_fila * (polo + 0.5))
        cx = g.x(d["posicion"] + (ep.get("polo", 0) or 0) + 0.5)
        cy = g.y_riel(d["piso"]) + (2 if ep.get("lado") == "arriba" else g.alto_disp - 2)
        return (cx, cy)
    if ep["tipo"] == "peine":
        pe = next((c for c in t.get("conexiones") or [] if c["id"] == ep["id"]), None)
        if pe is None:
            return None
        return (g.x((pe["desde"] + pe["hasta"] + 1) / 2), g.y_riel(pe["piso"]) - 6)
    if ep["tipo"] == "puente":
        pu = next((c for c in t.get("conexiones") or [] if c["id"] == ep["id"]), None)
        if pu is None:
            return None
        y = (g.y_piso(pu["pisoDestino"]) if ep.get("lado") == "abajo"
            else g.y_riel(pu["pisoOrigen"]) + g.alto_disp)
        return (g.x(pu["x"] + 0.5), y)
    if ep["tipo"] == "cano":
        cano = next((c for c in t.get("canos") or [] if c["id"] == ep["id"]), None)
        if cano is None:
            return None
        hermanos = sorted([c for c in t.get("canos") or [] if c["lado"] == cano["lado"]],
                          key=lambda c: c["orden"])
        n = max(len(hermanos), 1)
        orden = next((i for i, c in enumerate(hermanos) if c["id"] == cano["id"]), 0)
        x = MARGEN + (orden + 0.5) * (g.ancho - 2 * MARGEN) / n
        y = MARGEN + 10 if cano["lado"] == "arriba" else g.alto - MARGEN - 10
        return (x, y)
    return None


# ---------------------------------------------------------------- páginas
def _fondo(pg, g, t, fondo_riel=FONDO_RIEL):
    pg.draw_rect(pg.rect, color=None, fill=FONDO_HOJA)
    for piso in range(t["pisos"]):
        y0 = g.y_riel(piso)
        pg.draw_rect(pymupdf.Rect(MARGEN, y0, g.ancho - MARGEN, y0 + g.alto_disp),
                    color=(0.68, 0.73, 0.73), fill=fondo_riel, width=0.8, radius=0.05)
        pg.insert_text((MARGEN + 2, y0 - 5), f"Piso {piso+1}", fontsize=7, color=GRIS)


def _pagina_conexionado(doc, t: dict, obra: dict):
    g = _Geom(t)
    pg = doc.new_page(width=g.ancho, height=g.alto)
    _fondo(pg, g, t)
    pg.insert_text((MARGEN, 20), f"Tablero — {t.get('nombre','')} · conexionado",
                   fontsize=13, fontname="hebo", color=NAVY)

    # peines: dos barras (fase y neutro) si corresponde
    for con in t.get("conexiones") or []:
        if con["tipo"] != "peine":
            continue
        y = g.y_riel(con["piso"]) - 8
        x0, x1 = g.x(con["desde"]), g.x(con["hasta"] + 1)
        pg.draw_line((x0, y), (x1, y), color=COLOR_POLARIDAD["fase"], width=2.6)
        pg.draw_line((x0, y - 5), (x1, y - 5), color=COLOR_POLARIDAD["neutro"], width=2.6)

    # puentes: un conductor entre pisos
    for con in t.get("conexiones") or []:
        if con["tipo"] != "puente":
            continue
        x = g.x(con["x"] + 0.5)
        y0 = g.y_riel(con["pisoOrigen"]) + g.alto_disp
        y1 = g.y_piso(con["pisoDestino"])
        pg.draw_line((x, y0), (x, y1), color=COLOR_POLARIDAD.get(con.get("polaridad"), GRIS), width=2)

    # cables: ruteo en escuadra (vertical primero), separados en carriles
    # donde varios comparten corredor, con salto donde se cruzan
    con_pts = []
    for cable in t.get("cables") or []:
        a = _punto_endpoint(g, t, cable.get("origen"))
        b = _punto_endpoint(g, t, cable.get("destino"))
        if not a or not b:
            continue
        ruta = _ruta_a_pdf(g, t, cable.get("ruta") or [])
        pts = [list(p) for p in _ortogonalizar([a, *ruta, b])]
        con_pts.append((cable["id"], pts, cable))
    _separar_paralelos(con_pts)
    saltos = _calcular_saltos([(cid, pts) for cid, pts, _ in con_pts])
    for cid, pts, cable in con_pts:
        color = COLOR_POLARIDAD.get(cable.get("polaridad"), GRIS)
        _dibujar_cable(pg, pts, saltos.get(cid), color)

    # dispositivos, por encima del cableado
    for d in t.get("dispositivos") or []:
        if d.get("piso") is None:
            continue
        x0 = g.x(d["posicion"])
        w = d["polos"] * g.celda - 2
        y0 = g.y_riel(d["piso"]) + 2
        h = g.alto_disp - 4
        _dibujar_dispositivo(pg, x0, y0, w, h, d, _nombre_circuito(obra, d.get("circuitoId")))

    _bocas_de_cano(pg, g, t, obra)


def _bocas_de_cano(pg, g, t, obra):
    for lado in ("arriba", "abajo"):
        canos = sorted([c for c in t.get("canos") or [] if c["lado"] == lado],
                       key=lambda c: c["orden"])
        n = max(len(canos), 1)
        y = MARGEN + 10 if lado == "arriba" else g.alto - MARGEN - 10
        for i, cano in enumerate(canos):
            x = MARGEN + (i + 0.5) * (g.ancho - 2 * MARGEN) / n
            etiqueta = ("Acometida" if cano["tipo"] == "acometida" else
                       "Jabalina" if cano["tipo"] == "tierra" else
                       (_nombre_circuito(obra, cano.get("circuitoId")) or "Circuito"))
            color = (COLOR_POLARIDAD["tierra"] if cano["tipo"] == "tierra"
                    else COLOR_POLARIDAD["fase"] if cano["tipo"] == "acometida" else NAVY)
            pg.draw_circle((x, y), 6, color=color, fill=BLANCO, width=1.4)
            pg.draw_circle((x, y), 2.6, color=None, fill=color)
            pg.insert_textbox(pymupdf.Rect(x - 34, y + (10 if lado == "arriba" else -24),
                                          x + 34, y + (24 if lado == "arriba" else -10)),
                              etiqueta[:16], fontsize=6.4, color=GRIS, align=1)


def _pagina_tapa(doc, t: dict, obra: dict):
    """Vista con la tapa puesta: sólo las térmicas y su etiqueta, sin
    cableado ni caños — para pegar adentro del tablero como guía."""
    g = _Geom(t)
    pg = doc.new_page(width=g.ancho, height=g.alto)
    pg.draw_rect(pg.rect, color=None, fill=BLANCO)
    pg.insert_text((MARGEN, 20), f"Tablero — {t.get('nombre','')} · guía de tapa",
                   fontsize=13, fontname="hebo", color=NAVY)
    for piso in range(t["pisos"]):
        y0 = g.y_riel(piso)
        pg.draw_rect(pymupdf.Rect(MARGEN, y0, g.ancho - MARGEN, y0 + g.alto_disp),
                    color=(0.88, 0.88, 0.88), fill=(0.97, 0.97, 0.97), width=0.7, radius=0.05)
    for d in t.get("dispositivos") or []:
        if d.get("piso") is None:
            continue
        x0 = g.x(d["posicion"])
        w = d["polos"] * g.celda - 2
        y0 = g.y_riel(d["piso"]) + 2
        h = g.alto_disp - 4
        _dibujar_dispositivo(pg, x0, y0, w, h, d, _nombre_circuito(obra, d.get("circuitoId")))


def generar(t: dict, obra: dict) -> bytes:
    doc = pymupdf.open()
    _pagina_conexionado(doc, t, obra)
    _pagina_tapa(doc, t, obra)
    salida = io.BytesIO()
    doc.save(salida)
    doc.close()
    return salida.getvalue()
