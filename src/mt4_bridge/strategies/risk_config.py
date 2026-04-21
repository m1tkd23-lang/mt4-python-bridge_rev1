# src/mt4_bridge/strategies/risk_config.py
"""戦術固有の SL/TP 解決ヘルパー。

戦術モジュールが `SL_PIPS` / `TP_PIPS` を定義している場合はそれを使う。
combo 戦術(例: bollinger_combo_AB)は entry_lane から子戦術を解決する。

優先順位は呼び出し側で決める。典型的には:
  明示引数(BT の lane_sl_pips 等) > 戦術側定数 > グローバル fallback (app.yaml)
"""
from __future__ import annotations

import importlib


def _load_constants(strategy_name: str) -> tuple[float | None, float | None]:
    module_path = f"mt4_bridge.strategies.{strategy_name}"
    try:
        mod = importlib.import_module(module_path)
    except ImportError:
        return None, None
    sl = getattr(mod, "SL_PIPS", None)
    tp = getattr(mod, "TP_PIPS", None)
    sl_val = float(sl) if sl is not None else None
    tp_val = float(tp) if tp is not None else None
    return sl_val, tp_val


def _load_lane_strategy_map(strategy_name: str) -> dict[str, str] | None:
    module_path = f"mt4_bridge.strategies.{strategy_name}"
    try:
        mod = importlib.import_module(module_path)
    except ImportError:
        return None
    lane_map = getattr(mod, "LANE_STRATEGY_MAP", None)
    if not isinstance(lane_map, dict):
        return None
    return {str(k).strip().lower(): str(v) for k, v in lane_map.items()}


def resolve_strategy_risk_pips(
    strategy_name: str,
) -> tuple[float | None, float | None]:
    """戦術モジュールの SL_PIPS / TP_PIPS を返す。未定義なら (None, None)。"""
    return _load_constants(strategy_name)


def resolve_lane_risk_pips(
    strategy_name: str,
    entry_lane: str | None,
) -> tuple[float | None, float | None]:
    """lane 名から子戦術の SL_PIPS/TP_PIPS を解決する。

    優先順:
      1. strategy_name が combo 戦術で LANE_STRATEGY_MAP を持つ → lane 経由で子戦術の定数
      2. それ以外は strategy_name 自体の定数
    """
    lane_key = (entry_lane or "").strip().lower()
    lane_map = _load_lane_strategy_map(strategy_name)
    if lane_map and lane_key in lane_map:
        child_name = lane_map[lane_key]
        return _load_constants(child_name)
    return _load_constants(strategy_name)
