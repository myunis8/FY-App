"""Vínculos entre artefactos y teclas, y avisos derivados.

Se recalcula cada vez que cambian los elementos: al extraer, y también cuando
el usuario agrega o corrige una caja a mano. Una sola implementación, así el
tablero, el revisor y los módulos que vengan después ven siempre lo mismo.

Convención del estudio: la MAYÚSCULA nombra al artefacto y la misma letra en
minúscula nombra la tecla que lo comanda. Un punto es COMBINADO cuando esa
letra aparece en más de una tecla.
"""
from __future__ import annotations
import collections

# avisos que produce el extractor mirando la geometría del plano, y la
# condición que los deja sin efecto cuando el usuario corrige a mano
GEOMETRICOS = ("escala_asumida", "caja_faltante", "toma_sin_leyenda",
               "letra_sin_artefacto", "tecla_sin_simbolo", "llave_sin_letra")


def _sigue_vigente(aviso: dict, elementos: list[dict], plano: dict) -> bool:
    t = aviso.get("tipo")
    if t == "escala_asumida":
        return (plano.get("escala") or {}).get("metodo", "").startswith("fallback")
    if t == "letra_sin_artefacto":
        letra = (aviso.get("letra") or "").upper()
        return not any(e.get("tipo") == "artefacto" and (e.get("nombre") or "").upper() == letra
                       for e in elementos)
    if t == "tecla_sin_simbolo":
        letra = (aviso.get("letra") or "").lower()
        return not any(e.get("tipo") == "llave" and (e.get("letra") or "").lower() == letra
                       and e.get("origen") == "manual" for e in elementos)
    if t == "caja_faltante":
        texto = aviso.get("texto")
        return not any(e.get("origen") == "manual" and e.get("etiquetaTexto") == texto
                       for e in elementos)
    if t == "toma_sin_leyenda":
        sid = aviso.get("simbolo")
        return not any(e.get("id") == sid and e.get("revisadoPorUsuario") for e in elementos)
    return True


def recalcular(obra: dict) -> dict:
    """Actualiza los vínculos de cada elemento y devuelve el bloque validación."""
    elementos = obra.get("elementos") or []
    plano = obra.get("plano") or {}

    # teclas por caja: llave simple, doble o triple
    por_caja = collections.Counter(e.get("cajaId") for e in elementos
                                   if e.get("tipo") == "llave" and e.get("cajaId"))
    for e in elementos:
        if e.get("tipo") == "llave":
            n = por_caja.get(e.get("cajaId"), 1)
            e["teclasEnCaja"] = n
            e["subtipo"] = {1: "llave_1_tecla", 2: "llave_2_teclas",
                            3: "llave_3_teclas"}.get(n, f"llave_{n}_teclas")

    teclas = collections.defaultdict(list)
    artefactos = collections.defaultdict(list)
    for e in elementos:
        if e.get("tipo") == "llave" and e.get("letra"):
            teclas[e["letra"].upper()].append(e["id"])
        elif e.get("tipo") == "artefacto" and e.get("nombre"):
            artefactos[e["nombre"].upper()].append(e["id"])

    avisos = []
    for e in elementos:
        if e.get("tipo") == "artefacto":
            letra = (e.get("nombre") or "").upper()
            if not letra:
                avisos.append({"tipo": "artefacto_sin_letra", "gravedad": "error",
                               "simbolo": e["id"],
                               "detalle": "Este artefacto no tiene letra: no sé qué tecla lo comanda."})
                e["tipoComando"] = "sin_tecla"; e["comandadoPor"] = []
                continue
            ids = teclas.get(letra, [])
            e["comandadoPor"] = ids
            e["interruptor"] = letra.lower()
            n = len(ids)
            e["tipoComando"] = ("simple" if n == 1 else "combinado" if n == 2
                                else f"combinado_{n}_puntos" if n > 2 else "sin_tecla")
            if n == 0:
                avisos.append({"tipo": "artefacto_sin_tecla", "gravedad": "error",
                               "simbolo": e["id"], "letra": letra,
                               "detalle": f"El artefacto {letra} no tiene ninguna tecla {letra.lower()}."})
        elif e.get("tipo") == "llave":
            letra = (e.get("letra") or "").upper()
            ids = artefactos.get(letra, [])
            e["comanda"] = ids
            n = len(teclas.get(letra, []))
            e["tipoComando"] = ("simple" if n == 1 else "combinado" if n == 2
                                else f"combinado_{n}_puntos" if n > 2 else "sin_tecla")
            if not letra:
                avisos.append({"tipo": "tecla_sin_letra", "gravedad": "advertencia",
                               "simbolo": e["id"], "detalle": "Esta tecla no tiene letra."})
            elif not ids:
                avisos.append({"tipo": "tecla_sin_artefacto", "gravedad": "error",
                               "simbolo": e["id"], "letra": letra,
                               "detalle": f"La tecla {letra.lower()} no comanda ningún artefacto."})

    previos = [a for a in (plano.get("avisosExtraccion") or [])
               if _sigue_vigente(a, elementos, plano)]
    todos = previos + avisos + validar_circuitos(obra)
    return {"corridaEl": obra.get("validacion", {}).get("corridaEl", 0),
            "errores": [a for a in todos if a.get("gravedad") == "error"],
            "advertencias": [a for a in todos if a.get("gravedad") != "error"]}


