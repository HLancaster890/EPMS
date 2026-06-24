# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['activitywatch_Source code\\epms-agent-client\\epms_gateway\\__main__.py'],
    pathex=[],
    binaries=[],
    datas=[('activitywatch_Source code\\epms-agent-client\\epms_gateway', 'epms_gateway')],
    hiddenimports=['epms_gateway', 'epms_gateway.config', 'epms_gateway.auth', 'epms_gateway.server', 'urllib.parse'],
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
    name='EPMS_Gateway',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
