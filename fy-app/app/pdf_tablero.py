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
from datetime import datetime
import pymupdf
from . import config as cfgmod

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


def _texto_multilinea(pg, cx, y_top, texto, fontsize, color, ancho_max, negrita=True, max_lineas=3):
    """Como _texto_centrado, pero envuelve en varios renglones en vez de
    cortar el texto -- para una descripción larga de circuito, que es lo
    más importante de la guía de tapa, conviene verla completa aunque
    ocupe 2 o 3 líneas, no truncada en una sola."""
    if not texto:
        return 0
    fname = "hebo" if negrita else "helv"
    palabras = texto.split()
    lineas, actual = [], ""
    for palabra in palabras:
        prueba = (actual + " " + palabra).strip()
        if not actual or pymupdf.get_text_length(prueba, fontname=fname, fontsize=fontsize) <= ancho_max:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    if len(lineas) > max_lineas:
        lineas = lineas[:max_lineas]
        ultima = lineas[-1]
        while ultima and pymupdf.get_text_length(ultima + "…", fontname=fname, fontsize=fontsize) > ancho_max:
            ultima = ultima[:-1]
        lineas[-1] = ultima + "…"
    interlineado = fontsize * 1.25
    for i, linea in enumerate(lineas):
        w = pymupdf.get_text_length(linea, fontname=fname, fontsize=fontsize)
        pg.insert_text((cx - w / 2, y_top + i * interlineado), linea, fontsize=fontsize,
                       fontname=fname, color=color)
    return len(lineas) * interlineado


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
    tx, ty = x0 + w * 0.14, y0 + h * 0.2
    ts = 7.5
    pg.draw_line((tx + ts * 0.35, ty - ts), (tx, ty), color=TRAZO, width=0.9)
    pg.draw_line((tx + ts * 0.35, ty - ts), (tx + ts * 0.7, ty), color=TRAZO, width=0.9)
    pg.draw_line((tx, ty), (tx + ts * 0.7, ty), color=TRAZO, width=0.9)
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


def _cuerpo_conector_peine(g: "_Geom", con: dict) -> tuple[float, float]:
    """El cuerpo del conector siempre se apoya a la misma altura, tomando
    como referencia la barra de arriba (neutro) -- así uno de fase y uno de
    neutro sobre el mismo peine quedan alineados a la vista, aunque la
    patita hacia la barra de fase (más abajo) sea un poco más larga."""
    x = g.x(con["posicion"])
    y_neutro = g.y_riel(con["piso"]) - 13
    return (x, y_neutro - 7.5)


def _terminal_conector_peine(g: "_Geom", con: dict) -> tuple[float, float]:
    """Dónde engancha un cable: en la punta de la patita que sale del
    cuerpo, hacia arriba (carga superior) o hacia el costado (carga
    lateral) -- el cuerpo en sí siempre está apoyado arriba de la barra."""
    x, y = _cuerpo_conector_peine(g, con)
    if con.get("carga") == "lateral":
        return (x + 11, y)
    return (x, y - 7.5)


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
            elif con["tipo"] == "conectorPeine":
                tx, ty = _terminal_conector_peine(self, con)
                max_x, max_y = max(max_x, tx + MARGEN), max(max_y, ty + MARGEN)
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


