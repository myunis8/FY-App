"""Genera el PDF de presupuesto con PyMuPDF: logo, marca de agua, ítems y totales.

No se suma ninguna librería nueva: PyMuPDF ya es una dependencia del extractor
y alcanza para maquetar texto e imágenes en un PDF simple.
"""
from __future__ import annotations
import io
from datetime import datetime
import pymupdf
from . import config as cfgmod, precios as precios_mod, presupuesto as pres_mod

ANCHO, ALTO = 595, 842                      # A4 en puntos
MARGEN = 46
NAVY = (0x16/255, 0x28/255, 0x3f/255)
COPPER = (0xb5/255, 0x65/255, 0x1d/255)
MUTED = (0x5b/255, 0x6b/255, 0x7a/255)
LINE = (0xdd/255, 0xe3/255, 0xe2/255)
INK = (0x1c/255, 0x27/255, 0x33/255)


def _plata(n: float) -> str:
    return f"$ {n:,.0f}".replace(",", ".")


def _marca_de_agua(pg, cfg: dict):
    ruta = cfgmod.ruta_imagen("marca")
    if ruta is None or ruta.suffix.lower() == ".svg":
        return
    # OJO: "cfg.get(...) or 16" no sirve de piso si ya hay un valor guardado
    # en disco (8 es "truthy" en Python, así que nunca caía al default nuevo).
    # Por eso el cambio de la entrega anterior no se notaba: quien ya había
    # tocado la configuración seguía con el valor viejo de siempre. El piso
    # de abajo tiene que ser incondicional.
    op = max(0.16, min(0.55, (cfg.get("opacidadMarca") or 16) / 100))
    # el ancho/alto real del logo importa: forzarlo a un recuadro cuadrado
    # deforma cualquier logo que no sea 1:1 (la mayoría no lo son).
    try:
        pix = pymupdf.Pixmap(str(ruta))
        aspecto = pix.width / max(pix.height, 1)
    except Exception:
        aspecto = 1.0
    ancho = ANCHO * 0.86                       # bien grande, no sutil
    alto = ancho / aspecto if aspecto > 0 else ancho
    alto_max = ALTO * 0.58
    if alto > alto_max:
        alto = alto_max
        ancho = alto * aspecto
    x0 = (ANCHO - ancho) / 2
    y0 = (ALTO - alto) / 2
    rect = pymupdf.Rect(x0, y0, x0 + ancho, y0 + alto)
    pg.insert_image(rect, filename=str(ruta), overlay=True, alpha=op)


def _encabezado(pg, obra: dict, cfg: dict) -> float:
    y = MARGEN
    ruta = cfgmod.ruta_imagen("logo")
    if ruta is not None and ruta.suffix.lower() != ".svg":
        pix = pymupdf.Pixmap(str(ruta))
        alto_logo = 46
        ancho_logo = alto_logo * pix.width / max(pix.height, 1)
        pg.insert_image(pymupdf.Rect(MARGEN, y, MARGEN + ancho_logo, y + alto_logo),
                        filename=str(ruta))
        x_texto = MARGEN + ancho_logo + 16
    else:
        x_texto = MARGEN
    empresa = cfg.get("empresa") or ""
    if empresa:
        pg.insert_text((x_texto, y + 16), empresa, fontsize=13,
                       fontname="hebo", color=NAVY)
    contacto = cfg.get("contacto") or ""
    if contacto:
        pg.insert_text((x_texto, y + 32), contacto, fontsize=8, color=MUTED)

    fecha = datetime.now().strftime("%d/%m/%Y")
    pg.insert_text((ANCHO - MARGEN - 130, y + 10), "PRESUPUESTO",
                   fontsize=15, fontname="hebo", color=NAVY)
    pg.insert_text((ANCHO - MARGEN - 130, y + 26), f"Fecha: {fecha}", fontsize=8, color=MUTED)
    pg.insert_text((ANCHO - MARGEN - 130, y + 38),
                   f"Obra: {obra['obra'].get('nombre','')}"[:40], fontsize=8, color=MUTED)
    if obra["obra"].get("cliente"):
        pg.insert_text((ANCHO - MARGEN - 130, y + 50),
                       f"Cliente: {obra['obra']['cliente']}"[:40], fontsize=8, color=MUTED)

    y2 = y + 62
    pg.draw_line((MARGEN, y2), (ANCHO - MARGEN, y2), color=LINE, width=0.8)
    return y2 + 20


