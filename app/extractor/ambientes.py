"""Deteccion de ambientes (habitaculos) a partir de la capa de arquitectura."""
from __future__ import annotations
import itertools
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import numpy as np
import cv2
from . import config as C
from .geometria import Camino, Segmento, es_arquitectura


@dataclass
class Ambiente:
    id: str
    nombre: str
    origen_nombre: str            # heuristica | usuario | sin_clasificar
    confianza_nombre: float
    area_m2: float
    poligono_pt: List[Tuple[float, float]]
    centro_pt: Tuple[float, float]
    es_exterior: bool = False
    notas: List[str] = field(default_factory=list)


def _muros(caminos: List[Camino], ppm: float) -> List[Segmento]:
    """Se queda con el espesor de linea dominante de la capa de arquitectura.

    En los planos de AutoCAD el muro se dibuja con una pluma mas gruesa que el
    mobiliario y los artefactos.  Detectar ese espesor automaticamente evita
    que las mesadas, placares y sanitarios corten los ambientes en pedazos.
    """
    import collections as _c
    largo_por_ancho = _c.Counter()
    for c in caminos:
        if not es_arquitectura(c) or c.punteado:
            continue
        largo_por_ancho[round(c.ancho, 2)] += sum(s.largo for s in c.segmentos)
    if not largo_por_ancho:
        return []
    anchos = sorted(largo_por_ancho)
    total = sum(largo_por_ancho.values())
    # pluma de muro = el espesor mas grueso con presencia significativa (>8%)
    ancho_muro = max([a for a in anchos if largo_por_ancho[a] > 0.08 * total] or [anchos[-1]])
    out = []
    for c in caminos:
        if not es_arquitectura(c) or c.punteado:
            continue
        if round(c.ancho, 2) < ancho_muro - 1e-6:
            continue
        out.extend(c.segmentos)
    return out


def _puentes(segs: List[Segmento], ppm: float):
    """Cierra vanos: dos muros colineales separados por un hueco < GAP_MAX."""
    largos = [s for s in segs if s.largo > C.LARGO_MIN_MURO_M * ppm]
    maxgap = C.GAP_MAX_VANO_M * ppm
    perp = C.TOL_COLINEAL_M * ppm
    puentes = []
    # indexado por orientacion para no comparar todo contra todo
    for a, b in itertools.combinations(largos, 2):
        da = (a.p1 - a.p0); da = da / np.linalg.norm(da)
        db = (b.p1 - b.p0); db = db / np.linalg.norm(db)
        if abs(abs(float(np.dot(da, db))) - 1) > 0.01:
            continue
        n = np.array([-da[1], da[0]])
        if abs(float(np.dot(b.p0 - a.p0, n))) > perp: continue
        if abs(float(np.dot(b.p1 - a.p0, n))) > perp: continue
        ta = sorted([0.0, float(np.dot(a.p1 - a.p0, da))])
        tb = sorted([float(np.dot(b.p0 - a.p0, da)), float(np.dot(b.p1 - a.p0, da))])
        if tb[0] > ta[1]:
            gap, A, B = tb[0] - ta[1], a.p0 + da * ta[1], a.p0 + da * tb[0]
        elif ta[0] > tb[1]:
            gap, A, B = ta[0] - tb[1], a.p0 + da * tb[1], a.p0 + da * ta[0]
        else:
            continue
        if 0.5 < gap <= maxgap:
            puentes.append((A, B))
    return puentes


def _puentes_extremo(segs: List[Segmento], ppm: float):
    """Cierra pasos en 'T': punta libre de un tabique contra el muro de enfrente."""
    largos = [s for s in segs if s.largo > C.LARGO_MIN_MURO_M * ppm]
    maxgap = C.GAP_MAX_VANO_M * ppm
    puentes = []
    puntas = []
    for s in largos:
        for p in (s.p0, s.p1):
            libre = True
            for o in largos:
                if o is s:
                    continue
                if min(np.linalg.norm(p - o.p0), np.linalg.norm(p - o.p1)) < 0.06 * ppm:
                    libre = False; break
            if libre:
                puntas.append((p, s))
    for p, s in puntas:
        ds = (s.p1 - s.p0) / s.largo
        mejor, dmin = None, maxgap
        for o in largos:
            if o is s:
                continue
            do = (o.p1 - o.p0) / max(o.largo, 1e-9)
            if abs(float(np.dot(ds, do))) > 0.2:      # solo muros transversales
                continue
            t = float(np.dot(p - o.p0, do))
            if not (0 <= t <= o.largo):
                continue
            q = o.p0 + do * t
            d = float(np.linalg.norm(q - p))
            if 0.05 * ppm < d < dmin:
                mejor, dmin = q, d
        if mejor is not None:
            puentes.append((p, mejor))
    return puentes


