@echo off
setlocal
cd /d "%~dp0"

rem B route: build a standalone single-file exe with PyInstaller.
rem Uses a dedicated build venv (NOT the runtime vendor folder) so that
rem PyInstaller can discover webview / pythonnet / clr_loader.

set "PY="
if exist "vendor\runtime.txt" set /p PY=<"vendor\runtime.txt"
if not defined PY set "PY=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" (
    echo Python not found. Run setup.bat first.
    pause
    exit /b 1
)

set "BV=.build-venv\Scripts\python.exe"
if not exist "%BV%" (
    echo Creating build venv ...
    "%PY%" -m venv .build-venv
    if errorlevel 1 goto failed
    "%BV%" -m pip install --disable-pip-version-check -r requirements.txt pyinstaller
    if errorlevel 1 goto failed
)

echo Building exe (about 30-60s) ...
"%BV%" -m PyInstaller --noconfirm --distpath dist --workpath .build-work game-manager.spec
if errorlevel 1 goto failed

echo.
echo Done: standalone exe is in the dist\ folder
echo Run create_shortcut.ps1 -UseExe to point the desktop shortcut at it.
pause
exit /b 0

:failed
echo Build failed. See the output above.
pause
exit /b 1
