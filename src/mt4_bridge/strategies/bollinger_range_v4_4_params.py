# src/mt4_bridge/strategies/bollinger_range_v4_4_params.py
from __future__ import annotations


# =========================
# 調整パラメータ
# =========================
# ボリンジャーバンド
BOLLINGER_PERIOD = 20
BOLLINGER_SIGMA = 2.0
BOLLINGER_EXTREME_SIGMA = 3.0  # v4.4 追加: 3σ即時タッチ用

# レンジ判定用 MA
RANGE_MA_PERIOD = 10
RANGE_SLOPE_LOOKBACK = 5
RANGE_SLOPE_THRESHOLD = 0.0005

# レンジ判定用のバンド幅しきい値
# normalized_band_width = (upper - lower) / middle
RANGE_BAND_WIDTH_THRESHOLD = 0.003

# レンジ判定用のミドル距離しきい値
# distance_from_middle = abs(latest_close - middle_band) / middle_band
RANGE_MIDDLE_DISTANCE_THRESHOLD = 0.002

# トレンド判定用 MA
TREND_MA_PERIOD = 15
TREND_SLOPE_LOOKBACK = 2
TREND_SLOPE_THRESHOLD = 0.0003

# トレンド判定時に価格位置も見る
TREND_PRICE_POSITION_FILTER_ENABLED = True

# エントリー確認
# range:
#   previous_close がバンド外
#   latest_close がバンド内へ戻ったらエントリー
RANGE_REQUIRE_REENTRY_CONFIRMATION = True

# trend:
#   previous_close がまだブレイクしておらず
#   latest_close でブレイクしたらエントリー
TREND_REQUIRE_BREAK_CONFIRMATION = True

# 決済ルール
EXIT_ON_RANGE_MIDDLE_BAND = True
CLOSE_ON_OPPOSITE_TREND_STATE = True

# =========================
# v4.2 追加: range failure exit
# =========================
# レンジ回帰を狙ったポジションが失敗した時だけ早期撤退する
# adverse_move_threshold = band_width * ratio
# range_failure_exit は保険として有効(崩壊月を抑える役割)だが、
# 過敏すぎると middle 回帰で勝つはずの玉を -6 pips で切って機会損失になる。
# 2026-04-22 両データセット横断スイープ (0.0/0.2/0.28/0.4/0.6/1.0):
#   ratio=0.60 が総pips +1182.4, 最悪月 -48.7, 崩壊月 7 で全指標ベスト。
#   現行 0.28 は DUK 2024-07 で -113.4 の巨大崩壊を出す谷値だった。
ENABLE_RANGE_FAILURE_EXIT = True
RANGE_FAILURE_ADVERSE_MOVE_RATIO = 0.60

# =========================
# v4.4 追加: 3σタッチ即時エントリー(無効化)
# =========================
# 2026-04-21 方針変更: 2σ再突入エントリーのみに一本化
# (3σ即時は逆行リスクが大きく崩壊月の種となるため採用しない)
ENABLE_RANGE_EXTREME_TOUCH_ENTRY = False

# =========================
# v4.5 追加: 時間 stop (max holding bars)
# =========================
# 保有バー 13+ で勝率 26% / 平均 -5.25 pips と完全負け領域 (2026-04-22 実測)。
# 5min×N bar 以上経過しても中央回帰に届かないポジションは強制撤退する。
# BT と本番で同じロジックを使うため、latest_bar.time と position.open_time の
# 差分(分) を BAR_MINUTES で割ってバー数換算する (週末ギャップ影響は小さい)。
# 2026-04-23 sweep (N=8/10/12/15/20/30/50/OFF):
#   N=20 が総pips +1333.3, 最悪月 -49.4, 崩壊月 6 (OFF比 pips +60 / 崩壊-1) で最良。
#   N=12/15 は早切りすぎで途中勝ちも潰し pips 逆効果。
#   真のノイズは 21本以上の長時間保持で、N=20 がちょうどそこを遮断する。
ENABLE_TIME_STOP_EXIT = True
MAX_HOLDING_BARS = 20
BAR_MINUTES = 5  # M5 timeframe


# =========================
# 観測用パラメータ (TASK-0106)
# 以下は後続の観測実装で使用する設定値。
# 売買ロジックには影響しない。
# =========================

# --- mean reversion 観測 ---
# 中央回帰が完了したかを事後検証するための先読みバー数リスト
MEAN_REVERSION_LOOKAHEAD_BARS_LIST: list[int] = [5, 10, 20, 40]
# バンド端タッチ判定の許容誤差（価格÷middle の比率）
MEAN_REVERSION_TOUCH_EPSILON: float = 0.0002

# --- band walk 観測 ---
# バンドウォーク（連続的にバンド端付近に留まる）検出の後方参照バー数
BAND_WALK_LOOKBACK_BARS: int = 10
# バンドウォークと判定する最小ヒット数（lookback 内でバンド端 zone にいた本数）
BAND_WALK_MIN_HITS: int = 6
# バンド端 zone の幅（band_width に対する比率、upper/lower 側それぞれ）
BAND_EDGE_ZONE_RATIO: float = 0.15

# --- middle cross 観測 ---
# ミドルライン横断の有無を確認する後方参照バー数
MIDDLE_CROSS_LOOKBACK_BARS: int = 10

# --- one-side stay 観測 ---
# ミドルラインより片側に留まり続けているかを確認する後方参照バー数
ONE_SIDE_STAY_LOOKBACK_BARS: int = 15

# --- band width expansion 観測 ---
# バンド幅拡大を検出する後方参照バー数
BAND_WIDTH_EXPANSION_LOOKBACK_BARS: int = 10
# バンド幅拡大と判定する変化率しきい値（直近 / lookback前 の比率）
BAND_WIDTH_EXPANSION_THRESHOLD: float = 1.3

# --- trend slope acceleration 観測 ---
# トレンド傾きの加速度を計算する後方参照バー数
TREND_SLOPE_ACCEL_LOOKBACK_BARS: int = 5
# 加速度が有意とみなすしきい値
TREND_SLOPE_ACCEL_THRESHOLD: float = 0.0001

# --- progress check 観測 ---
# エントリー後の中央回帰進捗を確認するバー数
PROGRESS_CHECK_BARS: int = 10
# 進捗率しきい値（エントリー地点→middle 間の移動割合）
MIN_PROGRESS_TO_MIDDLE_RATIO: float = 0.3


def required_bars() -> int:
    return max(
        BOLLINGER_PERIOD + 1,
        RANGE_MA_PERIOD + RANGE_SLOPE_LOOKBACK,
        TREND_MA_PERIOD + TREND_SLOPE_LOOKBACK,
    )
