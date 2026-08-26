"""Exporta el tablero a PDF: una vista de conexionado a color (fondo claro
para que los cables se vean) y una vista de "tapa puesta" con etiquetas de
cada térmica, para pegar como referencia adentro del tablero real.

Es una versión simplificada de lo que se ve en pantalla: los cables se
dibujan en línea recta (no en escuadra con saltos de cruce) y los
dispositivos son rectángulos con su color y su etiqueta, no el esquema
detallado con tornillos. Alcanza para un documento útil de obra sin
reimplementar toda la geometría del editor interactivo.
"""
from __future__ import annotations
import io
import pymupdf

ANCHO, ALTO = 841.89, 595.28          # A4 apaisado: los tableros son anchos
MARGEN = 30
NAVY = (0x16/255, 0x28/255, 0x3f/255)
GRIS = (0x5b/255, 0x6b/255, 0x7a/255)
BLANCO = (1, 1, 1)
FONDO_HOJA = (0.99, 0.99, 0.98)
FONDO_RIEL = (0.87, 0.90, 0.90)
COLOR_POLARIDAD = {"fase": (0x8a/255, 0x5a/255, 0x2b/255),
                   "neutro": (0x2b/255, 0x6c/255, 0xa3/255),
                   "tierra": (0x2f/255, 0x7d/255, 0x5c/255)}
COLOR_ROL = {"general": (0x16/255, 0x28/255, 0x3f/255),
            "diferencial": (0x6a/255, 0x3d/255, 0x9a/255),
            "protector": (0xb3/255, 0x43/255, 0x2f/255),
            "tierra": (0x5b/255, 0x6b/255, 0x7a/255)}


def _hex(h: str):
    h = (h or "5b6b7a").lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))


def _color_dispositivo(d: dict):
    if d["tipo"] == "diferencial":
        return COLOR_ROL["diferencial"]
    if d["tipo"] == "protector":
        return COLOR_ROL["protector"]
    if d["tipo"] == "bornera":
        return COLOR_ROL["tierra"]
    if d.get("rol") == "general":
        return NAVY
    return _hex(d.get("color")) if d.get("color") else GRIS


class _Geom:
    """Convierte piso/posición del tablero a coordenadas de la hoja."""
    def __init__(self, t: dict):
        self.t = t
        ancho_disp = ANCHO - 2 * MARGEN
        self.celda = min(38, ancho_disp / max(t["bocasPorPiso"], 1))
        self.alto_disp = 46
        self.banda = 20
        self.franja = 26
        self.margen_piso = 14
        self.altura_piso = self.franja + self.banda + self.alto_disp + self.banda + self.margen_piso

    def x(self, posicion: float) -> float:
        return MARGEN + posicion * self.celda

    def y_piso(self, piso: int) -> float:
        return MARGEN + self.franja + piso * (self.altura_piso - self.franja)

    def y_riel(self, piso: int) -> float:
        return self.y_piso(piso) + self.banda

    def alto_total(self) -> float:
        return (MARGEN + self.franja + self.t["pisos"] * (self.altura_piso - self.franja)
               - self.margen_piso + self.franja + MARGEN)


def _rect_dispositivo(pg, g: _Geom, d: dict, etiqueta_circuito: str | None):
    x0 = g.x(d["posicion"])
    x1 = g.x(d["posicion"] + d["polos"]) - 2
    y0 = g.y_riel(d["piso"]) + 3
    y1 = y0 + g.alto_disp - 6
    color = _color_dispositivo(d)
    pg.draw_rect(pymupdf.Rect(x0, y0, x1, y1), color=color, fill=BLANCO, width=1.6, radius=0.12)
    pg.draw_rect(pymupdf.Rect(x0, y1 - 6, x1, y1), color=None, fill=color)
    nombre = {"general": "GRAL", "tierra": "PAT"}.get(d.get("rol"), "")
    if d["tipo"] == "diferencial":
        nombre = f'{d.get("corriente","")}A {d.get("sensibilidadMa","")}mA'
    elif d["tipo"] == "protector":
        nombre = f'{d.get("tensionV",220)}V'
    elif d["tipo"] == "termica":
        nombre = f'C{d.get("corriente","")}' if not nombre else nombre
    pg.insert_textbox(pymupdf.Rect(x0, y0 + 2, x1, y0 + 16), nombre, fontsize=7.5,
                      fontname="hebo", color=color, align=1)
    if etiqueta_circuito:
        pg.insert_textbox(pymupdf.Rect(x0, y0 + 16, x1, y0 + 28), etiqueta_circuito[:14],
                          fontsize=6.6, color=GRIS, align=1)


def _punto_endpoint(g: _Geom, t: dict, ep: dict):
    if not ep:
        return None
    if ep["tipo"] == "dispositivo":
        d = next((x for x in t["dispositivos"] if x["id"] == ep["id"]), None)
        if d is None or d.get("piso") is None:
            return None
        cx = g.x(d["posicion"] + (ep.get("polo", 0) or 0) + 0.5)
        cy = g.y_riel(d["piso"]) + (3 if ep.get("lado") == "arriba" else g.alto_disp - 3)
        return (cx, cy)
    if ep["tipo"] == "peine":
        pe = next((c for c in t.get("conexiones") or [] if c["id"] == ep["id"]), None)
        if pe is None:
            return None
        return (g.x((pe["desde"] + pe["hasta"] + 1) / 2), g.y_riel(pe["piso"]))
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
        x = MARGEN + (orden + 0.5) * (ANCHO - 2 * MARGEN) / n
        y = MARGEN + 8 if cano["lado"] == "arriba" else g.alto_total() - MARGEN - 8
        return (x, y)
    return None


