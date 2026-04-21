# src/mt4_bridge/strategies/bollinger_trend_B_params.py
from __future__ import annotations


# =========================
# 調整パラメータ
# =========================
# ボリンジャーバンド
BOLLINGER_PERIOD = 20
BOLLINGER_SIGMA = 2.0

# エントリー/エグジット用 σ
ENTRY_SIGMA_NORMAL = 0.0  # 0σ = middle band
ENTRY_SIGMA_STRONG = 1.0  # 1σ
EXIT_SIGMA = 2.0

# トレンド判定用 MA
TREND_MA_PERIOD = 30
TREND_SLOPE_LOOKBACK = 2
TREND_SLOPE_THRESHOLD = 0.00002
STRONG_TREND_SLOPE_THRESHOLD = 0.0005

# トレンド判定時に価格位置も見る
TREND_PRICE_POSITION_FILTER_ENABLED = True

# 決済ルール
CLOSE_ON_OPPOSITE_TREND_STATE = True

# トレンドレーン識別用 magic number (MT4 ポジション紐付け)
TREND_MAGIC_NUMBER = 44002


def required_bars() -> int:
    return max(
        BOLLINGER_PERIOD + 1,
        TREND_MA_PERIOD + TREND_SLOPE_LOOKBACK,
    )
