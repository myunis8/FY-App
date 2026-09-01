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
from . import config as cfgmod, materiales as mat_mod
from .pdf_presupuesto import _marca_de_agua, _logo, MARGEN, ANCHO, ALTO, NAVY, FONDO_TABLA_OPACIDAD

FIELD_COLOR = (0x28/255, 0x28/255, 0x28/255)
ITEM_COLOR = (0x50/255, 0x50/255, 0x50/255)
FOOTER_COLOR = (0x6e/255, 0x6e/255, 0x6e/255)
LINK_COLOR = (0xb5/255, 0x65/255, 0x1d/255)     # el mismo cobre que usa la lista de materiales en pantalla
ZEBRA = (0.95, 0.95, 0.95)
FILA_ALTO = 20.35
GAP_CAT_A_TABLA = 12
GAP_TABLA_A_CAT = 18
FIELD_LINEA = 16


def _plata(n: float) -> str:
    return f"$ {n:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def _uri(url: str) -> str:
    """Un link cargado a mano puede venir sin esquema ("ejemplo.com/x"); para
    que el visor de PDF lo abra como URL absoluta necesita http(s)://."""
    s = (url or "").strip()
    return s if "://" in s else "https://" + s


def _link_corto(url: str, ancho_max: float) -> str:
    """Versión legible del link para mostrar en la tabla: sin esquema ni
    barra final, recortada con … si no entra en el ancho de la columna."""
    s = (url or "").strip()
    for p in ("https://", "http://"):
        if s.lower().startswith(p):
            s = s[len(p):]
    if s.lower().startswith("www."):
        s = s[4:]
    s = s.rstrip("/")
    if pymupdf.get_text_length(s, fontname="helv", fontsize=8) <= ancho_max:
        return s
    while s and pymupdf.get_text_length(s + "…", fontname="helv", fontsize=8) > ancho_max:
        s = s[:-1]
    return s + "…"


def _nueva_pagina(doc, cfg: dict):
    pg = doc.new_page(width=ANCHO, height=ALTO)
    _marca_de_agua(pg, cfg)
    return pg, MARGEN + 10


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


def _ancho_columna_item(items: list[dict], tope: float = 320.0) -> float:
    max_w = max((pymupdf.get_text_length(str(i.get("item") or ""), fontname="helv", fontsize=9)
                for i in items), default=100)
    return max(160.0, min(tope, max_w + 80))


