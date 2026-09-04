"""Servidor local. Sirve la interfaz y expone la API sobre el almacen."""
from __future__ import annotations
import json, mimetypes, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import (almacen, config as cfgmod, contrato as C, canalizacion as canal_mod, extraccion, github as gh,
               materiales as mat_mod, pdf_informe, pdf_materiales, pdf_presupuesto, pdf_routeo, pdf_tablero,
               precios as precios_mod, presupuesto as pres_mod, sync, tablero as tablero_mod, vinculos)

if getattr(sys, "frozen", False):
    DIR_WEB = Path(sys._MEIPASS) / "web"        # bundle de PyInstaller
else:
    DIR_WEB = Path(__file__).resolve().parent.parent / "web"


class Handler(BaseHTTPRequestHandler):
    server_version = "FY Manager"

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
            if len(partes) == 4 and partes[:2] == ["api", "obras"] and partes[3] == "seguimiento":
                return self._actualizar_seguimiento(partes[2])
            if len(partes) == 4 and partes[:3] == ["api", "config", "imagen"]:
                return self._subir_imagen(partes[3])
            if len(partes) == 4 and partes[:2] == ["api", "obras"] and partes[3] == "tableros":
                return self._nuevo_tablero(partes[2])
            if len(partes) == 4 and partes[:2] == ["api", "obras"] and partes[3] == "canalizacion":
                return self._guardar_canalizacion(partes[2])
            if len(partes) == 6 and partes[:2] == ["api", "obras"] and partes[3] == "tableros" and partes[5] == "mover":
                return self._mover_dispositivo(partes[2], partes[4])
            if len(partes) == 6 and partes[:2] == ["api", "obras"] and partes[3] == "tableros" and partes[5] == "dispositivos":
                return self._agregar_dispositivo(partes[2], partes[4])
            if len(partes) == 6 and partes[:2] == ["api", "obras"] and partes[3] == "tableros" and partes[5] == "peine":
                return self._crear_peine(partes[2], partes[4])
            if len(partes) == 6 and partes[:2] == ["api", "obras"] and partes[3] == "tableros" and partes[5] == "conector-peine":
                return self._crear_conector_peine(partes[2], partes[4])
            if len(partes) == 6 and partes[:2] == ["api", "obras"] and partes[3] == "tableros" and partes[5] == "canos":
                return self._agregar_entrada_cano(partes[2], partes[4])
            if len(partes) == 7 and partes[:2] == ["api", "obras"] and partes[3] == "tableros" and partes[5] == "canos":
                return self._editar_entrada_cano(partes[2], partes[4], partes[6])
            if len(partes) == 8 and partes[:2] == ["api", "obras"] and partes[3] == "tableros" and partes[5] == "canos" and partes[7] == "mover":
                return self._mover_entrada_cano(partes[2], partes[4], partes[6])
            if len(partes) == 6 and partes[:2] == ["api", "obras"] and partes[3] == "tableros" and partes[5] == "cables":
                return self._crear_cable(partes[2], partes[4])
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
        if len(partes) == 7 and partes[:2] == ["api", "obras"] and partes[3] == "tableros" and partes[5] == "conexiones":
            obra = almacen.leer_obra(partes[2])
            if obra is None:
                return self._error("Esa obra no está en este equipo.", 404)
            t = next((x for x in obra.get("tableros") or [] if x["id"] == partes[4]), None)
            if t is None:
                return self._error("Ese tablero no existe.", 404)
            t.setdefault("conexiones", [])
            ok = tablero_mod.eliminar_conexion(t, partes[6])
            almacen.guardar_obra(obra, cfgmod.leer_config().get("usuario", ""))
            return self._json({"ok": ok})
        if len(partes) == 7 and partes[:2] == ["api", "obras"] and partes[3] == "tableros" and partes[5] == "canos":
            obra = almacen.leer_obra(partes[2])
            if obra is None:
                return self._error("Esa obra no está en este equipo.", 404)
            t = next((x for x in obra.get("tableros") or [] if x["id"] == partes[4]), None)
            if t is None:
                return self._error("Ese tablero no existe.", 404)
            t.setdefault("canos", []); t.setdefault("cables", [])
            ok = tablero_mod.eliminar_entrada_cano(t, partes[6])
            almacen.guardar_obra(obra, cfgmod.leer_config().get("usuario", ""))
            return self._json({"ok": ok})
        if len(partes) == 7 and partes[:2] == ["api", "obras"] and partes[3] == "tableros" and partes[5] == "cables":
            obra = almacen.leer_obra(partes[2])
            if obra is None:
                return self._error("Esa obra no está en este equipo.", 404)
            t = next((x for x in obra.get("tableros") or [] if x["id"] == partes[4]), None)
            if t is None:
                return self._error("Ese tablero no existe.", 404)
            t.setdefault("cables", [])
            ok = tablero_mod.eliminar_cable(t, partes[6])
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
        if ruta == "/api/materiales":
            return self._json(mat_mod.leer())
        if len(partes) == 4 and partes[:2] == ["api", "obras"] and partes[3] == "canalizacion":
            obra = almacen.leer_obra(partes[2])
            if obra is None:
                return self._error("Esa obra no está en este equipo.", 404)
            proyecto = canal_mod.leer_proyecto(obra)
            return self._json({
                "proyecto": proyecto,
                "circuitos": canal_mod.circuitos_para_canaliza(obra),
                "nodos": canal_mod.nodos_para_canaliza(obra),
                "pxPerM": canal_mod.pxpermetro_para_canaliza(obra),
                "planoUrl": (f"/api/obras/{partes[2]}/plano.png?zoom={canal_mod.ZOOM_PLANO}"
                            if (obra.get("plano") or {}).get("referencia") else None),
            })
        if len(partes) == 4 and partes[:2] == ["api", "obras"] and partes[3] == "materiales":
            obra = almacen.leer_obra(partes[2])
            if obra is None:
                return self._error("Esa obra no está en este equipo.", 404)
            return self._json({
                "catalogo": mat_mod.leer(),
                "obra": obra.get("materiales") or {"extras": [], "cables": []},
                "cajas": mat_mod.computar_cajas(obra),
                "tableros": mat_mod.computar_tableros(obra),
                "generales": mat_mod.computar_generales(obra),
                "termicas": mat_mod.computar_termicas(obra),
                "jabalina": mat_mod.computar_jabalina(obra),
                "canalizacion": mat_mod.computar_canalizacion(obra),
            })
        if len(partes) == 4 and partes[:2] == ["api", "obras"] and partes[3] == "verificaciones":
            obra = almacen.leer_obra(partes[2])
            if obra is None:
                return self._error("Esa obra no está en este equipo.", 404)
            return self._json(mat_mod.computar_verificaciones(obra))
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
        if len(partes) == 4 and partes[:2] == ["api", "obras"] and partes[3] == "informe.pdf":
            return self._pdf_informe(partes[2], urlparse(self.path).query)
        if len(partes) == 4 and partes[:2] == ["api", "obras"] and partes[3] == "materiales.pdf":
            return self._pdf_materiales(partes[2], urlparse(self.path).query)
        if (len(partes) == 6 and partes[:2] == ["api", "obras"] and partes[3] == "tableros"
                and partes[5] == "pdf"):
            return self._pdf_tablero(partes[2], partes[4])
        if (len(partes) == 6 and partes[:2] == ["api", "obras"] and partes[3] == "tableros"
                and partes[5] == "unifilar.pdf"):
            return self._pdf_tablero_unifilar(partes[2], partes[4])
        if len(partes) == 4 and partes[:2] == ["api", "obras"] and partes[3] == "tableros.pdf":
            return self._pdf_tableros_todos(partes[2])
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
        if ruta == "/api/materiales":
            return self._json(mat_mod.guardar(cuerpo))

        if len(partes) == 4 and partes[:2] == ["api", "obras"] and partes[3] == "presupuesto":
            obra = almacen.leer_obra(partes[2])
            if obra is None:
                return self._error("Esa obra no está en este equipo.", 404)
            pres = cuerpo.get("presupuesto")
            if pres is not None:
                obra["presupuesto"] = pres
            if cuerpo.get("recalcularCantidades"):
                sug, avisos_precios = pres_mod.sugerir_items(obra)
                previos = {i.get("clave"): i for i in (obra["presupuesto"].get("items") or [])}
                for it in sug:                       # conserva precios ya congelados
                    viejo = previos.get(it["clave"])
                    if viejo and viejo.get("congelado"):
                        it["precioUnitario"] = viejo["precioUnitario"]
                        it["congelado"] = True
                # los items que el usuario agregó a mano (tableros, PAT, lo
                # que sea que no se cuenta solo desde el plano) no tienen
                # origen "computo" -- se conservan tal cual, igual que ya se
                # hace con los extras cargados a mano
                items_manuales = [i for i in (obra["presupuesto"].get("items") or [])
                                  if i.get("origen") != "computo"]
                obra["presupuesto"]["items"] = items_manuales + sug
                obra["presupuesto"]["avisosPrecios"] = avisos_precios

                # elementos marcados "fuera del presupuesto original" (ver
                # circuitos.html): van a extras, no a items, y se recalculan
                # de la misma forma -- sin pisar los extras que el usuario
                # haya cargado a mano, que no tienen este origen
                sug_extra, avisos_extra = pres_mod.sugerir_items(obra, extra=True)
                extras_previos = {i.get("clave"): i for i in (obra["presupuesto"].get("extras") or [])}
                for it in sug_extra:
                    viejo = extras_previos.get(it["clave"])
                    if viejo and viejo.get("congelado"):
                        it["precioUnitario"] = viejo["precioUnitario"]
                        it["congelado"] = True
                extras_manuales = [i for i in (obra["presupuesto"].get("extras") or [])
                                   if i.get("origen") != "computo_extra"]
                obra["presupuesto"]["extras"] = extras_manuales + sug_extra
                obra["presupuesto"]["avisosPreciosExtra"] = avisos_extra
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
                "cantidadesExtra": pres_mod.cantidades(obra, extra=True),
                "totales": pres_mod.totales(obra.get("presupuesto") or {}),
                "comparacion": precios_mod.comparar(
                    (obra.get("presupuesto") or {}).get("items") or []),
            })

        if len(partes) == 4 and partes[:2] == ["api", "obras"] and partes[3] == "materiales":
            obra = almacen.leer_obra(partes[2])
            if obra is None:
                return self._error("Esa obra no está en este equipo.", 404)
            mat = cuerpo.get("materiales")
            if mat is not None:
                obra["materiales"] = mat
            if cuerpo.get("recalcularComputo"):
                obra["materiales"] = mat_mod.actualizar_computo_obra(obra, obra.get("materiales") or {})
            if cuerpo.get("guardar"):
                almacen.guardar_obra(obra, cfg.get("usuario", ""))
            return self._json({
                "ok": True,
                "materiales": obra.get("materiales") or {"extras": [], "cables": []},
                "cajas": mat_mod.computar_cajas(obra),
                "tableros": mat_mod.computar_tableros(obra),
                "generales": mat_mod.computar_generales(obra),
                "termicas": mat_mod.computar_termicas(obra),
                "jabalina": mat_mod.computar_jabalina(obra),
                "canalizacion": mat_mod.computar_canalizacion(obra),
            })

        if len(partes) == 4 and partes[:2] == ["api", "obras"] and partes[3] == "routeo.pdf":
            return self._pdf_routeo(partes[2], cuerpo)

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

        if len(partes) == 4 and partes[:3] == ["api", "sync", "borrar"]:
            return self._json(sync.borrar_obra_remota(cfg, partes[3]))

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

    def _actualizar_seguimiento(self, obra_id):
        obra = almacen.leer_obra(obra_id)
        if obra is None:
            return self._error("Esa obra no está en este equipo.", 404)
        cuerpo = self._cuerpo() or {}
        pago = cuerpo.get("pago") or {}
        seg = C.actualizar_seguimiento(obra, estado=cuerpo.get("estado"),
                                       pago_estado=pago.get("estado"),
                                       pago_porcentaje=pago.get("porcentaje"),
                                       usuario=cfgmod.leer_config().get("usuario", ""))
        almacen.guardar_obra(obra, cfgmod.leer_config().get("usuario", ""))
        return self._json({"ok": True, "seguimiento": seg})

    def _guardar_canalizacion(self, obra_id):
        obra = almacen.leer_obra(obra_id)
        if obra is None:
            return self._error("Esa obra no está en este equipo.", 404)
        cuerpo = self._cuerpo()
        # formato nuevo: {"proyecto": <lo que produce Canaliza>, "reasignaciones": [...]}
        # se mantiene compatible con el formato viejo (el proyecto directo, sin envolver)
        if isinstance(cuerpo, dict) and "proyecto" in cuerpo:
            proyecto, reasignaciones = cuerpo.get("proyecto"), cuerpo.get("reasignaciones") or []
        else:
            proyecto, reasignaciones = cuerpo, []
        canal_mod.guardar_proyecto(obra, proyecto)
        if canal_mod.aplicar_reasignaciones(obra, reasignaciones):
            obra["validacion"] = vinculos.recalcular(obra)
        almacen.guardar_obra(obra, cfgmod.leer_config().get("usuario", ""))
        return self._json({"ok": True})

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
        reclamar = len(obra.get("tableros") or []) == 1
        tablero_mod.sincronizar_circuitos(t, obra.get("circuitos") or [], t.get("fases", 1),
                                          reclamar_sueltos=reclamar)
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

    def _crear_peine(self, obra_id, tablero_id):
        obra = almacen.leer_obra(obra_id)
        if obra is None:
            return self._error("Esa obra no está en este equipo.", 404)
        t = next((x for x in obra.get("tableros") or [] if x["id"] == tablero_id), None)
        if t is None:
            return self._error("Ese tablero no existe.", 404)
        t.setdefault("conexiones", [])
        cuerpo = self._cuerpo()
        peine, msg = tablero_mod.crear_peine(t, cuerpo.get("piso"), cuerpo.get("desde"), cuerpo.get("hasta"))
        if peine is None:
            return self._error(msg)
        almacen.guardar_obra(obra, cfgmod.leer_config().get("usuario", ""))
        return self._json({"ok": True, "peine": peine, "tablero": t})

    def _crear_conector_peine(self, obra_id, tablero_id):
        obra = almacen.leer_obra(obra_id)
        if obra is None:
            return self._error("Esa obra no está en este equipo.", 404)
        t = next((x for x in obra.get("tableros") or [] if x["id"] == tablero_id), None)
        if t is None:
            return self._error("Ese tablero no existe.", 404)
        t.setdefault("conexiones", [])
        cuerpo = self._cuerpo()
        conector, msg = tablero_mod.crear_conector_peine(
            t, cuerpo.get("peineId"), cuerpo.get("posicion"),
            cuerpo.get("polaridad", "fase"), cuerpo.get("carga", "superior"))
        if conector is None:
            return self._error(msg)
        almacen.guardar_obra(obra, cfgmod.leer_config().get("usuario", ""))
        return self._json({"ok": True, "conector": conector, "tablero": t})

    def _agregar_entrada_cano(self, obra_id, tablero_id):
        obra = almacen.leer_obra(obra_id)
        if obra is None:
            return self._error("Esa obra no está en este equipo.", 404)
        t = next((x for x in obra.get("tableros") or [] if x["id"] == tablero_id), None)
        if t is None:
            return self._error("Ese tablero no existe.", 404)
        t.setdefault("canos", []); t.setdefault("cables", [])
        cuerpo = self._cuerpo()
        circ = next((c for c in obra.get("circuitos") or [] if c["id"] == cuerpo.get("circuitoId")), None)
        cano, msg = tablero_mod.agregar_entrada_cano(t, cuerpo.get("lado"), cuerpo.get("tipo"),
                                                     cuerpo.get("circuitoId"),
                                                     circ.get("tipo") if circ else None)
        if cano is None:
            return self._error(msg)
        almacen.guardar_obra(obra, cfgmod.leer_config().get("usuario", ""))
        return self._json({"ok": True, "cano": cano, "tablero": t})

    def _editar_entrada_cano(self, obra_id, tablero_id, cano_id):
        obra = almacen.leer_obra(obra_id)
        if obra is None:
            return self._error("Esa obra no está en este equipo.", 404)
        t = next((x for x in obra.get("tableros") or [] if x["id"] == tablero_id), None)
        if t is None:
            return self._error("Ese tablero no existe.", 404)
        cuerpo = self._cuerpo()
        circ = next((c for c in obra.get("circuitos") or [] if c["id"] == cuerpo.get("circuitoId")), None)
        cano, msg = tablero_mod.editar_entrada_cano(t, cano_id, cuerpo.get("tipo"),
                                                    cuerpo.get("circuitoId"),
                                                    circ.get("tipo") if circ else None)
        if cano is None:
            return self._error(msg)
        almacen.guardar_obra(obra, cfgmod.leer_config().get("usuario", ""))
        return self._json({"ok": True, "cano": cano, "tablero": t})

    def _mover_entrada_cano(self, obra_id, tablero_id, cano_id):
        obra = almacen.leer_obra(obra_id)
        if obra is None:
            return self._error("Esa obra no está en este equipo.", 404)
        t = next((x for x in obra.get("tableros") or [] if x["id"] == tablero_id), None)
        if t is None:
            return self._error("Ese tablero no existe.", 404)
        cuerpo = self._cuerpo()
        ok, msg = tablero_mod.mover_entrada_cano(t, cano_id, int(cuerpo.get("direccion", 1)))
        if not ok:
            return self._error(msg)
        almacen.guardar_obra(obra, cfgmod.leer_config().get("usuario", ""))
        return self._json({"ok": True, "tablero": t})

    def _crear_cable(self, obra_id, tablero_id):
        obra = almacen.leer_obra(obra_id)
        if obra is None:
            return self._error("Esa obra no está en este equipo.", 404)
        t = next((x for x in obra.get("tableros") or [] if x["id"] == tablero_id), None)
        if t is None:
            return self._error("Ese tablero no existe.", 404)
        t.setdefault("cables", [])
        cuerpo = self._cuerpo()
        cable, msg = tablero_mod.crear_cable(t, cuerpo.get("origen"), cuerpo.get("destino"),
                                            cuerpo.get("ruta"))
        if cable is None:
            return self._error(msg)
        almacen.guardar_obra(obra, cfgmod.leer_config().get("usuario", ""))
        return self._json({"ok": True, "cable": cable, "tablero": t})

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

    def _pdf_tablero(self, obra_id, tablero_id):
        obra = almacen.leer_obra(obra_id)
        if obra is None:
            return self._error("Esa obra no está en este equipo.", 404)
        t = next((x for x in obra.get("tableros") or [] if x["id"] == tablero_id), None)
        if t is None:
            return self._error("Ese tablero no existe.", 404)
        try:
            datos = pdf_tablero.generar(t, obra)
        except Exception as e:
            return self._error(f"No pude generar el PDF: {e}", 500)
        nombre = (t.get("nombre") or "tablero").replace(" ", "_")
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Content-Disposition", f'inline; filename="{nombre}.pdf"')
        self.end_headers()
        self.wfile.write(datos)

    def _pdf_tablero_unifilar(self, obra_id, tablero_id):
        obra = almacen.leer_obra(obra_id)
        if obra is None:
            return self._error("Esa obra no está en este equipo.", 404)
        t = next((x for x in obra.get("tableros") or [] if x["id"] == tablero_id), None)
        if t is None:
            return self._error("Ese tablero no existe.", 404)
        try:
            datos = pdf_tablero.generar_unifilar(t, obra)
        except Exception as e:
            return self._error(f"No pude generar el PDF: {e}", 500)
        nombre = (t.get("nombre") or "tablero").replace(" ", "_") + "_unifilar"
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Content-Disposition", f'inline; filename="{nombre}.pdf"')
        self.end_headers()
        self.wfile.write(datos)

    def _pdf_tableros_todos(self, obra_id):
        obra = almacen.leer_obra(obra_id)
        if obra is None:
            return self._error("Esa obra no está en este equipo.", 404)
        if not obra.get("tableros"):
            return self._error("Esta obra todavía no tiene ningún tablero.", 404)
        try:
            datos = pdf_tablero.generar_todos(obra)
        except Exception as e:
            return self._error(f"No pude generar el PDF: {e}", 500)
        nombre = (obra["obra"].get("nombre") or "obra").replace(" ", "_") + "_tableros"
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Content-Disposition", f'inline; filename="{nombre}.pdf"')
        self.end_headers()
        self.wfile.write(datos)

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

    def _pdf_informe(self, obra_id, query):
        obra = almacen.leer_obra(obra_id)
        if obra is None:
            return self._error("Esa obra no está en este equipo.", 404)
        qs = parse_qs(query)
        pedido = (qs.get("modulos") or [""])[0]
        if pedido:
            modulos = [m for m in pedido.split(",") if m in pdf_informe.MODULOS]
        else:
            modulos = pdf_informe.MODULOS_POR_DEFECTO
        materiales_con_precio = (qs.get("precio") or ["1"])[0] != "0"
        try:
            datos = pdf_informe.generar(obra, modulos, materiales_con_precio=materiales_con_precio)
        except Exception as e:
            return self._error(f"No pude generar el informe: {e}", 500)
        nombre = (obra["obra"].get("nombre") or "informe").replace(" ", "_")
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Content-Disposition", f'inline; filename="{nombre}_informe.pdf"')
        self.end_headers()
        self.wfile.write(datos)

    def _pdf_materiales(self, obra_id, query):
        obra = almacen.leer_obra(obra_id)
        if obra is None:
            return self._error("Esa obra no está en este equipo.", 404)
        qs = parse_qs(query)
        mostrar_precio = (qs.get("precio") or ["1"])[0] != "0"
        try:
            datos = pdf_materiales.generar(obra, mostrar_precio=mostrar_precio)
        except Exception as e:
            return self._error(f"No pude generar la lista de materiales: {e}", 500)
        nombre = (obra["obra"].get("nombre") or "obra").replace(" ", "_") + "_materiales"
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Content-Disposition", f'inline; filename="{nombre}.pdf"')
        self.end_headers()
        self.wfile.write(datos)

    def _pdf_routeo(self, obra_id, cuerpo):
        obra = almacen.leer_obra(obra_id)
        if obra is None:
            return self._error("Esa obra no está en este equipo.", 404)
        proyecto = cuerpo.get("proyecto") or obra.get("canalizacion") or {}
        try:
            datos = pdf_routeo.generar(
                obra, proyecto, cuerpo.get("hojas") or {},
                formato=cuerpo.get("formato", "a4"),
                orientacion=cuerpo.get("orientacion", "landscape"),
                ocultos=cuerpo.get("ocultos"))
        except ValueError as e:
            return self._error(str(e), 400)
        except Exception as e:
            return self._error(f"No pude generar el PDF de Routeo: {e}", 500)
        nombre = (obra["obra"].get("nombre") or "obra").replace(" ", "_") + "_routeo"
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