def _nombre_circuito(obra: dict, circuito_id: str | None) -> str | None:
    if not circuito_id:
        return None
    c = next((x for x in obra.get("circuitos") or [] if x["id"] == circuito_id), None)
    return c.get("nombre") if c else None


def _pagina_conexionado(doc, t: dict, obra: dict):
    g = _Geom(t)
    alto = min(max(g.alto_total(), 300), ALTO)
    pg = doc.new_page(width=ANCHO, height=alto)
    pg.draw_rect(pg.rect, color=None, fill=FONDO_HOJA)
    pg.insert_text((MARGEN, 18), f"Tablero — {t.get('nombre','')}", fontsize=13,
                   fontname="hebo", color=NAVY)

    for piso in range(t["pisos"]):
        y0 = g.y_riel(piso)
        pg.draw_rect(pymupdf.Rect(MARGEN, y0, ANCHO - MARGEN, y0 + g.alto_disp),
                    color=(0.7, 0.75, 0.75), fill=FONDO_RIEL, width=0.8, radius=0.06)
        pg.insert_text((MARGEN + 2, y0 - 4), f"Piso {piso+1}", fontsize=6.6, color=GRIS)

    # cables: línea recta entre los dos extremos, coloreada por polaridad
    for cable in t.get("cables") or []:
        a = _punto_endpoint(g, t, cable.get("origen"))
        b = _punto_endpoint(g, t, cable.get("destino"))
        if not a or not b:
            continue
        color = COLOR_POLARIDAD.get(cable.get("polaridad"), GRIS)
        pg.draw_line(a, b, color=color, width=1.3)

    # peines: una barra de color por encima de las térmicas que junta
    for con in t.get("conexiones") or []:
        if con["tipo"] != "peine":
            continue
        y = g.y_riel(con["piso"]) - 6
        pg.draw_line((g.x(con["desde"]), y), (g.x(con["hasta"] + 1), y),
                    color=COLOR_POLARIDAD["fase"], width=2.4)

    # puentes: un tramo vertical entre pisos
    for con in t.get("conexiones") or []:
        if con["tipo"] != "puente":
            continue
        x = g.x(con["x"] + 0.5)
        y0 = g.y_riel(con["pisoOrigen"]) + g.alto_disp
        y1 = g.y_piso(con["pisoDestino"])
        pg.draw_line((x, y0), (x, y1), color=COLOR_POLARIDAD.get(con.get("polaridad"), GRIS), width=2)

    # dispositivos por encima del cableado
    for d in t.get("dispositivos") or []:
        if d.get("piso") is None:
            continue
        _rect_dispositivo(pg, g, d, _nombre_circuito(obra, d.get("circuitoId")))

    # bocas de caño arriba/abajo
    for lado in ("arriba", "abajo"):
        canos = sorted([c for c in t.get("canos") or [] if c["lado"] == lado],
                       key=lambda c: c["orden"])
        n = max(len(canos), 1)
        y = MARGEN + 8 if lado == "arriba" else alto - MARGEN - 8
        for i, cano in enumerate(canos):
            x = MARGEN + (i + 0.5) * (ANCHO - 2 * MARGEN) / n
            etiqueta = ("Acometida" if cano["tipo"] == "acometida" else
                       "Jabalina" if cano["tipo"] == "tierra" else
                       (_nombre_circuito(obra, cano.get("circuitoId")) or "Circuito"))
            color = (COLOR_POLARIDAD["tierra"] if cano["tipo"] == "tierra"
                    else COLOR_POLARIDAD["fase"] if cano["tipo"] == "acometida" else NAVY)
            pg.draw_circle((x, y), 5, color=color, fill=BLANCO, width=1.3)
            pg.insert_textbox(pymupdf.Rect(x - 30, y + (8 if lado == "arriba" else -20),
                                          x + 30, y + (20 if lado == "arriba" else -8)),
                              etiqueta[:16], fontsize=6.2, color=GRIS, align=1)


def _pagina_tapa(doc, t: dict, obra: dict):
    """Vista con la tapa puesta: sólo las térmicas y su etiqueta, sin
    cableado — para pegar adentro del tablero como guía."""
    g = _Geom(t)
    alto = min(max(g.alto_total(), 300), ALTO)
    pg = doc.new_page(width=ANCHO, height=alto)
    pg.draw_rect(pg.rect, color=None, fill=BLANCO)
    pg.insert_text((MARGEN, 18), f"Tablero — {t.get('nombre','')} · guía de tapa",
                   fontsize=13, fontname="hebo", color=NAVY)

    for piso in range(t["pisos"]):
        y0 = g.y_riel(piso)
        pg.draw_rect(pymupdf.Rect(MARGEN, y0, ANCHO - MARGEN, y0 + g.alto_disp),
                    color=(0.85, 0.85, 0.85), fill=(0.96, 0.96, 0.96), width=0.8, radius=0.06)

    for d in t.get("dispositivos") or []:
        if d.get("piso") is None:
            continue
        _rect_dispositivo(pg, g, d, _nombre_circuito(obra, d.get("circuitoId")))


def generar(t: dict, obra: dict) -> bytes:
    doc = pymupdf.open()
    _pagina_conexionado(doc, t, obra)
    _pagina_tapa(doc, t, obra)
    salida = io.BytesIO()
    doc.save(salida)
    doc.close()
    return salida.getvalue()
