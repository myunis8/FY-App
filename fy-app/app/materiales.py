"""Lista de materiales: un catálogo de productos/accesorios reusable entre
obras (peines, borneras, soportes, tornillería, etc. -- las cosas que no
están en la lista de precios porque no se cobran por separado, pero hay que
comprarlas igual) más, por obra, cuántos de cada uno hacen falta y qué
rollos de cable conviene comprar.

El cómputo de cajas y tableros es automático, a partir de los mismos datos
que ya cargó Circuitos y Tablero -- no hay nada nuevo que cargar a mano para
ver ese número. Sigue funcionando aunque la obra esté en etapa preliminar y
todavía no se haya armado el tablero ni ruteado nada: en ese caso, lo que
depende de Routeo (cajas de inspección) simplemente da 0 con una nota, en
vez de fallar.
"""
from __future__ import annotations
import json
from pathlib import Path
from . import config as cfgmod

ARCHIVO = "materiales.json"

CATEGORIAS = ["Accesorios de tablero", "Puesta a tierra", "Canalización externa",
              "Fijación y tornillería", "Otros"]

# catálogo de arranque: lo típico que no está en precios.py porque no se
# cobra por separado (es insumo, no un ítem de presupuesto), pero hay que
# comprarlo igual. Se puede ampliar o editar desde materiales.html.
SEMILLA = [
    ("Accesorios de tablero", "Peine para térmicas", "u"),
    ("Accesorios de tablero", "Conector para peine", "u"),
    ("Accesorios de tablero", "Riel DIN", "m"),
    ("Accesorios de tablero", "Bornera de paso", "u"),
    ("Puesta a tierra", "Bornera de tierra", "u"),
    ("Puesta a tierra", "Cable de PAT (jabalina a barra)", "m"),
    ("Canalización externa", "Soporte para caño externo", "u"),
    ("Canalización externa", "Soporte para corrugado", "u"),
    ("Canalización externa", "Curva/codo para caño externo", "u"),
    ("Fijación y tornillería", "Conector para caja", "u"),
    ("Fijación y tornillería", "Tornillo autoperforante", "u"),
    ("Fijación y tornillería", "Taco Fischer S6/S8", "u"),
]


def _ruta() -> Path:
    return cfgmod.DIR_CONFIG / ARCHIVO


def leer() -> dict:
    p = _ruta()
    if not p.exists():
        datos = {"actualizadoEl": 0, "items": [
            {"id": f"mt_{i+1:03d}", "categoria": cat, "item": it, "unidad": un}
            for i, (cat, it, un) in enumerate(SEMILLA)]}
        guardar(datos)
        return datos
    try:
        datos = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"actualizadoEl": 0, "items": []}
    datos.setdefault("items", [])
    return datos


def guardar(datos: dict) -> dict:
    from .contrato import ahora
    datos["actualizadoEl"] = ahora()
    vistos = set()
    for i, it in enumerate(datos.get("items") or []):
        if not it.get("id") or it["id"] in vistos:
            it["id"] = f"mt_{ahora()}_{i}"
        vistos.add(it["id"])
    cfgmod.DIR_CONFIG.mkdir(parents=True, exist_ok=True)
    _ruta().write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return datos


# ------------------------------------------------------------- cómputo
def computar_cajas(obra: dict) -> dict:
    """Cajas octogonales y rectangulares: de los elementos ya cargados en
    Circuitos/Revisor -- siempre disponible, aunque la obra sea preliminar.
    Cajas de inspección: sólo si ya se ruteó algo en Routeo (son cajas de
    paso a lo largo de un caño, no algo que salga del plano de bocas)."""
    elementos = obra.get("elementos") or []
    octogonales = sum(1 for e in elementos if e.get("tipo") == "artefacto")
    rectangulares = sum(1 for e in elementos if e.get("tipo") in ("toma", "llave", "otros"))
    canal = obra.get("canalizacion") or {}
    nodos = canal.get("nodes") or []
    inspeccion = sum(1 for n in nodos if n.get("kind") == "insp")
    return {
        "octogonales": octogonales,
        "rectangulares": rectangulares,
        "inspeccion": inspeccion,
        "inspeccionDisponible": bool(nodos),   # si no hay nada ruteado, el 0 no significa "no hace falta ninguna"
    }


def computar_tableros(obra: dict) -> list[dict]:
    """Un renglón por tablero, con lo que lleva adentro -- general,
    diferencial, cuántas térmicas, y si tiene bornera de tierra (para la
    jabalina de PAT)."""
    salida = []
    for t in obra.get("tableros") or []:
        dispositivos = t.get("dispositivos") or []
        general = next((d for d in dispositivos if d.get("tipo") == "termica" and d.get("rol") == "general"), None)
        diferencial = next((d for d in dispositivos if d.get("tipo") == "diferencial"), None)
        termicas = sum(1 for d in dispositivos if d.get("tipo") == "termica" and d.get("rol") != "general")
        protectores = sum(1 for d in dispositivos if d.get("tipo") == "protector")
        tierra = any(d.get("tipo") == "bornera" for d in dispositivos)
        salida.append({
            "id": t.get("id"), "nombre": t.get("nombre"), "fases": t.get("fases", 1),
            "general": bool(general), "diferencial": bool(diferencial),
            "termicas": termicas, "protectores": protectores, "jabalinaPAT": tierra,
        })
    return salida
