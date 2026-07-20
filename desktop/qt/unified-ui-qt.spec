# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path.cwd()

datas = [
    (str(ROOT / 'unified-ui'), 'unified-ui'),
]

hiddenimports = collect_submodules('PySide6') + [
    'flask',
    'gevent',
    'geventwebsocket',
]

block_cipher = None

a = Analysis(
    [str(ROOT / 'desktop' / 'qt' / 'unified_ui_qt.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Unified UI Qt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Unified UI Qt',
)
app = BUNDLE(
    coll,
    name='Unified UI Qt.app',
    icon=None,
    bundle_identifier='ru.dogonin.unifiedui.qt',
    info_plist={
        'NSHighResolutionCapable': 'True',
        'CFBundleName': 'Unified UI Qt',
        'CFBundleDisplayName': 'Unified UI Qt',
    },
)