def resumen(obra: dict) -> dict:
    elementos = obra.get("elementos") or []
    c = collections.Counter(e.get("tipo") for e in elementos)
    teclas = {e["letra"].upper() for e in elementos
              if e.get("tipo") == "llave" and e.get("letra")}
    cuenta = collections.Counter((e.get("letra") or "").upper() for e in elementos
                                 if e.get("tipo") == "llave" and e.get("letra"))
    return {"artefactos": c.get("artefacto", 0), "tomas": c.get("toma", 0),
            "teclas": c.get("llave", 0), "otros": c.get("otros", 0),
            "sinReconocer": c.get("desconocido", 0),
            "circuitos": len(teclas),
            "combinados": sum(1 for v in cuenta.values() if v > 1),
            "manuales": sum(1 for e in elementos if e.get("origen") == "manual")}


# --------------------------------------------------------------- circuitos
# familia fina: qué elementos entran en cada tipo de circuito.
# "tomas" sin distinguir hacía que una preinstalación de A.A. -que es un
# tomacorriente como cualquier otro para el extractor- pudiera colarse en un
# TUG al sombrear una zona. Por eso la familia se afina por subtipo, no sólo
# por tipo de elemento.
TIPOS_CIRCUITO = {
    "IUG": {"nombre": "Iluminación de uso general", "familia": "luz", "maxBocas": 15,
            "seccionMin": 1.5, "proteccionMax": 16, "seccion": 1.5, "proteccion": 10},
    "TUG": {"nombre": "Tomacorrientes de uso general", "familia": "tomas_general", "maxBocas": 15,
            "seccionMin": 2.5, "proteccionMax": 20, "seccion": 2.5, "proteccion": 16},
    "IUE": {"nombre": "Iluminación de uso especial", "familia": "luz", "maxBocas": 15,
            "seccionMin": 1.5, "proteccionMax": 16, "seccion": 1.5, "proteccion": 10},
    "TUE": {"nombre": "Tomacorrientes de uso especial", "familia": "tomas_especial", "maxBocas": 12,
            "seccionMin": 2.5, "proteccionMax": 20, "seccion": 2.5, "proteccion": 16},
    "ACU": {"nombre": "Aire acondicionado", "familia": "tomas_aa", "maxBocas": 6,
            "seccionMin": 2.5, "proteccionMax": 25, "seccion": 2.5, "proteccion": 20},
    "OCE": {"nombre": "Otros circuitos específicos", "familia": "tomas_otro", "maxBocas": 12,
            "seccionMin": 2.5, "proteccionMax": 32, "seccion": 2.5, "proteccion": 20},
}

SUBTIPOS_ESPECIALES = ("toma_heladera", "toma_horno", "toma_microondas", "toma_anafe",
                       "toma_lavarropas", "toma_lavavajillas", "toma_termotanque")


def familia_de(e: dict) -> str | None:
    t, sub = e.get("tipo"), e.get("subtipo") or ""
    if t in ("artefacto", "llave"):
        return "luz"
    if t == "otros":
        return "tomas_especial"
    if t == "toma":
        if sub == "preinstalacion_aa":
            return "tomas_aa"
        if sub in SUBTIPOS_ESPECIALES:
            return "tomas_especial"
        return "tomas_general"
    return None


# compatibilidad: además de su familia natural, cada tipo de circuito acepta
# la familia "tomas_otro" (para el que no encaje en ningún casillero), y OCE
# acepta cualquier toma o salida de fuerza como comodín.
COMPATIBLE = {
    "luz": {"luz"},
    "tomas_general": {"tomas_general", "tomas_otro"},
    "tomas_especial": {"tomas_especial", "tomas_aa", "tomas_otro"},
    "tomas_aa": {"tomas_aa", "tomas_otro"},
    "tomas_otro": {"tomas_general", "tomas_especial", "tomas_aa", "tomas_otro"},
}

