"""Informe PDF de una automatización (ver automatizaciones.py): supuestos,
funcionamiento, esquemas, lista de componentes, cables, notas y pruebas.

Todo sale de `automatizaciones.resultado()` -- el mismo cálculo que ve la
pantalla --, y los esquemas son los mismos SVG, llevados al PDF tal cual.
"""
from __future__ import annotations
import pymupdf
from . import automatizaciones as A

ANCHO, ALTO = 595, 842
M = 40
NAVY = (0x16 / 255, 0x28 / 255, 0x3f / 255)
AZUL = (0x0f / 255, 0x5c / 255, 0x9a / 255)
GRIS = (0x5b / 255, 0x6b / 255, 0x7a / 255)
TEXTO = (0x22 / 255, 0x2c / 255, 0x38 / 255)
LINEA = (0xd5 / 255, 0xdb / 255, 0xe2 / 255)
ZEBRA = (0xf1 / 255, 0xf4 / 255, 0xf7 / 255)
CAJA = (0xee / 255, 0xf4 / 255, 0xf9 / 255)
AMBAR = (0xfd / 255, 0xf1 / 255, 0xdc / 255)
ROJO = (0xb3 / 255, 0x2f / 255, 0x2f / 255)
OBLIG = (0xb3 / 255, 0x2f / 255, 0x2f / 255)
RECOM = (0x0f / 255, 0x5c / 255, 0x9a / 255)
OPC = (0xb8 / 255, 0x79 / 255, 0x1a / 255)


_FUENTES = {}


def _len(texto: str, fontname: str, fontsize: float) -> float:
    """Ancho real del texto. pymupdf.get_text_length mide mal las letras con
    acento (las toma como más angostas), y eso hacía que el texto en negrita
    pisara al que sigue; Font.text_length mide bien."""
    f = _FUENTES.get(fontname)
    if f is None:
        f = _FUENTES[fontname] = pymupdf.Font(fontname)
    return f.text_length(texto, fontsize=fontsize)


def _wrap(texto: str, fs: float, ancho: float, fname="helv") -> list[str]:
    lineas = []
    for parr in str(texto).split("\n"):
        actual = ""
        for palabra in parr.split():
            prueba = (actual + " " + palabra).strip()
            if not actual or _len(prueba, fname, fs) <= ancho:
                actual = prueba
            else:
                lineas.append(actual)
                actual = palabra
        lineas.append(actual)
    return lineas or [""]