def _tabla(pg, y: float, titulo: str, items: list[dict]) -> float:
    if not items:
        return y
    pg.insert_text((MARGEN, y), titulo, fontsize=10, fontname="hebo", color=NAVY)
    y += 14
    cols = [MARGEN, MARGEN + 260, MARGEN + 320, MARGEN + 400, ANCHO - MARGEN]
    pg.draw_rect(pymupdf.Rect(MARGEN, y, ANCHO - MARGEN, y + 16),
                color=None, fill=(0.93, 0.95, 0.95))
    heads = ["Ítem", "Cant.", "Unitario", "Subtotal"]
    for h, x in zip(heads, cols[:-1]):
        pg.insert_text((x + 4, y + 11), h, fontsize=7.4, fontname="hebo", color=MUTED)
    y += 16
    for it in items:
        if y > ALTO - 140:
            return y                        # se corta acá; el llamador pagina
        sub = (it.get("precioUnitario") or 0) * (it.get("cantidad") or 0)
        fila = [str(it.get("item") or "")[:52],
               f'{it.get("cantidad",0):g} {it.get("unidad","u")}',
               _plata(it.get("precioUnitario") or 0), _plata(sub)]
        for val, x in zip(fila, cols[:-1]):
            pg.insert_text((x + 4, y + 10), val, fontsize=8.2, color=INK)
        y += 15
        pg.draw_line((MARGEN, y - 3), (ANCHO - MARGEN, y - 3), color=LINE, width=0.4)
    return y + 10


def _totales(pg, y: float, tot: dict, desc: dict | None) -> float:
    x0 = ANCHO - MARGEN - 210
    filas = [("Subtotal trabajos", tot["subtotal"])]
    if tot["extras"]:
        filas.append(("Extras", tot["extras"]))
    if tot["descuento"]:
        etiqueta = "Descuento"
        if desc and desc.get("motivo"):
            etiqueta += f" ({desc['motivo']})"
        filas.append((etiqueta, -tot["descuento"]))
    if tot["ajuste"]:
        filas.append(("Ajuste", tot["ajuste"]))
    for k, v in filas:
        pg.insert_text((x0, y), k, fontsize=8.6, color=MUTED)
        pg.insert_text((ANCHO - MARGEN - 4, y), _plata(v), fontsize=8.6,
                       color=INK, fontname="hebo")
        y += 15
    y += 4
    pg.draw_line((x0, y), (ANCHO - MARGEN, y), color=INK, width=1.1)
    y += 16
    pg.insert_text((x0, y), "TOTAL", fontsize=12, fontname="hebo", color=NAVY)
    pg.insert_text((ANCHO - MARGEN - 110, y), _plata(tot["total"]), fontsize=13,
                   fontname="hebo", color=NAVY)
    return y + 24


def _pie(pg, n: int, total: int):
    pg.insert_text((MARGEN, ALTO - 26), f"Página {n} de {total}", fontsize=7.4, color=MUTED)
    pg.insert_text((ANCHO - MARGEN - 220, ALTO - 26),
                   "Presupuesto sujeto a revisión de obra e insumos.",
                   fontsize=7.4, color=MUTED)


def generar(obra: dict) -> bytes:
    cfg = cfgmod.leer_config()
    pres = obra.get("presupuesto") or {}
    tot = pres_mod.totales(pres)
    items = [i for i in (pres.get("items") or []) if not i.get("opcional")]
    extras = [i for i in (pres.get("extras") or []) if not i.get("opcional")]
    opcionales = [i for i in (pres.get("items") or []) + (pres.get("extras") or [])
                  if i.get("opcional")]

    doc = pymupdf.open()
    pg = doc.new_page(width=ANCHO, height=ALTO)
    _marca_de_agua(pg, cfg)
    y = _encabezado(pg, obra, cfg)
    y = _tabla(pg, y, "Trabajos", items)
    y = _tabla(pg, y + 6, "Extras y adicionales", extras)
    if opcionales:
        y = _tabla(pg, y + 6, "Opcionales (no incluidos en el total)", opcionales)
    y = max(y + 10, ALTO - 190)
    _totales(pg, y, tot, pres.get("descuento"))
    _pie(pg, 1, 1)

    salida = io.BytesIO()
    doc.save(salida)
    doc.close()
    return salida.getvalue()
