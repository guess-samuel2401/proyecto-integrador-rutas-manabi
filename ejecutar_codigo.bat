@echo off
rem Ejecuta el programa desde el codigo fuente (requiere Python 3 con Tkinter).
rem Para usar el programa sin instalar Python, abre RutasManabi.exe.
cd /d "%~dp0"

rem Se prueba "import tkinter" en vez de solo buscar python: en Windows existe un
rem acceso directo de Microsoft Store llamado python.exe que no es Python de verdad.
python -c "import tkinter" >nul 2>nul && (python main.py & exit /b)
py -3 -c "import tkinter" >nul 2>nul && (py -3 main.py & exit /b)
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%D\python.exe" ("%%D\python.exe" main.py & exit /b)
)

echo No se encontro Python 3.
echo Instalalo desde https://www.python.org/downloads/ y marca la casilla
echo "Add python.exe to PATH" durante la instalacion. Luego vuelve a abrir este archivo.
pause
