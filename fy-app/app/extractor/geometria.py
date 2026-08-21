"""Extraccion de primitivas vectoriales del PDF (sin OCR, sin ML)."""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import numpy as np
import pymupdf
from . import config as C


@dataclass
class Segmento:
    x0: float; y0: float; x1: float; y1: float
    ancho: float
    color: Tuple[float, float, float]
    punteado: bool = False

    @property
    def largo(self) -> float:
        return math.hypot(self.x1 - self.x0, self.y1 - self.y0)

    @property
    def p0(self): return np.array([self.x0, self.y0])
    @property
    def p1(self): return np.array([self.x1, self.y1])


@dataclass
class Camino:
    """Un path del PDF, ya con su bbox y sus primitivas normalizadas."""
    tipo: str                      # 's' | 'f' | 'fs'
    color: Optional[tuple]
    relleno: Optional[tuple]
    ancho: float
    rect: Tuple[float, float, float, float]
    n_curvas: int
    n_lineas: int
    cerrado: bool
    segmentos: List[Segmento] = field(default_factory=list)
    punteado: bool = False

    @property
    def w(self): return self.rect[2] - self.rect[0]
    @property
    def h(self): return self.rect[3] - self.rect[1]
    @property
    def centro(self):
        return ((self.rect[0] + self.rect[2]) / 2, (self.rect[1] + self.rect[3]) / 2)


@dataclass
class Texto:
    texto: str
    x0: float; y0: float; x1: float; y1: float
    tam: float
    vertical: bool

    @property
    def centro(self): return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)


def _bezier(p0, p1, p2, p3, n=14):
    ts = np.linspace(0, 1, n)
    pts = []
    for t in ts:
        x = (1-t)**3*p0.x + 3*(1-t)**2*t*p1.x + 3*(1-t)*t*t*p2.x + t**3*p3.x
        y = (1-t)**3*p0.y + 3*(1-t)**2*t*p1.y + 3*(1-t)*t*t*p2.y + t**3*p3.y
        pts.append((x, y))
    return pts


def _es_punteado(d) -> bool:
    dash = d.get("dashes")
    return dash not in (None, "", "[] 0")


def leer_pdf(ruta: str, pagina: int = 0):
    """Devuelve (caminos, textos, rect_pagina, metadatos)."""
    doc = pymupdf.open(ruta)
    pg = doc[pagina]
    caminos: List[Camino] = []

    for d in pg.get_drawings():
        col, fil = d.get("color"), d.get("fill")
        ancho = max(d.get("width") or 0.1, 0.1)
        punteado = _es_punteado(d)
        segs, ncur, nlin = [], 0, 0
        for it in d["items"]:
            k = it[0]
            if k == "l":
                nlin += 1
                segs.append(Segmento(it[1].x, it[1].y, it[2].x, it[2].y, ancho, col or fil or (0, 0, 0), punteado))
            elif k == "re":
                r = it[1]
                esq = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1), (r.x0, r.y0)]
                for a, b in zip(esq, esq[1:]):
                    segs.append(Segmento(*a, *b, ancho, col or fil or (0, 0, 0), punteado))
                nlin += 4
            elif k == "qu":
                q = it[1]
                esq = [q.ul, q.ur, q.lr, q.ll, q.ul]
                for a, b in zip(esq, esq[1:]):
                    segs.append(Segmento(a.x, a.y, b.x, b.y, ancho, col or fil or (0, 0, 0), punteado))
                nlin += 4
            elif k == "c":
                ncur += 1
                pts = _bezier(*it[1:5])
                for a, b in zip(pts, pts[1:]):
                    segs.append(Segmento(*a, *b, ancho, col or fil or (0, 0, 0), punteado))
        r = d["rect"]
        cerrado = bool(d.get("closePath"))
        caminos.append(Camino(d["type"], col, fil, ancho,
                              (r.x0, r.y0, r.x1, r.y1), ncur, nlin, cerrado, segs, punteado))

    textos: List[Texto] = []
    for b in pg.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            vert = abs(l["dir"][1]) > 0.5
            for s in l["spans"]:
                t = s["text"].strip()
                if not t:
                    continue
                bb = s["bbox"]
                textos.append(Texto(t, bb[0], bb[1], bb[2], bb[3], round(s["size"], 2), vert))

    meta = {"titulo": doc.metadata.get("title"), "creador": doc.metadata.get("creator"),
            "creado": doc.metadata.get("creationDate")}
    rect = (pg.rect.x0, pg.rect.y0, pg.rect.x1, pg.rect.y1)
    doc.close()
    return caminos, textos, rect, meta


# ---------------------------------------------------------------- filtros
def _cerca(c, ref, tol=C.TOL_COLOR):
    return c is not None and all(abs(a - b) <= tol for a, b in zip(c, ref))


def es_electrico(cam: Camino) -> bool:
    return _cerca(cam.color, C.COLOR_ELECTRICO) or _cerca(cam.relleno, C.COLOR_ELECTRICO)


def es_arquitectura(cam: Camino) -> bool:
    def oscuro(c):
        return c is not None and max(c) < C.UMBRAL_NEGRO
    return oscuro(cam.color) or oscuro(cam.relleno)
