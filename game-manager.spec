# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onefile 配置。

依赖装在独立构建 venv 里（见 build_exe.bat），所以 collect_all 能正确
把 webview / pythonnet / clr_loader / Pillow 的数据文件与 pyd 收进 exe。
只读资源（web/、assets/）随包携带；games.db 由 src.paths 写到 exe 旁边。
"""
import os

from PyInstaller.utils.hooks import collect_all

ROOT = os.getcwd()

# 关键：collect_all(name) 返回 (datas, binaries, hiddenimports) 三元组。
# 必须在 Analysis 构造「之前」展开——hiddenimports 只有作为 Analysis 参数
# 传入才会被分析进 PYZ，事后追加 a.hiddenimports 是无效的。Pillow 的 WebP
# 编码依赖插件子模块（PIL.WebPImagePlugin 等），靠 hiddenimports 一并带入。
extra_datas, extra_binaries, extra_hidden = [], [], []
for mod in ('webview', 'pythonnet', 'clr_loader', 'proxy_tools', 'bottle', 'PIL'):
    try:
        d, b, h = collect_all(mod)
        extra_datas += d
        extra_binaries += b
        extra_hidden += h
    except Exception:
        pass

a = Analysis(
    ['build_entry.py'],
    pathex=[ROOT],
    binaries=extra_binaries,
    datas=[
        (os.path.join(ROOT, 'web', 'index.html'), 'web'),
        (os.path.join(ROOT, 'assets', 'app.ico'), 'assets'),
        (os.path.join(ROOT, 'src', 'pinyin_data.json'), 'src'),
    ] + extra_datas,
    hiddenimports=['clr', 'clr_loader', 'pythonnet', 'webview', 'PIL'] + extra_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

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
