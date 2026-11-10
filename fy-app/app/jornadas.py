"""Jornadas, gastos y rollos de cable usados en cada obra, y la estadística de
cuánto rindió la obra por hora-hombre.

Una JORNADA es un día de trabajo en la obra: cuántas personas fueron y
cuántas horas trabajó cada una (por defecto todas lo mismo), más los gastos
de ese día (almuerzo, combustible, yerba...), cada uno con entre cuántas
personas se divide (por defecto, todas las de la jornada). Se guarda en
`obra["jornadas"]`; se puede cargar desde la PC o desde el celular (en ese
caso llega por la bandeja del repositorio -- ver sync.sincronizar_jornadas).

Los ROLLOS usados son un contador por tipo de cable (sección + color/función)
en `obra["rollosUsados"]`, que se compara con lo que había estimado Routeo.

La ESTADÍSTICA final no usa ningún "costo por hora" cargado a mano: sale de
lo que realmente se cobró menos los gastos, dividido por las horas-hombre
trabajadas -- para ver si la obra salió cara o barata y comparar entre obras.
"""
from __future__ import annotations
import math, re, time
from datetime import date
from . import contrato as C

CATEGORIAS_GASTO = ["Almuerzo", "Combustible", "Yerba y mate", "Peajes y estacionamiento",
                    "Insumos y herramientas", "Otro"]
ROLLO_M = 100.0            # metros de un rollo de cable (supuesto: rollo estándar de 100 m)
MAX_PERSONAS = 30


def _num(v, default=None):
    if v is None or v == "":
        return default
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return default


def _fecha(v) -> str:
    return v if isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) else date.today().isoformat()


def normalizar_jornada(j: dict, usuario: str = "") -> dict:
    """Deja una jornada completa y coherente (las horas siempre como lista, una
    por persona). Los datos imposibles se corrigen al valor más cercano en vez
    de rechazar la jornada: una jornada cargada en obra no puede perderse por
    un campo mal escrito."""
    personas = int(max(1, min(MAX_PERSONAS, _num(j.get("personas"), 1) or 1)))
    iguales = bool(j.get("horasIguales", True))
    if iguales:
        if j.get("horasCada") not in (None, ""):
            cada = _num(j.get("horasCada"), 0.0)
        elif j.get("horas"):
            cada = _num(j["horas"][0], 0.0)
        else:
            cada = 0.0
        cada = max(0.0, cada or 0.0)
        horas = [cada] * personas
    else:
        crudas = [max(0.0, _num(h, 0.0) or 0.0) for h in (j.get("horas") or [])]
        horas = (crudas + [0.0] * personas)[:personas]
        cada = None
    gastos = []
    for g in j.get("gastos") or []:
        monto = _num(g.get("monto"), None)
        if monto is None or monto < 0:
            continue
        entre = _num(g.get("entre"), None)
        gastos.append({
            "id": g.get("id") or f"g_{int(time.time() * 1000):x}_{len(gastos)}",
            "categoria": g.get("categoria") if g.get("categoria") in CATEGORIAS_GASTO else "Otro",
            "monto": round(monto, 2),
            "entre": int(max(1, min(personas, entre))) if entre else None,    # None = todas las personas
            "nota": (g.get("nota") or "").strip(),
        })
    return {
        "id": j.get("id") or f"jn_{int(time.time() * 1000):x}",
        "fecha": _fecha(j.get("fecha")), "personas": personas,
        "horasIguales": iguales, "horasCada": cada, "horas": horas,
        "gastos": gastos, "nota": (j.get("nota") or "").strip(),
        "creadoPor": j.get("creadoPor") or usuario or "",
        "creadoEl": int(j.get("creadoEl") or time.time() * 1000),
        "origen": j.get("origen") or "pc",
    }


def ingerir(obra: dict, j: dict) -> bool:
    """Suma a la obra una jornada que llegó del celular (ya trae su id). Si el id ya
    está no se duplica. Devuelve True si se agregó."""
    if not isinstance(j, dict) or not j.get("id"):
        return False
    lista = obra.setdefault("jornadas", [])
    if any(x.get("id") == j["id"] for x in lista):
        return False
    lista.append(normalizar_jornada({**j, "origen": "celular"}))
    return True


