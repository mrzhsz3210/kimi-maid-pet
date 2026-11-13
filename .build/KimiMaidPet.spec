# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:/Users/20802/Desktop/《桌面》/网盘、工具/kimi-maid-pet/app/pet.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['autostart', 'selftest', 'version'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy', 'scipy', 'matplotlib', 'tkinter', 'PyQt5', 'PyQt6'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='KimiMaidPet',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
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
    name='KimiMaidPet',
)
