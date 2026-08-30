"""Rutas de datos y configuracion persistente del usuario."""
from __future__ import annotations
import json, os, sys
from pathlib import Path

APP_NOMBRE = "FY Manager"
APP_NOMBRES_ANTERIORES = ["FY-App", "ObrasElectricas"]


def _base_datos() -> Path:
    if sys.platform == "win32":
        raiz = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        raiz = os.path.expanduser("~/Library/Application Support")
    else:
        raiz = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(raiz) / APP_NOMBRE


def _base_config() -> Path:
    if sys.platform == "win32":
        raiz = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        raiz = os.path.expanduser("~/Library/Application Support")
    else:
        raiz = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(raiz) / APP_NOMBRE


DIR_DATOS = Path(os.environ.get("OBRAS_DIR_DATOS") or _base_datos())
DIR_CONFIG = Path(os.environ.get("OBRAS_DIR_CONFIG") or _base_config())
DIR_OBRAS = DIR_DATOS / "obras"
ARCHIVO_CONFIG = DIR_CONFIG / "config.json"
DIR_IMAGENES = DIR_CONFIG / "imagenes"
IMAGENES = {"logo": "logo", "marca": "marca"}     # logo de la empresa y marca de agua

CONFIG_POR_DEFECTO = {
    "usuario": "",
    "repo": "",            # "usuario/repositorio"
    "token": "",           # PAT fine-grained; nunca se empaqueta en el .exe
    "rama": "main",
    "ultimaSync": 0,
    "empresa": "",
    "cuit": "",
    "contacto": "",
    "opacidadMarca": 14,          # % de opacidad de la marca de agua en el PDF
}


def _mudar_datos_viejos():
    """La app tuvo otros nombres antes (ObrasElectricas, después FY-App). Si
    quedaron datos con alguno de esos nombres y todavía no hay nada con el
    nombre nuevo, se mudan solos -- se prueba en orden, del más reciente al
    más viejo, así que no importa desde qué nombre venga alguien."""
    for base, destino in ((_base_datos, DIR_DATOS), (_base_config, DIR_CONFIG)):
        if destino.exists():
            continue
        for nombre_viejo in APP_NOMBRES_ANTERIORES:
            viejo = base().parent / nombre_viejo
            if viejo.is_dir():
                try:
                    viejo.rename(destino)
                except OSError:
                    pass
                break


def asegurar_carpetas():
    _mudar_datos_viejos()
    DIR_OBRAS.mkdir(parents=True, exist_ok=True)
    DIR_CONFIG.mkdir(parents=True, exist_ok=True)
    DIR_IMAGENES.mkdir(parents=True, exist_ok=True)


def leer_config() -> dict:
    asegurar_carpetas()
    if not ARCHIVO_CONFIG.exists():
        return dict(CONFIG_POR_DEFECTO)
    try:
        cfg = json.loads(ARCHIVO_CONFIG.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(CONFIG_POR_DEFECTO)
    return {**CONFIG_POR_DEFECTO, **cfg}


def guardar_config(nueva: dict) -> dict:
    asegurar_carpetas()
    cfg = {**leer_config(), **{k: v for k, v in nueva.items() if k in CONFIG_POR_DEFECTO}}
    ARCHIVO_CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(ARCHIVO_CONFIG, 0o600)      # el token no es de lectura publica
    except OSError:
        pass
    return cfg


def ruta_imagen(clave: str):
    """Devuelve la imagen guardada para 'logo' o 'marca', si existe."""
    if clave not in IMAGENES:
        return None
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".svg"):
        p = DIR_IMAGENES / (IMAGENES[clave] + ext)
        if p.is_file():
            return p
    return None


def guardar_imagen(clave: str, datos: bytes, ext: str):
    asegurar_carpetas()
    vieja = ruta_imagen(clave)
    if vieja:
        try:
            vieja.unlink()
        except OSError:
            pass
    destino = DIR_IMAGENES / (IMAGENES[clave] + ext)
    destino.write_bytes(datos)
    return destino


def config_publica(cfg: dict | None = None) -> dict:
    """La misma config pero sin el token, para mandarla al navegador."""
    cfg = cfg or leer_config()
    return {**{k: v for k, v in cfg.items() if k != "token"},
            "tokenCargado": bool(cfg.get("token")),
            "logoCargado": ruta_imagen("logo") is not None,
            "marcaCargada": ruta_imagen("marca") is not None}
