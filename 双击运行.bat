@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo.
echo   Desktop Cat - source version
echo   =============================
echo.

rem ---- 1) reuse the standalone venv if it exists
if exist ".venv\Scripts\pythonw.exe" goto :run_venv

rem ---- 2) locate a Python interpreter
set "PY="
where py >nul 2>nul && goto :found_py
where python >nul 2>nul && goto :found_python
goto :no_python

:found_py
set "PY=py -3"
goto :check_pyside

:found_python
set "PY=python"
goto :check_pyside

rem ---- 3) does the system Python already have PySide6?
:check_pyside
%PY% -c "import PySide6" >nul 2>nul
if errorlevel 1 goto :make_venv
goto :run_system

rem ---- 4) run straight away (no extra download, instant start)
:run_system
echo   Found Python with PySide6, starting...
set "PYW="
for /f "delims=" %%i in ('%PY% -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),chr(112)+chr(121)+chr(116)+chr(104)+chr(111)+chr(110)+chr(119)+chr(46)+chr(101)+chr(120)+chr(101)))"') do set "PYW=%%i"
if defined PYW if exist "%PYW%" (
  start "" "%PYW%" main.py
  exit /b 0
)
start "" %PY% main.py
exit /b 0

rem ---- 5) first run: build an isolated venv
:make_venv
echo   [1/2] Creating virtual environment, please wait...
%PY% -m venv .venv
if errorlevel 1 goto :venv_fail
echo   [2/2] Installing PySide6, this may take a few minutes...
".venv\Scripts\python.exe" -m pip install --upgrade pip -q
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :install_fail
echo   Starting the cat...
start "" ".venv\Scripts\pythonw.exe" main.py
exit /b 0

:run_venv
echo   Using existing environment...
start "" ".venv\Scripts\pythonw.exe" main.py
exit /b 0

:no_python
echo   [!] Python not found.
echo       Option A: use the prebuilt "桌面小猫咪.exe" - no Python needed.
echo       Option B: install Python 3.9+ from https://www.python.org/downloads/
echo                 and tick "Add python.exe to PATH" during setup.
echo.
pause
exit /b 1

:venv_fail
echo   [!] Failed to create the virtual environment.
echo       You can also just run the prebuilt "桌面小猫咪.exe" instead.
echo.
pause
exit /b 1

:install_fail
echo   [!] Failed to install PySide6. Check your network and retry.
echo       You can also just run the prebuilt "桌面小猫咪.exe" instead.
echo.
pause
exit /b 1
