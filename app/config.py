"""Rutas de datos y configuracion persistente del usuario."""
from __future__ import annotations
import json, os, sys
from pathlib import Path

APP_NOMBRE = "ObrasElectricas"


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

CONFIG_POR_DEFECTO = {
    "usuario": "",
    "repo": "",            # "usuario/repositorio"
    "token": "",           # PAT fine-grained; nunca se empaqueta en el .exe
    "rama": "main",
    "ultimaSync": 0,
}


def asegurar_carpetas():
    DIR_OBRAS.mkdir(parents=True, exist_ok=True)
    DIR_CONFIG.mkdir(parents=True, exist_ok=True)


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


def config_publica(cfg: dict | None = None) -> dict:
    """La misma config pero sin el token, para mandarla al navegador."""
    cfg = cfg or leer_config()
    return {**{k: v for k, v in cfg.items() if k != "token"},
            "tokenCargado": bool(cfg.get("token"))}
