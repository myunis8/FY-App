"""Operaciones de sincronizacion: bajar el espejo y subir una obra."""
from __future__ import annotations
import json
from . import almacen, contrato as C, github as gh


def asegurar_plano(cfg: dict, obra_id: str, obra: dict) -> bool:
    """Si la obra referencia un plano pero el PDF no está en este equipo,
    lo trae del repositorio -- sin tocar el resto de obra.json (no hay que
    arriesgar pisar cambios locales todavía no subidos sólo por mirar la
    obra). Pasa esto, por ejemplo, con una obra que ya se había bajado a
    este equipo *antes* de que la sincronización supiera subir/bajar el
    PDF: su obra.json local nunca vuelve a pasar por traer_obra() sólo
    por abrirse, así que el plano quedaba pendiente para siempre.

    Best-effort: sin repo/token configurado, sin conexión, o cualquier
    otro problema, se ignora en silencio -- la obra igual se puede ver
    sin el plano, como pasaba antes."""
    if not cfg.get("repo") or not cfg.get("token"):
        return False
    plano = obra.get("plano") or {}
    archivo = plano.get("archivo")
    if not archivo:
        return False
    est = almacen.leer_sync(obra_id)
    falta_local = almacen.ruta_plano(obra_id, archivo) is None
    if not falta_local and plano.get("hash") == est.get("planoBajadoHash"):
        return False                       # ya está, y es el mismo archivo
    try:
        datos, _ = gh.bajar_archivo_bin(cfg, f"obras/{obra_id}/{archivo}")
    except gh.ErrorSync:
        return False
    if not datos:
        return False
    almacen.escribir_plano_bytes(obra_id, archivo, datos)
    est["planoBajadoHash"] = plano.get("hash")
    almacen.guardar_sync(obra_id, est)
    return True


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
    """Baja el obra.json completo y lo deja en el cache local. Si la obra
    tiene plano, también baja el PDF (no estaba pasando: sólo se bajaban
    obra.json/resumen.json) -- se salta si ya está el mismo archivo
    (mismo hash que la última vez que se bajó), para no repetir una
    transferencia pesada en cada sincronización."""
    obra, sha = gh.bajar_archivo(cfg, f"obras/{obra_id}/obra.json")
    if obra is None:
        raise gh.ErrorSync("Esa obra no está en el repositorio.", 404)
    almacen.escribir_desde_repo(obra_id, obra, sha)
    est = almacen.leer_sync(obra_id)
    est["soloResumen"] = False
    almacen.guardar_sync(obra_id, est)

    asegurar_plano(cfg, obra_id, obra)
    return almacen.leer_obra(obra_id)


