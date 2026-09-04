"""Informe general: junta en un solo PDF las páginas que ya arma cada
módulo, según cuáles haya elegido el usuario, más una portada y un par de
páginas propias (circuitos, resumen de routeo) para lo que todavía no tiene
su propio PDF.

Sigue el diseño que ya estaba anotado en el backlog del README: cada módulo
aporta su(s) página(s) ya generadas, y esto sólo arma la portada y las
concatena -- así sumar un módulo nuevo el día de mañana es agregar una
entrada en MODULOS y una función que aporte sus páginas, no rehacer nada.

Routeo aporta dos cosas: "routeo_plano" es la hoja general del plano (con la
foto de fondo, los circuitos y la leyenda), que la genera pdf_routeo.py del
lado del servidor igual que el resto; "routeo" es el resumen de materiales
calculado a partir de los tramos guardados.
"""
from __future__ import annotations
import io, math
from datetime import datetime
import pymupdf
from . import config as cfgmod, pdf_tablero, pdf_presupuesto, pdf_routeo, pdf_materiales

ANCHO, ALTO = 595.28, 841.89           # A4 en puntos, igual que el resto de los PDFs
MARGEN = 44
NAVY = (0x16/255, 0x28/255, 0x3f/255)
GRIS = (0x5b/255, 0x6b/255, 0x7a/255)
TRAZO = (0x28/255, 0x28/255, 0x28/255)
LINEA = (0.85, 0.86, 0.87)
ZEBRA = (0.95, 0.95, 0.95)
LOGO_LADO = 46

# orden fijo en el que aparecen los módulos si están elegidos -- no depende
# del orden en que vengan en el pedido del cliente
ORDEN_MODULOS = ["circuitos", "tableros", "routeo_plano", "routeo", "presupuesto", "materiales", "unifilar"]
MODULOS = {
    "circuitos":    "Circuitos",
    "tableros":     "Tablero(s) -- guía de tapa",
    "routeo_plano": "Routeo -- plano general (todos los circuitos, 1 hoja)",
    "routeo":       "Routeo (resumen de materiales)",
    "presupuesto":  "Presupuesto",
    "materiales":   "Lista de materiales",
    "unifilar":     "Esquema unifilar (beta)",
}
# todos marcados por defecto salvo el unifilar (beta) y el resumen de
# materiales de routeo (todavía en ajuste, se deja como opción aparte)
MODULOS_POR_DEFECTO = ["circuitos", "tableros", "routeo_plano", "presupuesto"]


def _logo(pg):
    ruta = cfgmod.ruta_imagen("logo")
    if ruta is None or ruta.suffix.lower() == ".svg":
        return None
    try:
        pix = pymupdf.Pixmap(str(ruta))
        aspecto = pix.width / max(pix.height, 1)
    except Exception:
        return None
    alto = LOGO_LADO
    ancho = alto * aspecto
    x0 = ANCHO - MARGEN - ancho
    y0 = MARGEN
    pg.insert_image(pymupdf.Rect(x0, y0, x0 + ancho, y0 + alto), filename=str(ruta))
    return x0


def _encabezado_pagina(pg, titulo):
    pg.insert_text((MARGEN, 34), titulo, fontsize=13, fontname="hebo", color=NAVY)
    pg.draw_line((MARGEN, 42), (ANCHO - MARGEN, 42), color=LINEA, width=0.8)


def _tabla_simple(pg, y0, encabezados, anchos, filas, fontsize=8.5):
    """Tabla genérica de una sola hoja (sin paginar) -- se usa para
    circuitos y para el resumen de routeo, que son listas cortas."""
    x0 = MARGEN
    xs = [x0]
    for a in anchos:
        xs.append(xs[-1] + a)
    fila_alto = 18
    pg.draw_rect(pymupdf.Rect(x0, y0, xs[-1], y0 + fila_alto), color=None, fill=NAVY)
    for i, h in enumerate(encabezados):
        pg.insert_text((xs[i] + 6, y0 + fila_alto - 6), h, fontsize=8.3, fontname="hebo", color=(1, 1, 1))
    y = y0 + fila_alto
    for i, fila in enumerate(filas):
        if y + fila_alto > ALTO - 70:
            break                      # el informe no pagina tablas largas; con muchos circuitos se recorta acá
        fill = ZEBRA if i % 2 == 0 else (1, 1, 1)
        pg.draw_rect(pymupdf.Rect(x0, y, xs[-1], y + fila_alto), color=None, fill=fill)
        for j, val in enumerate(fila):
            pg.insert_text((xs[j] + 6, y + fila_alto - 6), str(val)[:48], fontsize=fontsize, color=TRAZO)
        y += fila_alto
    return y


