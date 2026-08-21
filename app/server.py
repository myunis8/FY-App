"""Servidor local. Sirve la interfaz y expone la API sobre el almacen."""
from __future__ import annotations
import json, mimetypes, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import almacen, config as cfgmod, contrato as C, extraccion, github as gh, sync

if getattr(sys, "frozen", False):
    DIR_WEB = Path(sys._MEIPASS) / "web"        # bundle de PyInstaller
else:
    DIR_WEB = Path(__file__).resolve().parent.parent / "web"


class Handler(BaseHTTPRequestHandler):
    server_version = "ObrasElectricas"

    # ------------------------------------------------------------ utilidades
    def _json(self, datos, codigo=200):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _error(self, mensaje, codigo=400, extra=None):
        self._json({"error": mensaje, **(extra or {})}, codigo)

    def _cuerpo(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def log_message(self, *a):
        pass                                    # sin ruido en la consola

    # --------------------------------------------------------------- rutas
    def do_GET(self):
        ruta = urlparse(self.path).path
        if ruta.startswith("/api/"):
            return self._api_get(ruta)
        return self._estatico(ruta)

    def do_POST(self):
        ruta = urlparse(self.path).path
        if not ruta.startswith("/api/"):
            return self._error("Ruta desconocida", 404)
        try:
            partes = [p for p in ruta.split("/") if p]
            if len(partes) == 4 and partes[:2] == ["api", "obras"] and partes[3] == "plano":
                return self._subir_plano(partes[2])
            if len(partes) == 4 and partes[:2] == ["api", "obras"] and partes[3] == "extraer":
                return self._extraer(partes[2])
            return self._api_post(ruta)
        except gh.ErrorSync as e:
            return self._error(e.mensaje, 409 if e.conflicto else 502,
                               {"conflicto": e.conflicto})

    def do_PUT(self):
        ruta = urlparse(self.path).path
        partes = [p for p in ruta.split("/") if p]
        if len(partes) == 3 and partes[:2] == ["api", "obras"]:
            obra = self._cuerpo()
            if not obra:
                return self._error("No llegó ninguna obra para guardar.")
            obra.setdefault("obra", {})["id"] = partes[2]
            guardada = almacen.guardar_obra(obra, cfgmod.leer_config().get("usuario", ""))
            return self._json({"ok": True, "resumen": C.resumen(guardada)})
        return self._error("Ruta desconocida", 404)

    def do_DELETE(self):
        partes = [p for p in urlparse(self.path).path.split("/") if p]
        if len(partes) == 3 and partes[:2] == ["api", "obras"]:
            return self._json({"ok": almacen.borrar_obra(partes[2])})
        return self._error("Ruta desconocida", 404)

    # ----------------------------------------------------------------- API
    def _api_get(self, ruta):
        partes = [p for p in ruta.split("/") if p]
        if ruta == "/api/estado":
            cfg = cfgmod.leer_config()
            return self._json({
                "version": "0.1",
                "contrato": C.CONTRATO,
                "config": cfgmod.config_publica(cfg),
                "carpetaDatos": str(cfgmod.DIR_OBRAS),
                "listoParaSync": bool(cfg.get("repo") and cfg.get("token")),
            })
        if ruta == "/api/obras":
            return self._json({"obras": almacen.listar_resumenes()})
        if len(partes) == 3 and partes[:2] == ["api", "obras"]:
            obra = almacen.leer_obra(partes[2])
            if obra is None:
                return self._error("Esa obra no está en este equipo.", 404)
            return self._json(obra)
        if len(partes) == 4 and partes[:2] == ["api", "obras"] and partes[3] == "plano.png":
            return self._render_plano(partes[2], urlparse(self.path).query)
        if len(partes) == 4 and partes[:2] == ["api", "obras"] and partes[3] == "plano":
            obra = almacen.leer_obra(partes[2])
            nombre = ((obra or {}).get("plano") or {}).get("archivo")
            destino = almacen.ruta_plano(partes[2], nombre) if nombre else None
            if destino is None:
                return self._error("Esta obra todavía no tiene plano.", 404)
            datos = destino.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)
            return
        return self._error("Ruta desconocida", 404)

    def _api_post(self, ruta):
        cuerpo = self._cuerpo()
        cfg = cfgmod.leer_config()
        partes = [p for p in ruta.split("/") if p]

        if ruta == "/api/config":
            nueva = cfgmod.guardar_config(cuerpo)
            return self._json({"ok": True, "config": cfgmod.config_publica(nueva)})

        if ruta == "/api/config/verificar":
            datos = gh.verificar({**cfg, **{k: v for k, v in cuerpo.items() if v}},
                                 probar_escritura=cuerpo.get("probarEscritura", True))
            return self._json(datos)

        if ruta == "/api/obras":
            obra = C.obra_vacia(cuerpo.get("nombre", ""), cuerpo.get("cliente", ""),
                                cfg.get("usuario", ""))
            almacen.guardar_obra(obra)
            return self._json({"ok": True, "obra": obra})

        if ruta == "/api/sync/bajar":
            return self._json(sync.bajar_todo(cfg))

        if len(partes) == 4 and partes[:3] == ["api", "sync", "traer"]:
            return self._json({"ok": True, "obra": sync.traer_obra(cfg, partes[3])})

        if len(partes) == 4 and partes[:3] == ["api", "sync", "subir"]:
            return self._json(sync.subir_obra(cfg, partes[3], bool(cuerpo.get("forzar"))))

        return self._error("Ruta desconocida", 404)

    def _subir_plano(self, obra_id):
        obra = almacen.leer_obra(obra_id)
        if obra is None:
            return self._error("Esa obra no está en este equipo.", 404)
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return self._error("No llegó ningún archivo.")
        if n > 40 * 1024 * 1024:
            return self._error("El PDF supera los 40 MB.", 413)
        datos = self.rfile.read(n)
        if not datos.startswith(b"%PDF"):
            return self._error("El archivo no es un PDF.")
        nombre = unquote(self.headers.get("X-Nombre-Archivo") or "plano.pdf")
        obra["plano"] = almacen.guardar_plano(obra_id, nombre, datos)
        almacen.guardar_obra(obra, cfgmod.leer_config().get("usuario", ""))
        return self._json({"ok": True, "plano": obra["plano"]})

    def _extraer(self, obra_id):
        obra = almacen.leer_obra(obra_id)
        if obra is None:
            return self._error("Esa obra no está en este equipo.", 404)
        cuerpo = self._cuerpo()
        try:
            info = extraccion.ejecutar(obra, cuerpo.get("escalaPtPorMetro"),
                                       cuerpo.get("correcciones"))
        except ValueError as e:
            return self._error(str(e))
        except ImportError:
            return self._error("Falta instalar PyMuPDF y OpenCV para leer planos.", 500)
        except Exception as e:
            return self._error(f"No pude leer el plano: {e}", 500)
        almacen.guardar_obra(obra, cfgmod.leer_config().get("usuario", ""))
        return self._json({"ok": True, "obra": obra, **info})

    def _render_plano(self, obra_id, consulta):
        import io
        obra = almacen.leer_obra(obra_id) or {}
        nombre = (obra.get("plano") or {}).get("archivo")
        ruta = almacen.ruta_plano(obra_id, nombre) if nombre else None
        if ruta is None:
            return self._error("Esta obra todavía no tiene plano.", 404)
        try:
            import pymupdf
        except ImportError:
            return self._error("Falta instalar PyMuPDF.", 500)
        zoom = 2.0
        try:
            zoom = max(0.5, min(4.0, float(parse_qs(consulta).get("zoom", ["2"])[0])))
        except ValueError:
            pass
        doc = pymupdf.open(str(ruta))
        pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        datos = pix.tobytes("png")
        doc.close()
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    # ------------------------------------------------------------ estaticos
    def _estatico(self, ruta):
        if ruta in ("/", ""):
            ruta = "/index.html"
        destino = (DIR_WEB / ruta.lstrip("/")).resolve()
        if not str(destino).startswith(str(DIR_WEB.resolve())) or not destino.is_file():
            self.send_error(404, "No encontrado")
            return
        tipo = mimetypes.guess_type(str(destino))[0] or "application/octet-stream"
        datos = destino.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(datos)


def crear(puerto=0):
    """Puerto 0 = el sistema elige uno libre; evita choques con otras apps."""
    return ThreadingHTTPServer(("127.0.0.1", puerto), Handler)