def _tabla_categoria(pg, y: float, categoria: str, items: list[dict], mostrar_precio: bool) -> float:
    if not items:
        return y
    hay_links = any((it.get("_link") or "").strip() for it in items)
    x0, x1 = MARGEN, ANCHO - MARGEN
    col_link = min(150.0, 0.28 * (x1 - x0)) if hay_links else 0.0
    x1t = x1 - col_link                       # las columnas "de siempre" viven hasta acá; el link va de x1t a x1
    ancho_total = x1t - x0
    col_item = _ancho_columna_item(items, tope=240.0 if hay_links else 320.0)
    resto = ancho_total - col_item
    if mostrar_precio:
        col_unidad = resto * 0.16
        col_cant = resto * 0.16
        col_precio = resto * 0.34
        heads = ["Ítem", "Unidad", "Cant.", "P. estimado", "Subtotal"]
        xs = [x0, x0 + col_item, x0 + col_item + col_unidad,
             x0 + col_item + col_unidad + col_cant,
             x0 + col_item + col_unidad + col_cant + col_precio, x1t]
    else:
        col_unidad = resto * 0.4
        heads = ["Ítem", "Unidad", "Cant."]
        xs = [x0, x0 + col_item, x0 + col_item + col_unidad, x1t]

    pg.insert_text((x0, y), categoria, fontsize=11, fontname="hebo", color=NAVY)
    y += GAP_CAT_A_TABLA

    pg.draw_rect(pymupdf.Rect(x0, y, x1, y + FILA_ALTO), color=None, fill=NAVY, fill_opacity=FONDO_TABLA_OPACIDAD)
    for i, h in enumerate(heads):
        pg.insert_text((xs[i] + 5, y + FILA_ALTO - 6), h, fontsize=9, fontname="hebo", color=(1, 1, 1))
    if hay_links:
        pg.insert_text((x1t + 5, y + FILA_ALTO - 6), "Link", fontsize=9, fontname="hebo", color=(1, 1, 1))
    y += FILA_ALTO

    for i, it in enumerate(items):
        if y + FILA_ALTO > ALTO - 120:
            return -y
        fill = ZEBRA if i % 2 == 0 else (1, 1, 1)
        pg.draw_rect(pymupdf.Rect(x0, y, x1, y + FILA_ALTO), color=None, fill=fill,
                    fill_opacity=FONDO_TABLA_OPACIDAD)
        base = y + FILA_ALTO - 6
        link = (it.get("_link") or "").strip()
        nombre = str(it.get("item") or "")[:70]
        pg.insert_text((xs[0] + 5, base), nombre, fontsize=9,
                       color=LINK_COLOR if link else ITEM_COLOR)
        if link:
            w = pymupdf.get_text_length(nombre, fontname="helv", fontsize=9)
            pg.draw_line((xs[0] + 5, base + 1.5), (xs[0] + 5 + w, base + 1.5),
                         color=LINK_COLOR, width=0.4)
            pg.insert_link({"kind": pymupdf.LINK_URI, "uri": _uri(link),
                            "from": pymupdf.Rect(xs[0] + 3, y + 2, xs[1] - 3, y + FILA_ALTO - 2)})
        pg.insert_text((xs[1] + 5, base), str(it.get("unidad") or "u"),
                       fontsize=9, color=ITEM_COLOR)
        cant = f'{it.get("cantidad",0):g}'
        if mostrar_precio:
            precio = it.get("precioEstimado") or 0
            sub = precio * (it.get("cantidad") or 0)
            for valor, xd in ((cant, xs[3] - 5), (_plata(precio), xs[4] - 5), (_plata(sub), xs[5] - 5)):
                w = pymupdf.get_text_length(valor, fontname="helv", fontsize=9)
                pg.insert_text((xd - w, base), valor, fontsize=9, color=ITEM_COLOR)
        else:
            w = pymupdf.get_text_length(cant, fontname="helv", fontsize=9)
            pg.insert_text((xs[3] - 5 - w, base), cant, fontsize=9, color=ITEM_COLOR)
        if hay_links and link:
            corto = _link_corto(link, col_link - 10)
            pg.insert_text((x1t + 5, base), corto, fontsize=8, color=LINK_COLOR)
            w = pymupdf.get_text_length(corto, fontname="helv", fontsize=8)
            pg.draw_line((x1t + 5, base + 1.5), (x1t + 5 + w, base + 1.5),
                         color=LINK_COLOR, width=0.4)
            pg.insert_link({"kind": pymupdf.LINK_URI, "uri": _uri(link),
                            "from": pymupdf.Rect(x1t + 3, y + 2, x1 - 3, y + FILA_ALTO - 2)})
        y += FILA_ALTO
    return y + GAP_TABLA_A_CAT


def _es_cable_cano_estimado(e: dict) -> bool:
    """Los metros de cable y caño que salen de Routeo se reportan en pantalla
    para control, pero no van al PDF: en la lista que se le entrega, el cable
    se compra por rollo ("Rollos de cable a comprar") y el caño se redondea a
    mano. Los renglones de cable agregados a mano desde el catálogo no tienen
    origen "computo", así que sí se muestran."""
    return e.get("origen") == "computo" and (e.get("categoria") or "") == "Cables y caños"


