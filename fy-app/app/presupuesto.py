"""Armado del presupuesto: cantidades sugeridas, extras, opcionales y totales."""
from __future__ import annotations
import collections
from . import contrato as C, precios as precios_mod, vinculos

# Equivalencias entre lo que lee el extractor y los ítems de la lista de precios.
# El primero que exista en la lista es el que se usa. Si ninguno existe, no se
# omite en silencio: sugerir_items() lo reporta en "avisos" -- un precio que
# falta significa una línea entera ausente del presupuesto, y eso el usuario
# tiene que verlo, no descubrirlo por accidente.
EQUIVALENCIAS = [
    ("punto_simple",  ["Punto de luz"]),
    ("punto_combinado", ["Punto combinado"]),
    ("artefacto",     ["Artefacto aislado", "Artefacto no aislado"]),
    ("toma_comun",    ["Tomacorriente doble (dos bocas en una caja)", "Tomacorriente común"]),
    ("toma_aa",       ["Toma especial - Aire acondicionado"]),
    ("toma_cocina",   ["Toma especial - Cocina"]),
    ("toma_termo",    ["Toma especial - Termotanque"]),
]

# categorías que no se calculan solas desde el plano (ver precios.CATEGORIAS_APARTE)

SUB_COCINA = ("toma_horno", "toma_microondas", "toma_anafe", "toma_lavavajillas", "toma_heladera")
SUB_TERMO = ("toma_termotanque", "alimentacion_estufa", "toma_lavarropas")


def cantidades(obra: dict, extra: bool = False) -> dict:
    """Cuenta lo que hay en la obra, agrupado como se cobra.

    Con extra=True, sólo cuenta los elementos marcados a mano como "fuera
    del presupuesto original" (el checkbox de circuitos.html al agregar una
    caja nueva) -- así ese conteo se puede sumar aparte, como extra a
    cobrar, en vez de mezclarse en silencio con lo que ya se presupuestó al
    principio."""
    elementos = [e for e in (obra.get("elementos") or []) if bool(e.get("extra")) == extra]
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
        "circuitos": len(obra.get("circuitos") or []) if not extra else 0,
    }


def sugerir_items(obra: dict, extra: bool = False) -> tuple[list[dict], list[str]]:
    """Arma las líneas del presupuesto con la lista de precios de hoy.
    Devuelve (items, avisos): si algo que el plano detectó no tiene un ítem
    correspondiente en la lista de precios, esa línea NO se omite en
    silencio -- se informa en avisos, porque significa que falta un renglón
    entero del presupuesto sin que se note a simple vista.

    Con extra=True arma, con la misma lógica, sólo las líneas de los
    elementos marcados como agregado fuera del presupuesto original (ver
    cantidades()) -- para mandarlas a presupuesto.extras en vez de
    presupuesto.items."""
    lista = precios_mod.leer().get("items") or []
    porNombre = {it["item"]: it for it in lista}
    cant = cantidades(obra, extra=extra)
    prefijo = "extra_" if extra else ""
    salida, avisos = [], []
    for clave, nombres in EQUIVALENCIAS:
        n = cant.get(clave, 0)
        if not n:
            continue
        ref = next((porNombre[x] for x in nombres if x in porNombre), None)
        if ref is None:
            avisos.append(f"Se detectaron {n} de \"{clave}\" en el plano, pero no hay ningún ítem "
                          f"llamado {' / '.join(repr(x) for x in nombres)} en la lista de precios "
                          f"-- esta línea falta del presupuesto hasta que lo agregues.")
            continue
        salida.append({
            "id": f"it_{prefijo}{clave}",
            "precioId": ref["id"],
            "categoria": ref.get("categoria"),
            "item": ref["item"],
            "unidad": ref.get("unidad") or "u",
            "precioUnitario": float(ref.get("precio") or 0),
            "cantidad": n,
            "origen": "computo_extra" if extra else "computo",
            "clave": f"{prefijo}{clave}",
            "opcional": False,
        })
    return salida, avisos


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


def eventos_ganancia(obra: dict) -> list[dict]:
    """Ganancia reconocida en cada cambio de pago del seguimiento, en el
    momento en que efectivamente se cobró -- no todo junto al final ni al
    presupuestar. Usa contrato.monto_evento_pago() para cada entrada del
    historial de pago -- la misma cuenta que usa actualizar_seguimiento()
    para saber "cuánto ya se cobró", así que un "volver a pendiente" (o
    cualquier otro cambio) siempre cancela bien lo reconocido antes, sin
    que las dos funciones diverjan.

    Por ahora esta app sólo presupuesta mano de obra (todavía no se carga
    costo de materiales), así que el total del presupuesto -- trabajos y
    extras, que son plata real de la obra igual que los trabajos -- es
    ganancia pura, sin nada que restar. El día que se sume costo de
    material con un margen propio, esta es la única función que hay que
    tocar: acá es donde se define qué es "ganancia" de una obra."""
    seg = obra.get("seguimiento") or {}
    total = totales(obra.get("presupuesto") or {}).get("total") or 0
    eventos = [{"el": h.get("el"), "monto": C.monto_evento_pago(h, total)}
              for h in seg.get("historial") or [] if h.get("campo") == "pago"]

    # La suma tiene que dar exactamente lo que dice el estado de pago actual
    # -- ni un centavo más ni menos. Si una entrada vieja (de antes de que
    # existiera "montoDelta") deja la cuenta sin cerrar, el ajuste se absorbe
    # en el último evento, no se reparte a ciegas entre todos los meses --
    # así un "volver a pendiente" siempre deja la ganancia reconocida en $0,
    # aunque haya datos viejos de por medio.
    verdad = total * ((seg.get("pago") or {}).get("porcentaje") or 0) / 100
    suma = sum(e["monto"] for e in eventos)
    if eventos and abs(suma - verdad) > 0.01:
        eventos[-1]["monto"] += verdad - suma

    return [{"el": e["el"], "monto": round(e["monto"], 2)} for e in eventos if round(e["monto"], 2)]


def congelar(obra: dict, usuario: str = "") -> dict:
    """Deja constancia de con qué lista de precios se armó."""
    pres = obra.setdefault("presupuesto", {})
    lista = precios_mod.leer()
    pres["listaPreciosEl"] = lista.get("actualizadoEl")
    pres["congeladoEl"] = C.ahora()
    pres["congeladoPor"] = usuario
    return pres
