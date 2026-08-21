"""Servidor local. Sirve la interfaz y expone la API sobre el almacen."""
from __future__ import annotations
import json, mimetypes, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import (almacen, config as cfgmod, contrato as C, extraccion, github as gh,
               pdf_presupuesto, precios as precios_mod, presupuesto as pres_mod,
               sync, tablero as tablero_mod, vinculos)

if getattr(sys, "frozen", False):
    DIR_WEB = Path(sys._MEIPASS) / "web"        # bundle de PyInstaller
else:
    DIR_WEB = Path(__file__).resolve().parent.parent / "web"


class Handler(BaseHTTPRequestHandler):
    server_version = "FY-App"

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
            if len(partes) == 4 and partes[:2] == ["api", "obras"] and partes[3] == "revalidar":
                return self._revalidar(partes[2])
            if len(partes) == 4 and partes[:3] == ["api", "config", "imagen"]:
                return self._subir_imagen(partes[3])
            if len(partes) == 4 and partes[:2] == ["api", "obras"] and partes[3] == "tableros":
                return self._nuevo_tablero(partes[2])
            if len(partes) == 6 and partes[:2] == ["api", "obras"] and partes[3] == "tableros" and partes[5] == "mover":
                return self._mover_dispositivo(partes[2], partes[4])
            if len(partes) == 6 and partes[:2] == ["api", "obras"] and partes[3] == "tableros" and partes[5] == "dispositivos":
                return self._agregar_dispositivo(partes[2], partes[4])
            if len(partes) == 5 and partes[:2] == ["api", "obras"] and partes[3] == "tableros":
                return self._sincronizar_tablero(partes[2], partes[4])
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
        if len(partes) == 7 and partes[:2] == ["api", "obras"] and partes[3] == "tableros" and partes[5] == "dispositivos":
            obra = almacen.leer_obra(partes[2])
            if obra is None:
                return self._error("Esa obra no está en este equipo.", 404)
            t = next((x for x in obra.get("tableros") or [] if x["id"] == partes[4]), None)
            if t is None:
                return self._error("Ese tablero no existe.", 404)
            ok = tablero_mod.eliminar_dispositivo(t, partes[6])
            almacen.guardar_obra(obra, cfgmod.leer_config().get("usuario", ""))
            return self._json({"ok": ok})
        if len(partes) == 5 and partes[:2] == ["api", "obras"] and partes[3] == "tableros":
            obra = almacen.leer_obra(partes[2])
            if obra is None:
                return self._error("Esa obra no está en este equipo.", 404)
            obra["tableros"] = [t for t in obra.get("tableros") or [] if t["id"] != partes[4]]
            # los circuitos que apuntaban a este tablero quedan sin tablero, no se borran
            for c in obra.get("circuitos") or []:
                if c.get("tableroId") == partes[4]:
                    c["tableroId"] = None
            almacen.guardar_obra(obra, cfgmod.leer_config().get("usuario", ""))
            return self._json({"ok": True})
        return self._error("Ruta desconocida", 404)

    # ----------------------------------------------------------------- API
    def _api_get(self, ruta):
        partes = [p for p in ruta.split("/") if p]
        if ruta == "/api/estado":
            cfg = cfgmod.leer_config()
            from . import __version__
            return self._json({
                "version": __version__,
                "contrato": C.CONTRATO,
                "config": cfgmod.config_publica(cfg),
                "carpetaDatos": str(cfgmod.DIR_OBRAS),
                "listoParaSync": bool(cfg.get("repo") and cfg.get("token")),
            })
        if ruta == "/api/obras":
            return self._json({"obras": almacen.listar_resumenes()})
        if ruta == "/api/precios":
            return self._json(precios_mod.leer())
        if ruta == "/api/tablero/presets":
            return self._json({"presets": tablero_mod.PRESETS})
        if len(partes) == 4 and partes[:3] == ["api", "config", "imagen"]:
            destino = cfgmod.ruta_imagen(partes[3])
            if destino is None:
                return self._error("No hay imagen cargada.", 404)
            datos = destino.read_bytes()
            tipo = mimetypes.guess_type(str(destino))[0] or "image/png"
            self.send_response(200)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(datos)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(datos)
            return
        if len(partes) == 3 and partes[:2] == ["api", "obras"]:
            obra = almacen.leer_obra(partes[2])
            if obra is None:
                return self._error("Esa obra no está en este equipo.", 404)
            return self._json(obra)
        if len(partes) == 4 and partes[:2] == ["api", "obras"] and partes[3] == "plano.png":
            return self._render_plano(partes[2], urlparse(self.path).query)
        if len(partes) == 4 and partes[:2] == ["api", "obras"] and partes[3] == "presupuesto.pdf":
            return self._pdf_presupuesto(partes[2])
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

        if ruta == "/api/precios":
            return self._json(precios_mod.guardar(cuerpo))

        if len(partes) == 4 and partes[:2] == ["api", "obras"] and partes[3] == "presupuesto":
            obra = almacen.leer_obra(partes[2])
            if obra is None:
                return self._error("Esa obra no está en este equipo.", 404)
            pres = cuerpo.get("presupuesto")
            if pres is not None:
                obra["presupuesto"] = pres
            if cuerpo.get("recalcularCantidades"):
                sug = pres_mod.sugerir_items(obra)
                previos = {i.get("clave"): i for i in (obra["presupuesto"].get("items") or [])}
                for it in sug:                       # conserva precios ya congelados
                    viejo = previos.get(it["clave"])
                    if viejo and viejo.get("congelado"):
                        it["precioUnitario"] = viejo["precioUnitario"]
                        it["congelado"] = True
                obra["presupuesto"]["items"] = sug
            if cuerpo.get("congelar"):
                pres_mod.congelar(obra, cfg.get("usuario", ""))
                for it in obra["presupuesto"].get("items") or []:
                    it["congelado"] = True
            if cuerpo.get("guardar"):
                almacen.guardar_obra(obra, cfg.get("usuario", ""))
            return self._json({
                "ok": True,
                "presupuesto": obra.get("presupuesto") or {},
                "cantidades": pres_mod.cantidades(obra),
                "totales": pres_mod.totales(obra.get("presupuesto") or {}),
                "comparacion": precios_mod.comparar(
                    (obra.get("presupuesto") or {}).get("items") or []),
            })

        if ruta == "/api/config/verificar":
            datos = gh.verificar({**cfg, **{k: v for k, v in cuerpo.items() if v}},
                                 probar_escritura=cuerpo.get("probarEscritura", True))
            return self._json(datos)

        if ruta == "/api/obras":
            obra = C.obra_vacia(cuerpo.get("nombre", ""), cuerpo.get("cliente", ""),
                                cfg.get("usuario", ""))
            obra["obra"]["sinPlano"] = bool(cuerpo.get("sinPlano"))
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

    def _subir_imagen(self, clave):
        if clave not in cfgmod.IMAGENES:
            return self._error("Imagen desconocida.", 404)
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return self._error("No llegó ninguna imagen.")
        if n > 6 * 1024 * 1024:
            return self._error("La imagen supera los 6 MB.", 413)
        datos = self.rfile.read(n)
        firmas = {b"\x89PNG": ".png", b"\xff\xd8\xff": ".jpg", b"RIFF": ".webp",
                  b"<svg": ".svg", b"<?xm": ".svg"}
        ext = next((v for k, v in firmas.items() if datos.startswith(k)), None)
        if ext is None:
            return self._error("El archivo tiene que ser PNG, JPG, WEBP o SVG.")
        cfgmod.guardar_imagen(clave, datos, ext)
        return self._json({"ok": True, "clave": clave})

    def _revalidar(self, obra_id):
        """Recalcula vínculos y avisos con los elementos que manda el revisor.

        No guarda: el revisor puede pedirlo en cada cambio y decidir después si
        guarda o descarta.
        """
        obra = self._cuerpo() or almacen.leer_obra(obra_id)
        if not obra:
            return self._error("Esa obra no está en este equipo.", 404)
        obra["validacion"] = vinculos.recalcular(obra)
        return self._json({"ok": True, "validacion": obra["validacion"],
                           "elementos": obra.get("elementos") or [],
                           "resumen": vinculos.resumen(obra)})

    def _nuevo_tablero(self, obra_id):
        obra = almacen.leer_obra(obra_id)
        if obra is None:
            return self._error("Esa obra no está en este equipo.", 404)
        cuerpo = self._cuerpo()
        fases = 3 if (cuerpo.get("fases") == 3) else 1
        t = tablero_mod.tablero_nuevo(cuerpo.get("nombre", ""), cuerpo.get("tipo", "principal"),
                                      cuerpo.get("preset", "12"), fases)
        if cuerpo.get("bocas") and cuerpo.get("pisos"):
            t["bocas"] = int(cuerpo["bocas"]); t["pisos"] = int(cuerpo["pisos"])
            t["bocasPorPiso"] = tablero_mod.bocas_por_piso(t["bocas"], t["pisos"])
        obra.setdefault("tableros", []).append(t)
        almacen.guardar_obra(obra, cfgmod.leer_config().get("usuario", ""))
        return self._json({"ok": True, "tablero": t, "obra": obra})

    def _sincronizar_tablero(self, obra_id, tablero_id):
        obra = almacen.leer_obra(obra_id)
        if obra is None:
            return self._error("Esa obra no está en este equipo.", 404)
        t = next((x for x in obra.get("tableros") or [] if x["id"] == tablero_id), None)
        if t is None:
            return self._error("Ese tablero no existe.", 404)
        cuerpo = self._cuerpo()
        if "tablero" in cuerpo:                       # el cliente mandó ediciones (nombre, etc)
            t.update({k: v for k, v in cuerpo["tablero"].items() if k != "dispositivos"})
        tablero_mod.sincronizar_circuitos(t, obra.get("circuitos") or [], t.get("fases", 1))
        avisos = tablero_mod.validar(t, obra.get("circuitos") or [])
        almacen.guardar_obra(obra, cfgmod.leer_config().get("usuario", ""))
        return self._json({"ok": True, "tablero": t, "avisos": avisos})

    def _agregar_dispositivo(self, obra_id, tablero_id):
        obra = almacen.leer_obra(obra_id)
        if obra is None:
            return self._error("Esa obra no está en este equipo.", 404)
        t = next((x for x in obra.get("tableros") or [] if x["id"] == tablero_id), None)
        if t is None:
            return self._error("Ese tablero no existe.", 404)
        cuerpo = self._cuerpo()
        try:
            d = tablero_mod.agregar_dispositivo(t, cuerpo.get("tipo", "termica"), cuerpo)
        except ValueError as e:
            return self._error(str(e))
        almacen.guardar_obra(obra, cfgmod.leer_config().get("usuario", ""))
        return self._json({"ok": True, "dispositivo": d, "tablero": t})

    def _mover_dispositivo(self, obra_id, tablero_id):
        obra = almacen.leer_obra(obra_id)
        if obra is None:
            return self._error("Esa obra no está en este equipo.", 404)
        t = next((x for x in obra.get("tableros") or [] if x["id"] == tablero_id), None)
        if t is None:
            return self._error("Ese tablero no existe.", 404)
        cuerpo = self._cuerpo()
        ok, msg = tablero_mod.mover_dispositivo(t, cuerpo.get("dispositivoId"),
                                                cuerpo.get("piso"), cuerpo.get("posicion"))
        if not ok:
            return self._error(msg, 409)
        avisos = tablero_mod.validar(t, obra.get("circuitos") or [])
        almacen.guardar_obra(obra, cfgmod.leer_config().get("usuario", ""))
        return self._json({"ok": True, "tablero": t, "avisos": avisos})

    def _pdf_presupuesto(self, obra_id):
        obra = almacen.leer_obra(obra_id)
        if obra is None:
            return self._error("Esa obra no está en este equipo.", 404)
        try:
            datos = pdf_presupuesto.generar(obra)
        except Exception as e:
            return self._error(f"No pude generar el PDF: {e}", 500)
        nombre = (obra["obra"].get("nombre") or "presupuesto").replace(" ", "_")
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Content-Disposition", f'inline; filename="{nombre}.pdf"')
        self.end_headers()
        self.wfile.write(datos)

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