class _Doc:
    def __init__(self, titulo_pie: str):
        self.doc = pymupdf.open()
        self.pie = titulo_pie
        self.pg = None
        self.y = 0
        self._nueva()

    def _nueva(self):
        self.pg = self.doc.new_page(width=ANCHO, height=ALTO)
        n = len(self.doc)
        self.pg.draw_line((M, ALTO - 36), (ANCHO - M, ALTO - 36), color=LINEA, width=0.6)
        self.pg.insert_text((M, ALTO - 24), self.pie, fontsize=7, fontname="helv", color=GRIS)
        w = _len(f"Página {n}", "helv", 7)
        self.pg.insert_text((ANCHO - M - w, ALTO - 24), f"Página {n}", fontsize=7, fontname="helv", color=GRIS)
        self.y = M + 6

    def hay(self, alto: float):
        if self.y + alto > ALTO - 48:
            self._nueva()

    def titulo(self, texto: str, grande=False):
        fs = 20 if grande else 12.5
        self.hay(fs + 20)
        self.pg.insert_text((M, self.y + fs), texto, fontsize=fs, fontname="hebo", color=NAVY if grande else AZUL)
        self.y += fs + (10 if grande else 8)

    def subtitulo(self, texto: str):
        self.hay(18)
        self.pg.insert_text((M, self.y + 9), texto, fontsize=9.5, fontname="hebo", color=TEXTO)
        self.y += 15

    def parrafo(self, texto: str, fs=9, color=TEXTO, indent=0, negrita_ini: str | None = None, espacio=4):
        ancho = ANCHO - 2 * M - indent
        pre = (negrita_ini + " ") if negrita_ini else ""
        lineas = _wrap(pre + texto, fs, ancho)
        for i, l in enumerate(lineas):
            self.hay(fs * 1.35)
            x = M + indent
            if i == 0 and negrita_ini:
                w = _len(negrita_ini + " ", "hebo", fs)
                self.pg.insert_text((x, self.y + fs), negrita_ini, fontsize=fs, fontname="hebo", color=color)
                self.pg.insert_text((x + w + 1.2, self.y + fs), l[len(negrita_ini) + 1:], fontsize=fs, fontname="helv", color=color)
            else:
                self.pg.insert_text((x, self.y + fs), l, fontsize=fs, fontname="helv", color=color)
            self.y += fs * 1.35
        self.y += espacio

    def vineta(self, texto: str, negrita: str | None = None, fs=9):
        ancho = ANCHO - 2 * M - 14
        pre = (negrita + " ") if negrita else ""
        lineas = _wrap(pre + texto, fs, ancho)
        for i, l in enumerate(lineas):
            self.hay(fs * 1.35)
            if i == 0:
                self.pg.draw_circle((M + 4, self.y + fs * 0.62), 1.4, color=None, fill=TEXTO)
                if negrita:
                    w = _len(negrita + " ", "hebo", fs)
                    self.pg.insert_text((M + 14, self.y + fs), negrita, fontsize=fs, fontname="hebo", color=TEXTO)
                    self.pg.insert_text((M + 14 + w + 1.2, self.y + fs), l[len(negrita) + 1:], fontsize=fs, fontname="helv", color=TEXTO)
                else:
                    self.pg.insert_text((M + 14, self.y + fs), l, fontsize=fs, fontname="helv", color=TEXTO)
            else:
                self.pg.insert_text((M + 14, self.y + fs), l, fontsize=fs, fontname="helv", color=TEXTO)
            self.y += fs * 1.35
        self.y += 2.5

    def caja(self, lineas: list[tuple[str, str]], fondo=CAJA, borde=AZUL, fs=8.2):
        """Recuadro con renglones (negrita opcional)."""
        ancho = ANCHO - 2 * M - 16
        bloques = []
        alto = 12
        for neg, txt in lineas:
            ls = _wrap((neg + " " if neg else "") + txt, fs, ancho)
            bloques.append((neg, ls))
            alto += len(ls) * fs * 1.35 + 3
        self.hay(alto + 6)
        r = pymupdf.Rect(M, self.y, ANCHO - M, self.y + alto)
        self.pg.draw_rect(r, color=borde, fill=fondo, width=0.8)
        y = self.y + 8
        for neg, ls in bloques:
            for i, l in enumerate(ls):
                if i == 0 and neg:
                    w = _len(neg + " ", "hebo", fs)
                    self.pg.insert_text((M + 8, y + fs), neg, fontsize=fs, fontname="hebo", color=TEXTO)
                    self.pg.insert_text((M + 8 + w + 1.2, y + fs), l[len(neg) + 1:], fontsize=fs, fontname="helv", color=TEXTO)
                else:
                    self.pg.insert_text((M + 8, y + fs), l, fontsize=fs, fontname="helv", color=TEXTO)
                y += fs * 1.35
            y += 3
        self.y += alto + 8

    def tabla(self, cols: list[tuple[str, float]], filas: list[list[str]], fs=7.8, colores_col: dict | None = None):
        """cols = [(encabezado, fracción del ancho)]; el alto de cada fila sale del texto envuelto."""
        total = ANCHO - 2 * M
        anchos = [total * f for _, f in cols]

        def encabezado():
            self.hay(20)
            self.pg.draw_rect(pymupdf.Rect(M, self.y, ANCHO - M, self.y + 17), color=None, fill=AZUL)
            x = M
            for (t, _), w in zip(cols, anchos):
                self.pg.insert_text((x + 5, self.y + 11.5), t, fontsize=7.8, fontname="hebo", color=(1, 1, 1))
                x += w
            self.y += 17

        encabezado()
        for n, fila in enumerate(filas):
            celdas = [_wrap(c, fs, w - 10, "hebo" if i == 0 else "helv") for i, (c, w) in enumerate(zip(fila, anchos))]
            alto = max(len(c) for c in celdas) * fs * 1.3 + 8
            if self.y + alto > ALTO - 48:
                self._nueva(); encabezado()
            if n % 2:
                self.pg.draw_rect(pymupdf.Rect(M, self.y, ANCHO - M, self.y + alto), color=None, fill=ZEBRA)
            x = M
            for i, (c, w) in enumerate(zip(celdas, anchos)):
                col = (colores_col or {}).get(i, TEXTO)
                for k, l in enumerate(c):
                    cc = col
                    if callable(col):
                        cc = col(fila[i])
                    self.pg.insert_text((x + 5, self.y + 4 + fs + k * fs * 1.3), l, fontsize=fs,
                                        fontname="hebo" if i == 0 or callable(col) else "helv", color=cc)
                x += w
            self.pg.draw_line((M, self.y + alto), (ANCHO - M, self.y + alto), color=LINEA, width=0.4)
            self.y += alto
        self.y += 8

    def svg(self, svg: str, titulo: str | None = None):
        src = pymupdf.open("svg", svg.encode("utf-8"))
        pdf = pymupdf.open("pdf", src.convert_to_pdf())
        w0, h0 = pdf[0].rect.width, pdf[0].rect.height
        ancho = ANCHO - 2 * M
        alto = ancho * h0 / w0
        self.hay(alto + (30 if titulo else 12))     # título y dibujo juntos, nunca el título solo
        if titulo:
            self.subtitulo(titulo)
        self.pg.show_pdf_page(pymupdf.Rect(M, self.y, M + ancho, self.y + alto), pdf, 0)
        self.pg.draw_rect(pymupdf.Rect(M, self.y, M + ancho, self.y + alto), color=LINEA, fill=None, width=0.5)
        self.y += alto + 10


