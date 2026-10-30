@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
where py >nul 2>nul
if errorlevel 1 goto python_fallback
py -3 -m venv .venv
if errorlevel 1 goto fail
goto install
:python_fallback
where python >nul 2>nul
if errorlevel 1 goto missing
python -m venv .venv
if errorlevel 1 goto fail
:install
if exist ".venv\reelforge-ready-0.5.0" goto launch
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto fail
type nul > ".venv\reelforge-ready-0.5.0"
:launch
".venv\Scripts\python.exe" -m reelforge
if errorlevel 1 goto fail
exit /b 0
:missing
echo Install Python 3.11 or later, then run this launcher again.
pause
exit /b 1
:fail
echo ReelForge could not start. See the error above and README.md.
pause
exit /b 1