def _descripcion_circuito(obra, circuito_id):
    if not circuito_id:
        return None
    c = next((x for x in obra.get("circuitos") or [] if x["id"] == circuito_id), None)
    return (c.get("notas") or "").strip() if c else None


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
    encima del otro y no se puede seguir ninguno -- el caso más común es
    justo el más importante: varios conductores (fase/neutro/tierra) que
    salen del MISMO punto de origen (una entrada de caño) hacia destinos
    distintos comparten el primer tramo entero, that es el tramo por el que
    "salen" del origen. Por eso acá se consideran TODOS los tramos de cada
    cable, incluido el primero y el último -- se acepta que el extremo quede
    a unos pocos puntos del centro exacto de la terminal (el propio dibujo
    de la terminal ya tiene un margen visual de sobra para disimularlo),
    a cambio de que los conductores dejen de superponerse por completo.
    Modifica `pts` (listas mutables) en el lugar."""
    entradas = []   # (cable_idx, seg_idx, 'h'|'v', coordenada, r0, r1)
    for ci, (_cid, pts, _cable) in enumerate(cables_con_pts):
        for si in range(0, len(pts) - 1):        # todos los tramos: pts[si] -> pts[si+1]
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
                antes, despues = (sx - d * 2.2, y0), (sx + d * 2.2, y0)
                pico = (sx, y0 - 2.6)
            else:
                d = 1 if y1 > y0 else -1
                antes, despues = (x0, sy - d * 2.2), (x0, sy + d * 2.2)
                pico = (x0 + 2.6, sy)
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
    if ep["tipo"] == "conectorPeine":
        con = next((c for c in t.get("conexiones") or [] if c["id"] == ep["id"]), None)
        if con is None:
            return None
        return _terminal_conector_peine(g, con)
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
    pg.insert_text((MARGEN, 20), f"Tablero · {t.get('nombre','')} · conexionado",
                   fontsize=13, fontname="hebo", color=NAVY)

    # peines: dos barras (fase y neutro) si corresponde
    for con in t.get("conexiones") or []:
        if con["tipo"] != "peine":
            continue
        y = g.y_riel(con["piso"]) - 8
        x0, x1 = g.x(con["desde"]), g.x(con["hasta"] + 1)
        pg.draw_line((x0, y), (x1, y), color=COLOR_POLARIDAD["fase"], width=2.6)
        pg.draw_line((x0, y - 5), (x1, y - 5), color=COLOR_POLARIDAD["neutro"], width=2.6)

    # conectores de peine: el cuerpo SIEMPRE se apoya arriba de la barra del
    # peine (nunca al costado) -- lo que cambia con la carga es hacia dónde
    # sale el cable real desde ese cuerpo: derecho hacia arriba (superior) o
    # hacia el costado (lateral). Ese cable se dibuja aparte, como cualquier
    # otro (más abajo, en el bloque de "cables").
    for con in t.get("conexiones") or []:
        if con["tipo"] != "conectorPeine":
            continue
        color = COLOR_POLARIDAD.get(con.get("polaridad"), GRIS)
        x = g.x(con["posicion"])
        y_barra = g.y_riel(con["piso"]) - (13 if con.get("polaridad") == "neutro" else 8)
        xc, yc = _cuerpo_conector_peine(g, con)
        tx, ty = _terminal_conector_peine(g, con)
        pg.draw_line((x, y_barra), (xc, yc), color=color, width=2.2)
        pg.draw_line((xc, yc), (tx, ty), color=color, width=1.9)
        w, h = 7.2, 7.8
        pg.draw_rect(pymupdf.Rect(xc - w / 2, yc - h / 2, xc + w / 2, yc + h / 2),
                    color=(0.6, 0.6, 0.6), fill=color, width=0.7, radius=0.25)
        r = min(w, h) * 0.24
        pg.draw_circle((xc, yc), r, color=BLANCO, fill=BLANCO)
        pg.draw_line((xc - r * 0.6, yc), (xc + r * 0.6, yc), color=color, width=1.1)
        pg.draw_circle((tx, ty), 1.4, color=color, fill=color)

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

    # dispositivos, por encima del cableado -- se deja un margen visible a
    # los costados (en vez de ocupar la celda entera) para que un cable que
    # pasa por atrás asome en el hueco con la térmica de al lado
    for d in t.get("dispositivos") or []:
        if d.get("piso") is None:
            continue
        x0 = g.x(d["posicion"]) + g.celda * 0.16
        w = d["polos"] * g.celda - g.celda * 0.32
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
    cableado ni caños — para pegar adentro del tablero como guía. Con un
    enmarcado tipo gabinete real (marco + tornillos en las esquinas), para
    que la hoja se sienta como el tablero físico y no sólo un diagrama.
    Las térmicas van más separadas que en la hoja de conexionado -- acá no
    hay cables que necesiten espacio para pasar, pero sí hace falta lugar
    para la descripción de cada circuito, que es lo más importante de esta
    hoja."""
    g = _Geom(t)
    ESCALA_X = 1.45   # separación extra entre térmicas, sólo en esta hoja
    boca_max = max([t.get("bocasPorPiso", 0) or 0] +
                   [d["posicion"] + d["polos"] for d in t.get("dispositivos") or []
                    if d.get("piso") is not None] + [0])

    def xt(pos):
        return MARGEN + pos * g.celda * ESCALA_X

    ancho_disp = MARGEN * 2 + boca_max * g.celda * ESCALA_X
    MARCO = 16
    ancho, alto = ancho_disp + MARCO * 2, g.alto + MARCO * 2 + 8
    pg = doc.new_page(width=ancho, height=alto)
    pg.draw_rect(pg.rect, color=None, fill=(0.93, 0.94, 0.95))
    pg.insert_text((MARCO, 20), f"Tablero · {t.get('nombre','')} · guía de tapa",
                   fontsize=13, fontname="hebo", color=NAVY)
    # el gabinete en sí: un marco grueso con tornillos en las esquinas,
    # como para que se sienta la tapa real del tablero
    y_gabinete = 30
    marco_rect = pymupdf.Rect(MARCO, y_gabinete, ancho - MARCO, y_gabinete + g.alto)
    pg.draw_rect(marco_rect, color=(0.35, 0.38, 0.42), fill=(0.99, 0.99, 0.98), width=2.4, radius=0.02)
    for esq_x in (marco_rect.x0 + 9, marco_rect.x1 - 9):
        for esq_y in (marco_rect.y0 + 9, marco_rect.y1 - 9):
            _tornillo(pg, esq_x, esq_y, 3.4, cruz=True)
    dx, dy = MARCO, y_gabinete
    for piso in range(t["pisos"]):
        y0 = g.y_riel(piso) + dy
        pg.draw_rect(pymupdf.Rect(dx + MARGEN, y0, dx + ancho_disp - MARGEN, y0 + g.alto_disp),
                    color=(0.88, 0.88, 0.88), fill=(0.97, 0.97, 0.97), width=0.7, radius=0.05)
    for d in t.get("dispositivos") or []:
        if d.get("piso") is None:
            continue
        margen_disp = g.celda * ESCALA_X * 0.11
        x0 = dx + xt(d["posicion"]) + margen_disp
        w = d["polos"] * g.celda * ESCALA_X - margen_disp * 2
        y0 = dy + g.y_riel(d["piso"]) + 2
        h = g.alto_disp - 4
        _dibujar_dispositivo(pg, x0, y0, w, h, d, _nombre_circuito(obra, d.get("circuitoId")))
        # con circuito: circuito.notas es la única fuente (la misma que se
        # edita en Circuitos y en el panel de Tablero) -- nunca d.descripcion,
        # que sólo aplica a dispositivos sin circuito (térmica general,
        # diferencial, protector, bornera).
        cid = d.get("circuitoId")
        desc = _descripcion_circuito(obra, cid) if cid else (d.get("descripcion") or "").strip() or None
        if desc:
            _texto_multilinea(pg, x0 + w / 2, y0 + h + 13, desc, 8.5, TRAZO,
                              d["polos"] * g.celda * ESCALA_X * 0.92, negrita=True, max_lineas=3)


