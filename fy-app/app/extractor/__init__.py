"""Extractor: PDF vectorial de AutoCAD -> bloques `plano`, `ambientes` y
`elementos` del contrato obra.json.

No usa OCR ni modelos entrenados: el PDF conserva la geometria exacta y el
texto como texto, asi que todo sale de leer primitivas y aplicar las
convenciones de dibujo del estudio.

Convenciones que interpreta:
  - capa electrica = rojo puro
  - circulo lleno            -> artefacto de luz (con vastago = aplique)
  - barra maciza             -> artefacto lineal
  - semicirculo              -> tomacorriente
  - letra MAYUSCULA          -> nombre del artefacto
  - letra minuscula          -> tecla que lo comanda (una tecla por letra)
  - misma letra en 2 teclas  -> punto combinado
  - circulo sin letra + "alimentación ..." -> salida de fuerza, no es luz
"""
from __future__ import annotations
import collections, math
from typing import Optional

from . import config as C
from .geometria import leer_pdf
from .calibracion import calibrar, punto_referencia
from .simbolos import detectar as detectar_simbolos, escala_simbolos
from .etiquetas import interpretar

CLASES_TOMA = {"tomacorriente"}
CLASES_LUZ = {"boca_luz", "aplique", "luminaria_lineal"}

PREFIJO = {"boca_luz": "A", "aplique": "A", "luminaria_lineal": "A",
           "tomacorriente": "T", "llave": "LL", "otros": "O",
           "desconocido": "X"}

SUBTIPOS_OTROS = ("alimentacion_extractor", "alimentacion_estufa",
                  "alimentacion_bomba", "alimentacion_otros", "toma_termotanque")


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _dist_bbox(p, bbox):
    """Distancia al rectangulo del simbolo, no a su centro.

    Hace falta para los artefactos lineales: la letra se rotula en un extremo
    de la barra.
    """
    x, y = p
    return math.hypot(max(bbox[0] - x, 0, x - bbox[2]),
                      max(bbox[1] - y, 0, y - bbox[3]))


def _id_estable(clase: str, xm: float, ym: float) -> str:
    """Id derivado de la posicion en centimetros respecto del origen.

    Cuando el arquitecto manda el plano corregido y se vuelve a extraer, todo
    lo que no se movio conserva su id, asi que los circuitos y la canalizacion
    siguen enganchados y solo aparecen altas y bajas reales.
    """
    return f"{PREFIJO.get(clase, 'X')}-{round(xm * 100):05d}-{round(ym * 100):05d}"


# --------------------------------------------------------------- asociaciones
def _asignar_etiquetas(simbolos, etiquetas, ppm, avisos):
    ALIM = SUBTIPOS_OTROS
    destinos = [s for s in simbolos
                if s.clase in CLASES_TOMA or s.clase == "desconocido"
                or s.clase in ("boca_luz", "aplique")]
    rmax = C.DIST_MAX_ETIQUETA_M * ppm
    pares = []
    for i, e in enumerate(etiquetas):
        for j, s in enumerate(destinos):
            # un circulo rojo solo puede recibir una leyenda de alimentacion
            if s.clase in ("boca_luz", "aplique") and e.subtipo not in ALIM:
                continue
            d = _dist((e.x, e.y), (s.x, s.y))
            if d <= rmax:
                pares.append((d, i, j))
    pares.sort()
    salida, usadas, usados = {}, set(), set()
    for d, i, j in pares:
        if i in usadas or j in usados:
            continue
        usadas.add(i); usados.add(j)
        salida[destinos[j].id] = (etiquetas[i], round(max(0.5, 1 - d / rmax), 2))
    for i, e in enumerate(etiquetas):
        if i not in usadas:
            # Caso tipico: al plano le falta el simbolo. La leyenda esta, la
            # caja no se dibujo. Se avisa como error y se ofrece colocarla.
            avisos.append({
                "tipo": "caja_faltante", "gravedad": "error",
                "texto": e.texto, "pt": [round(e.x, 1), round(e.y, 1)],
                "sugerencia": {"tipo": "otros" if e.subtipo in SUBTIPOS_OTROS else "toma",
                               "subtipo": e.subtipo, "alturaM": e.altura_m,
                               "etiquetaTexto": e.texto},
                "detalle": f"Hay una leyenda «{e.texto}» sin ninguna caja dibujada cerca. "
                           "Puede ser que falte el símbolo en el plano: colocala vos."})
    for j, s in enumerate(destinos):
        if j not in usados and s.clase in CLASES_TOMA:
            avisos.append({"tipo": "toma_sin_leyenda", "gravedad": "advertencia",
                           "simbolo": s.id, "pt": [round(s.x, 1), round(s.y, 1)],
                           "detalle": "Sin leyenda cerca: la tomé como doble, sin altura."})
    return salida


