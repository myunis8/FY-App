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
        "canalizacion": {"nodos": [], "tramos": [], "conductores": [], "reglas": {}},
        "computo": None,
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
    return obra


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
        "canalizado": bool(canal.get("tramos")),
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
