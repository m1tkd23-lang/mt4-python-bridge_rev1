# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(SPECPATH) / "src"))

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
hiddenimports += collect_submodules('mt4_bridge.strategies')
hiddenimports += collect_submodules('mt4_bridge')

# 明示フォールバック (collect_submodules が空でも最低限これだけは積む)
hiddenimports += [
    'mt4_bridge.strategies.bollinger_range_A',
    'mt4_bridge.strategies.bollinger_trend_B',
    'mt4_bridge.strategies.bollinger_trend_B_params',
    'mt4_bridge.strategies.bollinger_trend_B_indicators',
    'mt4_bridge.strategies.bollinger_trend_B_rules',
    'mt4_bridge.strategies.bollinger_combo_AB',
    'mt4_bridge.strategies.bollinger_combo_A_retry',
    'mt4_bridge.strategies.risk_config',
]


a = Analysis(
    ['src\\app_watch_gui.py'],
    pathex=['src'],
    binaries=[],
    datas=[],
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
    [],
    exclude_binaries=True,
    name='mt4-watch-gui',
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
    name='mt4-watch-gui',
)
