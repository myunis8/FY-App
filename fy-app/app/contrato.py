"""Contrato obra.json v1: creacion, migracion y proyeccion a resumen."""
from __future__ import annotations
import time, uuid

CONTRATO = 1

BLOQUES = ("plano", "ambientes", "elementos", "circuitos", "tableros",
           "canalizacion", "computo", "presupuesto", "seguimiento", "validacion")

ESTADOS = {
    "preliminar": "Presupuesto preliminar",
    "aprobado": "Presupuesto aprobado",
    "en_curso": "En curso",
    "realizado": "Realizado",
}
ESTADOS_PAGO = {"pendiente": "Pendiente", "parcial": "Pago parcial", "pagado": "Pagado"}


def nuevo_id() -> str:
    return "obra_" + uuid.uuid4().hex[:8]


def ahora() -> int:
    return int(time.time() * 1000)


def obra_vacia(nombre: str = "", cliente: str = "", usuario: str = "") -> dict:
    t = ahora()
    return {
        "contrato": CONTRATO,
        "obra": {"id": nuevo_id(), "nombre": nombre or "Obra sin nombre",
                 "cliente": cliente, "direccion": "", "tipoInstalacion": "Monofásica",
                 "sinPlano": False,
                 "creadoEl": t, "actualizadoEl": t, "actualizadoPor": usuario},
        "plano": None,
        "ambientes": [], "elementos": [], "circuitos": [], "tableros": [],
        "canalizacion": None,   # el proyecto tal cual lo produce buildProjectData() de Canaliza
        "computo": None,
        "materiales": {"extras": [], "cables": []},
        "presupuesto": {"items": [], "descuento": None, "ajusteFinal": None,
                        "fechaEmision": None},
        "seguimiento": {"estado": "preliminar",
                        "pago": {"estado": "pendiente", "porcentaje": 0},
                        "historial": []},
        "validacion": {"corridaEl": 0, "errores": [], "advertencias": []},
        "historial": [],
    }


def normalizar(obra: dict) -> dict:
    """Completa lo que falte sin tocar lo que ya existe.

    Regla de oro del contrato: no se borra ninguna clave desconocida, para que
    una version vieja de un modulo no destruya datos de una version nueva.
    """
    base = obra_vacia()
    for k, v in base.items():
        obra.setdefault(k, v)
    obra["contrato"] = CONTRATO
    obra["obra"].setdefault("id", nuevo_id())
    _consolidar_descripcion_dispositivos(obra)
    return obra


def _consolidar_descripcion_dispositivos(obra: dict) -> None:
    """Un dispositivo de Tablero atado a un circuito (circuitoId) ya no tiene
    descripción propia: usa circuito.notas, la misma que se edita en
    Circuitos y en el panel de Tablero, para que las dos pantallas siempre
    muestren y guarden lo mismo (antes se podían desincronizar: Tablero tenía
    su propio `descripcion` por dispositivo que nunca se mostraba junto a la
    del circuito). Si un dispositivo viejo ya tenía su propia `descripcion`
    de antes de este cambio, se migra a circuito.notas en vez de perderse
    (sin pisar una que el usuario ya haya cargado ahí)."""
    circuitos_por_id = {c["id"]: c for c in obra.get("circuitos") or [] if c.get("id")}
    for t in obra.get("tableros") or []:
        for d in t.get("dispositivos") or []:
            cid = d.get("circuitoId")
            if not cid or not d.get("descripcion"):
                continue
            circ = circuitos_por_id.get(cid)
            if not circ:
                continue
            if not circ.get("notas"):
                circ["notas"] = d["descripcion"]
            d["descripcion"] = None


def monto_evento_pago(h: dict, total: float) -> float:
    """Cuánto reconoce de ganancia una entrada del historial de pago.

    Si tiene "montoDelta" (todo lo grabado desde que existe ese campo), se
    usa tal cual -- es el monto exacto que se congeló en su momento. Una
    entrada vieja, de antes de que existiera montoDelta, se estima con el
    % de aquel momento contra el total de ahora, como aproximación.

    Esta es la ÚNICA función que debe usarse para eso -- presupuesto.py
    (para mostrar la ganancia reconocida) y esta misma actualizar_seguimiento
    (para saber cuánto ya se cobró antes de un cambio nuevo) tienen que
    coincidir siempre, o un "volver a pendiente" no cancela bien lo que
    una entrada vieja sin montoDelta venía sumando."""
    if "montoDelta" in h:
        return h["montoDelta"]
    antes = (h.get("de") or {}).get("porcentaje") or 0
    despues = (h.get("a") or {}).get("porcentaje") or 0
    return total * (despues - antes) / 100


