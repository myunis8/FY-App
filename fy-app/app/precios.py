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
    ("Puntos", "Punto de luz", "u", 19363),
    ("Puntos", "Punto combinado", "u", 20842),
    ("Tomas", "Tomacorriente común", "u", 24525),
    ("Tomas", "Tomacorriente doble (dos bocas en una caja)", "u", 32000),
    ("Tomas", "Toma con tapa IP44 (exterior o zona húmeda)", "u", 29800),
    ("Tomas", "Toma con protección para niños", "u", 27200),
    ("Tomas", "Toma USB + 220V", "u", 38500),
    ("Tomas", "Toma trifásica industrial (rotativa)", "u", 61500),
    ("Tomas", "Toma especial - Cocina", "u", 34525),
    ("Tomas", "Toma especial - Aire acondicionado", "u", 34525),
    ("Tomas", "Toma especial - Termotanque", "u", 34525),
    ("Tomas", "Boca combinada (interruptor + toma)", "u", 24525),
    ("Iluminación", "Artefacto aislado", "u", 29715),
    ("Iluminación", "Artefacto no aislado", "u", 29715),
    ("Tableros", "Tablero seccional monofásico", "u", 227652),
    ("Tableros", "Tablero seccional trifásico", "u", 325000),
    ("Tableros", "Tablero principal monofásico", "u", 320310),
    ("Tableros", "Tablero principal trifásico", "u", 433760),
    ("Puesta a tierra", "Jabalina + cable + conexión (PAT)", "u", 162585),
    ("Trabajos adicionales", "Conexión al medidor (trabajo en tensión)", "u", 200000),
    ("Automatizaciones", "Flotante a 220V", "u", 100000),
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
        datos = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"actualizadoEl": 0, "moneda": "ARS", "items": []}
    return _completar_faltantes(datos)


def _completar_faltantes(datos: dict) -> dict:
    """Dos casos, no uno: un ítem puede faltar del todo (se agrega), o puede
    ya existir pero con el precio en $0 de una semilla vieja de antes de que
    se cargaran precios reales — desde afuera eso se ve exactamente como
    "no lo agregaste", así que también se actualiza. Nunca se toca un precio
    que ya sea distinto de 0 (ahí sí puede ser una edición real del usuario)."""
    items = datos.setdefault("items", [])
    por_nombre = {(it.get("item") or "").strip().lower(): it for it in items}
    orden_por_categoria: dict[str, int] = {}
    for it in items:
        cat = it.get("categoria") or "Otros"
        orden_por_categoria[cat] = max(orden_por_categoria.get(cat, -1), it.get("orden", -1))
    cambio = False
    for cat, nombre, unidad, precio in SEMILLA:
        clave = nombre.strip().lower()
        existente = por_nombre.get(clave)
        if existente is None:
            orden_por_categoria[cat] = orden_por_categoria.get(cat, -1) + 1
            nuevo = {"id": f"pr_nuevo_{int(time.time()*1000)}_{len(items)}", "categoria": cat,
                    "item": nombre, "unidad": unidad, "precio": precio,
                    "orden": orden_por_categoria[cat]}
            items.append(nuevo)
            por_nombre[clave] = nuevo
            cambio = True
        elif not existente.get("precio"):
            existente["precio"] = precio
            cambio = True
    if cambio:
        guardar(datos)
    return datos


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
