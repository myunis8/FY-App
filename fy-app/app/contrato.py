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


def actualizar_seguimiento(obra: dict, estado: str | None = None, pago_estado: str | None = None,
                            pago_porcentaje=None, usuario: str = "") -> dict:
    """Cambia estado y/o pago de la obra y deja un registro en el
    historial de quién y cuándo lo cambió (el campo ya estaba en el
    esquema desde el principio, pero nada lo llenaba todavía). Si un campo
    no viene, queda como estaba -- no hay valores por adivinar.

    El porcentaje de pago sigue al estado: "pendiente" siempre es 0%,
    "pagado" siempre es 100%, y sólo "parcial" admite un número propio (si
    no llega ninguno, sigue con el que ya había, o 50% la primera vez).
    """
    seg = obra.setdefault("seguimiento", {})
    seg.setdefault("estado", "preliminar")
    seg.setdefault("pago", {"estado": "pendiente", "porcentaje": 0})
    seg.setdefault("historial", [])
    t = ahora()

    if estado is not None and estado in ESTADOS and estado != seg["estado"]:
        seg["historial"].append({"el": t, "por": usuario or "", "campo": "estado",
                                 "de": seg["estado"], "a": estado})
        seg["estado"] = estado

    if pago_estado is not None and pago_estado in ESTADOS_PAGO:
        if pago_estado == "pendiente":
            pct = 0
        elif pago_estado == "pagado":
            pct = 100
        else:
            pct = pago_porcentaje if pago_porcentaje is not None else (seg["pago"].get("porcentaje") or 50)
        pct = max(0, min(100, int(pct)))
        anterior, nuevo = dict(seg["pago"]), {"estado": pago_estado, "porcentaje": pct}
        if nuevo != anterior:
            seg["historial"].append({"el": t, "por": usuario or "", "campo": "pago",
                                     "de": anterior, "a": nuevo})
            seg["pago"] = nuevo
    elif pago_porcentaje is not None and seg["pago"].get("estado") == "parcial":
        pct = max(1, min(99, int(pago_porcentaje)))
        if pct != seg["pago"].get("porcentaje"):
            anterior = dict(seg["pago"])
            seg["pago"]["porcentaje"] = pct
            seg["historial"].append({"el": t, "por": usuario or "", "campo": "pago",
                                     "de": anterior, "a": dict(seg["pago"])})
    return seg


def total_presupuesto(obra: dict) -> float:
    items = (obra.get("presupuesto") or {}).get("items") or []
    return sum((it.get("precio") or 0) * (it.get("cantidad") or 0) for it in items)


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
    }
