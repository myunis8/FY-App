"""Genera el PDF de presupuesto con PyMuPDF, con un formato fijo y exacto:
el mismo que ya se usó y se validó, para no estar cambiando de formato entre
una entrega y la siguiente. Los números de esta plantilla (posiciones,
tamaños, colores, alpha de la marca de agua) se sacaron directo de un PDF de
referencia ya aprobado, leyendo su contenido con PyMuPDF en vez de calcular
a ojo desde una captura de pantalla.
"""
from __future__ import annotations
import io
from datetime import datetime
import pymupdf
from . import config as cfgmod, precios as precios_mod, presupuesto as pres_mod

ANCHO, ALTO = 595.28, 841.89                # A4 en puntos, igual que la referencia
MARGEN = 40
NAVY = (0x16/255, 0x28/255, 0x3f/255)
FIELD_COLOR = (0x28/255, 0x28/255, 0x28/255)
ITEM_COLOR = (0x50/255, 0x50/255, 0x50/255)
FOOTER_COLOR = (0x6e/255, 0x6e/255, 0x6e/255)
ZEBRA = (0.95, 0.95, 0.95)
# los fondos de fila (encabezado navy y cebra gris) van con esta opacidad en
# vez de 100% -- si fueran opacos del todo, tapan la marca de agua entera
# apenas hay una tabla encima (que es casi toda la hoja). 0.82 deja pasar
# lo suficiente de la marca sin perder legibilidad del texto de la tabla.
FONDO_TABLA_OPACIDAD = 0.82

FILA_ALTO = 20.35
GAP_CAT_A_TABLA = 12
GAP_TABLA_A_CAT = 18
FIELD_LINEA = 16

# tamaño y alpha de la marca de agua: 4.5% quedó casi invisible ahora que la
# opacidad se aplica de verdad (antes el bug del parámetro alpha= la dejaba
# siempre opaca, así que un número bajo no se notaba). 12% es un punto medio
# genuinamente visible sin tapar el contenido.
MARCA_FRACCION_ANCHO = 0.8
MARCA_ALPHA = 0.22
LOGO_LADO = 46
LOGO_MARGEN_DER = 40
LOGO_MARGEN_SUP = 24


def _plata(n: float) -> str:
    return f"$ {n:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def _marca_de_agua(pg, cfg: dict):
    ruta = cfgmod.ruta_imagen("marca")
    if ruta is None or ruta.suffix.lower() == ".svg":
        return
    try:
        pix = pymupdf.Pixmap(str(ruta))
        aspecto = pix.width / max(pix.height, 1)
    except Exception:
        aspecto = 1.0
    # Ya me pasó dos veces: un valor guardado en disco de una entrega
    # anterior (8, 14, 16...) le ganaba a cualquier default nuevo que yo
    # pusiera acá. Esta vez el pedido es "más traslúcido" (mas bajo), así que
    # el límite tiene que ser un TECHO, no un piso — el resultado nunca puede
    # ser más visible que MARCA_ALPHA, pase lo que pase con lo guardado.
    # Iba por el tercer round de "piso" y "techo" y seguía rompiéndose cada
    # vez que cambiaba el default: si el usuario nunca tocó el control, lo
    # que hay guardado es un default MÍO de una entrega anterior (8, 14, 16,
    # 4.5...), no una elección real. En vez de acotar el valor, detecto esos
    # números puntuales y los reemplazo por el default vigente. Si el
    # usuario puso otro número explícito, se respeta tal cual.
    _DEFAULTS_VIEJOS = {8, 14, 16, 4.5, 4, 5}
    guardado = cfg.get("opacidadMarca")
    if guardado is None or float(guardado) in _DEFAULTS_VIEJOS:
        op = MARCA_ALPHA
    else:
        op = max(0.01, min(0.6, float(guardado) / 100))
    ancho = ANCHO * MARCA_FRACCION_ANCHO
    alto = ancho / aspecto if aspecto > 0 else ancho
    x0 = (ANCHO - ancho) / 2
    y0 = (ALTO - alto) / 2                  # centrada exacto, como en la referencia
    rect = pymupdf.Rect(x0, y0, x0 + ancho, y0 + alto)

    # OJO — descubrimiento importante: en esta versión de PyMuPDF (1.28.x),
    # el parámetro alpha= de insert_image() NO es opacidad — es sólo un flag
    # de rendimiento ("la imagen tiene o no canal alfa propio"). Pasarle 0.07
    # ahí (como hacía antes) no atenuaba nada; la marca salía siempre a full,
    # y cualquier aspecto "tenue" que se veía antes era casualidad del gris
    # del logo, no una transparencia real. La única forma real de bajarle la
    # opacidad es armar un graphics state con /ca y aplicarlo en el content
    # stream, que es exactamente lo que hacía el PDF de referencia a mano.
    gs_nombre = pg._set_opacity(CA=1, ca=op)
    pg.insert_image(rect, filename=str(ruta), overlay=True)
    xref_cont = pg.get_contents()[0]
    contenido = pg.read_contents().decode("latin-1")
    marcador = contenido.rfind("q\n")       # el bloque que insert_image acaba de agregar
    if marcador >= 0:
        nuevo = contenido[:marcador] + f"q\n/{gs_nombre} gs\n" + contenido[marcador + 2:]
        pg.parent.update_stream(xref_cont, nuevo.encode("latin-1"))


