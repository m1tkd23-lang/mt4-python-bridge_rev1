# src/explore_gui_app/constants.py
"""explore_gui_app で共有する定数。"""
from __future__ import annotations


# Explore タブ / Backtest 単発タブで選択可能な戦術名。
# ここを変更するだけで両タブの戦略コンボ候補が同期される。
AVAILABLE_STRATEGIES: list[str] = [
    "bollinger_range_v4_4",
    "bollinger_range_v4_4_tuned_a",
    "bollinger_range_A",
    "bollinger_trend_B",
    "bollinger_combo_AB",
]
