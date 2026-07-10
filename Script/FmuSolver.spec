# -*- mode: python ; coding: utf-8 -*-

import os
import runpy

runpy.run_path(os.path.join(SPECPATH, 'update_build_version.py'), run_name='__main__')


a = Analysis(
    ['FmuLauncherUniversal.py'],
    pathex=[],
    binaries=[],
    datas=[('fmusolver_full.ico', '.')],
    hiddenimports=[],
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
