"""Armado del presupuesto: cantidades sugeridas, extras, opcionales y totales."""
from __future__ import annotations
import collections
from . import contrato as C, precios as precios_mod, vinculos

# Equivalencias entre lo que lee el extractor y los ítems de la lista de precios.
# El primero que exista en la lista es el que se usa.
EQUIVALENCIAS = [
    ("punto_simple",  ["Punto de luz"]),
    ("punto_combinado", ["Punto combinado"]),
    ("artefacto",     ["Artefacto aislado", "Artefacto no aislado"]),
    ("toma_comun",    ["Tomacorriente común"]),
    ("toma_aa",       ["Toma especial - Aire acondicionado"]),
    ("toma_cocina",   ["Toma especial - Cocina"]),
    ("toma_termo",    ["Toma especial - Termotanque"]),
]

# categorías que no se calculan solas desde el plano (ver precios.CATEGORIAS_APARTE)

SUB_COCINA = ("toma_horno", "toma_microondas", "toma_anafe", "toma_lavavajillas")
SUB_TERMO = ("toma_termotanque", "alimentacion_estufa")


def cantidades(obra: dict) -> dict:
    """Cuenta lo que hay en la obra, agrupado como se cobra."""
    elementos = obra.get("elementos") or []
    teclas = collections.Counter((e.get("letra") or "").upper() for e in elementos
                                 if e.get("tipo") == "llave" and e.get("letra"))
    combinados = sum(1 for v in teclas.values() if v > 1)
    simples = sum(1 for v in teclas.values() if v == 1)

    tomas = collections.Counter()
    for e in elementos:
        if e.get("tipo") not in ("toma", "otros"):
            continue
        s = e.get("subtipo") or ""
        if s == "preinstalacion_aa":
            tomas["toma_aa"] += 1
        elif s in SUB_COCINA:
            tomas["toma_cocina"] += 1
        elif s in SUB_TERMO:
            tomas["toma_termo"] += 1
        else:
            tomas["toma_comun"] += 1

    return {
        "punto_simple": simples,
        "punto_combinado": combinados,
        "artefacto": sum(1 for e in elementos if e.get("tipo") == "artefacto"),
        "toma_comun": tomas["toma_comun"],
        "toma_aa": tomas["toma_aa"],
        "toma_cocina": tomas["toma_cocina"],
        "toma_termo": tomas["toma_termo"],
        "circuitos": len(obra.get("circuitos") or []),
    }


def sugerir_items(obra: dict) -> list[dict]:
    """Arma las líneas del presupuesto con la lista de precios de hoy."""
    lista = precios_mod.leer().get("items") or []
    porNombre = {it["item"]: it for it in lista}
    cant = cantidades(obra)
    salida = []
    for clave, nombres in EQUIVALENCIAS:
        n = cant.get(clave, 0)
        if not n:
            continue
        ref = next((porNombre[x] for x in nombres if x in porNombre), None)
        if ref is None:
            continue
        salida.append({
            "id": f"it_{clave}",
            "precioId": ref["id"],
            "categoria": ref.get("categoria"),
            "item": ref["item"],
            "unidad": ref.get("unidad") or "u",
            "precioUnitario": float(ref.get("precio") or 0),
            "cantidad": n,
            "origen": "computo",
            "clave": clave,
            "opcional": False,
        })
    return salida


def totales(pres: dict) -> dict:
    """Subtotal, extras, descuento y ajuste final.

    Los opcionales se muestran aparte y no entran en el total: son un
    "si querés, sumamos esto".
    """
    def suma(items):
        return sum(float(i.get("precioUnitario") or 0) * float(i.get("cantidad") or 0)
                   for i in items)

    items = [i for i in (pres.get("items") or []) if not i.get("opcional")]
    extras = [i for i in (pres.get("extras") or []) if not i.get("opcional")]
    opcionales = [i for i in (pres.get("items") or []) + (pres.get("extras") or [])
                  if i.get("opcional")]

    sub = suma(items)
    ext = suma(extras)
    bruto = sub + ext

    desc = pres.get("descuento") or {}
    monto_desc = 0.0
    if desc.get("tipo") == "porcentaje":
        monto_desc = bruto * float(desc.get("valor") or 0) / 100
    elif desc.get("tipo") == "monto":
        monto_desc = float(desc.get("valor") or 0)
    monto_desc = min(monto_desc, bruto)

    neto = bruto - monto_desc
    ajuste = pres.get("ajusteFinal") or {}
    final = neto
    monto_ajuste = 0.0
    if ajuste.get("activo") and ajuste.get("valor") not in (None, ""):
        final = float(ajuste["valor"])          # precio final impuesto: redondeo
        monto_ajuste = final - neto

    return {
        "subtotal": round(sub, 2),
        "extras": round(ext, 2),
        "bruto": round(bruto, 2),
        "descuento": round(monto_desc, 2),
        "neto": round(neto, 2),
        "ajuste": round(monto_ajuste, 2),
        "total": round(final, 2),
        "opcionales": round(suma(opcionales), 2),
        "nOpcionales": len(opcionales),
    }


def congelar(obra: dict, usuario: str = "") -> dict:
    """Deja constancia de con qué lista de precios se armó."""
    pres = obra.setdefault("presupuesto", {})
    lista = precios_mod.leer()
    pres["listaPreciosEl"] = lista.get("actualizadoEl")
    pres["congeladoEl"] = C.ahora()
    pres["congeladoPor"] = usuario
    return pres
