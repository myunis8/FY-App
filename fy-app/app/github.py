"""Sincronizacion con un repo privado de GitHub. Sin dependencias externas.

Estructura en el repo:
    obras/<obra_id>/obra.json
    obras/<obra_id>/resumen.json
    obras/<obra_id>/<plano>.pdf

No hay ningun archivo compartido entre obras: por eso dos personas trabajando
en obras distintas nunca chocan.
"""
from __future__ import annotations
import base64, json, urllib.error, urllib.request

API = "https://api.github.com"


class ErrorSync(Exception):
    def __init__(self, mensaje, codigo=None, conflicto=False):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo
        self.conflicto = conflicto


def _pedir(cfg: dict, ruta: str, metodo="GET", cuerpo=None):
    if not cfg.get("repo"):
        raise ErrorSync("Todavía no configuraste el repositorio.")
    if not cfg.get("token"):
        raise ErrorSync("Todavía no cargaste el token de acceso.")
    url = ruta if ruta.startswith("http") else f"{API}{ruta}"
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(url, data=datos, method=metodo)
    req.add_header("Authorization", f"Bearer {cfg['token']}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if datos:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            crudo = r.read()
            return json.loads(crudo) if crudo else {}
    except urllib.error.HTTPError as e:
        detalle = ""
        try:
            detalle = json.loads(e.read()).get("message", "")
        except Exception:
            pass
        if e.code == 401:
            raise ErrorSync("El token no es válido o venció.", 401)
        if e.code == 403:
            raise ErrorSync(
                "El token puede leer el repositorio pero no escribir en él. "
                "En GitHub: Settings → Developer settings → Personal access tokens → "
                "Fine-grained tokens → tu token → Repository permissions → "
                "Contents: Read and write. Después volvé a pegar el token acá.", 403)
        if e.code == 404:
            raise ErrorSync("No se encontró el repositorio o la ruta.", 404)
        if e.code == 409:
            raise ErrorSync("La obra cambió en el repositorio desde que la abriste.",
                            409, conflicto=True)
        if e.code == 422 and "does not match" in detalle:
            raise ErrorSync("La obra cambió en el repositorio desde que la abriste.",
                            409, conflicto=True)
        raise ErrorSync(f"GitHub respondió {e.code}. {detalle}".strip(), e.code)
    except urllib.error.URLError:
        raise ErrorSync("Sin conexión con GitHub.")


ARCHIVO_PRUEBA = ".fy-app/conexion.json"


def verificar(cfg: dict, probar_escritura: bool = True) -> dict:
    """Comprueba el acceso real al repositorio.

    Ojo: el bloque `permissions` que devuelve GitHub refleja tu rol en el
    repositorio (sos el dueño), NO los permisos del token fine-grained. Un
    token de sólo lectura sobre tu propio repo igual informa push: true.
    Por eso la única verificación confiable es intentar escribir.
    """
    info = _pedir(cfg, f"/repos/{cfg['repo']}")
    datos = {
        "repo": info.get("full_name"),
        "privado": info.get("private", True),
        "ramaPorDefecto": info.get("default_branch") or "main",
        "vacio": bool(info.get("size", 0) == 0),
        "puedeLeer": True,
    }
    if not probar_escritura:
        datos["puedeEscribir"] = None
        datos["perfil"] = "desconocido"
        return datos

    try:
        contenido = json.dumps({"app": "FY Manager",
                                "prueba": "acceso de escritura"}).encode()
        sha = sha_de(cfg, ARCHIVO_PRUEBA)
        subir_archivo(cfg, ARCHIVO_PRUEBA, contenido,
                      "Prueba de conexión de FY Manager", sha)
        datos["puedeEscribir"] = True
        datos["perfil"] = "editor"
    except ErrorSync as e:
        if e.codigo == 403:
            datos["puedeEscribir"] = False
            datos["perfil"] = "lector"
            datos["motivo"] = e.mensaje
        else:
            raise
    return datos


def _contenido(cfg: dict, ruta: str):
    return _pedir(cfg, f"/repos/{cfg['repo']}/contents/{ruta}?ref={cfg.get('rama','main')}")


def listar_obras(cfg: dict) -> tuple[list[str], bool]:
    """Devuelve (ids, existe_carpeta). Distinguir el caso 'todavía no hay
    ninguna obra subida' del caso 'la rama o el repo están mal' evita que la
    sincronización parezca exitosa cuando en realidad no encontró nada."""
    try:
        items = _contenido(cfg, "obras")
    except ErrorSync as e:
        if e.codigo == 404:
            return [], False
        raise
    return [i["name"] for i in items if i.get("type") == "dir"], True


def bajar_archivo(cfg: dict, ruta: str) -> tuple[dict | None, str | None]:
    try:
        r = _contenido(cfg, ruta)
    except ErrorSync as e:
        if e.codigo == 404:
            return None, None
        raise
    crudo = base64.b64decode(r.get("content", "")).decode("utf-8")
    return json.loads(crudo), r.get("sha")


def subir_archivo(cfg: dict, ruta: str, contenido: bytes, mensaje: str,
                  sha: str | None = None) -> str:
    cuerpo = {"message": mensaje,
              "content": base64.b64encode(contenido).decode(),
              "branch": cfg.get("rama", "main")}
    if sha:
        cuerpo["sha"] = sha
    r = _pedir(cfg, f"/repos/{cfg['repo']}/contents/{ruta}", "PUT", cuerpo)
    return (r.get("content") or {}).get("sha", "")


def sha_de(cfg: dict, ruta: str) -> str | None:
    try:
        r = _contenido(cfg, ruta)
    except ErrorSync as e:
        if e.codigo == 404:
            return None
        raise
    return r.get("sha")


def borrar_archivo(cfg: dict, ruta: str, sha: str, mensaje: str) -> None:
    _pedir(cfg, f"/repos/{cfg['repo']}/contents/{ruta}", "DELETE",
          {"message": mensaje, "sha": sha, "branch": cfg.get("rama", "main")})


def borrar_carpeta(cfg: dict, ruta: str, mensaje: str) -> int:
    """Borra recursivamente todos los archivos bajo `ruta`. La API de
    Contents no tiene "borrar carpeta": una carpeta deja de existir en git
    cuando se borra su último archivo, así que hay que borrar uno por uno.
    Devuelve cuántos archivos borró (0 si la carpeta no existía)."""
    try:
        items = _contenido(cfg, ruta)
    except ErrorSync as e:
        if e.codigo == 404:
            return 0
        raise
    borrados = 0
    for it in items:
        if it.get("type") == "dir":
            borrados += borrar_carpeta(cfg, it["path"], mensaje)
        elif it.get("type") == "file":
            borrar_archivo(cfg, it["path"], it["sha"], mensaje)
            borrados += 1
    return borrados