def _color_tipo(v: str):
    return {"Obligatorio": OBLIG, "Recomendado": RECOM, "Opcional": OPC}.get(v, TEXTO)


def generar(auto: dict, obra: dict | None = None) -> bytes:
    r = A.resultado(auto)
    if "error" in r:
        raise ValueError(r["error"])
    nombre_obra = ((obra or {}).get("obra") or {}).get("nombre") or ""
    pie = f"{r['nombre']} · {r['titulo']}" + (f" · {nombre_obra}" if nombre_obra else "")
    d = _Doc(pie)
    p = r["params"]

    d.titulo(r["titulo"], grande=True)
    d.parrafo(f"{r['nombre']} · {r['sistema']} · comando en {p['tensionComando']} " +
              ("VAC" if p["tensionComando"] == "24" else "V") +
              (" · selector Manual / 0 / Automático" if p["selector"] else " · sólo automático"),
              9.5, GRIS, espacio=8)

    d.caja([("Supuestos de este informe", "")] + [("", s) for s in r["supuestos"]])

    if r["avisos"]:
        for a in r["avisos"]:
            if a["gravedad"] == "info":
                continue
            d.caja([("Atención:", a["texto"])], fondo=AMBAR, borde=OPC)

    d.titulo("1. Cómo funciona")
    for f in r["funcionamiento"]:
        d.vineta(f["d"], f["t"] + ":")

    d.titulo("2. Circuito esquemático")
    d.svg(r["svg"]["potencia"], "2.1 Circuito de potencia (220 V)")
    d.parrafo("La alimentación pasa por la termomagnética y el diferencial" +
              ("; de ahí se toma la alimentación del transformador de comando y sigue " if p["tensionComando"] == "24"
               else "; de ahí se toma el comando y sigue ") +
              "al contactor, a la protección del motor y a la bomba.", 8, GRIS)
    d.svg(r["svg"]["comando"], "2.2 Circuito de comando")
    d.subtitulo("Notas de conexión")
    for n in r["notas"]:
        d.vineta(n)

    d.titulo("3. Lista de componentes")
    d.parrafo("Especificaciones técnicas; sin marcas ni precios (se arman con la lista de precios de la obra). "
              "Las referencias de catálogo son sugerencias a verificar. Cada ítem indica si responde a un requisito "
              "normativo, a una buena práctica o a una decisión de diseño.", 8, GRIS)
    d.tabla([("Ref.", 0.08), ("Componente", 0.2), ("Especificación", 0.4), ("Tipo", 0.11), ("Criterio", 0.21)],
            [[c["ref"] or "-" if c["cantidad"] == 1 else f'{c["ref"]} (x{c["cantidad"]})', c["nombre"],
              c["especificacion"], c["tipo"], c["criterio"]] for c in r["componentes"]],
            colores_col={3: _color_tipo})

    d.titulo("4. Cables y caída de tensión")
    d.parrafo("Caída de tensión: dV = 2 x L x I x rho / S, con cobre rho = 0,018 ohm·mm²/m (L largo, I corriente, S sección).", 8, GRIS)
    d.tabla([("Tramo", 0.27), ("Cable", 0.32), ("Largo", 0.1), ("Resultado", 0.31)],
            [[c["tramo"], c["cable"], c["largo"], c["resultado"]] for c in r["cables"]])

    if r["conexionPotencia"]:
        d.titulo("5. Conexión de potencia con bomba monofásica")
        d.tabla([("Desde", 0.28), ("Hasta", 0.32), ("Qué es", 0.4)], r["conexionPotencia"])

    d.titulo(("6" if r["conexionPotencia"] else "5") + ". Prueba antes de dejarlo en servicio")
    for t in r["pruebas"]:
        d.vineta(t)
    d.caja([("", "La conexión a la red y la verificación final conviene que las haga un electricista matriculado. "
             "Este informe es una guía de diseño basada en los datos cargados; las tablas de selección son "
             "simplificaciones de diseño y no reemplazan el proyecto ni la normativa vigente.")],
           fondo=AMBAR, borde=OPC)
    return d.doc.tobytes(garbage=3, deflate=True)
