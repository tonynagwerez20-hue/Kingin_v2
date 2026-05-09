# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto', 'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan', 'uvicorn.lifespan.on', 'fastapi', 'lightgbm', 'zmq', 'pandas', 'joblib', 'dotenv', 'Engine.main_loop']
hiddenimports += collect_submodules('Engine')
hiddenimports += collect_submodules('support')
hiddenimports += collect_submodules('execution')
hiddenimports += collect_submodules('utils')
hiddenimports += collect_submodules('data_feed')
hiddenimports += collect_submodules('config')
hiddenimports += collect_submodules('mt5')
hiddenimports += collect_submodules('risk')


a = Analysis(
    ['kingin_api.py'],
    pathex=[],
    binaries=[],
    datas=[('Engine', 'Engine'), ('support', 'support'), ('execution', 'execution'), ('utils', 'utils'), ('data_feed', 'data_feed'), ('config', 'config'), ('mt5', 'mt5'), ('risk', 'risk')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'matplotlib', 'scipy', 'notebook', 'PIL', 'PyQt5', 'PySide2', 'tkinter', 'numpy.distutils', 'IPython', 'jedi'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='kingin_api',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
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
    name='kingin_api',
)
