# -*- mode: python ; coding: utf-8 -*-


from PyInstaller.utils.hooks import collect_all

proto_datas, proto_binaries, proto_hiddenimports = collect_all('google.protobuf')

a = Analysis(
    ['DataVisualizerPython.py'],
    pathex=[],
    binaries=proto_binaries,
    datas=proto_datas,
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
    name='DataVisualizer64',
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DataVisualizer64',
)
