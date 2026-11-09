"""Stock propio: materiales que tenemos guardados para cubrir imprevistos en
una obra (algo que no se había previsto) sin ir a comprarlo en el momento.

NO está atado a la lista de materiales de ninguna obra: esa lista es una
estimación de "lo que hace falta" y nunca toca el stock. Acá sólo se mueve
stock a mano, con dos tipos de movimiento:

  - reposición: entra material (una compra, o un sobrante de obra);
  - consumo:    sale material (se usó en una obra).

El stock actual de cada ítem es la suma de reposiciones menos consumos --
siempre se calcula del registro de movimientos, nunca se guarda un "saldo".
Los ítems posibles son los de la lista de materiales (materiales.json).

Costos: se usa el ÚLTIMO PRECIO DE REPOSICIÓN. Un movimiento puede traer su
precio; si no lo trae, toma el último precio cargado de ese ítem; si no hay
ninguno, queda marcado como "falta precio" -- nunca es un error. Un sobrante
(reposición sin precio de compra) tampoco cambia el último precio. Es global
(no va dentro de ninguna obra): vive en stock.json junto a precios.json y
materiales.json.
"""
from __future__ import annotations
import json, re, time
from datetime import date
from pathlib import Path
from . import config as cfgmod, materiales as mat_mod

ARCHIVO = "stock.json"
TIPOS = ("reposicion", "consumo")


def _ruta() -> Path:
    return cfgmod.DIR_CONFIG / ARCHIVO


def leer() -> dict:
    p = _ruta()
    if not p.exists():
        return {"movimientos": []}
    try:
        datos = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"movimientos": []}
    datos.setdefault("movimientos", [])
    return datos


def guardar(datos: dict) -> dict:
    cfgmod.DIR_CONFIG.mkdir(parents=True, exist_ok=True)
    tmp = _ruta().with_suffix(".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_ruta())
    return datos


def _num(v):
    """float o None -- un campo vacío o ilegible no es error, es 'sin dato'."""
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


def _clave_orden(m: dict):
    return (m.get("fecha") or "", m.get("creadoEl") or 0, m.get("id") or "")


def ultimo_precio(movs: list[dict], item_id: str):
    """Último precio de reposición CARGADO (no heredado) de un ítem, o None."""
    con_precio = [m for m in movs if m.get("itemId") == item_id and m.get("tipo") == "reposicion"
                  and m.get("precioOrigen") == "cargado" and m.get("precioUnitario") is not None]
    return max(con_precio, key=_clave_orden)["precioUnitario"] if con_precio else None


def _fecha(v) -> str:
    return v if isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) else date.today().isoformat()


def agregar(datos: dict, mov: dict, usuario: str = "") -> dict:
    """Registra un movimiento. Los errores son sólo de datos imposibles (tipo
    desconocido, cantidad no positiva, ítem inexistente); la falta de precio
    nunca lo es."""
    tipo = mov.get("tipo")
    if tipo not in TIPOS:
        raise ValueError("El movimiento tiene que ser una reposición o un consumo.")
    cantidad = _num(mov.get("cantidad"))
    if cantidad is None or cantidad <= 0:
        raise ValueError("La cantidad tiene que ser mayor que cero (puede tener decimales).")
    item = next((i for i in mat_mod.leer().get("items") or [] if i.get("id") == mov.get("itemId")), None)
    if item is None:
        raise ValueError("Ese ítem no está en la lista de materiales.")
    precio = _num(mov.get("precioUnitario"))
    if precio is not None and precio < 0:
        raise ValueError("El precio no puede ser negativo.")
    origen = "cargado" if precio is not None else None
    if precio is None:
        ultimo = ultimo_precio(datos["movimientos"], item["id"])
        if ultimo is not None:
            precio, origen = ultimo, "ultimo"
    m = {
        "id": f"mv_{int(time.time() * 1000):x}_{len(datos['movimientos'])}",
        "fecha": _fecha(mov.get("fecha")), "tipo": tipo,
        "itemId": item["id"], "item": item["item"], "unidad": item.get("unidad") or "u",
        "cantidad": cantidad, "precioUnitario": precio, "precioOrigen": origen,
        # un sobrante entra sin precio de compra: no cambia el último precio
        "sobrante": bool(mov.get("sobrante")) and tipo == "reposicion",
        "obraId": mov.get("obraId") or None, "obraNombre": (mov.get("obraNombre") or "").strip() or None,
        "nota": (mov.get("nota") or "").strip(),
        "creadoEl": int(time.time() * 1000), "creadoPor": usuario,
    }
    if m["sobrante"] and origen == "cargado":
        m["sobrante"] = False          # si trae precio es una compra, no un sobrante
    datos["movimientos"].append(m)
    return m


