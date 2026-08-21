"""Deteccion y clasificacion de simbolos de la capa electrica.

Nota importante sobre como exporta AutoCAD: un circulo relleno se dibuja como
una pila de barras horizontales muy finas ('fs' de 0.1-0.6pt de alto), no como
un circulo relleno.  El contorno si aparece como un path de 4 curvas de Bezier.
Por eso la deteccion se apoya en los paths de curvas y trata las barras como
relleno a ignorar.
"""
from __future__ import annotations
import collections, itertools, math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import numpy as np
from . import config as C
from .geometria import Camino, Segmento, es_electrico


@dataclass
class Simbolo:
    id: str
    clase: str                     # boca_luz | aplique | tomacorriente | llave | desconocido
    x: float; y: float             # centro en pt PDF
    bbox: Tuple[float, float, float, float]
    orientacion: Optional[float] = None
    largo_m: Optional[float] = None
    caja: Optional[str] = None
    n_brazos: int = 1
    confianza: float = 1.0
    notas: List[str] = field(default_factory=list)


# ------------------------------------------------------- utilidades de forma
def _es_barra_relleno(cam: Camino) -> bool:
    """Barra de scanline del relleno solido de AutoCAD."""
    return cam.tipo in ("f", "fs") and min(cam.w, cam.h) < 0.75 and cam.n_curvas == 0


def _diametro_circulo(cam: Camino) -> Optional[float]:
    if cam.n_curvas < 3:
        return None
    if max(cam.w, cam.h) == 0 or abs(cam.w - cam.h) > 0.3 * max(cam.w, cam.h):
        return None
    return (cam.w + cam.h) / 2


def _barra_maciza(sub, ppm):
    """Barra roja maciza = luminaria lineal (tira LED, tubo, bajo alacena)."""
    if any(c.n_curvas for c in sub):
        return None
    x0 = min(c.rect[0] for c in sub); y0 = min(c.rect[1] for c in sub)
    x1 = max(c.rect[2] for c in sub); y1 = max(c.rect[3] for c in sub)
    w, h = x1 - x0, y1 - y0
    L, e = max(w, h), min(w, h)
    if L < 0.40 * ppm or e > 0.12 * ppm or L / max(e, 1e-6) < 4:
        return None
    return (x0, y0, x1, y1, L / ppm, 0.0 if w >= h else 90.0)


def escala_simbolos(caminos: List[Camino]) -> float:
    """Diametro tipico de la boca de luz, en pt.  Da la escala de los bloques."""
    ds = [d for c in caminos if es_electrico(c) and (d := _diametro_circulo(c))]
    if not ds:
        return 5.6
    hist = collections.Counter(round(d * 2) / 2 for d in ds)
    return max(hist.items(), key=lambda kv: (kv[1], kv[0]))[0]


