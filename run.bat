@echo off
setlocal
cd /d "%~dp0"

rem C2: load the interpreter recorded by setup.bat (vendor .pyd files are
rem CPython-version-specific, so setup and run MUST use the same python).
set "PY="
if exist "vendor\runtime.txt" set /p PY=<"vendor\runtime.txt"
if defined PY goto checkvendor

rem Fallback if setup was not run: prefer a real system Python 3.9+,
rem then fall back to the DSH bundled runtime (original decision #3).
where python >nul 2>nul
if errorlevel 1 goto bundled
python -c "import sys;sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>nul
if errorlevel 1 goto bundled
set "PY=python"
goto checkvendor

:bundled
set "BUNDLED=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if exist "%BUNDLED%" set "PY=%BUNDLED%"
if defined PY goto checkvendor
echo Python 3.9+ not found. Install Python or check the DSH bundled runtime.
pause
exit /b 1

:checkvendor
if not exist "vendor\webview\__init__.py" (
    echo Dependencies not installed. Run setup.bat once first.
    pause
    exit /b 1
)
echo Using: %PY%
"%PY%" -m src.webapp
if errorlevel 1 pause