def _portada(doc, obra: dict, modulos: list[str], cfg: dict):
    pg = doc.new_page(width=ANCHO, height=ALTO)
    _logo(pg)
    o = obra.get("obra", {})
    pg.insert_text((MARGEN, 140), "Informe general de obra", fontsize=22, fontname="hebo", color=NAVY)
    pg.insert_text((MARGEN, 168), o.get("nombre") or "Obra sin nombre", fontsize=14, fontname="helv",
                   color=GRIS)

    campos = [
        ("Cliente", o.get("cliente") or "-"),
        ("Dirección", o.get("direccion") or "-"),
        ("Tipo de instalación", o.get("tipoInstalacion") or "-"),
        ("Fecha del informe", datetime.now().strftime("%d/%m/%Y")),
        ("Generado por", cfg.get("empresa") or "-"),
    ]
    y = 220
    for k, v in campos:
        pg.insert_text((MARGEN, y), k, fontsize=9.5, fontname="hebo", color=TRAZO)
        pg.insert_text((MARGEN + 160, y), str(v)[:60], fontsize=9.5, color=TRAZO)
        y += 20

    y += 20
    pg.insert_text((MARGEN, y), "Este informe incluye", fontsize=11, fontname="hebo", color=NAVY)
    y += 8
    pg.draw_line((MARGEN, y), (ANCHO - MARGEN, y), color=LINEA, width=0.8)
    y += 20
    for clave in ORDEN_MODULOS:
        if clave not in modulos:
            continue
        pg.insert_text((MARGEN, y), "•", fontsize=10, color=NAVY)
        pg.insert_text((MARGEN + 14, y), MODULOS[clave], fontsize=10, color=TRAZO)
        y += 18


# --------------------------------------------------------------- circuitos
def _pagina_circuitos(doc, obra: dict):
    pg = doc.new_page(width=ANCHO, height=ALTO)
    _encabezado_pagina(pg, "Circuitos")
    circuitos = obra.get("circuitos") or []
    if not circuitos:
        pg.insert_text((MARGEN, 70), "Todavía no hay circuitos armados en esta obra.",
                       fontsize=10, color=GRIS)
        return
    anchos = [70, 60, 65, 70, ANCHO - 2 * MARGEN - 265]
    filas = [[c.get("nombre") or "-", c.get("tipo") or "-",
             f'{c.get("seccionMm2","-")} mm²' if c.get("seccionMm2") else "-",
             f'{c.get("proteccionA","-")} A' if c.get("proteccionA") else "-",
             c.get("notas") or ""] for c in circuitos]
    _tabla_simple(pg, 58, ["Nombre", "Tipo", "Sección", "Protección", "Descripción"], anchos, filas)


# ------------------------------------------------------------------ routeo
def _long_pts(pts):
    total = 0.0
    for i in range(1, len(pts)):
        a, b = pts[i - 1], pts[i]
        total += math.hypot(b["x"] - a["x"], b["y"] - a["y"])
    return total