def _logo(pg):
    ruta = cfgmod.ruta_imagen("logo")
    if ruta is None or ruta.suffix.lower() == ".svg":
        return
    try:
        pix = pymupdf.Pixmap(str(ruta))
        aspecto = pix.width / max(pix.height, 1)
    except Exception:
        aspecto = 1.0
    alto = LOGO_LADO
    ancho = alto * aspecto
    x0 = ANCHO - LOGO_MARGEN_DER - ancho
    y0 = LOGO_MARGEN_SUP
    pg.insert_image(pymupdf.Rect(x0, y0, x0 + ancho, y0 + alto), filename=str(ruta))


def _encabezado(pg, obra: dict, cfg: dict) -> float:
    """Título, logo arriba a la derecha, y los datos de la obra en una lista
    simple de campo: valor. Sin bloque de empresa/contacto superpuesto: eso
    ya lo dice el logo."""
    _logo(pg)
    pg.insert_text((MARGEN, 50), "Presupuesto - Instalación Eléctrica",
                   fontsize=18, fontname="hebo", color=NAVY)

    campos = [
        ("Cliente:", obra["obra"].get("cliente") or "-"),
        ("Obra / dirección:", obra["obra"].get("nombre") or "-"),
        ("Fecha:", datetime.now().strftime("%d/%m/%Y")),
        ("Tipo de instalación:",
         "Trifásica" if obra["obra"].get("tipoInstalacion") == 3 else "Monofásica"),
    ]
    y = 78
    for etiqueta, valor in campos:
        pg.insert_text((MARGEN, y), etiqueta, fontsize=10, fontname="hebo", color=FIELD_COLOR)
        pg.insert_text((MARGEN + 130, y), str(valor)[:60], fontsize=10, color=FIELD_COLOR)
        y += FIELD_LINEA
    return y + 26                            # arranca la primera categoría acá


def _ancho_columna_item(items: list[dict]) -> float:
    max_w = max((pymupdf.get_text_length(str(i.get("item") or ""), fontname="helv", fontsize=9)
                for i in items), default=100)
    return max(130.0, min(280.0, max_w + 80))


def _tabla_categoria(pg, y: float, categoria: str, items: list[dict]) -> float:
    """Una tabla por categoría, como Puntos / Tomas / Iluminación / etc.
    Columna de ítem adaptable al texto más largo; el resto, proporcional."""
    if not items:
        return y
    x0, x1 = MARGEN, ANCHO - MARGEN
    ancho_total = x1 - x0
    col_item = _ancho_columna_item(items)
    resto = ancho_total - col_item
    col_unidad = resto * 0.14
    col_cant = resto * 0.14
    col_precio = resto * 0.32
    col_subtotal = resto - col_unidad - col_cant - col_precio

    xs = [x0, x0 + col_item, x0 + col_item + col_unidad,
         x0 + col_item + col_unidad + col_cant,
         x0 + col_item + col_unidad + col_cant + col_precio, x1]

    pg.insert_text((x0, y), categoria, fontsize=11, fontname="hebo", color=NAVY)
    y += GAP_CAT_A_TABLA

    pg.draw_rect(pymupdf.Rect(x0, y, x1, y + FILA_ALTO), color=None, fill=NAVY, fill_opacity=FONDO_TABLA_OPACIDAD)
    heads = ["Ítem", "Unidad", "Cant.", "P. Unitario", "Subtotal"]
    for i, h in enumerate(heads):
        pg.insert_text((xs[i] + 5, y + FILA_ALTO - 6), h, fontsize=9, fontname="hebo",
                       color=(1, 1, 1))
    y += FILA_ALTO

    for i, it in enumerate(items):
        if y + FILA_ALTO > ALTO - 120:
            return -y                        # negativo: aviso al llamador de que hay que paginar
        fill = ZEBRA if i % 2 == 0 else (1, 1, 1)
        pg.draw_rect(pymupdf.Rect(x0, y, x1, y + FILA_ALTO), color=None, fill=fill,
                    fill_opacity=FONDO_TABLA_OPACIDAD)
        sub = (it.get("precioUnitario") or 0) * (it.get("cantidad") or 0)
        pg.insert_text((xs[0] + 5, y + FILA_ALTO - 6), str(it.get("item") or "")[:60],
                       fontsize=9, color=ITEM_COLOR)
        pg.insert_text((xs[1] + 5, y + FILA_ALTO - 6), str(it.get("unidad") or "u"),
                       fontsize=9, color=ITEM_COLOR)
        for valor, xd in ((f'{it.get("cantidad",0):g}', xs[3] - 5),
                          (_plata(it.get("precioUnitario") or 0), xs[4] - 5),
                          (_plata(sub), xs[5] - 5)):
            w = pymupdf.get_text_length(valor, fontname="helv", fontsize=9)
            pg.insert_text((xd - w, y + FILA_ALTO - 6), valor, fontsize=9, color=ITEM_COLOR)
        y += FILA_ALTO
    return y + GAP_TABLA_A_CAT