def _circuito_de(obra, circuito_id):
    if not circuito_id:
        return None
    return next((x for x in obra.get("circuitos") or [] if x["id"] == circuito_id), None)


def _contar_lineas(texto, fontsize, ancho_max, max_lineas=3):
    """Misma lógica de ajuste de línea que _texto_multilinea, pero sin
    dibujar nada -- para poder calcular de antemano cuánto va a ocupar una
    descripción de circuito y armar la página del tamaño justo, en vez de
    adivinar un alto fijo con de más o de menos lugar."""
    if not texto:
        return 0
    fname = "helv"
    palabras = texto.split()
    lineas, actual = [], ""
    for palabra in palabras:
        prueba = (actual + " " + palabra).strip()
        if not actual or pymupdf.get_text_length(prueba, fontname=fname, fontsize=fontsize) <= ancho_max:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return min(len(lineas), max_lineas)


# ---------------------------------------------------------------- unifilar
def _simbolo_interruptor(pg, x, y, alto=18, color=None):
    """Símbolo IEC de interruptor termomagnético unipolar: el conductor se
    corta en un hueco chico, con dos terminales (puntos) y una diagonal
    entre ellos -- el símbolo de "llave abierta" de cualquier plano
    unifilar, no una convención propia de esta app."""
    color = color or TRAZO
    g = alto * 0.5
    y0, y1 = y - g / 2, y + g / 2
    pg.draw_line((x, y - alto / 2), (x, y0), color=color, width=1.3)
    pg.draw_line((x, y1), (x, y + alto / 2), color=color, width=1.3)
    pg.draw_circle((x, y0), 1.3, color=color, fill=color)
    pg.draw_circle((x, y1), 1.3, color=color, fill=color)
    pg.draw_line((x - g * 0.4, y0 + g * 0.1), (x + g * 0.4, y1 - g * 0.1), color=color, width=1.4)


def _simbolo_diferencial(pg, x, y, alto=22, color=None):
    """Símbolo de interruptor diferencial: un cuadro en la línea con "IΔn"
    adentro -- así es como lo escribe cualquier plano o catálogo, no sólo
    la letra griega sola. La Δ se dibuja a mano (un triángulo) en vez de
    escribirla como texto porque la fuente base no siempre trae ese glifo
    y queda un carácter roto."""
    color = color or COLOR_ROL["diferencial"]
    w, h = alto * 1.15, alto * 0.8
    pg.draw_line((x, y - alto / 2), (x, y - h / 2), color=color, width=1.3)
    pg.draw_line((x, y + h / 2), (x, y + alto / 2), color=color, width=1.3)
    r = pymupdf.Rect(x - w / 2, y - h / 2, x + w / 2, y + h / 2)
    pg.draw_rect(r, color=color, fill=BLANCO, width=1.1)
    fs = h * 0.5
    ancho_i = pymupdf.get_text_length("I", fontname="hebo", fontsize=fs)
    ancho_n = pymupdf.get_text_length("n", fontname="helv", fontsize=fs)
    tri = h * 0.3
    total = ancho_i + tri * 1.3 + ancho_n
    x0 = x - total / 2
    ty = y + h * 0.18
    pg.insert_text((x0, ty), "I", fontsize=fs, fontname="hebo", color=color)
    tri_cx = x0 + ancho_i + tri * 0.65
    tri_top, tri_bot = ty - tri * 0.9, ty + tri * 0.12
    pg.draw_line((tri_cx, tri_top), (tri_cx - tri * 0.5, tri_bot), color=color, width=1.0)
    pg.draw_line((tri_cx, tri_top), (tri_cx + tri * 0.5, tri_bot), color=color, width=1.0)
    pg.draw_line((tri_cx - tri * 0.5, tri_bot), (tri_cx + tri * 0.5, tri_bot), color=color, width=1.0)
    pg.insert_text((tri_cx + tri * 0.65, ty), "n", fontsize=fs * 0.85, fontname="helv", color=color)


def _simbolo_tierra(pg, x, y, ancho=14, color=None):
    """Símbolo IEC de puesta a tierra: tres barras horizontales decrecientes."""
    color = color or COLOR_POLARIDAD["tierra"]
    for i, w in enumerate((ancho, ancho * 0.62, ancho * 0.3)):
        yy = y + i * 3.6
        pg.draw_line((x - w / 2, yy), (x + w / 2, yy), color=color, width=1.3)


