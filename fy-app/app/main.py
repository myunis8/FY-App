"""Punto de entrada: levanta el servidor local y abre el navegador."""
from __future__ import annotations
import sys, threading, time, webbrowser
from . import config as cfgmod, server

# tiempo sin latido de ninguna pestaña de la app antes de cerrar el
# servidor solo (ver server.registrar_latido / web/latido.js). Generoso a
# propósito: cubre el arranque del navegador y la primera carga de la
# página sin que se cierre antes de tiempo.
_TIMEOUT_LATIDO_SEG = 40


def _ocultar_consola():
    """En la ventana negra de la consola no queda nada que hacer una vez
    que hay una forma confiable de cerrar la app sola (ver _vigilar_latido)
    -- se oculta del todo en vez de dejarla de fondo. No hace nada fuera de
    Windows. Ojo: corriendo `python -m app.main` desde una terminal ya
    abierta, GetConsoleWindow() devuelve ESA terminal (no una propia) y
    quedaría oculta -- por eso nunca se usa esa forma para probar, sólo el
    .exe empaquetado (console=True en obras.spec), que siempre abre la suya."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)   # SW_HIDE
    except Exception:
        pass


def _vigilar_latido(httpd):
    while True:
        time.sleep(5)
        if server.segundos_sin_latido() > _TIMEOUT_LATIDO_SEG:
            httpd.shutdown()
            return


def main():
    cfgmod.asegurar_carpetas()
    httpd = server.crear(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
    puerto = httpd.server_address[1]
    url = f"http://127.0.0.1:{puerto}/"
    print("FY Manager")
    print(f"  Interfaz: {url}")
    print(f"  Datos:    {cfgmod.DIR_OBRAS}")
    print("  Se cierra sola al cerrar el navegador (o cerrá esta ventana).")
    threading.Timer(0.6, lambda: webbrowser.open(url, new=1)).start()
    threading.Thread(target=_vigilar_latido, args=(httpd,), daemon=True).start()
    _ocultar_consola()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nListo.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
