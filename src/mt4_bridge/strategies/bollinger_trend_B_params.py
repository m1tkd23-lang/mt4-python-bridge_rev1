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
# 2026-04-21 修正 1: trend_slope 閾値を大幅に厳しく。
# 旧値 0.00002 は "ノイズレベルの傾きでも trend_up と判定" する過剰発火で、
# B 戦術が常時エントリーする暴走状態になっていた。A戦術と同レベルに引き上げ。
TREND_SLOPE_THRESHOLD = 0.0003
STRONG_TREND_SLOPE_THRESHOLD = 0.0008

# トレンド判定時に価格位置も見る
TREND_PRICE_POSITION_FILTER_ENABLED = True

# 決済ルール
CLOSE_ON_OPPOSITE_TREND_STATE = True

# トレンドレーン識別用 magic number (MT4 ポジション紐付け)
TREND_MAGIC_NUMBER = 44002


# ===================================================================
# B戦術ゲーティング パラメータ (2026-04-21 導入)
# ===================================================================
# A戦術のフィルタと同様に、B戦術も有効/無効を個別に切替可能にする。
# 既定値は「AB 合わせて勝つ」方針に沿って、B が A の弱点期間だけに
# 限定発火する設定。

# 修正2: H1 コンテキストフィルタ
# B戦術は H1 トレンドが明確に同方向のときだけエントリー。
# A戦術の対策④ (逆張り禁止) の鏡像として、B戦術は順張り必須にする。
B_H1_TREND_FILTER_ENABLED = True
B_H1_LOOKBACK_BARS = 60
B_H1_TREND_THRESHOLD_PIPS = 15.0  # A戦術の対策④と同値で開始
B_PIP_MULTIPLIER = 100.0  # USDJPY 用

# 修正3: 時刻フィルタ (B 固有の弱時刻帯)
# 2026-04-21 BT 分析で、B の SL 集中時刻が {4, 8, 10} であることを確認。
# これらは欧州オープン前〜朝の薄商い帯で、5分足 BB の "強い傾き"
# がノイズに過ぎない時間帯が多い。除外すると 2026-02 の崩壊月が解消される。
# 寄与 (単独): {4}=+0.8, {8}=+20.0, {10}=+18.0 pips ≈ 独立に加算
# 採用: {4, 8, 10} 併用で B +229.6 → +268.4 (+38.8), 崩壊月 1→0
B_TIME_FILTER_ENABLED = True
B_ENTRY_BANNED_HOURS = {4, 8, 10}

# ===================================================================
# リスク設定 (戦術固有の SL/TP)
# ===================================================================
# B戦術はトレンド追従なので TP を広めに取る。
# これは BT / ライブ双方で戦術固有値として使われ、
# config/app.yaml の risk.sl_pips/tp_pips はフォールバック扱い。
SL_PIPS = 20.0
TP_PIPS = 40.0


def required_bars() -> int:
    return max(
        BOLLINGER_PERIOD + 1,
        TREND_MA_PERIOD + TREND_SLOPE_LOOKBACK,
    )
