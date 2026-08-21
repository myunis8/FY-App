"""Deteccion automatica de escala y del punto de referencia del plano."""
from __future__ import annotations
import re, collections, statistics
from dataclasses import dataclass, asdict
from typing import List, Optional
import numpy as np
from . import config as C
from .geometria import Texto, Camino, es_arquitectura

RE_COTA = re.compile(r"^\d{1,2}[,.]\d{2}$")


@dataclass
class Calibracion:
    pt_por_metro: float
    escala_nominal: str
    metodo: str
    confianza: float
    n_muestras: int


def _cotas(textos: List[Texto]):
    out = []
    for t in textos:
        if RE_COTA.match(t.texto):
            v = float(t.texto.replace(",", "."))
            if 0.05 <= v <= 30:
                out.append((v, *t.centro, t.vertical))
    return out


def calibrar(textos: List[Texto], pt_por_metro_forzado: Optional[float] = None) -> Calibracion:
    """Escala a partir de cadenas de cotas.

    Dos cotas consecutivas de la misma cadena estan centradas sobre tramos
    contiguos, por lo que la distancia entre sus centros es (v1+v2)/2 * escala.
    Con muchos pares, la mediana es muy robusta.  No necesita leer la geometria
    de las lineas de cota.
    """
    if pt_por_metro_forzado:
        return Calibracion(pt_por_metro_forzado, _nominal(pt_por_metro_forzado), "manual", 1.0, 0)

    cotas = _cotas(textos)
    ratios = []
    for vertical in (False, True):
        grupo = [c for c in cotas if c[3] is vertical]
        eje = 2 if vertical else 1          # cadena vertical -> varia y
        otro = 1 if vertical else 2
        cadenas = collections.defaultdict(list)
        for c in grupo:
            cadenas[round(c[otro] / 3.0)].append(c)   # tolerancia de 3pt
        for items in cadenas.values():
            items.sort(key=lambda t: t[eje])
            for a, b in zip(items, items[1:]):
                d = abs(b[eje] - a[eje])
                esperado = (a[0] + b[0]) / 2
                if esperado <= 0:
                    continue
                ratios.append(d / esperado)
    if len(ratios) >= 4:
        arr = np.array(ratios)
        med = np.median(arr)
        buenos = arr[np.abs(arr - med) / med < 0.05]      # descarta pares de cadenas distintas
        if len(buenos) >= 4:
            v = float(np.median(buenos))
            disp = float(np.std(buenos) / v)
            conf = max(0.0, min(1.0, 1 - disp * 10))
            return Calibracion(round(v, 4), _nominal(v), "cadena_de_cotas", round(conf, 3), len(buenos))

    return Calibracion(C.PT_POR_METRO_FALLBACK, _nominal(C.PT_POR_METRO_FALLBACK),
                       "fallback_1:50", 0.0, 0)


def _nominal(ppm: float) -> str:
    for nombre, v in C.ESCALAS_CONOCIDAS.items():
        if abs(ppm - v) / v < C.TOL_ESCALA_CONOCIDA:
            return nombre
    return f"1:{round(1000/(ppm/72*25.4)):d}"


@dataclass
class Referencia:
    """Punto de origen del sistema de coordenadas exportado."""
    descripcion: str
    x_pdf_pt: float
    y_pdf_pt: float
    envolvente_pdf_pt: tuple
    envolvente_m: tuple

    def a_metros(self, x, y, ppm):
        return ((x - self.x_pdf_pt) / ppm, (self.y_pdf_pt - y) / ppm)


def punto_referencia(caminos: List[Camino], ppm: float) -> Referencia:
    """Esquina inferior-izquierda del envolvente de muros de la vivienda.

    Se acota la busqueda a la zona util del plano (bounding box de la capa
    electrica ampliada), para no incluir el rotulo ni el marco de la lamina.
    Es un punto univoco, reproducible y facil de verificar a ojo.
    """
    from .geometria import es_electrico
    rojos = [c.rect for c in caminos if es_electrico(c)]
    if not rojos:
        raise ValueError("No se detecto capa electrica (roja) en el plano")
    zx0 = min(r[0] for r in rojos) - 1.5 * ppm
    zy0 = min(r[1] for r in rojos) - 1.5 * ppm
    zx1 = max(r[2] for r in rojos) + 1.5 * ppm
    zy1 = max(r[3] for r in rojos) + 1.5 * ppm

    segs = [s for c in caminos if es_arquitectura(c) and not c.punteado
            for s in c.segmentos if s.largo > C.LARGO_MIN_MURO_M * ppm]
    dentro = [s for s in segs
              if zx0 <= min(s.x0, s.x1) and max(s.x0, s.x1) <= zx1
              and zy0 <= min(s.y0, s.y1) and max(s.y0, s.y1) <= zy1]
    if not dentro:
        raise ValueError("No se detectaron muros en la zona del plano")
    ex0 = min(min(s.x0, s.x1) for s in dentro)
    ex1 = max(max(s.x0, s.x1) for s in dentro)
    ey0 = min(min(s.y0, s.y1) for s in dentro)
    ey1 = max(max(s.y0, s.y1) for s in dentro)
    return Referencia(
        "Esquina inferior-izquierda (X minima, Y maxima del PDF) del envolvente "
        "exterior de muros de la planta. Eje X hacia la derecha, eje Y hacia "
        "arriba, unidad metro.",
        round(ex0, 3), round(ey1, 3),
        (round(ex0, 2), round(ey0, 2), round(ex1, 2), round(ey1, 2)),
        (0.0, 0.0, round((ex1 - ex0) / ppm, 3), round((ey1 - ey0) / ppm, 3)))
