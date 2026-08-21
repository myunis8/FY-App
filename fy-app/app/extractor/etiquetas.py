"""Agrupacion de spans de texto en etiquetas y su interpretacion semantica."""
from __future__ import annotations
import re, unicodedata
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from . import config as C
from .geometria import Texto

RE_ALTURA = re.compile(r"h\s*[:=]?\s*(\d{1,2}[.,]\d{1,2})\s*m?", re.I)
RE_MULT = re.compile(r"\(?\s*x\s*(\d)\s*\)?", re.I)
RE_COTA = re.compile(r"^\d{1,2}[,.]\d{2}$")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


@dataclass
class Etiqueta:
    texto: str
    x: float; y: float                 # centro en pt PDF
    bbox: Tuple[float, float, float, float]
    subtipo: Optional[str] = None
    altura_m: Optional[float] = None
    multiplicidad: int = 1
    vertical: bool = False


@dataclass
class LetraCircuito:
    letra: str
    mayuscula: bool
    x: float; y: float


def _agrupar(spans: List[Texto], sep_v=3.4) -> List[List[Texto]]:
    """Une renglones de una misma leyenda.

    1) agrupa por columna: solape horizontal > 45% del renglon mas angosto y
       separacion vertical menor a sep_v puntos;
    2) dentro de la columna, corta cada vez que un renglon empieza con una
       palabra que inicia leyenda ("toma", "preinstalacion", ...), para no
       fusionar 'toma horno' con 'toma microondas'.
    """
    cols: List[List[Texto]] = []
    for a in sorted(spans, key=lambda t: (t.vertical, round(t.y0, 1), t.x0)):
        puesto = False
        for col in cols:
            if col[0].vertical != a.vertical:
                continue
            gx0 = min(t.x0 for t in col); gx1 = max(t.x1 for t in col)
            gy0 = min(t.y0 for t in col); gy1 = max(t.y1 for t in col)
            if not a.vertical:
                ancho = min(gx1 - gx0, a.x1 - a.x0) or 1
                solape = (min(gx1, a.x1) - max(gx0, a.x0)) / ancho
                cerca = (a.y0 - gy1 < sep_v) and (gy0 - a.y1 < sep_v)
            else:
                alto = min(gy1 - gy0, a.y1 - a.y0) or 1
                solape = (min(gy1, a.y1) - max(gy0, a.y0)) / alto
                cerca = (a.x0 - gx1 < sep_v) and (gx0 - a.x1 < sep_v)
            if solape > 0.45 and cerca:
                col.append(a); puesto = True; break
        if not puesto:
            cols.append([a])

    grupos: List[List[Texto]] = []
    for col in cols:
        col.sort(key=lambda t: (t.x0 if t.vertical else t.y0))
        actual: List[Texto] = []
        for t in col:
            inicia = any(_norm(t.texto).startswith(p) for p in C.INICIA_ETIQUETA)
            if inicia and actual:
                grupos.append(actual); actual = []
            actual.append(t)
        if actual:
            grupos.append(actual)
    return grupos


def interpretar(textos: List[Texto], area_plano=None) -> Tuple[List[Etiqueta], List[LetraCircuito], List[Texto]]:
    """Separa el texto en: etiquetas de caja, letras de circuito y resto."""
    letras, resto, candidatos = [], [], []
    for t in textos:
        s = t.texto.strip()
        if len(s) == 1 and s.isalpha():
            cx, cy = t.centro
            letras.append(LetraCircuito(s, s.isupper(), cx, cy))
        elif RE_COTA.match(s):
            resto.append(t)
        else:
            candidatos.append(t)

    etiquetas = []
    for grupo in _agrupar(candidatos):
        grupo.sort(key=lambda t: (t.y0, t.x0))
        txt = " ".join(t.texto for t in grupo)
        n = _norm(txt)
        if not any(p in n for p in C.PALABRAS_ETIQUETA):
            resto.extend(grupo)
            continue
        x0 = min(t.x0 for t in grupo); y0 = min(t.y0 for t in grupo)
        x1 = max(t.x1 for t in grupo); y1 = max(t.y1 for t in grupo)
        e = Etiqueta(re.sub(r"\s+", " ", txt).strip(), (x0+x1)/2, (y0+y1)/2,
                     (x0, y0, x1, y1), vertical=grupo[0].vertical)
        m = RE_ALTURA.search(n)
        if m:
            e.altura_m = float(m.group(1).replace(",", "."))
        mm = RE_MULT.search(n)
        if mm:
            e.multiplicidad = int(mm.group(1))
        for subtipo, claves in C.REGLAS_SUBTIPO:
            if any(_norm(k) in n for k in claves):
                e.subtipo = subtipo
                break
        if e.subtipo is None:
            e.subtipo = "especial"
        etiquetas.append(e)
    return etiquetas, letras, resto