# ------------------------------------------------------- íconos de circuito
# Pictogramas simples (sólo trazos, sin relleno de color) para que se lea de
# un vistazo qué alimenta cada circuito -- el mismo espíritu que cualquier
# esquema unifilar entregable, sin pretender ser un dibujo técnico del
# artefacto real.
def _icono_lampara(pg, cx, cy, s, color):
    r = s * 0.3
    pg.draw_circle((cx, cy - s * 0.06), r, color=color, fill=BLANCO, width=1.1)
    pg.draw_line((cx - r * 0.4, cy - s * 0.06), (cx + r * 0.4, cy - s * 0.06), color=color, width=0.8)
    for i in range(3):
        yy = cy - s * 0.06 + r + i * (s * 0.08)
        pg.draw_line((cx - s * 0.12, yy), (cx + s * 0.12, yy), color=color, width=0.9)


def _icono_toma(pg, cx, cy, s, color):
    w = h = s * 0.6
    pg.draw_rect(pymupdf.Rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2),
                color=color, fill=BLANCO, width=1.1, radius=0.14)
    for dx in (-s * 0.11, s * 0.11):
        pg.draw_line((cx + dx, cy - s * 0.1), (cx + dx, cy + s * 0.08), color=color, width=1.3)


def _icono_lavarropas(pg, cx, cy, s, color):
    w, h = s * 0.58, s * 0.66
    pg.draw_rect(pymupdf.Rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2),
                color=color, fill=BLANCO, width=1.1, radius=0.1)
    pg.draw_circle((cx, cy + s * 0.06), s * 0.19, color=color, width=1.0)
    pg.draw_circle((cx, cy + s * 0.06), s * 0.09, color=color, width=0.8)
    pg.draw_line((cx - w * 0.3, cy - h * 0.3), (cx + w * 0.12, cy - h * 0.3), color=color, width=0.9)


def _icono_termotanque(pg, cx, cy, s, color):
    w, h = s * 0.4, s * 0.7
    pg.draw_rect(pymupdf.Rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2),
                color=color, fill=BLANCO, width=1.1, radius=0.4)
    pg.draw_line((cx - w * 0.3, cy - h * 0.12), (cx + w * 0.3, cy - h * 0.12), color=color, width=0.9)


def _icono_cocina(pg, cx, cy, s, color):
    w, h = s * 0.64, s * 0.54
    pg.draw_rect(pymupdf.Rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2),
                color=color, fill=BLANCO, width=1.1, radius=0.08)
    for dx in (-w * 0.22, w * 0.22):
        for dy in (-h * 0.2, h * 0.2):
            pg.draw_circle((cx + dx, cy + dy), s * 0.065, color=color, width=0.9)


def _icono_aire(pg, cx, cy, s, color):
    w, h = s * 0.76, s * 0.32
    pg.draw_rect(pymupdf.Rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2),
                color=color, fill=BLANCO, width=1.1, radius=0.3)
    for i in range(3):
        xx = cx - w * 0.24 + i * (w * 0.24)
        pg.draw_line((xx, cy + h * 0.1), (xx + w * 0.1, cy + h * 0.34), color=color, width=0.9)


def _icono_ducha(pg, cx, cy, s, color):
    w = s * 0.5
    pg.draw_line((cx - w / 2, cy - s * 0.24), (cx + w / 2, cy - s * 0.24), color=color, width=1.3)
    pg.draw_line((cx - w * 0.32, cy - s * 0.24), (cx - w * 0.32, cy - s * 0.32), color=color, width=1.0)
    pg.draw_line((cx + w * 0.32, cy - s * 0.24), (cx + w * 0.32, cy - s * 0.32), color=color, width=1.0)
    for dx in (-w * 0.28, 0, w * 0.28):
        pg.draw_line((cx + dx, cy - s * 0.16), (cx + dx, cy + s * 0.26), color=color, width=0.9)


def _icono_generico(pg, cx, cy, s, color):
    w = h = s * 0.5
    pg.draw_rect(pymupdf.Rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2),
                color=color, fill=BLANCO, width=1.1, radius=0.1)
    _texto_centrado(pg, cx, cy + s * 0.1, "E", s * 0.4, color, negrita=True)


def _icono_para_circuito(circuito):
    tipo = (circuito or {}).get("tipo")
    texto = ((circuito or {}).get("notas") or "").lower()
    if tipo in ("IUG", "IUE") or "ilumina" in texto:
        return _icono_lampara
    if "termotanque" in texto or "calefón" in texto or "calefon" in texto:
        return _icono_termotanque
    if "cocina" in texto or "horno" in texto or "anafe" in texto:
        return _icono_cocina
    if tipo == "ACU" or "aire acondicionado" in texto or " a/a" in texto:
        return _icono_aire
    if "lavarropa" in texto:
        return _icono_lavarropas
    if "ducha" in texto:
        return _icono_ducha
    if tipo == "TUG":
        return _icono_toma
    return _icono_generico


