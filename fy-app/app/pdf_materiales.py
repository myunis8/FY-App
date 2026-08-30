"""PDF de la lista de materiales de una obra: mismo lenguaje visual que el
presupuesto (marca de agua, logo, tablas por categoría) -- se reusan esas
piezas directamente de pdf_presupuesto.py en vez de mantener una copia
aparte que se pueda desincronizar.

A diferencia del presupuesto, acá el precio es opcional: a veces sólo se
entrega la lista de qué comprar, sin decir cuánto sale (por ejemplo, cuando
el cliente compra los materiales por su cuenta).
"""
from __future__ import annotations
import io
from datetime import datetime
import pymupdf
from . import config as cfgmod
from .pdf_presupuesto import _marca_de_agua, _logo, MARGEN, ANCHO, ALTO, NAVY, FONDO_TABLA_OPACIDAD

FIELD_COLOR = (0x28/255, 0x28/255, 0x28/255)
ITEM_COLOR = (0x50/255, 0x50/255, 0x50/255)
FOOTER_COLOR = (0x6e/255, 0x6e/255, 0x6e/255)
ZEBRA = (0.95, 0.95, 0.95)
FILA_ALTO = 20.35
GAP_CAT_A_TABLA = 12
GAP_TABLA_A_CAT = 18
FIELD_LINEA = 16


def _plata(n: float) -> str:
    return f"$ {n:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def _encabezado(pg, obra: dict, cfg: dict) -> float:
    _logo(pg)
    pg.insert_text((MARGEN, 50), "Lista de materiales", fontsize=18, fontname="hebo", color=NAVY)
    campos = [
        ("Obra:", obra["obra"].get("nombre") or "-"),
        ("Dirección:", obra["obra"].get("direccion") or "-"),
        ("Fecha:", datetime.now().strftime("%d/%m/%Y")),
    ]
    y = 78
    for etiqueta, valor in campos:
        pg.insert_text((MARGEN, y), etiqueta, fontsize=10, fontname="hebo", color=FIELD_COLOR)
        pg.insert_text((MARGEN + 90, y), str(valor)[:70], fontsize=10, color=FIELD_COLOR)
        y += FIELD_LINEA
    return y + 26


def _ancho_columna_item(items: list[dict]) -> float:
    max_w = max((pymupdf.get_text_length(str(i.get("item") or ""), fontname="helv", fontsize=9)
                for i in items), default=100)
    return max(160.0, min(320.0, max_w + 80))


def _tabla_categoria(pg, y: float, categoria: str, items: list[dict], mostrar_precio: bool) -> float:
    if not items:
        return y
    x0, x1 = MARGEN, ANCHO - MARGEN
    ancho_total = x1 - x0
    col_item = _ancho_columna_item(items)
    resto = ancho_total - col_item
    if mostrar_precio:
        col_unidad = resto * 0.16
        col_cant = resto * 0.16
        col_precio = resto * 0.34
        col_subtotal = resto - col_unidad - col_cant - col_precio
        heads = ["Ítem", "Unidad", "Cant.", "P. estimado", "Subtotal"]
        xs = [x0, x0 + col_item, x0 + col_item + col_unidad,
             x0 + col_item + col_unidad + col_cant,
             x0 + col_item + col_unidad + col_cant + col_precio, x1]
    else:
        col_unidad = resto * 0.4
        col_cant = resto - col_unidad
        heads = ["Ítem", "Unidad", "Cant."]
        xs = [x0, x0 + col_item, x0 + col_item + col_unidad, x1]

    pg.insert_text((x0, y), categoria, fontsize=11, fontname="hebo", color=NAVY)
    y += GAP_CAT_A_TABLA

    pg.draw_rect(pymupdf.Rect(x0, y, x1, y + FILA_ALTO), color=None, fill=NAVY, fill_opacity=FONDO_TABLA_OPACIDAD)
    for i, h in enumerate(heads):
        pg.insert_text((xs[i] + 5, y + FILA_ALTO - 6), h, fontsize=9, fontname="hebo", color=(1, 1, 1))
    y += FILA_ALTO

    for i, it in enumerate(items):
        if y + FILA_ALTO > ALTO - 120:
            return -y
        fill = ZEBRA if i % 2 == 0 else (1, 1, 1)
        pg.draw_rect(pymupdf.Rect(x0, y, x1, y + FILA_ALTO), color=None, fill=fill,
                    fill_opacity=FONDO_TABLA_OPACIDAD)
        pg.insert_text((xs[0] + 5, y + FILA_ALTO - 6), str(it.get("item") or "")[:70],
                       fontsize=9, color=ITEM_COLOR)
        pg.insert_text((xs[1] + 5, y + FILA_ALTO - 6), str(it.get("unidad") or "u"),
                       fontsize=9, color=ITEM_COLOR)
        cant = f'{it.get("cantidad",0):g}'
        if mostrar_precio:
            precio = it.get("precioEstimado") or 0
            sub = precio * (it.get("cantidad") or 0)
            for valor, xd in ((cant, xs[3] - 5), (_plata(precio), xs[4] - 5), (_plata(sub), xs[5] - 5)):
                w = pymupdf.get_text_length(valor, fontname="helv", fontsize=9)
                pg.insert_text((xd - w, y + FILA_ALTO - 6), valor, fontsize=9, color=ITEM_COLOR)
        else:
            w = pymupdf.get_text_length(cant, fontname="helv", fontsize=9)
            pg.insert_text((xs[3] - 5 - w, y + FILA_ALTO - 6), cant, fontsize=9, color=ITEM_COLOR)
        y += FILA_ALTO
    return y + GAP_TABLA_A_CAT