def actualizar_seguimiento(obra: dict, estado: str | None = None, pago_estado: str | None = None,
                            pago_porcentaje=None, pago_monto=None, usuario: str = "") -> dict:
    """Cambia estado y/o pago de la obra y deja un registro en el
    historial de quién y cuándo lo cambió (el campo ya estaba en el
    esquema desde el principio, pero nada lo llenaba todavía). Si un campo
    no viene, queda como estaba -- no hay valores por adivinar.

    El porcentaje de pago sigue al estado: "pendiente" siempre es 0%,
    "pagado" siempre es 100%, y sólo "parcial" admite un valor propio --
    por porcentaje o directamente por un monto en pesos (no siempre se
    sabe qué % representa lo que se cobró). Si no llega ninguno de los
    dos, sigue con lo que ya había, o 50% la primera vez.

    Cada cambio de pago queda con "montoDelta": lo que se reconoce de
    ganancia en ESE momento, calculado contra el total del presupuesto
    de ahora y descontando lo ya reconocido en cambios anteriores. Así,
    si después se agrega un extra o se toca el descuento, lo que ya se
    había cobrado no se recalcula para atrás -- y cuando finalmente se
    marca "pagado", lo que falta para llegar al total de ese momento se
    reconoce de una, así que el total siempre cierra bien aunque el
    presupuesto haya cambiado en el medio."""
    seg = obra.setdefault("seguimiento", {})
    seg.setdefault("estado", "preliminar")
    seg.setdefault("pago", {"estado": "pendiente", "porcentaje": 0})
    seg.setdefault("historial", [])
    t = ahora()

    if estado is not None and estado in ESTADOS and estado != seg["estado"]:
        seg["historial"].append({"el": t, "por": usuario or "", "campo": "estado",
                                 "de": seg["estado"], "a": estado})
        seg["estado"] = estado

    pago_estado_valido = pago_estado is not None and pago_estado in ESTADOS_PAGO
    toca_parcial = ((pago_porcentaje is not None or pago_monto is not None)
                    and seg["pago"].get("estado") == "parcial")
    if pago_estado_valido or toca_parcial:
        total = total_presupuesto(obra)
        ya_cobrado = sum(monto_evento_pago(h, total) for h in seg["historial"] if h.get("campo") == "pago")
        estado_nuevo = pago_estado if pago_estado_valido else seg["pago"]["estado"]

        if estado_nuevo == "pendiente":
            monto = 0.0
        elif estado_nuevo == "pagado":
            monto = total
        elif pago_monto is not None:
            monto = max(0.0, min(float(pago_monto), total))
        elif pago_porcentaje is not None:
            monto = total * max(0, min(100, int(pago_porcentaje))) / 100
        else:
            monto = ya_cobrado or total * 0.5

        pct = round(monto / total * 100) if total else 0
        if estado_nuevo == "parcial":
            pct = max(1, min(99, pct))

        anterior, nuevo = dict(seg["pago"]), {"estado": estado_nuevo, "porcentaje": pct}
        if nuevo != anterior:
            seg["historial"].append({"el": t, "por": usuario or "", "campo": "pago",
                                     "de": anterior, "a": nuevo,
                                     "montoDelta": round(monto - ya_cobrado, 2)})
            seg["pago"] = nuevo
    return seg


def total_presupuesto(obra: dict) -> float:
    """Monto final del presupuesto: trabajos + extras, menos descuento, con
    el ajuste final si está activo -- los extras son plata real de la obra
    tanto como los trabajos. Misma fórmula que presupuesto.totales()["total"]
    (no se puede importar ese módulo acá: presupuesto.py ya importa a este,
    sería circular) -- si se retoca una, retocar la otra."""
    pres = obra.get("presupuesto") or {}

    def suma(items):
        return sum((it.get("precioUnitario") or 0) * (it.get("cantidad") or 0)
                  for it in items if not it.get("opcional"))

    bruto = suma(pres.get("items") or []) + suma(pres.get("extras") or [])
    desc = pres.get("descuento") or {}
    monto_desc = 0.0
    if desc.get("tipo") == "porcentaje":
        monto_desc = bruto * float(desc.get("valor") or 0) / 100
    elif desc.get("tipo") == "monto":
        monto_desc = float(desc.get("valor") or 0)
    monto_desc = min(monto_desc, bruto)
    neto = bruto - monto_desc

    ajuste = pres.get("ajusteFinal") or {}
    if ajuste.get("activo") and ajuste.get("valor") not in (None, ""):
        return float(ajuste["valor"])
    return neto


def progreso(obra: dict) -> dict:
    canal = obra.get("canalizacion") or {}
    sin_plano = bool((obra.get("obra") or {}).get("sinPlano"))
    return {
        # una obra sin plano (reparación, trabajo chico) no queda trabada en
        # el primer paso: los elementos se cargan a mano
        "extraido": bool(obra.get("elementos")) or sin_plano,
        "sinPlano": sin_plano,
        "circuitosAsignados": bool(obra.get("circuitos")),
        "canalizado": bool(canal.get("runs")),
        "presupuestado": bool((obra.get("presupuesto") or {}).get("items")),
    }


def resumen(obra: dict) -> dict:
    """Proyeccion liviana para el tablero. Siempre derivada, nunca editada."""
    o = obra.get("obra") or {}
    seg = obra.get("seguimiento") or {}
    val = obra.get("validacion") or {}
    plano = obra.get("plano") or {}
    hist = obra.get("historial") or []
    return {
        "id": o.get("id"),
        "nombre": o.get("nombre") or "Obra sin nombre",
        "cliente": o.get("cliente") or "",
        "estado": seg.get("estado") or "preliminar",
        "pago": seg.get("pago") or {"estado": "pendiente", "porcentaje": 0},
        "total": round(total_presupuesto(obra), 2),
        "actualizadoEl": o.get("actualizadoEl") or 0,
        "actualizadoPor": o.get("actualizadoPor") or "",
        "sinPlano": bool(o.get("sinPlano")),
        "progreso": progreso(obra),
        "pendientes": len(val.get("errores") or []) + len(val.get("advertencias") or []),
        "planoRevision": plano.get("revision") if plano else None,
        "ultimaActividad": hist[-1] if hist else None,
    }
