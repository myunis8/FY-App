# -*- mode: python ; coding: utf-8 -*-
# Empaquetado para Windows:  pyinstaller obras.spec
# Genera dist\FY Manager.exe, un unico archivo sin instalador.

a = Analysis(
    ['obras.py'],
    pathex=[],
    binaries=[],
    datas=[('web', 'web')],        # la interfaz viaja adentro del .exe
    hiddenimports=['pymupdf', 'numpy'],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'pydoc', 'doctest'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='FY Manager',
    debug=False,
    strip=False,
    upx=True,
    console=True,                  # la ventana negra es el boton de salir
    disable_windowed_traceback=False,
    icon=None,
)
