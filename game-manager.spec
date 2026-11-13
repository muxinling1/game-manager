# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onefile 配置。

依赖装在独立构建 venv 里（见 build_exe.bat），所以 collect_all 能正确
把 webview / pythonnet / clr_loader 的数据文件与 pyd 收进 exe。
只读资源（web/、assets/）随包携带；games.db 由 src.paths 写到 exe 旁边。
"""
import os

from PyInstaller.utils.hooks import collect_all

ROOT = os.getcwd()

a = Analysis(
    ['build_entry.py'],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (os.path.join(ROOT, 'web', 'index.html'), 'web'),
        (os.path.join(ROOT, 'assets', 'app.ico'), 'assets'),
    ],
    hiddenimports=['clr', 'clr_loader', 'pythonnet', 'webview'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

# 关键：把 pywebview 平台后端与 .NET 互操作的数据/二进制全部收进来
for mod in ('webview', 'pythonnet', 'clr_loader', 'proxy_tools', 'bottle'):
    try:
        a.datas, a.binaries = collect_all(mod, a.datas, a.binaries)
    except Exception:
        pass

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='本地游戏库管理器',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,               # 无黑窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, 'assets', 'app.ico'),
)