def _asignar_mayusculas(simbolos, letras, ppm, avisos):
    luces = [s for s in simbolos if s.clase in CLASES_LUZ]
    grupo = [L for L in letras if L.mayuscula]
    rmax = C.DIST_MAX_LETRA_M * ppm
    pares = []
    for i, L in enumerate(grupo):
        for j, s in enumerate(luces):
            d = _dist_bbox((L.x, L.y), s.bbox)
            if d <= rmax:
                pares.append((d, i, j))
    pares.sort()
    salida, usadas, usados = {}, set(), set()
    for d, i, j in pares:
        if i in usadas or j in usados:
            continue
        usadas.add(i); usados.add(j)
        salida[luces[j].id] = grupo[i].letra
    for i, L in enumerate(grupo):
        if i not in usadas:
            avisos.append({"tipo": "letra_sin_artefacto", "gravedad": "error",
                           "letra": L.letra, "pt": [round(L.x, 1), round(L.y, 1)],
                           "detalle": f"La letra {L.letra} no tiene ningún artefacto cerca."})
    return salida


def _modulos_de_llave(simbolos, letras, ppm, avisos):
    """Una tecla por cada letra minuscula rotulada en el plano.

    Una llave de dos teclas se dibuja con un solo eje y dos palancas, asi que
    contar ejes da un numero equivocado. La letra manda; el eje mas cercano
    aporta la posicion y agrupa la caja.
    """
    ejes = [s for s in simbolos if s.clase == "llave"]
    rmax = C.DIST_MAX_LETRA_M * ppm
    modulos = []
    for L in sorted([l for l in letras if not l.mayuscula],
                    key=lambda l: (l.letra, l.y, l.x)):
        cerca = min(ejes, key=lambda s: _dist_bbox((L.x, L.y), s.bbox)) if ejes else None
        d = _dist_bbox((L.x, L.y), cerca.bbox) if cerca else 1e9
        if cerca is None or d > rmax:
            avisos.append({"tipo": "tecla_sin_simbolo", "gravedad": "advertencia",
                           "letra": L.letra, "pt": [round(L.x, 1), round(L.y, 1)],
                           "detalle": f"La tecla {L.letra} no tiene ninguna llave dibujada cerca."})
            modulos.append({"letra": L.letra, "x": L.x, "y": L.y,
                            "caja": None, "confianza": 0.4})
        else:
            modulos.append({"letra": L.letra, "x": cerca.x, "y": cerca.y,
                            "caja": cerca.caja or cerca.id,
                            "confianza": round(max(0.5, 1 - d / rmax), 2)})
    usadas = {m["caja"] for m in modulos}
    for s in ejes:
        if (s.caja or s.id) not in usadas:
            avisos.append({"tipo": "llave_sin_letra", "gravedad": "advertencia",
                           "pt": [round(s.x, 1), round(s.y, 1)],
                           "detalle": "Hay una llave dibujada sin letra que la identifique."})
    return modulos


