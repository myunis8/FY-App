"""Parametros ajustables del extractor. Todo en un solo lugar."""
from dataclasses import dataclass, field

# --- Colores (RGB 0..1) ---------------------------------------------------
COLOR_ELECTRICO = (1.0, 0.0, 0.0)      # capa roja = instalacion electrica
TOL_COLOR = 0.12
UMBRAL_NEGRO = 0.75                    # max(r,g,b) < 0.75  -> se considera "muro/arquitectura"

# --- Geometria de simbolos (en puntos PDF, tamano de papel, NO escala) ----
# Los bloques de AutoCAD se plotean a tamano fijo de papel, por eso estos
# valores son estables entre planos.
DIAM_BOCA_MIN, DIAM_BOCA_MAX = 4.6, 7.2      # circulo lleno = boca de luz
DIAM_LLAVE_MIN, DIAM_LLAVE_MAX = 1.8, 3.4    # circulo chico = eje de la llave
SEMI_LARGO_MIN, SEMI_LARGO_MAX = 5.4, 8.4    # semicirculo = tomacorriente
SEMI_ALTO_MIN, SEMI_ALTO_MAX = 2.4, 4.6
GAP_CLUSTER = 1.2                            # pt: distancia para unir primitivas en un simbolo

# --- Escala ---------------------------------------------------------------
ESCALAS_CONOCIDAS = {"1:25": 113.386, "1:50": 56.693, "1:75": 37.795, "1:100": 28.346}
PT_POR_METRO_FALLBACK = 56.693               # 1:50 si no se puede calibrar
TOL_ESCALA_CONOCIDA = 0.02                   # 2% para reportar "1:50" en vez de valor crudo

# --- Ambientes ------------------------------------------------------------
LARGO_MIN_MURO_M = 0.30        # segmento negro solido minimo para considerarlo muro
GAP_MAX_VANO_M = 1.45          # ancho maximo de vano/puerta que se cierra automaticamente
TOL_COLINEAL_M = 0.035         # desalineacion maxima para considerar dos muros colineales
AREA_MIN_AMBIENTE_M2 = 1.0
PX_POR_PT = 3.0                # resolucion de la rasterizacion interna

# --- Asociacion etiqueta <-> simbolo --------------------------------------
DIST_MAX_ETIQUETA_M = 1.60     # radio de busqueda etiqueta -> simbolo
DIST_MAX_LETRA_M = 0.90        # radio de busqueda letra de circuito -> simbolo
DIST_MAX_AMBIENTE_M = 0.45     # tolerancia para pegar un elemento sobre muro a su ambiente

# --- Diccionario semantico (subtipos de caja) ------------------------------
# orden importa: se evalua de arriba hacia abajo
REGLAS_SUBTIPO = [
    ("preinstalacion_aa",  ["preinstalacion a.a", "preinstalacion aa", "preinstalación a.a", "pre instalacion a.a"]),
    ("toma_heladera",      ["heladera"]),
    ("toma_horno",         ["horno"]),
    ("toma_microondas",    ["microondas", "micro ondas"]),
    ("toma_anafe",         ["anafe", "hornalla"]),
    ("toma_lavarropas",    ["lavarropas", "lavaropas"]),
    ("toma_lavavajillas",  ["lavavajillas", "lavavajilla"]),
    ("toma_termotanque",   ["termotanque", "calefon", "calefón"]),
    ("alimentacion_extractor", ["extractor", "campana"]),
    ("alimentacion_estufa",["estufa"]),
    ("alimentacion_bomba", ["bomba"]),
    ("toma_tv",            ["toma tv", "tv", "cable"]),
    ("toma_datos",         ["datos", "internet", "rj45", "telefono", "teléfono"]),
    ("toma_exterior",      ["exterior", "intemperie"]),
    ("toma_doble",         ["toma doble", "toma_doble", "tomacorriente doble", "doble"]),
    ("toma_simple",        ["toma simple", "simple"]),
    ("tablero",            ["tablero", "ts ", "tsg"]),
]

PALABRAS_ETIQUETA = ("toma", "preinstal", "alimenta", "tablero", "estufa",
                     "calefon", "calefón", "termotanque", "extractor", "tv", "caja")

# --- Heuristica de nombre de ambiente -------------------------------------
# (nombre, subtipos que suman, peso)
REGLAS_AMBIENTE = [
    ("cocina",    {"toma_heladera": 3, "toma_horno": 3, "toma_microondas": 3,
                   "alimentacion_extractor": 2, "toma_anafe": 2, "toma_lavavajillas": 1}),
    ("lavadero",  {"toma_lavarropas": 3, "toma_termotanque": 2}),
    ("estar",     {"toma_tv": 2, "alimentacion_estufa": 2}),
    ("dormitorio",{"toma_tv": 1, "preinstalacion_aa": 1}),
]
