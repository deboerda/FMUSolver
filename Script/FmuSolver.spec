# -*- mode: python ; coding: utf-8 -*-

import os
import runpy
from PyInstaller.utils.hooks import collect_all

runpy.run_path(os.path.join(SPECPATH, 'update_build_version.py'), run_name='__main__')

proto_datas, proto_binaries, proto_hiddenimports = collect_all('google.protobuf')

a = Analysis(
    ['FmuLauncherUniversal.py'],
    pathex=[],
    binaries=proto_binaries,
    datas=[('fmusolver_full.ico', '.')] + proto_datas,
    hiddenimports=['google.protobuf'] + proto_hiddenimports,
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
    [],
    exclude_binaries=True,
    name='FmuSolver',
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
    icon='fmusolver_full.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FmuSolver',
)