def _resumen_routeo(doc, obra: dict):
    pg = doc.new_page(width=ANCHO, height=ALTO)
    _encabezado_pagina(pg, "Routeo -- resumen de materiales")
    canal = obra.get("canalizacion") or {}
    runs = canal.get("runs") or []
    px_por_m = canal.get("pxPerM")
    if not runs or not px_por_m:
        pg.insert_text((MARGEN, 70),
                       "Todavía no se cargó routeo para esta obra, o no tiene escala calibrada.",
                       fontsize=10, color=GRIS)
        return
    circuitos_por_id = {c["id"]: c for c in canal.get("circuits") or []}
    cable_por_seccion: dict[float, float] = {}
    total_cable = 0.0
    for r in runs:
        c = circuitos_por_id.get(r.get("circuit"))
        seccion = (c or {}).get("section") or 0
        largo_m = _long_pts(r.get("pts") or []) / px_por_m
        metros_cable = largo_m * (r.get("cables") or 1)
        cable_por_seccion[seccion] = cable_por_seccion.get(seccion, 0) + metros_cable
        total_cable += metros_cable

    y = 58
    pg.insert_text((MARGEN, y), f"{len(runs)} tramo(s) cargado(s), sobre {len(circuitos_por_id)} circuito(s).",
                   fontsize=9.5, color=TRAZO)
    y += 26
    filas = [[f"{sec} mm²" if sec else "sin sección", f"{m:.1f} m"]
             for sec, m in sorted(cable_por_seccion.items())]
    y = _tabla_simple(pg, y, ["Sección de cable", "Metros totales (todos los conductores)"],
                      [200, ANCHO - 2 * MARGEN - 200], filas)
    y += 10
    pg.insert_text((MARGEN, y), f"Total de cable: {total_cable:.1f} m", fontsize=10, fontname="hebo", color=NAVY)
    y += 30
    pg.insert_textbox(pymupdf.Rect(MARGEN, y, ANCHO - MARGEN, y + 60),
                      "Esta página es un resumen calculado a partir de los mismos tramos cargados en "
                      "Routeo -- no el plano ni el cómputo de caños y cajas, que se arman en el navegador "
                      "a partir de la foto del plano. Para eso, exportá el PDF desde el propio módulo Routeo.",
                      fontsize=8.3, color=GRIS, lineheight=1.4)


def generar(obra: dict, modulos: list[str] | set[str], *, materiales_con_precio: bool = True) -> bytes:
    modulos = set(modulos)
    cfg = cfgmod.leer_config()
    doc = pymupdf.open()
    _portada(doc, obra, [m for m in ORDEN_MODULOS if m in modulos], cfg)

    if "circuitos" in modulos:
        _pagina_circuitos(doc, obra)

    if "routeo_plano" in modulos:
        try:
            b = pdf_routeo.generar(obra, obra.get("canalizacion") or {}, {"general": True})
            sub = pymupdf.open(stream=b, filetype="pdf")
            doc.insert_pdf(sub)
            sub.close()
        except ValueError:
            pass                       # obra sin plano: se omite la hoja, como antes

    if "routeo" in modulos:
        _resumen_routeo(doc, obra)

    if "tableros" in modulos:
        # sólo la guía de tapa (cómo va a quedar) -- el conexionado es
        # detalle de instalación, no algo para mostrarle al cliente en el
        # informe general
        for t in obra.get("tableros") or []:
            sub = pymupdf.open(stream=pdf_tablero.generar_tapa(t, obra), filetype="pdf")
            doc.insert_pdf(sub)
            sub.close()

    if "unifilar" in modulos:
        for t in obra.get("tableros") or []:
            sub = pymupdf.open(stream=pdf_tablero.generar_unifilar(t, obra), filetype="pdf")
            doc.insert_pdf(sub)
            sub.close()

    if "presupuesto" in modulos:
        sub = pymupdf.open(stream=pdf_presupuesto.generar(obra), filetype="pdf")
        doc.insert_pdf(sub)
        sub.close()

    if "materiales" in modulos:
        sub = pymupdf.open(stream=pdf_materiales.generar(obra, mostrar_precio=materiales_con_precio), filetype="pdf")
        doc.insert_pdf(sub)
        sub.close()

    salida = io.BytesIO()
    # deflate: ahora el informe puede traer la hoja del plano de Routeo (con la
    # foto de fondo), así que conviene recomprimir en vez de guardar en crudo
    doc.save(salida, deflate=True, garbage=3)
    doc.close()
    return salida.getvalue()
