"""Almacen local en disco. El repo de GitHub es un espejo, no la fuente."""
from __future__ import annotations
import json, shutil
from datetime import datetime
from pathlib import Path
from . import config as cfgmod
from . import contrato as C
from . import presupuesto as pres_mod


def _dir(obra_id: str) -> Path:
    return cfgmod.DIR_OBRAS / obra_id


def _leer_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def listar_resumenes() -> list[dict]:
    cfgmod.asegurar_carpetas()
    out = []
    for d in sorted(cfgmod.DIR_OBRAS.iterdir()) if cfgmod.DIR_OBRAS.exists() else []:
        if not d.is_dir():
            continue
        r = _leer_json(d / "resumen.json")
        if r is None:                      # resumen perdido: se reconstruye
            obra = _leer_json(d / "obra.json")
            if obra is None:
                continue
            r = C.resumen(C.normalizar(obra))
            (d / "resumen.json").write_text(json.dumps(r, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
        r["sincronizada"] = (d / ".sync.json").exists()
        out.append(r)
    out.sort(key=lambda r: r.get("actualizadoEl") or 0, reverse=True)
    return out


def listar_historial(limite: int = 500) -> list[dict]:
    """Historial de todas las obras juntas, más reciente primero.

    A diferencia de listar_resumenes(), acá hace falta leer obra.json
    completo (el resumen liviano sólo guarda la última actividad, no la
    lista entera) -- pero esto sólo se pide cuando alguien abre la pantalla
    de historial general, no en cada carga del tablero."""
    cfgmod.asegurar_carpetas()
    todo = []
    for d in cfgmod.DIR_OBRAS.iterdir() if cfgmod.DIR_OBRAS.exists() else []:
        if not d.is_dir():
            continue
        obra = _leer_json(d / "obra.json")
        if obra is None:
            continue
        nombre = (obra.get("obra") or {}).get("nombre") or d.name
        for h in obra.get("historial") or []:
            todo.append({**h, "obraId": d.name, "obraNombre": nombre})
    todo.sort(key=lambda h: h.get("el") or 0, reverse=True)
    return todo[:limite]


def listar_finanzas() -> dict:
    """Ganancia reconocida de todas las obras, agrupada por mes y por año
    -- ver presupuesto.eventos_ganancia() para de dónde sale cada monto y
    en qué momento se reconoce (cuando se fue cobrando, no todo junto al
    final ni al presupuestar)."""
    cfgmod.asegurar_carpetas()
    por_mes: dict[str, float] = {}
    por_anio: dict[str, float] = {}
    total = 0.0
    obras_con_cobro = 0
    for d in cfgmod.DIR_OBRAS.iterdir() if cfgmod.DIR_OBRAS.exists() else []:
        if not d.is_dir():
            continue
        obra = _leer_json(d / "obra.json")
        if obra is None:
            continue
        eventos = pres_mod.eventos_ganancia(obra)
        if eventos:
            obras_con_cobro += 1
        for ev in eventos:
            dt = datetime.fromtimestamp((ev.get("el") or 0) / 1000)
            clave_mes, clave_anio = dt.strftime("%Y-%m"), dt.strftime("%Y")
            por_mes[clave_mes] = por_mes.get(clave_mes, 0) + ev["monto"]
            por_anio[clave_anio] = por_anio.get(clave_anio, 0) + ev["monto"]
            total += ev["monto"]
    return {
        "porMes": dict(sorted(por_mes.items())),
        "porAnio": dict(sorted(por_anio.items())),
        "total": round(total, 2),
        "promedioPorObra": round(total / obras_con_cobro, 2) if obras_con_cobro else 0,
        "obrasConCobro": obras_con_cobro,
    }


def leer_obra(obra_id: str) -> dict | None:
    obra = _leer_json(_dir(obra_id) / "obra.json")
    return C.normalizar(obra) if obra else None


HISTORIAL_MAX = 200


def guardar_obra(obra: dict, usuario: str = "", *, modulo: str | None = None,
                 resumen: str = "") -> dict:
    """Guarda obra.json + resumen.json.

    `modulo` es opcional a propósito: la mayoría de los guardados son
    ediciones chiquitas y frecuentes (mover un dispositivo de tablero, por
    ejemplo) que no vale la pena dejar registradas una por una -- inundarían
    el historial. Sólo se pasa `modulo` en las acciones que un usuario
    reconocería como "hice tal cosa" (guardar, extraer, sincronizar, etc.)."""
    obra = C.normalizar(obra)
    obra["obra"]["actualizadoEl"] = C.ahora()
    if usuario:
        obra["obra"]["actualizadoPor"] = usuario
    if modulo:
        hist = obra.setdefault("historial", [])
        hist.append({"el": obra["obra"]["actualizadoEl"], "por": usuario or "—",
                    "modulo": modulo, "resumen": resumen})
        if len(hist) > HISTORIAL_MAX:
            del hist[:len(hist) - HISTORIAL_MAX]
    d = _dir(obra["obra"]["id"])
    d.mkdir(parents=True, exist_ok=True)
    (d / "obra.json").write_text(json.dumps(obra, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
    res = C.resumen(obra)
    (d / "resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
    return obra


def borrar_obra(obra_id: str) -> bool:
    d = _dir(obra_id)
    if not d.exists():
        return False
    shutil.rmtree(d)
    return True


def guardar_plano(obra_id: str, nombre: str, datos: bytes) -> dict:
    """Guarda el PDF junto a la obra y devuelve el bloque `plano` del contrato.

    El PDF se guarda como archivo aparte, nunca embebido en obra.json: meterlo
    adentro multiplicaría el peso del JSON y rompería el guardado por bloques.
    """
    import hashlib, re
    d = _dir(obra_id)
    d.mkdir(parents=True, exist_ok=True)
    limpio = re.sub(r"[^\w.\- ]", "_", nombre) or "plano.pdf"
    (d / limpio).write_bytes(datos)
    return {
        "archivo": limpio,
        "hash": "sha256:" + hashlib.sha256(datos).hexdigest(),
        "tamanoBytes": len(datos),
        "cargadoEl": C.ahora(),
        "revision": None,
        "pagina": 1,
        "escala": None,
        "referencia": None,
    }


def ruta_plano(obra_id: str, nombre: str) -> Path | None:
    p = _dir(obra_id) / nombre
    return p if p.is_file() else None


# --- estado de sincronizacion por obra ---------------------------------
def leer_sync(obra_id: str) -> dict:
    return _leer_json(_dir(obra_id) / ".sync.json") or {}


def guardar_sync(obra_id: str, estado: dict):
    d = _dir(obra_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / ".sync.json").write_text(json.dumps(estado, ensure_ascii=False, indent=2),
                                  encoding="utf-8")


def escribir_desde_repo(obra_id: str, obra: dict, sha_obra: str, resumen: dict | None = None):
    """Guarda una obra bajada del repo sin tocar la marca de tiempo."""
    d = _dir(obra_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "obra.json").write_text(json.dumps(C.normalizar(obra), ensure_ascii=False, indent=2),
                                 encoding="utf-8")
    res = resumen or C.resumen(C.normalizar(obra))
    (d / "resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
    guardar_sync(obra_id, {"shaObra": sha_obra, "bajadaEl": C.ahora()})
