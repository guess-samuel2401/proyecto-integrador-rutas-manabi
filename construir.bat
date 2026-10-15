@echo off
rem Genera dist\RutasManabi.exe a partir del codigo fuente.
rem Requiere: python -m pip install pyinstaller
cd /d "%~dp0"

set PY=python
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python313\python.exe"

%PY% -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name RutasManabi ^
    --icon recursos\icono.ico ^
    --add-data "recursos\icono.ico;recursos" ^
    --add-data "datos\lugares.json;datos_iniciales" ^
    --add-data "datos\conexiones.json;datos_iniciales" ^
    --add-data "datos\mapa_base.json;datos_iniciales" ^
    main.py

if errorlevel 1 (
    echo.
    echo Error al generar el ejecutable.
    pause
    exit /b 1
)
echo.
echo Listo: dist\RutasManabi.exe
pause