def _tabla_referencias(pg, x0, y0, w):
    """Tabla de referencias con el mismo formato de dos columnas (símbolo /
    descripción) que trae cualquier plano de este tipo -- se arma como
    tabla de verdad (con filas y encabezado), no como una lista suelta."""
    filas = [
        (lambda cx, cy: _simbolo_interruptor(pg, cx, cy, alto=13, color=NAVY), "Interruptor termomagnético"),
        (lambda cx, cy: _simbolo_diferencial(pg, cx, cy, alto=13), "Interruptor diferencial"),
        (lambda cx, cy: pg.draw_line((cx - 7, cy), (cx + 7, cy), color=COLOR_POLARIDAD["fase"], width=2.2),
         "Conductor de fase (L)"),
        (lambda cx, cy: pg.draw_line((cx - 7, cy), (cx + 7, cy), color=COLOR_POLARIDAD["neutro"], width=2.2),
         "Conductor de neutro (N)"),
        (lambda cx, cy: pg.draw_line((cx - 7, cy), (cx + 7, cy), color=COLOR_POLARIDAD["tierra"], width=1.8,
                                     dashes="[2 1.4] 0"), "Conductor de protección (PE)"),
        (lambda cx, cy: _simbolo_tierra(pg, cx, cy + 2, ancho=10), "Puesta a tierra"),
    ]
    fila_h = 17
    alto = 20 + len(filas) * fila_h
    pg.draw_rect(pymupdf.Rect(x0, y0, x0 + w, y0 + alto), color=(0.8, 0.82, 0.84), fill=BLANCO,
                width=0.8, radius=0.02)
    _texto_centrado(pg, x0 + w / 2, y0 + 13, "REFERENCIAS", 8, NAVY, negrita=True)
    pg.draw_line((x0, y0 + 19), (x0 + w, y0 + 19), color=(0.85, 0.86, 0.87), width=0.6)
    col_simbolo = x0 + 22
    for i, (dibujar, etiqueta) in enumerate(filas):
        cy = y0 + 19 + fila_h * (i + 0.55)
        dibujar(col_simbolo, cy)
        pg.insert_text((x0 + 42, cy + 3), etiqueta, fontsize=6.6, fontname="helv", color=TRAZO)
        if i < len(filas) - 1:
            pg.draw_line((x0, y0 + 19 + fila_h * (i + 1)), (x0 + w, y0 + 19 + fila_h * (i + 1)),
                        color=(0.92, 0.93, 0.94), width=0.5)
    return alto


def _caja_datos_generales(pg, x0, y0, w, fases):
    """Ficha de datos generales de la instalación -- tensión, sistema,
    puesta a tierra, norma. La mayoría son estándar para una instalación
    residencial conectada a red en Argentina (por eso esta app ya asume
    AEA en todos lados: H07V-U, IUG/TUG/TUE, etc.) y no hay ningún campo
    hoy donde cargarlos obra por obra -- si en algún momento se agregan,
    acá es el lugar natural para leerlos en vez de estos valores fijos."""
    filas = [
        ("TENSIÓN NOMINAL", "380 V~  50 Hz" if fases == 3 else "220 V~  50 Hz"),
        ("SISTEMA", "TT"),
        ("PUESTA A TIERRA", "Jabalina 5/8\" x 2,40 m"),
        ("RESISTENCIA ESTIMADA", "< 10 ohm"),
        ("NORMA APLICADA", "AEA 90364"),
    ]
    fila_h = 16.4
    alto = len(filas) * fila_h
    col_izq = w * 0.46
    pg.draw_rect(pymupdf.Rect(x0, y0, x0 + w, y0 + alto), color=(0.8, 0.82, 0.84), fill=BLANCO, width=0.8)
    for i, (k, v) in enumerate(filas):
        yy = y0 + i * fila_h
        if i:
            pg.draw_line((x0, yy), (x0 + w, yy), color=(0.88, 0.89, 0.9), width=0.5)
        pg.draw_line((x0 + col_izq, yy), (x0 + col_izq, yy + fila_h), color=(0.88, 0.89, 0.9), width=0.5)
        pg.insert_text((x0 + 8, yy + fila_h * 0.68), k, fontsize=6.6, fontname="hebo", color=TRAZO)
        pg.insert_text((x0 + col_izq + 8, yy + fila_h * 0.68), v, fontsize=6.8, fontname="helv", color=NAVY)
    return alto