def actualizar(datos: dict, mov_id: str, campos: dict) -> dict:
    """Corrige un movimiento ya cargado (típico: completar el precio que
    faltaba). Sólo se tocan los campos que vienen."""
    m = next((x for x in datos["movimientos"] if x.get("id") == mov_id), None)
    if m is None:
        raise ValueError("Ese movimiento no existe.")
    if "cantidad" in campos:
        c = _num(campos["cantidad"])
        if c is None or c <= 0:
            raise ValueError("La cantidad tiene que ser mayor que cero.")
        m["cantidad"] = c
    if "precioUnitario" in campos:
        p = _num(campos["precioUnitario"])
        if p is not None and p < 0:
            raise ValueError("El precio no puede ser negativo.")
        m["precioUnitario"] = p
        m["precioOrigen"] = "cargado" if p is not None else None
        if p is not None:
            m["sobrante"] = False
    if "fecha" in campos:
        m["fecha"] = _fecha(campos["fecha"])
    for k in ("nota", "obraNombre"):
        if k in campos:
            m[k] = (campos[k] or "").strip() or ("" if k == "nota" else None)
    return m


def borrar(datos: dict, mov_id: str) -> bool:
    antes = len(datos["movimientos"])
    datos["movimientos"] = [m for m in datos["movimientos"] if m.get("id") != mov_id]
    return len(datos["movimientos"]) != antes


# ---------------------------------------------------------------- vistas
def listado(datos: dict) -> list[dict]:
    """Movimientos, el más nuevo primero, con el precio que se les atribuye
    HOY: el cargado, el último vigente al registrarlo, o -- si en su momento
    no había ninguno y desde entonces se cargó uno -- el último de ahora
    (marcado 'estimado'). Sin ninguno: 'falta'."""
    movs = datos["movimientos"]
    out = []
    for m in sorted(movs, key=_clave_orden, reverse=True):
        precio, estado = m.get("precioUnitario"), m.get("precioOrigen") or "falta"
        if precio is None:
            ult = ultimo_precio(movs, m["itemId"])
            if ult is not None:
                precio, estado = ult, "estimado"
        out.append({**m, "precioEfectivo": precio, "estadoPrecio": estado if precio is not None else "falta"})
    return out


def resumen(datos: dict) -> list[dict]:
    """Stock actual por ítem (sólo los que tuvieron algún movimiento)."""
    movs = datos["movimientos"]
    catalogo = {i["id"]: i for i in mat_mod.leer().get("items") or []}
    por_item: dict[str, dict] = {}
    for m in movs:
        f = por_item.setdefault(m["itemId"], {"itemId": m["itemId"], "item": m.get("item"),
                                              "unidad": m.get("unidad") or "u", "cantidad": 0.0,
                                              "ultimaFecha": ""})
        f["cantidad"] += m["cantidad"] if m["tipo"] == "reposicion" else -m["cantidad"]
        f["ultimaFecha"] = max(f["ultimaFecha"], m.get("fecha") or "")
    out = []
    for iid, f in por_item.items():
        cat = catalogo.get(iid)
        if cat:                                   # el nombre actual de la lista manda
            f["item"], f["unidad"] = cat["item"], cat.get("unidad") or f["unidad"]
            f["categoria"] = cat.get("categoria")
        f["cantidad"] = round(f["cantidad"], 4)
        f["ultimoPrecio"] = ultimo_precio(movs, iid)
        f["valor"] = round(f["cantidad"] * f["ultimoPrecio"], 2) if f["ultimoPrecio"] is not None else None
        f["faltaPrecio"] = f["ultimoPrecio"] is None and f["cantidad"] > 0
        f["negativo"] = f["cantidad"] < 0
        out.append(f)
    out.sort(key=lambda f: (f.get("item") or "").lower())
    return out


def payload(datos: dict | None = None) -> dict:
    """Todo lo que necesita la pantalla."""
    datos = datos if datos is not None else leer()
    movs = datos["movimientos"]
    items = []
    for i in sorted(mat_mod.leer().get("items") or [], key=lambda i: (i.get("categoria") or "", i.get("item") or "")):
        items.append({"id": i["id"], "item": i["item"], "unidad": i.get("unidad") or "u",
                      "categoria": i.get("categoria"), "ultimoPrecio": ultimo_precio(movs, i["id"])})
    return {"items": items, "resumen": resumen(datos), "movimientos": listado(datos)}
