"""Lista de precios global y congelamiento por obra.

La lista vive en un solo lugar y se actualiza a mano. Cuando una obra se
presupuesta, los precios se COPIAN dentro de la obra: así un presupuesto ya
entregado no cambia solo cuando actualices la lista. Al reabrirlo se puede
comparar lo congelado contra lo vigente, que es lo que sirve para reajustar.

Las categorías marcadas "aparte" (Trabajos adicionales, Automatizaciones) no
se calculan solas desde el plano: se agregan a mano en el presupuesto, porque
son trabajos que no salen de contar cajas.
"""
from __future__ import annotations
import json, time
from pathlib import Path
from . import config as cfgmod

ARCHIVO = "precios.json"

CATEGORIAS = ["Puntos", "Tomas", "Iluminación", "Tableros", "Puesta a tierra",
              "Canalización", "Trabajos adicionales", "Automatizaciones", "Otros"]

# categorías que no se calculan solas: siempre se agregan a mano
CATEGORIAS_APARTE = {"Trabajos adicionales", "Automatizaciones"}

SEMILLA = [
    ("Puntos", "Punto de luz", "u", 0),
    ("Puntos", "Punto combinado", "u", 0),
    ("Tomas", "Tomacorriente común", "u", 0),
    ("Tomas", "Toma especial - Cocina", "u", 0),
    ("Tomas", "Toma especial - Aire acondicionado", "u", 0),
    ("Tomas", "Toma especial - Termotanque", "u", 0),
    ("Tomas", "Boca combinada (interruptor + toma)", "u", 0),
    ("Iluminación", "Artefacto aislado", "u", 0),
    ("Iluminación", "Artefacto no aislado", "u", 0),
    ("Tableros", "Tablero seccional monofásico", "u", 0),
    ("Tableros", "Tablero seccional trifásico", "u", 0),
    ("Tableros", "Tablero principal monofásico", "u", 0),
    ("Tableros", "Tablero principal trifásico", "u", 0),
    ("Puesta a tierra", "Jabalina + cable + conexión (PAT)", "u", 0),
    ("Trabajos adicionales", "Conexión al medidor (trabajo en tensión)", "u", 0),
    ("Automatizaciones", "Flotante a 220V", "u", 0),
    ("Automatizaciones", "Flotante a 24V", "u", 0),
]


def _ruta() -> Path:
    cfgmod.asegurar_carpetas()
    return cfgmod.DIR_DATOS / ARCHIVO


def leer() -> dict:
    p = _ruta()
    if not p.exists():
        datos = {"actualizadoEl": 0, "moneda": "ARS", "items": [
            {"id": f"pr_{i+1:03d}", "categoria": cat, "item": it, "unidad": un,
             "precio": pr, "orden": i}
            for i, (cat, it, un, pr) in enumerate(SEMILLA)]}
        guardar(datos)
        return datos
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"actualizadoEl": 0, "moneda": "ARS", "items": []}


def guardar(datos: dict) -> dict:
    datos["actualizadoEl"] = int(time.time() * 1000)
    vistos = set()
    for i, it in enumerate(datos.get("items") or []):
        if not it.get("id") or it["id"] in vistos:
            it["id"] = f"pr_{int(time.time()*1000)}_{i}"
        vistos.add(it["id"])
        it["precio"] = float(it.get("precio") or 0)
        it.setdefault("orden", i)
    _ruta().write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return datos


def vigente_por_id() -> dict:
    return {it["id"]: it for it in (leer().get("items") or [])}


def comparar(items_congelados: list[dict]) -> list[dict]:
    """Precio congelado contra el de la lista de hoy, para ver si reajustar."""
    hoy = vigente_por_id()
    salida = []
    for it in items_congelados:
        act = hoy.get(it.get("precioId"))
        vig = float(act["precio"]) if act else None
        cong = float(it.get("precioUnitario") or 0)
        salida.append({
            "id": it.get("id"), "item": it.get("item"),
            "cantidad": it.get("cantidad"),
            "congelado": cong, "vigente": vig,
            "variacion": None if not vig or not cong else round((vig - cong) / cong * 100, 1),
            "existe": act is not None,
        })
    return salida
