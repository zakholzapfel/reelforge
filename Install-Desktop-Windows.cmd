@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Install Python 3.11 or later from python.org, then run this setup again.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto failed
)
.venv\Scripts\python.exe -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11 or later is required.'"
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -e ".[desktop]"
if errorlevel 1 goto failed
.venv\Scripts\python.exe scripts\install_desktop.py
if errorlevel 1 goto failed
echo ReelForge shortcuts are ready in your Start menu and Desktop.
pause
exit /b 0
:failed
echo Setup did not finish. Read the message above and see docs\DESKTOP.md.
pause
exit /b 1
