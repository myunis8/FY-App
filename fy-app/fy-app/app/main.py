"""Punto de entrada: levanta el servidor local y abre el navegador."""
from __future__ import annotations
import sys, threading, webbrowser
from . import config as cfgmod, server


def main():
    cfgmod.asegurar_carpetas()
    httpd = server.crear(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
    puerto = httpd.server_address[1]
    url = f"http://127.0.0.1:{puerto}/"
    print("FY-App")
    print(f"  Interfaz: {url}")
    print(f"  Datos:    {cfgmod.DIR_OBRAS}")
    print("  Cerrá esta ventana para salir.")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nListo.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