def _pagina_unifilar(doc, t: dict, obra: dict):
    """Esquema unifilar del tablero: la topología eléctrica (interruptor
    general → diferencial → barras → una térmica por circuito, con su
    ícono, descripción y sección de cable), no la disposición física como
    las otras dos hojas. Pensada para entregar junto con el resto de la
    documentación, con el mismo formato que trae cualquier plano de este
    tipo que le llegue al cliente.

    Se apoya en datos que la app ya tiene (protecciones, secciones,
    descripción de cada circuito); los datos generales de la instalación
    (tensión, sistema, puesta a tierra, norma) son estándar para el tipo de
    obra que maneja esta app -- ver _caja_datos_generales. Lo único que
    deliberadamente NO se muestra es un resumen de potencias por circuito
    (como el que suele traer un plano así), porque esta app hoy no carga
    ninguna potencia por circuito en ningún lado: mostrarlo sería
    inventar un número, no informarlo."""
    dispositivos = t.get("dispositivos") or []
    general = next((d for d in dispositivos if d.get("tipo") == "termica" and d.get("rol") == "general"), None)
    diferencial = next((d for d in dispositivos if d.get("tipo") == "diferencial"), None)
    tierra = next((d for d in dispositivos if d.get("tipo") == "bornera"), None)
    ramales = sorted(
        [d for d in dispositivos if d.get("tipo") in ("termica", "protector") and d.get("rol") != "general"],
        key=lambda d: (d.get("piso") if d.get("piso") is not None else 999,
                       d.get("posicion") if d.get("posicion") is not None else 999))
    fases = t.get("fases", 1)
    hilos = 5 if fases == 3 else 3   # F+F+F+N+PE vs. F+N+PE, para la etiqueta "n x sección"

    COL = 106
    M = 28
    INFO_W = 232
    REF_W = 210
    X_CADENA = M + INFO_W + 46
    X_RAMALES = X_CADENA + 100
    ancho = max(X_CADENA + REF_W + 60, X_RAMALES + max(len(ramales), 1) * COL - COL / 2 + M + REF_W + 40)

    # --- alto: se calcula de antemano, igual que antes, según la descripción
    # más larga y si hay diferencial/tierra, para no dejar una hoja con un
    # tamaño fijo que sobre o falte
    y0_cadena = 78
    y_gen0 = y0_cadena + 16 + (22 + 14 if general else 0)
    y_dif0 = y_gen0 + (24 + 16 if diferencial else 0)
    y_bus0 = y_dif0 + 14
    y_ramal0 = y_bus0 + 24 + 44                       # y_ramal + separación hasta el ícono
    max_desc_alto = 0
    for d in ramales:
        circuito = _circuito_de(obra, d.get("circuitoId"))
        desc = (circuito.get("notas") or "").strip() if circuito else ""
        if not desc and d.get("tipo") == "protector":
            desc = "Protector de sobretensión"
        n_lineas = _contar_lineas(desc, 6.6, COL - 12) if desc else 1
        max_desc_alto = max(max_desc_alto, n_lineas * 6.6 * 1.25)
    y_final_ramales_est = y_ramal0 + 13 + 11 + max_desc_alto + 13
    info_h = 5 * 16.4                       # debe coincidir con _caja_datos_generales
    ref_h = 20 + 6 * 17                     # debe coincidir con _tabla_referencias
    y_fin_fichas = (y0_cadena - 6) + max(info_h, ref_h)
    alto_diagrama = max(y_final_ramales_est, y_fin_fichas)
    NOTAS_H = 46
    TITULO_H = 30
    alto = alto_diagrama + 20 + NOTAS_H + TITULO_H + M

    pg = doc.new_page(width=ancho, height=alto)
    pg.draw_rect(pg.rect, color=None, fill=FONDO_HOJA)
    _texto_centrado(pg, ancho / 2, 24, "ESQUEMA UNIFILAR DE TABLERO", 14, NAVY, negrita=True)
    _texto_centrado(pg, ancho / 2, 40, t.get("nombre", ""), 10, GRIS, negrita=True)

    # ficha de datos generales, arriba a la izquierda
    _caja_datos_generales(pg, M, y0_cadena - 6, INFO_W, fases)
    # tabla de referencias, arriba a la derecha
    _tabla_referencias(pg, ancho - M - REF_W, y0_cadena - 6, REF_W)

    x = X_CADENA
    y = y0_cadena
    pg.insert_text((x - 20, y - 4), "F (L)", fontsize=7, fontname="hebo", color=COLOR_POLARIDAD["fase"])
    pg.insert_text((x + 6, y - 4), "N", fontsize=7, fontname="hebo", color=COLOR_POLARIDAD["neutro"])
    y_bajada = y + 12
    pg.draw_line((x - 9, y), (x - 9, y_bajada), color=COLOR_POLARIDAD["fase"], width=1.6)
    pg.draw_line((x + 9, y), (x + 9, y_bajada), color=COLOR_POLARIDAD["neutro"], width=1.6)

    def _tramo(y0, alto_tramo):
        y1 = y0 + alto_tramo
        pg.draw_line((x - 9, y0), (x - 9, y1), color=COLOR_POLARIDAD["fase"], width=1.6)
        pg.draw_line((x + 9, y0), (x + 9, y1), color=COLOR_POLARIDAD["neutro"], width=1.6)
        return y1

    y_gen = y_bajada
    if general:
        y_gen = _tramo(y_bajada, 14)
        _simbolo_interruptor(pg, x, y_gen, color=NAVY)
        lx = x + 20
        pg.insert_text((lx, y_gen - 6), "INTERRUPTOR TERMOMAGNÉTICO GENERAL", fontsize=6.4,
                       fontname="hebo", color=NAVY)
        pg.insert_text((lx, y_gen + 5), f'{general.get("polos", 2)}P · {general.get("corriente","")} A · Curva C',
                       fontsize=7.6, fontname="hebo", color=NAVY)
        y_gen = _tramo(y_gen, 14)

    y_dif = y_gen
    if diferencial:
        y_dif = _tramo(y_gen, 20)
        _simbolo_diferencial(pg, x, y_dif)
        ma = diferencial.get("sensibilidadMa")
        lx = x + 20
        pg.insert_text((lx, y_dif - 6), "INTERRUPTOR DIFERENCIAL", fontsize=6.4,
                       fontname="hebo", color=COLOR_ROL["diferencial"])
        etiqueta = f'{diferencial.get("polos",2)}P · {diferencial.get("corriente","")} A' + \
                   (f' · {ma} mA' if ma else '') + ' · Tipo A'
        pg.insert_text((lx, y_dif + 5), etiqueta, fontsize=7.6, fontname="hebo", color=COLOR_ROL["diferencial"])
        y_dif = _tramo(y_dif, 14)

    y_bus = y_dif + 10

    xs = [X_RAMALES + i * COL for i in range(len(ramales))] or [X_CADENA]
    x_izq = min([X_CADENA - 14] + xs)
    x_der = max(xs) if ramales else X_CADENA + 40
    pg.draw_line((x_izq, y_bus), (x_der, y_bus), color=COLOR_POLARIDAD["fase"], width=2.2)
    pg.draw_line((x_izq, y_bus + 7), (x_der, y_bus + 7), color=COLOR_POLARIDAD["neutro"], width=2.2)
    pg.insert_text((x_izq + 14, y_bus - 8), "BARRA DE FASE (L)", fontsize=6, fontname="hebo",
                   color=COLOR_POLARIDAD["fase"])
    pg.insert_text((x_izq + 14, y_bus + 22), "BARRA DE NEUTRO (N)", fontsize=6, fontname="hebo",
                   color=COLOR_POLARIDAD["neutro"])
    pg.draw_line((x - 9, y_dif), (x - 9, y_bus), color=COLOR_POLARIDAD["fase"], width=1.6)
    pg.draw_line((x + 9, y_dif), (x + 9, y_bus), color=COLOR_POLARIDAD["neutro"], width=1.6)

    # tierra: barra propia a continuación de fase/neutro, punteada, con el
    # símbolo de jabalina en la punta -- en una instalación TT es un
    # sistema aparte, no una barra que "cuelga" de fase/neutro
    if tierra:
        xt0, xt1 = x_der + 20, x_der + 46
        pg.draw_line((xt0, y_bus), (xt1, y_bus), color=COLOR_POLARIDAD["tierra"], width=1.8, dashes="[3 2] 0")
        pg.insert_text((xt0, y_bus - 4), "BARRA DE TIERRA (PE)", fontsize=6, fontname="hebo",
                       color=COLOR_POLARIDAD["tierra"])
        _simbolo_tierra(pg, xt1 + 8, y_bus, ancho=11)

    # ramales: uno por térmica/protector que no sea general, en el mismo
    # orden físico (piso, posición) que tienen en el tablero real
    y_ramal = y_bus + 24
    y_icono = y_ramal + 44
    y_pe_bajo = 0
    for i, d in enumerate(ramales):
        xr = xs[i]
        circuito = _circuito_de(obra, d.get("circuitoId"))
        color = COLOR_ROL["protector"] if d.get("tipo") == "protector" else _color_familia(d)
        pg.draw_line((xr, y_bus), (xr, y_ramal), color=color, width=1.5)
        _simbolo_interruptor(pg, xr, y_ramal, color=color)
        y_txt = y_ramal + 11
        etiqueta_itm = f"ITM {i+1}"
        if d.get("tipo") == "protector":
            etiqueta_itm = f"DPS {i+1}"
        pg.insert_text((xr - 22, y_txt), etiqueta_itm, fontsize=6.6, fontname="hebo", color=NAVY)
        if d.get("tipo") == "protector":
            spec = f'{d.get("tensionV","")} V' if d.get("tensionV") else ""
        else:
            spec = f'{d.get("polos",1)}P · {d.get("corriente","")} A · Curva C'
        pg.insert_text((xr - 22, y_txt + 9), spec, fontsize=6, fontname="helv", color=GRIS)
        pg.draw_line((xr, y_ramal), (xr, y_icono - 12), color=color, width=1.3)
        icono = _icono_para_circuito(circuito) if d.get("tipo") != "protector" else _icono_generico
        icono(pg, xr, y_icono, 26, color)
        y_txt = y_icono + 22
        nombre = f"CIRCUITO {i+1}"
        _texto_centrado(pg, xr, y_txt, nombre, 7.4, NAVY, negrita=True)
        y_txt += 10
        desc = (circuito.get("notas") or "").strip() if circuito else ""
        if not desc and d.get("tipo") == "protector":
            desc = "Protector de sobretensión"
        if desc:
            y_txt += _texto_multilinea(pg, xr, y_txt, desc, 6.6, GRIS, COL - 12, negrita=False, max_lineas=3)
        else:
            _texto_centrado(pg, xr, y_txt, "Sin descripción cargada", 6.6, GRIS, negrita=False)
            y_txt += 9
        if circuito and circuito.get("seccionMm2") and d.get("tipo") != "protector":
            _texto_centrado(pg, xr, y_txt + 6, f'{hilos} x {circuito["seccionMm2"]} mm²', 6.8, TRAZO, negrita=True)
            y_txt += 6
        y_pe_bajo = max(y_pe_bajo, y_txt + 10)

    y_pe_bajo = max(y_pe_bajo, y_bus + 40)

    # conductor de protección (PE) a nivel de circuito: baja de cada uno y
    # se junta con los demás en una línea punteada al pie, con su propio
    # símbolo de tierra -- además de la barra de tierra de arriba, así queda
    # visible que todas las masas comparten el mismo PE, como aclara la nota
    if tierra and ramales:
        y_pe = y_pe_bajo
        for i, xr in enumerate(xs):
            pg.draw_line((xr, y_pe_bajo - 10), (xr, y_pe), color=COLOR_POLARIDAD["tierra"], width=1.2,
                        dashes="[2 1.4] 0")
        pg.draw_line((xs[0], y_pe), (xs[-1], y_pe), color=COLOR_POLARIDAD["tierra"], width=1.4,
                    dashes="[2 1.4] 0")
        _simbolo_tierra(pg, xs[0] - 18, y_pe, ancho=10)
        y_pe_bajo = y_pe + 12

    y_pie = M + y_pe_bajo + 8

    # notas, abajo a la izquierda
    notas = [
        "Todas las masas metálicas de tomas y artefactos se conectan a la barra de tierra (PE).",
        "Sección de conductor y protección de cada circuito: las mismas cargadas en el módulo Circuitos.",
    ]
    notas_w = ancho * 0.56
    pg.draw_rect(pymupdf.Rect(M, y_pie, M + notas_w, y_pie + NOTAS_H), color=(0.8, 0.82, 0.84), fill=BLANCO, width=0.8)
    pg.insert_text((M + 8, y_pie + 12), "NOTAS", fontsize=7, fontname="hebo", color=NAVY)
    for i, n in enumerate(notas):
        pg.insert_text((M + 8, y_pie + 24 + i * 10), f"• {n}", fontsize=6, fontname="helv", color=TRAZO)

    # cuadro de título, abajo, todo el ancho
    y_tit = y_pie + NOTAS_H + 6
    cfg = cfgmod.leer_config()
    cel_w = ancho / 3
    pg.draw_rect(pymupdf.Rect(M, y_tit, ancho - M, y_tit + TITULO_H), color=(0.7, 0.72, 0.74), fill=BLANCO, width=0.9)
    campos = [
        ("OBRA", obra.get("obra", {}).get("nombre") or "-",
         "UBICACIÓN", obra.get("obra", {}).get("direccion") or "-"),
        ("TABLERO", t.get("nombre") or "-", "FECHA", datetime.now().strftime("%d/%m/%Y")),
        ("REALIZÓ", cfg.get("empresa") or "-", "", ""),
    ]
    for i, (k1, v1, k2, v2) in enumerate(campos):
        cx0 = M + i * cel_w
        if i:
            pg.draw_line((cx0, y_tit), (cx0, y_tit + TITULO_H), color=(0.85, 0.86, 0.87), width=0.6)
        pg.insert_text((cx0 + 8, y_tit + 12), k1, fontsize=6, fontname="hebo", color=GRIS)
        pg.insert_text((cx0 + 8, y_tit + 21), str(v1)[:40], fontsize=7.4, fontname="hebo", color=NAVY)
        if k2:
            pg.insert_text((cx0 + cel_w * 0.55, y_tit + 12), k2, fontsize=6, fontname="hebo", color=GRIS)
            pg.insert_text((cx0 + cel_w * 0.55, y_tit + 21), str(v2)[:36], fontsize=7.4, fontname="hebo", color=NAVY)
    try:
        ruta_logo = cfgmod.ruta_imagen("logo")
        if ruta_logo is not None and ruta_logo.suffix.lower() != ".svg":
            pix = pymupdf.Pixmap(str(ruta_logo))
            aspecto = pix.width / max(pix.height, 1)
            alto_logo = TITULO_H - 10
            ancho_logo = alto_logo * aspecto
            x0 = ancho - M - 8 - ancho_logo
            pg.insert_image(pymupdf.Rect(x0, y_tit + 5, x0 + ancho_logo, y_tit + 5 + alto_logo),
                            filename=str(ruta_logo))
    except Exception:
        pass