# ------------------------------------------------------------ clusterizacion
def _clusterizar(caminos: List[Camino], gap: float) -> List[List[int]]:
    n = len(caminos)
    padre = list(range(n))
    def find(x):
        while padre[x] != x:
            padre[x] = padre[padre[x]]; x = padre[x]
        return x
    celdas = collections.defaultdict(list)
    for i, c in enumerate(caminos):
        x0, y0, x1, y1 = c.rect
        for gx in range(int((x0 - gap) // 12), int((x1 + gap) // 12) + 1):
            for gy in range(int((y0 - gap) // 12), int((y1 + gap) // 12) + 1):
                celdas[(gx, gy)].append(i)
    for idxs in celdas.values():
        for i, j in itertools.combinations(sorted(set(idxs)), 2):
            a, b = caminos[i].rect, caminos[j].rect
            if not (a[0]-gap > b[2] or b[0]-gap > a[2] or a[1]-gap > b[3] or b[1]-gap > a[3]):
                ra, rb = find(i), find(j)
                if ra != rb:
                    padre[ra] = rb
    grupos = collections.defaultdict(list)
    for i in range(n):
        grupos[find(i)].append(i)
    return list(grupos.values())


# ------------------------------------------------------------------ deteccion
def detectar(caminos: List[Camino], ppm: float, d_boca: Optional[float] = None) -> List[Simbolo]:
    elec = [c for c in caminos if es_electrico(c)]
    D = d_boca or escala_simbolos(caminos)
    lo_b, hi_b = D * 0.80, D * 1.25          # circulo grande  -> boca de luz
    lo_l, hi_l = D * 0.30, D * 0.62          # circulo chico   -> eje de llave
    semi_lo, semi_hi = D * 1.00, D * 1.55    # semicirculo     -> tomacorriente

    simbolos: List[Simbolo] = []
    k = 0
    for g in _clusterizar(elec, C.GAP_CLUSTER):
        sub = [elec[i] for i in g]
        k += 1
        sid = f"S{k:03d}"
        # trazos reales (excluye las barras de relleno)
        trazos = [s for c in sub if not _es_barra_relleno(c) and c.n_curvas == 0
                  for s in c.segmentos if s.largo > D * 0.35]
        bocas, ejes, semis = [], [], []
        for c in sub:
            d = _diametro_circulo(c)
            if d and lo_b <= d <= hi_b:
                bocas.append(c); continue
            if d and lo_l <= d <= hi_l:
                ejes.append(c); continue
            if c.n_curvas in (1, 2, 3):
                largo, alto = max(c.w, c.h), min(c.w, c.h)
                if semi_lo <= largo <= semi_hi and 0.38 <= alto / max(largo, 1e-6) <= 0.75:
                    semis.append(c)
        emitidos = 0
        for j, sc in enumerate(semis):
            cx, cy = sc.centro
            simbolos.append(Simbolo(f"{sid}-{j+1}" if len(semis) > 1 else sid,
                                    "tomacorriente", cx, cy, sc.rect,
                                    orientacion=_orient_semi(sc), confianza=0.95))
            emitidos += 1
        for j, bc in enumerate(bocas):
            cx, cy = bc.centro
            r = max(bc.w, bc.h) / 2
            vast = [s for s in trazos
                    if min(math.hypot(s.x0-cx, s.y0-cy), math.hypot(s.x1-cx, s.y1-cy)) < r * 1.6]
            clase, ori = ("boca_luz", None)
            if vast:
                s = max(vast, key=lambda s: s.largo)
                a, b = s.p0, s.p1
                if np.linalg.norm(a - np.array([cx, cy])) > np.linalg.norm(b - np.array([cx, cy])):
                    a, b = b, a
                d_ = b - a
                clase = "aplique"
                ori = round(math.degrees(math.atan2(-d_[1], d_[0])) % 360, 1)
            simbolos.append(Simbolo(f"{sid}-L{j+1}" if len(bocas) > 1 else sid,
                                    clase, cx, cy, bc.rect, orientacion=ori, confianza=0.95))
            emitidos += 1
        # cada eje = un modulo de llave (una tecla). Una caja puede tener varios.
        for j, ec in enumerate(ejes):
            cx, cy = ec.centro
            simbolos.append(Simbolo(f"{sid}-T{j+1}" if len(ejes) > 1 else sid,
                                    "llave", cx, cy, ec.rect,
                                    n_brazos=len(ejes), caja=sid, confianza=0.9))
            emitidos += 1
        if not emitidos:
            barra = _barra_maciza(sub, ppm)
            if barra:
                bx0, by0, bx1, by1, largo, ang = barra
                simbolos.append(Simbolo(sid, "luminaria_lineal",
                                        (bx0 + bx1) / 2, (by0 + by1) / 2,
                                        (bx0, by0, bx1, by1), orientacion=ang,
                                        largo_m=round(largo, 3), confianza=0.85,
                                        notas=[]))
                continue
            x0 = min(c.rect[0] for c in sub); y0 = min(c.rect[1] for c in sub)
            x1 = max(c.rect[2] for c in sub); y1 = max(c.rect[3] for c in sub)
            if max(x1 - x0, y1 - y0) > D * 0.5:
                simbolos.append(Simbolo(sid, "desconocido", (x0+x1)/2, (y0+y1)/2,
                                        (x0, y0, x1, y1), confianza=0.3,
                                        notas=["simbolo no reconocido: revisar manualmente"]))
    return simbolos


def _orient_semi(cam: Camino) -> float:
    """Angulo hacia donde 'mira' el toma (opuesto al muro). 0=+X, 90=arriba."""
    cx, cy = cam.centro
    pts = [((s.x0 + s.x1) / 2, (s.y0 + s.y1) / 2) for s in cam.segmentos]
    if not pts:
        return 0.0
    px = float(np.mean([p[0] for p in pts])); py = float(np.mean([p[1] for p in pts]))
    if cam.w >= cam.h:
        return 90.0 if py < cy else 270.0
    return 0.0 if px > cx else 180.0
