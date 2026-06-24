# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ['..\\Resources\\services\\epms_server_service.py'],
    pathex=['..\\Resources', '..\\Resources\\services'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'epms_server_service',
        'routes', 'routes.state', 'routes.models', 'routes.helpers',
        'routes.auth_routes', 'routes.agent_routes',
        'epms_server.rbac', 'epms_server.ad_login', 'epms_server.aggregation',
        'epms_common', 'epms_common.settings', 'epms_common.db',
        'epms_common.middleware',
        'fastapi', 'uvicorn', 'asyncpg', 'pydantic', 'jwt',
        'cryptography', 'websockets', 'starlette.websockets',
        'multipart', 'openpyxl',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
              'matplotlib', 'scipy', 'pandas', 'numpy'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='epms-server',
          debug=False, bootloader_ignore_signals=False, strip=False,
          upx=True, console=False, disable_windowed_traceback=False,
          argv_emulation=False, target_arch=None, codesign_identity=None,
          entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True,
               upx_exclude=[], name='epms-server')