def horas_hombre(j: dict) -> float:
    return float(sum(j.get("horas") or []))


def gasto_total(j: dict) -> float:
    return float(sum(g.get("monto") or 0 for g in j.get("gastos") or []))


def cobrado(obra: dict) -> float:
    """Lo que realmente se cobró hasta ahora: lo reconocido en cada cambio de pago
    (misma cuenta que usan Presupuesto y Seguimiento)."""
    seg = obra.get("seguimiento") or {}
    total = C.total_presupuesto(obra)
    return float(sum(C.monto_evento_pago(h, total) for h in seg.get("historial") or [] if h.get("campo") == "pago"))


def resumen_obra(obra: dict) -> dict:
    jornadas = obra.get("jornadas") or []
    horas = sum(horas_hombre(j) for j in jornadas)
    gastos = sum(gasto_total(j) for j in jornadas)
    por_cat: dict[str, float] = {}
    for j in jornadas:
        for g in j.get("gastos") or []:
            por_cat[g["categoria"]] = round(por_cat.get(g["categoria"], 0.0) + g["monto"], 2)
    pago = (obra.get("seguimiento") or {}).get("pago") or {}
    cob = cobrado(obra)
    total = C.total_presupuesto(obra)
    pagada = pago.get("estado") == "pagado"
    out = {
        "jornadas": len(jornadas), "horasHombre": round(horas, 2), "gastos": round(gastos, 2),
        "gastosPorCategoria": por_cat,
        "personasPromedio": round(sum(j["personas"] for j in jornadas) / len(jornadas), 1) if jornadas else 0,
        "cobrado": round(cob, 2), "presupuesto": round(total, 2),
        "pagoEstado": pago.get("estado") or "pendiente", "pagada": pagada,
        "neto": round(cob - gastos, 2),
        # lo que quedó por hora trabajada: sólo tiene sentido con horas cargadas y algo cobrado
        "pesosPorHora": round((cob - gastos) / horas, 2) if horas > 0 and cob > 0 else None,
        # igual, pero contra el total del presupuesto (para estimar antes de que paguen todo)
        "pesosPorHoraPresupuesto": round((total - gastos) / horas, 2) if horas > 0 and total > 0 else None,
    }
    return out


# ------------------------------------------------------------------ rollos
def rollos_vista(obra: dict) -> list[dict]:
    """Un renglón por tipo de cable (sección + color/función), con lo que
    estimó Routeo y lo que se usó realmente. Los tipos salen de la estimación;
    los que tienen rollos usados pero ya no están en ella se conservan."""
    from . import materiales as mat_mod
    usados = obra.get("rollosUsados") or {}
    est = mat_mod.computar_canalizacion(obra)
    filas: dict[str, dict] = {}
    for sec, colores in (est.get("cableColor") or {}).items():
        for color, metros in colores.items():
            clave = f"{sec}|{color}"
            filas[clave] = {"clave": clave, "seccion": sec, "color": color, "estimadoM": float(metros)}
    for clave in usados:
        if clave not in filas:
            sec, _, color = clave.partition("|")
            try:
                sec = float(sec)
            except ValueError:
                pass
            filas[clave] = {"clave": clave, "seccion": sec, "color": color, "estimadoM": 0.0}
    out = []
    for f in filas.values():
        u = int(usados.get(f["clave"]) or 0)
        out.append({**f, "estimadoRollos": round(f["estimadoM"] / ROLLO_M, 2), "usados": u,
                    "diferencia": round(u - f["estimadoM"] / ROLLO_M, 2) if f["estimadoM"] else None})
    out.sort(key=lambda f: (float(f["seccion"]) if isinstance(f["seccion"], (int, float)) else 0, f["color"]))
    return out


def clave_rollo(seccion, color: str) -> str:
    return f"{seccion}|{color}"