def _footer(pg):
    fecha = datetime.now().strftime("%d/%m/%Y")
    texto = (f"Los valores originales de este presupuesto corresponden al día de su emisión "
            f"({fecha}) y podrían sufrir modificaciones por inflación u otras variaciones de "
            "costos hasta el momento de confirmar y ejecutar el trabajo.")
    pg.insert_textbox(pymupdf.Rect(MARGEN, ALTO - 90, ANCHO - MARGEN, ALTO - 40), texto,
                      fontsize=8.5, fontname="helv", color=FOOTER_COLOR, lineheight=1.35)


def _items_por_categoria(items: list[dict]) -> list[tuple[str, list[dict]]]:
    orden = precios_mod.CATEGORIAS
    agrupado: dict[str, list[dict]] = {}
    for it in items:
        cat = it.get("categoria") or "Otros"
        agrupado.setdefault(cat, []).append(it)
    salida = [(cat, agrupado[cat]) for cat in orden if cat in agrupado]
    salida += [(cat, v) for cat, v in agrupado.items() if cat not in orden]
    return salida


def generar(obra: dict) -> bytes:
    cfg = cfgmod.leer_config()
    pres = obra.get("presupuesto") or {}
    tot = pres_mod.totales(pres)
    items = [i for i in (pres.get("items") or []) + (pres.get("extras") or [])
            if not i.get("opcional")]
    diferencia = [i for i in (pres.get("diferencia") or []) if not i.get("opcional")]
    opcionales = [i for i in (pres.get("items") or []) + (pres.get("extras") or [])
                 + (pres.get("diferencia") or []) if i.get("opcional")]

    doc = pymupdf.open()
    pg = doc.new_page(width=ANCHO, height=ALTO)
    _marca_de_agua(pg, cfg)
    y = _encabezado(pg, obra, cfg)

    for cat, its in _items_por_categoria(items):
        y = _tabla_categoria(pg, y, cat, its)
        if y < 0:                            # se quedó sin lugar: pagina y sigue esa categoría
            pg = doc.new_page(width=ANCHO, height=ALTO)
            _marca_de_agua(pg, cfg)
            y = MARGEN + 10
            y = _tabla_categoria(pg, y, cat, its)

    # "Diferencia" -- trabajo que el cliente pidió sumar después de un
    # checkpoint. Va aparte, con su propio encabezado por categoría, para
    # que en el PDF quede clarísimo qué era el alcance original y qué se
    # agregó después (y por qué el total subió).
    if diferencia:
        if y > ALTO - 200:
            pg = doc.new_page(width=ANCHO, height=ALTO)
            _marca_de_agua(pg, cfg)
            y = MARGEN + 10
        for cat, its in _items_por_categoria(diferencia):
            y = _tabla_categoria(pg, y, f"Diferencia — {cat}", its)
            if y < 0:
                pg = doc.new_page(width=ANCHO, height=ALTO)
                _marca_de_agua(pg, cfg)
                y = MARGEN + 10
                y = _tabla_categoria(pg, y, f"Diferencia — {cat}", its)

    if opcionales:
        if y > ALTO - 200:
            pg = doc.new_page(width=ANCHO, height=ALTO)
            _marca_de_agua(pg, cfg)
            y = MARGEN + 10
        for cat, its in _items_por_categoria(opcionales):
            y = _tabla_categoria(pg, y, f"{cat} (opcional, no incluido en el total)", its)

    if y > ALTO - 130:
        pg = doc.new_page(width=ANCHO, height=ALTO)
        _marca_de_agua(pg, cfg)
        y = MARGEN + 20

    pg.insert_text((MARGEN, y + 12), f"Subtotal instalación: {_plata(tot['subtotal'] + tot['extras'])}",
                   fontsize=12, fontname="hebo", color=NAVY)
    y += 12 + 26
    if tot["diferencia"]:
        pg.insert_text((MARGEN, y), f"Diferencia: {_plata(tot['diferencia'])}",
                       fontsize=12, fontname="hebo", color=NAVY)
        y += 26
    pg.insert_text((MARGEN, y), f"TOTAL GENERAL: {_plata(tot['total'])}",
                   fontsize=15, fontname="hebo", color=NAVY)

    for pg2 in doc:
        _footer(pg2)

    salida = io.BytesIO()
    doc.save(salida)
    doc.close()
    return salida.getvalue()
