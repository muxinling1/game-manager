@echo off
setlocal
cd /d "%~dp0"

rem Prefer a real system Python 3.9+, then fall back to the DSH bundled runtime.
set "PY="
where python >nul 2>nul
if errorlevel 1 goto bundled
python -c "import sys;sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>nul
if errorlevel 1 goto bundled
set "PY=python"
goto ready

:bundled
set "BUNDLED=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if exist "%BUNDLED%" set "PY=%BUNDLED%"
if defined PY goto ready
echo Python 3.9+ not found. Install Python or check the DSH bundled runtime.
pause
exit /b 1

:ready
echo Using: %PY%
"%PY%" -m src.app
if errorlevel 1 pause
