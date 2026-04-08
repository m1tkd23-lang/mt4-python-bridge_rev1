# src\backtest_gui_app\constants.py
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = REPO_ROOT / "data"
DEFAULT_STRATEGIES_DIR = REPO_ROOT / "src" / "mt4_bridge" / "strategies"

# USDJPY系専用:
# 1.0 lot = 約 1000 円 / pip
USDJPY_YEN_PER_PIP_PER_1LOT = 1000.0