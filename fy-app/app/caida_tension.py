"""Caída de tensión en los conductores de una instalación.

Cálculo puro: recibe los datos de cada tramo por parámetro (no lee obra.json
ni conoce el resto de la app) y devuelve un reporte por tramo. Lo usa
`materiales.computar_verificaciones()` para el módulo de Verificaciones
técnicas; más adelante puede alimentar también el DRC de Routeo.

`analizar_tramo()` despacha según el tipo de conductor (campo `tipo_conductor`
o el `ctype`/`kind` del circuito, ver `tipo_conductor_de()`):

  - "terminal":  circuito terminal (IUG, TUG, ...). Caída al peor caso, con
                 I = ampacidad; chequeo "realista" con I = protección del circuito.
  - "acometida": alimentador principal. Peor caso con I = min(ampacidad,
                 corriente del interruptor general del tablero). Si todavía no
                 hay interruptor general, usa la ampacidad y marca "pendiente".
  - "pe":        conductor de protección / PAT. NO lleva caída de tensión: se
                 verifica la relación de sección PE/fase (IEC/IRAM 60364-5-54)
                 y, si se pasa una resistencia de PAT, su límite normativo.

Fórmulas de caída (L = largo de un tramo, ida solamente, no ida y vuelta):

    monofásico / CC   ΔV = 2 · L · I · ρ / S
    trifásico         ΔV = √3 · L · I · ρ / S

con ρ = 0,0175 Ω·mm²/m (cobre a 20 °C) o 0,028 (aluminio). ΔV% = 100 · ΔV / V.
La corriente máxima admisible y el largo máximo para un ΔV% dado son el
despeje directo de esas mismas ecuaciones.

La tabla de ampacidad es una REFERENCIA de diseño (AEA 90364-7-771 / IRAM,
método B1: en cañería sobre pared, 2 conductores cargados, aislación PVC) y se
puede reemplazar por región/instalación sin tocar el resto del módulo.
"""
from __future__ import annotations

# ------------------------------------------------------------------ constantes
RESISTIVIDAD = {"cobre": 0.0175, "aluminio": 0.028}          # Ω·mm²/m a 20 °C
K_SISTEMA = {"monofasico": 2.0, "continua": 2.0, "trifasico": 3 ** 0.5}
TENSION_NOMINAL = {"monofasico": 230.0, "continua": 230.0, "trifasico": 400.0}

# serie de secciones normalizadas IRAM (mm²)
SECCIONES_NORMALIZADAS = [1.0, 1.5, 2.5, 4.0, 6.0, 10.0, 16.0, 25.0,
                          35.0, 50.0, 70.0, 95.0, 120.0]

# ΔV% máximo por categoría de circuito (%). El usuario puede pasar otro.
LIMITE_CAIDA_DEFAULT = {"iluminacion": 3.0, "fuerza_motriz": 5.0, "otros": 5.0}

# Por encima de este largo (m), el "largo máximo admisible" que despeja la
# fórmula pierde utilidad práctica (ninguna instalación razonable llega ahí):
# se informa como no limitante en vez de mostrar un número enorme. Configurable.
LARGO_MAX_REFERENCIA_M = 500.0

# tipo de circuito de la app -> categoría de límite
CATEGORIA_POR_TIPO = {
    "IUG": "iluminacion", "IUE": "iluminacion", "iluminacion": "iluminacion",
    "motor": "fuerza_motriz", "fuerza_motriz": "fuerza_motriz",
    "TUG": "otros", "TUE": "otros", "ACU": "otros", "OCE": "otros",
    "tomas": "otros", "especial": "otros",
}

# Ampacidad Iz (A) por sección y material. AEA 90364-7-771 / IRAM, método B1,
# 2 conductores cargados, aislación PVC. Referencia de diseño, ajustable por
# norma -- la estructura queda lista para NEC / IEC.
AMPACIDAD = {
    "IRAM": {
        "cobre": {1.0: 11, 1.5: 15, 2.5: 21, 4: 28, 6: 36, 10: 50,
                  16: 68, 25: 89, 35: 110, 50: 134, 70: 171, 95: 207},
        "aluminio": {16: 53, 25: 70, 35: 86, 50: 104, 70: 133, 95: 161},
    },
}
NORMA_DEFAULT = "IRAM"


