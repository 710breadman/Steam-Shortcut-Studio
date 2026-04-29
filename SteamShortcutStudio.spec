# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

python_root = Path(sys.executable).resolve().parent
tcl_root = python_root / 'tcl'

datas = []
if (tcl_root / 'tcl8.6').exists():
    datas.append((str(tcl_root / 'tcl8.6'), 'tcl\\tcl8.6'))
if (tcl_root / 'tk8.6').exists():
    datas.append((str(tcl_root / 'tk8.6'), 'tcl\\tk8.6'))
datas += [
    ('steam_shortcut_studio\\assets\\sss.png', 'steam_shortcut_studio\\assets'),
    ('steam_shortcut_studio\\assets\\sss.ico', 'steam_shortcut_studio\\assets'),
]
binaries = []
hiddenimports = []
for package in ('PIL', 'certifi'):
    tmp_ret = collect_all(package)
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SteamShortcutStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='steam_shortcut_studio\\assets\\sss.ico',
)