def _footer(pg):
    fecha = datetime.now().strftime("%d/%m/%Y")
    texto = (f"Lista armada el {fecha}. Las cantidades de cajas y térmicas son una "
            "estimación a partir de lo cargado en Circuitos y Tablero -- conviene "
            "confirmarlas contra el plano antes de comprar.")
    pg.insert_textbox(pymupdf.Rect(MARGEN, ALTO - 90, ANCHO - MARGEN, ALTO - 40), texto,
                      fontsize=8.5, fontname="helv", color=FOOTER_COLOR, lineheight=1.35)


def _items_por_categoria(items: list[dict]) -> list[tuple[str, list[dict]]]:
    orden = mat_mod.CATEGORIAS
    agrupado: dict[str, list[dict]] = {}
    for it in items:
        cat = it.get("categoria") or "Otros"
        agrupado.setdefault(cat, []).append(it)
    salida = [(cat, agrupado[cat]) for cat in orden if cat in agrupado]
    salida += [(cat, v) for cat, v in agrupado.items() if cat not in orden]
    return salida


def _links_de_catalogo() -> tuple[dict, dict]:
    """El link de compra vive en el catálogo (materiales.json), no en el
    renglón de la obra. Se resuelve por id de catálogo y, como respaldo, por
    nombre exacto -- así un catalogoId viejo no deja el ítem sin link."""
    cat = mat_mod.leer().get("items") or []
    por_id = {c.get("id"): (c.get("link") or "").strip() for c in cat}
    por_nombre = {(c.get("item") or "").strip().lower(): (c.get("link") or "").strip() for c in cat}
    return por_id, por_nombre


def generar(obra: dict, mostrar_precio: bool = True) -> bytes:
    cfg = cfgmod.leer_config()
    mat = obra.get("materiales") or {}
    link_por_id, link_por_nombre = _links_de_catalogo()

    def _link_de(e: dict) -> str:
        return (link_por_id.get(e.get("catalogoId"))
                or link_por_nombre.get((e.get("item") or "").strip().lower()) or "")

    items = [{**e, "_link": _link_de(e)}
             for e in sorted(mat.get("extras") or [], key=lambda i: i.get("orden", 0))
             if not _es_cable_cano_estimado(e)]
    total = sum((i.get("precioEstimado") or 0) * (i.get("cantidad") or 0) for i in items) if mostrar_precio else 0

    doc = pymupdf.open()
    pg = doc.new_page(width=ANCHO, height=ALTO)
    _marca_de_agua(pg, cfg)
    y = _encabezado(pg, obra, cfg)

    for cat, its in _items_por_categoria(items):
        y = _tabla_categoria(pg, y, cat, its, mostrar_precio)
        if y < 0:
            pg, y = _nueva_pagina(doc, cfg)
            y = _tabla_categoria(pg, y, cat, its, mostrar_precio)

    cables = [c for c in (mat.get("cables") or []) if c.get("necesita")]
    if cables:
        filas_cable = [{"item": f'Rollo de cable {c.get("seccionMm2")} mm² - {c.get("color","")}'
                       + (f' ({c["notas"]})' if c.get("notas") else ""),
                       "unidad": "rollo", "cantidad": 1, "precioEstimado": 0} for c in cables]
        if y > ALTO - 140:
            pg, y = _nueva_pagina(doc, cfg)
        y = _tabla_categoria(pg, y, "Rollos de cable a comprar", filas_cable, False)
        if y < 0:                              # no entraron las filas: página nueva y de vuelta
            pg, y = _nueva_pagina(doc, cfg)
            y = _tabla_categoria(pg, y, "Rollos de cable a comprar", filas_cable, False)

    if mostrar_precio:
        if y > ALTO - 80:
            pg, y = _nueva_pagina(doc, cfg)
        pg.insert_text((MARGEN, y + 12), f"Total estimado: {_plata(total)}",
                       fontsize=13, fontname="hebo", color=NAVY)

    for p in doc:
        _footer(p)

    salida = io.BytesIO()
    doc.save(salida)
    doc.close()
    return salida.getvalue()