# ------------------------------------------------------------------ helpers
def _num(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _norm_sistema(sistema: str) -> str:
    s = (sistema or "").strip().lower()
    if s in ("tri", "trifasico", "trifásico", "3f", "3", "3x380", "3x400"):
        return "trifasico"
    if s in ("cc", "dc", "continua"):
        return "continua"
    return "monofasico"


def factor_sistema(sistema: str) -> float:
    return K_SISTEMA[_norm_sistema(sistema)]


def resistividad(material: str) -> float:
    return RESISTIVIDAD.get((material or "cobre").strip().lower(), RESISTIVIDAD["cobre"])


def tension_de(sistema: str, tension_v=None) -> float:
    if tension_v:
        return float(tension_v)
    return TENSION_NOMINAL[_norm_sistema(sistema)]


def limite_de(categoria: str, limites: dict | None = None) -> float:
    tabla = {**LIMITE_CAIDA_DEFAULT, **(limites or {})}
    cat = CATEGORIA_POR_TIPO.get((categoria or "").strip())
    if cat is None:
        cat = categoria if categoria in tabla else "otros"
    return float(tabla.get(cat, tabla["otros"]))


def ampacidad(S, material="cobre", norma=NORMA_DEFAULT, correcciones=None):
    """Iz (A) del conductor, o None si esa sección no está tabulada para ese
    material. `correcciones` es un dict de factores multiplicativos (temperatura
    ambiente, agrupamiento de circuitos, ...); en esta versión los llamadores
    pasan None, pero la estructura queda lista para incorporarlos."""
    tabla = AMPACIDAD.get(norma, AMPACIDAD[NORMA_DEFAULT]).get(
        (material or "cobre").strip().lower(), {})
    base = tabla.get(_num(S))
    if base is None:
        return None
    factor = 1.0
    for k in (correcciones or {}).values():
        factor *= float(k)
    return base * factor


def seccion_siguiente(S):
    """Próxima sección normalizada estrictamente mayor a S, o None."""
    s = _num(S)
    for x in SECCIONES_NORMALIZADAS:
        if x > s + 1e-9:
            return x
    return None


def _ceil_normalizada(x: float):
    for v in SECCIONES_NORMALIZADAS:
        if v >= x - 1e-9:
            return v
    return round(x, 2)


# --------------------------------------------------------- tipo de conductor
# Tres tipos, con lógica propia (ver analizar_tramo):
#   - "terminal":  circuito terminal (IUG, TUG, TUE, ...). Regla estándar.
#   - "acometida": alimentador principal medidor->tablero. El peor caso usa
#                  min(ampacidad, corriente del interruptor general).
#   - "pe":        conductor de protección / PAT. NO se le calcula caída de
#                  tensión; se verifica la relación de sección PE/fase y,
#                  si hay dato, la resistencia de puesta a tierra.
TIPO_CONDUCTOR = {
    "ACO": "acometida", "acometida": "acometida", "alimentador": "acometida",
    "PAT": "pe", "tierra": "pe", "pe": "pe", "PE": "pe",
}
UL_CONTACTO = 50.0                       # V, tensión de contacto convencional (locales secos)


def tipo_conductor_de(tramo: dict) -> str:
    for clave in ("tipo_conductor", "ctype", "kind", "categoria"):
        v = (tramo.get(clave) or "").strip()
        if v in TIPO_CONDUCTOR:
            return TIPO_CONDUCTOR[v]
    return "terminal"


def seccion_pe_minima(seccion_fase):
    """Sección mínima del conductor de protección según IEC/IRAM 60364-5-54:
    S_PE = S_fase si S_fase <= 16 mm²; 16 mm² si 16 < S_fase <= 35; S_fase/2
    si S_fase > 35 -- redondeada hacia arriba a sección normalizada."""
    s = _num(seccion_fase)
    if s <= 0:
        return None
    if s <= 16:
        minimo = s
    elif s <= 35:
        minimo = 16.0
    else:
        minimo = s / 2.0
    return _ceil_normalizada(minimo)


def limite_resistencia_pat(esquema="TT", i_dif_a=None, ul=UL_CONTACTO):
    """Límite de resistencia de puesta a tierra (Ω).
    - TT:  U_L / IΔn  (IΔn = corriente diferencial nominal, en A).
    - TN / IT: el criterio es por impedancia de lazo de falla / primera falla,
      no por un valor simple de resistencia -- fuera del alcance de esta versión
      (se devuelve None)."""
    if (esquema or "TT").strip().upper() == "TT" and i_dif_a and i_dif_a > 0:
        return round(ul / float(i_dif_a), 1)
    return None


# ------------------------------------------------------------------ cálculo directo
def caida_tension(*, L, S, I, sistema, material="cobre", tension_v=None, rho=None) -> dict:
    L, S, I = _num(L), _num(S), _num(I)
    k = factor_sistema(sistema)
    rho = resistividad(material) if rho is None else float(rho)
    V = tension_de(sistema, tension_v)
    if S <= 0 or V <= 0:
        return {"deltaV_v": None, "deltaV_pct": None, "tension_v": V,
                "k": round(k, 4), "rho": rho, "motivo": "sección o tensión inválida"}
    dv = k * L * I * rho / S
    return {"deltaV_v": round(dv, 3), "deltaV_pct": round(100 * dv / V, 3),
            "tension_v": V, "k": round(k, 4), "rho": rho}


def corriente_maxima(*, L, S, sistema, tension_v, limite_pct, material="cobre"):
    """I (A) que hace que ΔV% sea exactamente limite_pct. None si no se puede."""
    L, S = _num(L), _num(S)
    k = factor_sistema(sistema)
    rho = resistividad(material)
    V = tension_de(sistema, tension_v)
    if L <= 0 or k <= 0 or rho <= 0:
        return None
    return (limite_pct / 100.0) * V * S / (k * L * rho)


def longitud_maxima(*, S, I, sistema, tension_v, limite_pct, material="cobre"):
    """L (m) que hace que ΔV% sea exactamente limite_pct para esa corriente."""
    S, I = _num(S), _num(I)
    k = factor_sistema(sistema)
    rho = resistividad(material)
    V = tension_de(sistema, tension_v)
    if I <= 0 or k <= 0 or rho <= 0:
        return None
    return (limite_pct / 100.0) * V * S / (k * I * rho)


# ------------------------------------------------------------------ reporte por tramo
def analizar_tramo(tramo: dict, *, limites=None, norma=NORMA_DEFAULT,
                   largo_ref_m=LARGO_MAX_REFERENCIA_M) -> dict:
    """Despacha según el tipo de conductor (terminal / acometida / pe). `tramo`
    (todo opcional salvo S, y L para los que llevan caída):

        {id, tipo_conductor, L, sistema, S, material, tension_v, categoria,
         limite_pct, proteccion_a, corriente_a,      # terminal / acometida
         interruptor_general_a,                      # acometida
         seccion_fase_mm2, esquema_tierra, i_dif_a, resistencia_pat_ohm}  # pe
    """
    tipo = tipo_conductor_de(tramo)
    if tipo == "pe":
        return _analizar_pe(tramo)
    return _analizar_caida(tramo, tipo=tipo, limites=limites, norma=norma,
                           largo_ref_m=largo_ref_m)


def _analizar_caida(tramo: dict, *, tipo="terminal", limites=None, norma=NORMA_DEFAULT,
                    largo_ref_m=LARGO_MAX_REFERENCIA_M) -> dict:
    """Caída de tensión de un conductor terminal o de acometida.

    La corriente máxima admisible que despeja la fórmula se capa a la ampacidad
    real del conductor: si la fórmula da más, el factor limitante es la
    ampacidad, no la caída (el tramo es demasiado corto para que la caída sea
    la restricción activa). Se informa en `factor_limitante`.

    Estados:
      - "excede_caida_tension": a la corriente de referencia de la protección
        (la del circuito para terminal; el interruptor general para acometida),
        ΔV% > límite.
      - "excede_longitud": al peor caso, ΔV% > límite (el largo real supera el
        máximo admisible).
      - "pendiente": acometida sin interruptor general definido todavía.
      - "ok" / "sin_dato".
    """
    L = _num(tramo.get("L"))
    S = _num(tramo.get("S"))
    sistema = _norm_sistema(tramo.get("sistema"))
    material = (tramo.get("material") or "cobre").strip().lower()
    V = tension_de(sistema, tramo.get("tension_v"))
    categoria = tramo.get("categoria") or "otros"
    limite_pct = (float(tramo["limite_pct"]) if tramo.get("limite_pct") not in (None, "")
                  else limite_de(categoria, limites))
    manual_a = tramo.get("corriente_a")
    manual_a = float(manual_a) if manual_a not in (None, "") else None

    iz = ampacidad(S, material, norma)

    # --- corriente de referencia según el tipo de conductor
    pendiente_general = False
    if tipo == "acometida":
        i_gen = tramo.get("interruptor_general_a")
        i_gen = float(i_gen) if i_gen not in (None, "", 0) else None
        i_prot = i_gen                              # la "protección" de la acometida es el general
        if i_gen is not None and iz:
            i_ref = min(iz, i_gen)
        elif i_gen is not None:
            i_ref = i_gen
        else:
            i_ref = iz
            pendiente_general = True
    else:                                            # terminal
        p = tramo.get("proteccion_a")
        i_prot = float(p) if p not in (None, "", 0) else None
        i_ref = iz

    i_peor = manual_a if manual_a is not None else i_ref
    origen = ("manual" if manual_a is not None
              else "ampacidad" if tipo != "acometida"
              else "ampacidad (falta interruptor general)" if pendiente_general
              else "min(ampacidad, interruptor general)")

    entrada = {"L": L, "sistema": sistema, "S": S, "material": material,
               "tension_v": V, "categoria": categoria, "limite_pct": limite_pct,
               "ampacidad_a": round(iz, 1) if iz else None,
               "proteccion_a": round(i_prot, 1) if i_prot else None,
               "tipo_conductor": tipo, "norma": norma}

    peor = None
    if i_peor:
        cc = caida_tension(L=L, S=S, I=i_peor, sistema=sistema, material=material, tension_v=V)
        peor = {"corriente_a": round(i_peor, 1), "origen": origen,
                "deltaV_v": cc["deltaV_v"], "deltaV_pct": cc["deltaV_pct"]}

    proteccion = None
    if i_prot:
        cc = caida_tension(L=L, S=S, I=i_prot, sistema=sistema, material=material, tension_v=V)
        proteccion = {"corriente_a": round(i_prot, 1),
                      "deltaV_v": cc["deltaV_v"], "deltaV_pct": cc["deltaV_pct"]}

    # corriente máxima por caída, capada a la ampacidad real del conductor
    i_max_formula = corriente_maxima(L=L, S=S, sistema=sistema, tension_v=V,
                                     limite_pct=limite_pct, material=material)
    if i_max_formula is None:
        i_max, factor_limitante = None, None
    elif iz is not None and i_max_formula > iz:
        i_max, factor_limitante = round(iz, 1), "ampacidad del conductor"
    else:
        i_max, factor_limitante = round(i_max_formula, 1), "caída de tensión"

    l_max = (longitud_maxima(S=S, I=i_peor, sistema=sistema, tension_v=V,
                             limite_pct=limite_pct, material=material)
             if i_peor else None)
    l_max_no_limitante = l_max is not None and l_max > largo_ref_m

    dv_peor = peor["deltaV_pct"] if peor else None
    dv_prot = proteccion["deltaV_pct"] if proteccion else None
    if dv_peor is None:
        estado = "sin_dato"
    elif dv_prot is not None and dv_prot > limite_pct:
        estado = "excede_caida_tension"
    elif dv_peor > limite_pct:
        estado = "excede_longitud"
    elif pendiente_general:
        estado = "pendiente"
    else:
        estado = "ok"

    margen = round(limite_pct - dv_peor, 3) if dv_peor is not None else None

    # sugerencia: menor sección normalizada > S que cumple, a igual corriente
    sugerencia = None
    if estado in ("excede_caida_tension", "excede_longitud") and i_peor:
        s = S
        while True:
            s = seccion_siguiente(s)
            if s is None:
                break
            cc = caida_tension(L=L, S=s, I=i_peor, sistema=sistema, material=material, tension_v=V)
            if cc["deltaV_pct"] is not None and cc["deltaV_pct"] <= limite_pct:
                sugerencia = {"seccion_mm2": s, "deltaV_pct": cc["deltaV_pct"]}
                break

    return {
        "id": tramo.get("id"),
        "tipo_conductor": tipo,
        "entrada": entrada,
        "peor_caso": peor,
        "proteccion": proteccion,
        "corriente_max_admisible_a": i_max,
        "corriente_max_formula_a": round(i_max_formula, 1) if i_max_formula is not None else None,
        "factor_limitante": factor_limitante,
        "longitud_max_admisible_m": round(l_max, 1) if l_max is not None else None,
        "longitud_max_no_limitante": l_max_no_limitante,
        "largo_referencia_m": largo_ref_m,
        "margen_pct": margen,
        "estado": estado,
        "pendiente_proteccion_general": pendiente_general,
        "sugerencia": sugerencia,
    }


def _analizar_pe(tramo: dict) -> dict:
    """Conductor de protección / PAT: no lleva caída de tensión. Se verifica
    la relación de sección PE/fase (IEC/IRAM 60364-5-54) y, si se pasa una
    resistencia de puesta a tierra medida/estimada, su límite normativo.

    Estados: "cumple" | "no_cumple" | "sin_dato"."""
    s_pe = _num(tramo.get("S"))
    s_fase_in = tramo.get("seccion_fase_mm2")
    s_fase = _num(s_fase_in) if s_fase_in not in (None, "", 0) else None
    s_pe_min = seccion_pe_minima(s_fase) if s_fase else None

    relacion = None
    if s_pe > 0 and s_pe_min is not None:
        relacion = {"seccion_pe_mm2": s_pe, "seccion_fase_mm2": s_fase,
                    "seccion_pe_minima_mm2": s_pe_min,
                    "cumple": s_pe + 1e-9 >= s_pe_min}

    pat = None
    r_med = tramo.get("resistencia_pat_ohm")
    if r_med not in (None, ""):
        esquema = (tramo.get("esquema_tierra") or "TT").strip().upper()
        i_dif = tramo.get("i_dif_a")
        i_dif = float(i_dif) if i_dif not in (None, "", 0) else None
        lim = limite_resistencia_pat(esquema, i_dif)
        pat = {"resistencia_ohm": round(float(r_med), 2), "esquema": esquema,
               "i_dif_a": i_dif, "limite_ohm": lim,
               "cumple": (float(r_med) <= lim) if lim is not None else None}

    if relacion is None:
        estado = "sin_dato"
    else:
        ok_pat = True if (pat is None or pat["cumple"] is None) else pat["cumple"]
        estado = "cumple" if (relacion["cumple"] and ok_pat) else "no_cumple"

    return {
        "id": tramo.get("id"),
        "tipo_conductor": "pe",
        "entrada": {"S": s_pe, "seccion_fase_mm2": s_fase,
                    "esquema_tierra": tramo.get("esquema_tierra") or None},
        "relacion_pe_fase": relacion,
        "puesta_a_tierra": pat,
        "estado": estado,
    }


def analizar(tramos, *, limites=None, norma=NORMA_DEFAULT,
             largo_ref_m=LARGO_MAX_REFERENCIA_M) -> list:
    return [analizar_tramo(t, limites=limites, norma=norma, largo_ref_m=largo_ref_m)
            for t in (tramos or [])]
