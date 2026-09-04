"""Operaciones de sincronizacion: bajar el espejo y subir una obra."""
from __future__ import annotations
import json
from . import almacen, contrato as C, github as gh


def bajar_todo(cfg: dict) -> dict:
    """Trae los resumenes de todas las obras del repo.

    No baja los obra.json completos: el tablero solo necesita el resumen.
    La obra entera se pide recien cuando se abre.
    """
    ids, existe = gh.listar_obras(cfg)
    nuevas, actualizadas = 0, 0
    for oid in ids:
        remoto, _ = gh.bajar_archivo(cfg, f"obras/{oid}/resumen.json")
        if remoto is None:
            continue
        local = None
        for r in almacen.listar_resumenes():
            if r.get("id") == oid:
                local = r
                break
        if local is None:
            nuevas += 1
        elif (remoto.get("actualizadoEl") or 0) > (local.get("actualizadoEl") or 0):
            actualizadas += 1
        else:
            continue
        d = almacen._dir(oid)
        d.mkdir(parents=True, exist_ok=True)
        (d / "resumen.json").write_text(json.dumps(remoto, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
        est = almacen.leer_sync(oid)
        est["resumenRemotoEl"] = remoto.get("actualizadoEl") or 0
        est["soloResumen"] = not (d / "obra.json").exists()
        almacen.guardar_sync(oid, est)
    return {"enRepo": len(ids), "nuevas": nuevas, "actualizadas": actualizadas,
            "carpetaCreada": existe}


def traer_obra(cfg: dict, obra_id: str) -> dict:
    """Baja el obra.json completo y lo deja en el cache local."""
    obra, sha = gh.bajar_archivo(cfg, f"obras/{obra_id}/obra.json")
    if obra is None:
        raise gh.ErrorSync("Esa obra no está en el repositorio.", 404)
    almacen.escribir_desde_repo(obra_id, obra, sha)
    est = almacen.leer_sync(obra_id)
    est["soloResumen"] = False
    almacen.guardar_sync(obra_id, est)
    return almacen.leer_obra(obra_id)


def subir_obra(cfg: dict, obra_id: str, forzar: bool = False) -> dict:
    """Sube obra.json + resumen.json.

    Verifica el sha guardado al bajar/subir por ultima vez. Si en el repo hay
    otro sha, alguien (o vos desde otra maquina) escribio en el medio: no se
    pisa nada y se avisa.
    """
    obra = almacen.leer_obra(obra_id)
    if obra is None:
        raise gh.ErrorSync("No existe esa obra en este equipo.", 404)

    ruta_obra = f"obras/{obra_id}/obra.json"
    est = almacen.leer_sync(obra_id)
    sha_local = est.get("shaObra")
    sha_remoto = gh.sha_de(cfg, ruta_obra)

    if sha_remoto and sha_local and sha_remoto != sha_local and not forzar:
        remoto, _ = gh.bajar_archivo(cfg, f"obras/{obra_id}/resumen.json")
        raise gh.ErrorSync(
            "La obra cambió en el repositorio desde la última vez que la bajaste"
            + (f" (última edición: {(remoto or {}).get('actualizadoPor') or 'otro equipo'})." if remoto else "."),
            409, conflicto=True)

    nombre = obra["obra"].get("nombre") or obra_id
    sha_nuevo = gh.subir_archivo(
        cfg, ruta_obra,
        json.dumps(obra, ensure_ascii=False, indent=2).encode("utf-8"),
        f"Actualiza {nombre}", sha_remoto)

    res = C.resumen(obra)
    ruta_res = f"obras/{obra_id}/resumen.json"
    gh.subir_archivo(cfg, ruta_res,
                     json.dumps(res, ensure_ascii=False, indent=2).encode("utf-8"),
                     f"Actualiza resumen de {nombre}", gh.sha_de(cfg, ruta_res))

    almacen.guardar_sync(obra_id, {"shaObra": sha_nuevo, "subidaEl": C.ahora()})
    return {"ok": True, "sha": sha_nuevo}


def borrar_obra_remota(cfg: dict, obra_id: str) -> dict:
    """Borra del repositorio todo lo que se subió de esta obra (obra.json,
    resumen.json y lo que haya adentro de su carpeta). No toca nada local
    -- de eso se encarga almacen.borrar_obra() aparte."""
    borrados = gh.borrar_carpeta(cfg, f"obras/{obra_id}", f"Borra la obra {obra_id} del repositorio")
    return {"ok": True, "borrados": borrados}
