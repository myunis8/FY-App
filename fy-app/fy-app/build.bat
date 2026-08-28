@echo off
REM Compila FY-App.exe. Ejecutar desde esta carpeta.
setlocal

where python >nul 2>nul
if errorlevel 1 (
  echo No se encontro Python. Instalalo desde python.org y marca "Add to PATH".
  pause & exit /b 1
)

echo Instalando dependencias si hacen falta...
python -m pip install --quiet --upgrade -r requirements.txt || goto :error

echo Compilando...
python -m PyInstaller --clean --noconfirm obras.spec || goto :error

echo.
echo Listo: dist\FY-App.exe
echo Copialo donde quieras. No necesita instalacion ni Python.
pause
exit /b 0

:error
echo.
echo La compilacion fallo. Revisa el mensaje de arriba.
pause
exit /b 1