def subir_obra(cfg: dict, obra_id: str, forzar: bool = False) -> dict:
    """Sube obra.json + resumen.json + el PDF del plano (si hay y cambió
    desde la última subida, comparando por hash -- no tiene sentido resubir
    el mismo archivo pesado en cada sincronización).

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

    plano = obra.get("plano") or {}
    archivo_plano = plano.get("archivo")
    plano_hash_subido = est.get("planoSubidoHash")
    if archivo_plano and plano.get("hash") != plano_hash_subido:
        ruta_local = almacen.ruta_plano(obra_id, archivo_plano)
        if ruta_local:
            ruta_plano_repo = f"obras/{obra_id}/{archivo_plano}"
            gh.subir_archivo(cfg, ruta_plano_repo, ruta_local.read_bytes(),
                             f"Sube el plano de {nombre}", gh.sha_de(cfg, ruta_plano_repo))
            plano_hash_subido = plano.get("hash")

    est2 = {**est, "shaObra": sha_nuevo, "subidaEl": C.ahora(), "planoSubidoHash": plano_hash_subido}
    try:
        est2["jornadasHash"] = publicar_jornadas(cfg, obra_id, obra, est.get("jornadasHash"))
    except Exception:
        pass
    # los PDF de consulta para el celular: si falla alguno, la obra igual quedó subida
    try:
        est2["pdfHashes"], pdfs = publicar_pdfs(cfg, obra_id, obra, est.get("pdfHashes") or {})
    except Exception:
        pdfs = []
    almacen.guardar_sync(obra_id, est2)
    return {"ok": True, "sha": sha_nuevo, "pdfs": pdfs}


# ------------------------------------------------ PDF y stock para el celular
def publicar_pdfs(cfg: dict, obra_id: str, obra: dict, hashes_previos: dict) -> tuple[dict, list[str]]:
    """Genera los PDF principales de la obra y los sube a obras/<id>/pdf/ --
    así el celular (que no tiene cómo generarlos) puede consultarlos y
    descargarlos. Un PDF que no cambió (mismo hash) no se vuelve a subir, y
    uno que no se puede generar (obra todavía incompleta) se omite sin
    error. Devuelve (hashes nuevos, nombres subidos)."""
    import hashlib
    import pymupdf
    from . import pdf_informe, pdf_materiales, pdf_presupuesto, pdf_tablero
    nombre = obra["obra"].get("nombre") or obra_id
    generadores = [
        ("presupuesto.pdf", lambda: pdf_presupuesto.generar(obra, modo="con")),
        ("informe.pdf", lambda: pdf_informe.generar(obra, pdf_informe.MODULOS_POR_DEFECTO)),
        ("materiales.pdf", lambda: pdf_materiales.generar(obra, mostrar_precio=True)),
        ("tableros.pdf", lambda: pdf_tablero.generar_todos(obra) if obra.get("tableros") else None),
    ]
    hashes, subidos = dict(hashes_previos), []
    for archivo, gen in generadores:
        try:
            datos = gen()
        except Exception:
            continue
        if not datos:
            continue
        # compactado (los PDF salen sin comprimir: 19 MB -> ~1,5 MB) y huella por TEXTO,
        # no por bytes: cada generación cambia el id interno del PDF aunque el contenido sea
        # el mismo, y no tiene sentido resubir lo que no cambió
        doc = pymupdf.open(stream=datos, filetype="pdf")
        huella = hashlib.sha256(chr(10).join(pg.get_text() for pg in doc).encode("utf-8")).hexdigest()
        if hashes.get(archivo) == huella:
            doc.close()
            continue
        datos = doc.tobytes(garbage=4, deflate=True, clean=True)
        doc.close()
        h = huella
        ruta = f"obras/{obra_id}/pdf/{archivo}"
        gh.subir_archivo(cfg, ruta, datos, f"PDF {archivo} de {nombre}", gh.sha_de(cfg, ruta))
        hashes[archivo] = h
        subidos.append(archivo)
    return hashes, subidos


def publicar_jornadas(cfg: dict, obra_id: str, obra: dict, hash_previo: str | None) -> str:
    """Publica obras/<id>/jornadas.json (la lista de jornadas de la obra) para que el
    celular la lea. Es chica y sólo se sube si cambió. Devuelve la huella vigente."""
    import hashlib
    cuerpo = json.dumps(obra.get("jornadas") or [], ensure_ascii=False, sort_keys=True)
    h = hashlib.sha256(cuerpo.encode("utf-8")).hexdigest()
    if h != hash_previo:
        ruta = f"obras/{obra_id}/jornadas.json"
        gh.subir_archivo(cfg, ruta, cuerpo.encode("utf-8"), "Jornadas de la obra", gh.sha_de(cfg, ruta))
    return h


def sincronizar_jornadas(cfg: dict) -> dict:
    """Jornadas cargadas desde el celular: cada una llega en su propio archivo
    (obras/<id>/jornadas_movil/<id>.json, así nunca chocan). Se ingresan a la
    obra de esta PC y se borran de la bandeja; además se publica jornadas.json
    de cada obra para que el celular vea la lista al día. Una obra que esta PC
    no tiene completa (sólo el resumen) se deja como está: sus jornadas esperan
    en la bandeja hasta que se baje."""
    from . import config as cfgmod, jornadas as jor_mod
    ids, _ = gh.listar_obras(cfg)
    nuevas = 0
    for oid in ids:
        obra = almacen.leer_obra(oid)
        if obra is None:
            continue
        try:
            items = gh._contenido(cfg, f"obras/{oid}/jornadas_movil")
        except gh.ErrorSync as e:
            if e.codigo != 404:
                raise
            items = []
        entradas = []
        for it in items if isinstance(items, list) else []:
            if it.get("type") != "file" or not it.get("name", "").endswith(".json"):
                continue
            j, sha = gh.bajar_archivo(cfg, it["path"])
            if j is not None and jor_mod.ingerir(obra, j):
                nuevas += 1
            entradas.append((it["path"], sha))
        if entradas:
            usuario = cfgmod.leer_config().get("usuario", "")
            almacen.guardar_obra(obra, usuario, modulo="Jornadas", resumen="Ingresó jornadas cargadas desde el celular")
            for ruta, sha in entradas:                # ya están en la obra: salen de la bandeja
                if sha:
                    gh.borrar_archivo(cfg, ruta, sha, "Jornada ya ingresada en la PC")
        est = almacen.leer_sync(oid)
        h = publicar_jornadas(cfg, oid, obra, est.get("jornadasHash"))
        if h != est.get("jornadasHash"):
            almacen.guardar_sync(oid, {**est, "jornadasHash": h})
    return {"jornadasNuevas": nuevas}


def sincronizar_stock(cfg: dict) -> dict:
    """Stock propio <-> celular. La PC es la dueña de los datos: el celular
    sólo AGREGA movimientos, cada uno en su propio archivo (stock/movil/<id>.json,
    así nunca chocan entre sí ni con la PC). Acá se (1) ingresan al stock local
    y se borran del repo, y (2) se publica stock/estado.json -- el catálogo y
    todos los movimientos -- para que el celular lo lea."""
    from . import stock as stock_mod
    datos = stock_mod.leer()
    nuevos = 0
    try:
        items = gh._contenido(cfg, "stock/movil")
    except gh.ErrorSync as e:
        if e.codigo != 404:
            raise
        items = []
    for it in items if isinstance(items, list) else []:
        if it.get("type") != "file" or not it.get("name", "").endswith(".json"):
            continue
        mov, sha = gh.bajar_archivo(cfg, it["path"])
        if mov is not None and stock_mod.ingerir(datos, mov):
            nuevos += 1
        if sha:                                   # ya entró (o no sirve): sale de la bandeja
            gh.borrar_archivo(cfg, it["path"], sha, "Movimiento de stock ya ingresado en la PC")
    if nuevos:
        stock_mod.guardar(datos)
    ruta = "stock/estado.json"
    gh.subir_archivo(cfg, ruta, json.dumps(stock_mod.estado_publico(datos), ensure_ascii=False).encode("utf-8"),
                     "Estado del stock propio", gh.sha_de(cfg, ruta))
    return {"nuevosDelCelular": nuevos, "movimientos": len(datos["movimientos"])}


def borrar_obra_remota(cfg: dict, obra_id: str) -> dict:
    """Borra del repositorio todo lo que se subió de esta obra (obra.json,
    resumen.json y lo que haya adentro de su carpeta). No toca nada local
    -- de eso se encarga almacen.borrar_obra() aparte."""
    borrados = gh.borrar_carpeta(cfg, f"obras/{obra_id}", f"Borra la obra {obra_id} del repositorio")
    return {"ok": True, "borrados": borrados}


# --------------------------------------------------------------- bloqueo
# "Semáforo" para que dos personas no editen la misma obra a la vez: un
# archivo lock.json en la carpeta de la obra del repositorio (la única
# verdad compartida entre máquinas, ya que no hay un servidor central). Es
# un bloqueo blando: vence solo si nadie manda latido por LOCK_TTL_MIN, y
# se puede forzar -- no hay forma de garantizar exclusión real entre
# equipos que pueden estar sin conexión, así que esto es la mejor
# aproximación práctica. El respaldo real contra pisadas sigue siendo la
# verificación de sha en subir_obra().
LOCK_TTL_MIN = 20


def _vencido(lock: dict) -> bool:
    latido = lock.get("latido") or lock.get("desde") or 0
    return (C.ahora() - latido) > LOCK_TTL_MIN * 60 * 1000


def _ruta_lock(obra_id: str) -> str:
    return f"obras/{obra_id}/lock.json"


def estado_lock(cfg: dict, obra_id: str) -> dict:
    """Sólo consulta, no toma ni libera nada."""
    if not cfg.get("repo") or not cfg.get("token"):
        return {"bloqueada": False}
    lock, _ = gh.bajar_archivo(cfg, _ruta_lock(obra_id))
    if not lock or _vencido(lock):
        return {"bloqueada": False}
    return {"bloqueada": True, **lock}


def tomar_lock(cfg: dict, obra_id: str, usuario: str, maquina: str, forzar: bool = False) -> dict:
    """Sin repositorio configurado no hay con quién coordinarse: se deja
    editar directamente (mismo criterio que subir/bajar, que ya requieren
    repo)."""
    if not cfg.get("repo") or not cfg.get("token"):
        return {"ok": True, "sinRepo": True}
    ruta = _ruta_lock(obra_id)
    actual, sha = gh.bajar_archivo(cfg, ruta)
    if actual and not _vencido(actual) and actual.get("usuario") != usuario and not forzar:
        return {"ok": False, **actual}
    ahora = C.ahora()
    desde = actual.get("desde", ahora) if (actual and actual.get("usuario") == usuario) else ahora
    nuevo = {"usuario": usuario, "maquina": maquina, "desde": desde, "latido": ahora}
    gh.subir_archivo(cfg, ruta, json.dumps(nuevo, ensure_ascii=False).encode("utf-8"),
                     f"Bloquea {obra_id} para edición ({usuario})", sha)
    return {"ok": True}


def latido_lock(cfg: dict, obra_id: str, usuario: str) -> dict:
    """Refresca el vencimiento -- sólo si el lock sigue siendo mío (si otro
    lo forzó mientras tanto, no lo piso de vuelta con un latido viejo)."""
    if not cfg.get("repo") or not cfg.get("token"):
        return {"ok": True}
    ruta = _ruta_lock(obra_id)
    actual, sha = gh.bajar_archivo(cfg, ruta)
    if not actual or actual.get("usuario") != usuario:
        return {"ok": False}
    actual["latido"] = C.ahora()
    gh.subir_archivo(cfg, ruta, json.dumps(actual, ensure_ascii=False).encode("utf-8"),
                     f"Late el bloqueo de {obra_id} ({usuario})", sha)
    return {"ok": True}


def liberar_lock(cfg: dict, obra_id: str, usuario: str) -> dict:
    if not cfg.get("repo") or not cfg.get("token"):
        return {"ok": True}
    ruta = _ruta_lock(obra_id)
    actual, sha = gh.bajar_archivo(cfg, ruta)
    if actual and sha and actual.get("usuario") == usuario:
        gh.borrar_archivo(cfg, ruta, sha, f"Libera el bloqueo de {obra_id} ({usuario})")
    return {"ok": True}