def detectar(caminos: List[Camino], ppm: float, rect_pagina, envolvente=None, muros_virtuales=None) -> Tuple[List[Ambiente], np.ndarray, float]:
    segs = _muros(caminos, ppm)
    if not segs:
        return [], np.zeros((1, 1), np.uint8), C.PX_POR_PT
    S = C.PX_POR_PT
    W = int(rect_pagina[2] * S) + 2
    H = int(rect_pagina[3] * S) + 2
    mask = np.zeros((H, W), np.uint8)
    P = lambda x, y: (int(round(x * S)), int(round(y * S)))
    for s in segs:
        cv2.line(mask, P(s.x0, s.y0), P(s.x1, s.y1), 255, max(1, int(round(s.ancho * S))))
    for A, B in _puentes(segs, ppm) + _puentes_extremo(segs, ppm):
        cv2.line(mask, P(*A), P(*B), 255, 2)
    for A, B in (muros_virtuales or []):          # tabiques agregados a mano
        cv2.line(mask, P(*A), P(*B), 255, 3)
    cerrado = cv2.dilate(mask, np.ones((3, 3), np.uint8))
    n, lab, stats, cent = cv2.connectedComponentsWithStats(255 - cerrado, 4)
    px_m2 = (S * ppm) ** 2

    # exterior = componente que toca el borde de la hoja, o que cae fuera del
    # envolvente de muros (zona de cotas, rotulo, patio, etc.)
    borde = set(lab[0, :]) | set(lab[-1, :]) | set(lab[:, 0]) | set(lab[:, -1])
    if envolvente is not None:
        ex0, ey0, ex1, ey1 = envolvente
        m = 0.15 * ppm
        for i in range(1, n):
            x, y = cent[i][0] / S, cent[i][1] / S
            if not (ex0 - m <= x <= ex1 + m and ey0 - m <= y <= ey1 + m):
                borde.add(i)
        # tambien: componentes cuyo bbox excede el envolvente en mas del 25%
        for i in range(1, n):
            bx, by, bw, bh = stats[i, 0]/S, stats[i, 1]/S, stats[i, 2]/S, stats[i, 3]/S
            fuera = (max(0, ex0 - bx) + max(0, bx + bw - ex1)) * bh + \
                    (max(0, ey0 - by) + max(0, by + bh - ey1)) * bw
            if fuera > 0.25 * (bw * bh):
                borde.add(i)

    ambientes: List[Ambiente] = []
    k = 0
    for i in range(1, n):
        area = stats[i, 4] / px_m2
        if area < C.AREA_MIN_AMBIENTE_M2:
            continue
        comp = (lab == i).astype(np.uint8) * 255
        cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            continue
        c = max(cnts, key=cv2.contourArea)
        eps = 0.006 * cv2.arcLength(c, True)
        poly = cv2.approxPolyDP(c, eps, True).reshape(-1, 2) / S
        k += 1
        ambientes.append(Ambiente(
            id=f"amb_{k:02d}", nombre="desconocido", origen_nombre="sin_clasificar",
            confianza_nombre=0.0, area_m2=round(area, 2),
            poligono_pt=[(round(float(x), 2), round(float(y), 2)) for x, y in poly],
            centro_pt=(float(cent[i][0]) / S, float(cent[i][1]) / S),
            es_exterior=i in borde))
    return ambientes, lab, S


def ambiente_de(punto_pt, ambientes, lab, S, ppm, tol_m=C.DIST_MAX_AMBIENTE_M):
    """Ambiente que contiene el punto; si cae sobre un muro, busca alrededor."""
    x, y = punto_pt
    idx = {a.id: a for a in ambientes}
    H, W = lab.shape
    def et(px, py):
        if 0 <= py < H and 0 <= px < W:
            return int(lab[py, px])
        return 0
    orden = {}
    k = 0
    for i in range(1, lab.max() + 1):
        pass
    # mapa etiqueta->ambiente
    mapa = {}
    for a in ambientes:
        px, py = int(a.centro_pt[0] * S), int(a.centro_pt[1] * S)
        l = et(px, py)
        if l:
            mapa.setdefault(l, a.id)
    # si el centroide cae fuera del componente, reconstruimos por mascara
    if len(mapa) < len(ambientes):
        for a in ambientes:
            if a.id in mapa.values():
                continue
            poly = np.array([[int(px * S), int(py * S)] for px, py in a.poligono_pt])
            m = np.zeros(lab.shape, np.uint8)
            cv2.fillPoly(m, [poly], 1)
            vals, cnts = np.unique(lab[m == 1], return_counts=True)
            vals = [v for v, c in sorted(zip(vals, cnts), key=lambda t: -t[1]) if v != 0]
            if vals:
                mapa.setdefault(int(vals[0]), a.id)
    r = int(tol_m * ppm * S)
    px, py = int(round(x * S)), int(round(y * S))
    l = et(px, py)
    if l in mapa:
        return mapa[l], 1.0
    mejor, dmin = None, 1e9
    for dx in range(-r, r + 1, 2):
        for dy in range(-r, r + 1, 2):
            d = dx * dx + dy * dy
            if d > r * r or d >= dmin:
                continue
            l = et(px + dx, py + dy)
            if l in mapa:
                mejor, dmin = mapa[l], d
    if mejor:
        return mejor, round(max(0.4, 1 - (dmin ** .5) / (r + 1e-9)), 2)
    return None, 0.0


def nombrar(ambientes: List[Ambiente], elementos):
    """Heuristica de nombre segun los artefactos que contiene el ambiente."""
    por_amb = {}
    for e in elementos:
        if e.get("ambiente_id"):
            por_amb.setdefault(e["ambiente_id"], []).append(e)
    for a in ambientes:
        if a.es_exterior:
            a.nombre, a.origen_nombre, a.confianza_nombre = "exterior", "heuristica", 0.8
            continue
        subs = [e.get("subtipo") for e in por_amb.get(a.id, [])]
        mejor, punt = None, 0
        for nombre, pesos in C.REGLAS_AMBIENTE:
            p = sum(pesos.get(s, 0) for s in subs)
            if p > punt:
                mejor, punt = nombre, p
        if mejor and punt >= 3:
            a.nombre = mejor
            a.origen_nombre = "heuristica"
            a.confianza_nombre = round(min(0.9, 0.4 + 0.1 * punt), 2)
        else:
            a.nombre = "desconocido"
            a.origen_nombre = "sin_clasificar"
            a.confianza_nombre = 0.0
            a.notas.append("completar nombre manualmente")
    return ambientes