def _footer(pg):
    fecha = datetime.now().strftime("%d/%m/%Y")
    texto = (f"Lista armada el {fecha}. Las cantidades de cajas, térmicas, cable y caño son una "
            "estimación a partir de lo cargado en Circuitos, Tablero y Routeo -- conviene "
            "confirmarlas contra el plano antes de comprar.")
    pg.insert_textbox(pymupdf.Rect(MARGEN, ALTO - 90, ANCHO - MARGEN, ALTO - 40), texto,
                      fontsize=8.5, fontname="helv", color=FOOTER_COLOR, lineheight=1.35)


def _items_por_categoria(items: list[dict]) -> list[tuple[str, list[dict]]]:
    from . import materiales as mat_mod
    orden = mat_mod.CATEGORIAS
    agrupado: dict[str, list[dict]] = {}
    for it in items:
        cat = it.get("categoria") or "Otros"
        agrupado.setdefault(cat, []).append(it)
    salida = [(cat, agrupado[cat]) for cat in orden if cat in agrupado]
    salida += [(cat, v) for cat, v in agrupado.items() if cat not in orden]
    return salida


def generar(obra: dict, mostrar_precio: bool = True) -> bytes:
    cfg = cfgmod.leer_config()
    mat = obra.get("materiales") or {}
    items = sorted(mat.get("extras") or [], key=lambda i: i.get("orden", 0))
    total = sum((i.get("precioEstimado") or 0) * (i.get("cantidad") or 0) for i in items) if mostrar_precio else 0

    doc = pymupdf.open()
    pg = doc.new_page(width=ANCHO, height=ALTO)
    _marca_de_agua(pg, cfg)
    y = _encabezado(pg, obra, cfg)

    for cat, its in _items_por_categoria(items):
        y = _tabla_categoria(pg, y, cat, its, mostrar_precio)
        if y < 0:
            pg = doc.new_page(width=ANCHO, height=ALTO)
            _marca_de_agua(pg, cfg)
            y = MARGEN + 10
            y = _tabla_categoria(pg, y, cat, its, mostrar_precio)

    cables = [c for c in (mat.get("cables") or []) if c.get("necesita")]
    if cables:
        if y > ALTO - 160:
            pg = doc.new_page(width=ANCHO, height=ALTO)
            _marca_de_agua(pg, cfg)
            y = MARGEN + 10
        filas_cable = [{"item": f'Rollo de cable {c.get("seccionMm2")} mm² - {c.get("color","")}'
                       + (f' ({c["notas"]})' if c.get("notas") else ""),
                       "unidad": "rollo", "cantidad": 1, "precioEstimado": 0} for c in cables]
        y = _tabla_categoria(pg, y, "Rollos de cable a comprar", filas_cable, False)

    if mostrar_precio and y < ALTO - 60:
        pg.insert_text((MARGEN, y + 12), f"Total estimado: {_plata(total)}",
                       fontsize=13, fontname="hebo", color=NAVY)

    for p in doc:
        _footer(p)

    salida = io.BytesIO()
    doc.save(salida)
    doc.close()
    return salida.getvalue()
