@echo off
setlocal
cd /d "%~dp0"

rem C2 first-run setup: install pywebview into .\vendor (needs internet ONCE).
rem The chosen interpreter is recorded so run.bat uses the SAME one, because
rem vendor contains .pyd binaries bound to a specific CPython version.

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
echo Installing dependencies into .\vendor ...
if not exist vendor mkdir vendor
"%PY%" -m pip install --disable-pip-version-check --target vendor -r requirements.txt
if errorlevel 1 goto failed
> "vendor\runtime.txt" echo %PY%
echo Done. Now run run.bat (no internet needed afterwards).
pause
exit /b 0

:failed
echo Install failed. Check your network and try again.
pause
exit /b 1