# ------------------------------------------------------------------ extraccion
def extraer(ruta_pdf: str, pt_por_metro: Optional[float] = None,
            correcciones: Optional[dict] = None) -> dict:
    correcciones = correcciones or {}
    caminos, textos, rect, meta = leer_pdf(str(ruta_pdf))
    avisos: list[dict] = []

    cal = calibrar(textos, pt_por_metro or correcciones.get("escalaPtPorMetro"))
    if cal.metodo.startswith("fallback"):
        avisos.append({"tipo": "escala_asumida", "gravedad": "error",
                       "detalle": "Este plano no tiene cotas acotadas, así que asumí "
                                  "1:50. Si la escala es otra, corregila antes de seguir: "
                                  "todas las medidas dependen de esto."})
    ppm = cal.pt_por_metro
    ref = punto_referencia(caminos, ppm)
    a_m = lambda x, y: ref.a_metros(x, y, ppm)

    D = escala_simbolos(caminos)
    simbolos = detectar_simbolos(caminos, ppm, D)
    etiquetas, letras, _ = interpretar(textos)
    etiq_de = _asignar_etiquetas(simbolos, etiquetas, ppm, avisos)
    letra_de = _asignar_mayusculas(simbolos, letras, ppm, avisos)
    modulos = _modulos_de_llave(simbolos, letras, ppm, avisos)

    # ---- elementos ----
    elementos = []
    vistos = collections.Counter()

    def agregar(clase, x, y, extra):
        xm, ym = a_m(x, y)
        eid = _id_estable(clase, xm, ym)
        vistos[eid] += 1
        if vistos[eid] > 1:                       # dos símbolos en el mismo cm
            eid = f"{eid}b{vistos[eid]}"
        base = {
            "id": eid,
            "posicionM": {"x": round(xm, 3), "y": round(ym, 3)},
            "posicionPdfPt": {"x": round(x, 2), "y": round(y, 2)},
            "revisadoPorUsuario": False,
            "notas": [],
        }
        base.update(extra)
        elementos.append(base)
        return base

    for s in simbolos:
        if s.clase == "llave":
            continue                              # los ejes los reemplazan las teclas
        et, conf_et = etiq_de.get(s.id, (None, 0.0))

        if s.clase in CLASES_TOMA or s.clase == "desconocido":
            subtipo = et.subtipo if et else ("toma_doble" if s.clase in CLASES_TOMA else None)
            e = agregar("tomacorriente" if s.clase in CLASES_TOMA else "desconocido",
                        s.x, s.y, {
                            "tipo": "toma" if s.clase in CLASES_TOMA else "desconocido",
                            "subtipo": subtipo,
                            "alturaM": et.altura_m if et else None,
                            "orientacionDeg": s.orientacion,
                            "etiquetaTexto": et.texto if et else None,
                            "confianza": {"simbolo": s.confianza, "etiqueta": conf_et},
                        })
            if et and et.multiplicidad > 1:
                e["cajasAgrupadas"] = et.multiplicidad
            if not et and s.clase in CLASES_TOMA:
                e["notas"].append("Subtipo asumido: doble, sin altura")
            continue

        if s.clase in CLASES_LUZ:
            letra = letra_de.get(s.id)
            if letra is None and et and et.subtipo in SUBTIPOS_OTROS:
                agregar("otros", s.x, s.y, {
                    "tipo": "otros", "subtipo": et.subtipo,
                    "alturaM": et.altura_m, "etiquetaTexto": et.texto,
                    "confianza": {"simbolo": s.confianza, "etiqueta": conf_et}})
                continue
            e = agregar(s.clase, s.x, s.y, {
                "tipo": "artefacto",
                "subtipo": {"boca_luz": "boca_techo", "aplique": "aplique_pared",
                            "luminaria_lineal": "artefacto_lineal"}[s.clase],
                "nombre": letra,
                "interruptor": letra.lower() if letra else None,
                "orientacionDeg": s.orientacion,
                "confianza": {"simbolo": s.confianza, "etiqueta": conf_et}})
            if s.largo_m:
                e["largoM"] = s.largo_m
            if letra is None:
                e["notas"].append("Sin letra de circuito")

    for m in modulos:
        agregar("llave", m["x"], m["y"], {
            "tipo": "llave", "subtipo": "modulo_llave", "letra": m["letra"],
            "cajaId": m["caja"], "confianza": {"simbolo": m["confianza"], "etiqueta": 1.0}})

    return {
        "escala": {"ptPorMetro": cal.pt_por_metro, "nominal": cal.escala_nominal,
                   "metodo": cal.metodo, "confianza": cal.confianza,
                   "muestras": cal.n_muestras, "diametroSimboloPt": D},
        "referencia": {
            "descripcion": ref.descripcion,
            "origenPdfPt": {"x": ref.x_pdf_pt, "y": ref.y_pdf_pt},
            "envolventeMurosPdfPt": list(ref.envolvente_pdf_pt),
            "envolventeMurosM": list(ref.envolvente_m),
            "unidad": "m", "ejeX": "derecha", "ejeY": "arriba"},
        "paginaPt": {"ancho": round(rect[2], 1), "alto": round(rect[3], 1)},
        "elementos": elementos,
        "avisos": avisos,
    }