def generar(t: dict, obra: dict) -> bytes:
    doc = pymupdf.open()
    _pagina_conexionado(doc, t, obra)
    _pagina_tapa(doc, t, obra)
    salida = io.BytesIO()
    doc.save(salida)
    doc.close()
    return salida.getvalue()


def generar_todos(obra: dict) -> bytes:
    """Todos los tableros de la obra (principal y seccionales), uno a
    continuación del otro en un solo PDF -- para no tener que descargar y
    entregar un archivo por tablero cuando hay más de uno."""
    doc = pymupdf.open()
    for t in obra.get("tableros") or []:
        sub = pymupdf.open(stream=generar(t, obra), filetype="pdf")
        doc.insert_pdf(sub)
        sub.close()
    salida = io.BytesIO()
    doc.save(salida)
    doc.close()
    return salida.getvalue()


def generar_unifilar(t: dict, obra: dict) -> bytes:
    """PDF aparte, sólo con el esquema unifilar -- todavía está en beta
    (ver notas en _pagina_unifilar), así que se ofrece con su propio botón
    en vez de venir siempre pegado al PDF principal de conexionado/tapa."""
    doc = pymupdf.open()
    _pagina_unifilar(doc, t, obra)
    salida = io.BytesIO()
    doc.save(salida)
    doc.close()
    return salida.getvalue()


def generar_tapa(t: dict, obra: dict) -> bytes:
    """Sólo la guía de tapa (la vista de cómo va a quedar el tablero) --
    sin la hoja de conexionado. Se usa en el Informe general: ahí sólo
    interesa mostrar cómo va a quedar, no el detalle de cableado interno."""
    doc = pymupdf.open()
    _pagina_tapa(doc, t, obra)
    salida = io.BytesIO()
    doc.save(salida)
    doc.close()
    return salida.getvalue()