# secciones y su corriente máxima de protección (cobre, cañería embutida)
MAX_PROTECCION = {1.0: 10, 1.5: 16, 2.5: 20, 4.0: 25, 6.0: 32, 10.0: 50, 16.0: 63}

# qué elementos tienen que estar sí o sí en algún circuito
CONSUMOS = ("artefacto", "toma", "otros")


def validar_circuitos(obra: dict) -> list[dict]:
    elementos = obra.get("elementos") or []
    circuitos = obra.get("circuitos") or []
    porId = {e["id"]: e for e in elementos if e.get("id")}
    avisos = []

    asignaciones = collections.Counter()
    for c in circuitos:
        for eid in c.get("elementos") or []:
            asignaciones[eid] += 1

    faltan = [e for e in elementos
              if e.get("tipo") in CONSUMOS and not asignaciones.get(e["id"])]
    if faltan:
        porTipo = collections.Counter(e["tipo"] for e in faltan)
        detalle = ", ".join(f"{v} {k}" for k, v in porTipo.items())
        avisos.append({"tipo": "elementos_sin_circuito", "gravedad": "error",
                       "cantidad": len(faltan), "ids": [e["id"] for e in faltan],
                       "detalle": f"Quedan {len(faltan)} sin circuito ({detalle})."})

    for eid, n in asignaciones.items():
        if n > 1:
            avisos.append({"tipo": "elemento_repetido", "gravedad": "error",
                           "simbolo": eid,
                           "detalle": f"El elemento {eid} está en {n} circuitos a la vez."})
        elif eid not in porId:
            avisos.append({"tipo": "elemento_inexistente", "gravedad": "advertencia",
                           "simbolo": eid,
                           "detalle": f"Un circuito referencia {eid}, que ya no existe."})

    for c in circuitos:
        nom = c.get("nombre") or c.get("id")
        regla = TIPOS_CIRCUITO.get(c.get("tipo") or "", {})
        ids = [i for i in (c.get("elementos") or []) if i in porId]
        # las teclas no cuentan como boca: se cuentan los consumos
        bocas = [i for i in ids if porId[i].get("tipo") in CONSUMOS]
        if not bocas:
            avisos.append({"tipo": "circuito_vacio", "gravedad": "advertencia",
                           "circuitoId": c.get("id"),
                           "detalle": f"El circuito {nom} no tiene ninguna boca."})
        maxb = regla.get("maxBocas")
        if maxb and len(bocas) > maxb:
            avisos.append({"tipo": "circuito_excedido", "gravedad": "error",
                           "circuitoId": c.get("id"),
                           "detalle": f"{nom} tiene {len(bocas)} bocas y el máximo para "
                                      f"{c.get('tipo')} es {maxb}."})
        sec, prot = c.get("seccionMm2"), c.get("proteccionA")
        if sec and regla.get("seccionMin") and sec < regla["seccionMin"]:
            avisos.append({"tipo": "seccion_insuficiente", "gravedad": "error",
                           "circuitoId": c.get("id"),
                           "detalle": f"{nom}: {sec} mm² es menos que el mínimo de "
                                      f"{regla['seccionMin']} mm² para {c.get('tipo')}."})
        familia = regla.get("familia")
        aceptadas = COMPATIBLE.get(familia, {familia}) if familia else None
        mezclados = [i for i in ids
                     if familia and familia_de(porId[i]) not in aceptadas
                     and familia_de(porId[i]) is not None]
        if mezclados:
            ejemplos = ", ".join(porId[i].get("subtipo") or porId[i].get("tipo") for i in mezclados[:3])
            avisos.append({"tipo": "familia_mezclada", "gravedad": "advertencia",
                           "circuitoId": c.get("id"), "ids": mezclados,
                           "detalle": f"{nom} tiene {len(mezclados)} elementos que no son de "
                                      f"{TIPOS_CIRCUITO.get(c.get('tipo',''),{}).get('nombre','ese tipo')} "
                                      f"({ejemplos}). No es un error -- revisá si es a propósito."})
        if sec and prot and MAX_PROTECCION.get(sec) and prot > MAX_PROTECCION[sec]:
            avisos.append({"tipo": "proteccion_excedida", "gravedad": "error",
                           "circuitoId": c.get("id"),
                           "detalle": f"{nom}: {prot} A es demasiado para {sec} mm² "
                                      f"(máximo {MAX_PROTECCION[sec]} A)."})
    return avisos
