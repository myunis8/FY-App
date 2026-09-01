"""Caída de tensión en los conductores de una instalación.

Cálculo puro: recibe los datos de cada tramo por parámetro (no lee obra.json
ni conoce el resto de la app) y devuelve un reporte por tramo. Lo usa
`materiales.computar_verificaciones()` para el módulo de Verificaciones
técnicas; más adelante puede alimentar también el DRC de Routeo.

Fórmulas (L = largo de un tramo, ida solamente, no ida y vuelta):

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
def analizar_tramo(tramo: dict, *, limites=None, norma=NORMA_DEFAULT) -> dict:
    """Reporte de caída de tensión de un tramo. `tramo` (todo opcional salvo L y S):

        {id, L, sistema, S, material, tension_v, categoria, limite_pct,
         proteccion_a, corriente_a}

    Estados:
      - "excede_caida_tension": con I = corriente de la protección, ΔV% > límite.
      - "excede_longitud":      con I = ampacidad del conductor, ΔV% > límite
                                (equivale a que el largo real supere el máximo).
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
    prot_a = tramo.get("proteccion_a")
    prot_a = float(prot_a) if prot_a not in (None, "", 0) else None
    manual_a = tramo.get("corriente_a")
    manual_a = float(manual_a) if manual_a not in (None, "") else None

    iz = ampacidad(S, material, norma)

    entrada = {"L": L, "sistema": sistema, "S": S, "material": material,
               "tension_v": V, "categoria": categoria, "limite_pct": limite_pct,
               "ampacidad_a": round(iz, 1) if iz else None,
               "proteccion_a": prot_a, "norma": norma}

    # peor caso: I = ampacidad del conductor (o corriente manual si se forzó)
    i_peor = manual_a if manual_a is not None else iz
    peor = None
    if i_peor:
        cc = caida_tension(L=L, S=S, I=i_peor, sistema=sistema, material=material, tension_v=V)
        peor = {"corriente_a": round(i_peor, 1),
                "origen": "manual" if manual_a is not None else "ampacidad",
                "deltaV_v": cc["deltaV_v"], "deltaV_pct": cc["deltaV_pct"]}

    # a la corriente de la protección: chequeo "realista"
    proteccion = None
    if prot_a:
        cc = caida_tension(L=L, S=S, I=prot_a, sistema=sistema, material=material, tension_v=V)
        proteccion = {"corriente_a": round(prot_a, 1),
                      "deltaV_v": cc["deltaV_v"], "deltaV_pct": cc["deltaV_pct"]}

    i_max = corriente_maxima(L=L, S=S, sistema=sistema, tension_v=V,
                             limite_pct=limite_pct, material=material)
    l_max = (longitud_maxima(S=S, I=i_peor, sistema=sistema, tension_v=V,
                             limite_pct=limite_pct, material=material)
             if i_peor else None)

    dv_peor = peor["deltaV_pct"] if peor else None
    dv_prot = proteccion["deltaV_pct"] if proteccion else None
    if dv_peor is None:
        estado = "sin_dato"
    elif dv_prot is not None and dv_prot > limite_pct:
        estado = "excede_caida_tension"
    elif dv_peor > limite_pct:
        estado = "excede_longitud"
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
        "entrada": entrada,
        "peor_caso": peor,
        "proteccion": proteccion,
        "corriente_max_admisible_a": round(i_max, 1) if i_max is not None else None,
        "longitud_max_admisible_m": round(l_max, 1) if l_max is not None else None,
        "margen_pct": margen,
        "estado": estado,
        "sugerencia": sugerencia,
    }


def analizar(tramos, *, limites=None, norma=NORMA_DEFAULT) -> list:
    return [analizar_tramo(t, limites=limites, norma=norma) for t in (tramos or [])]
