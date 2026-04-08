# TEST/analyze_b3_march_detail.py

import pandas as pd
from pathlib import Path

csv_path = Path(
    r"C:\WS\repos\mt4-python-bridge\TEST\bollinger_trend_B3_weak_start_v3_1__USDJPY-cd5_20250521_2026-01__trades.csv"
)

df = pd.read_csv(csv_path)

# 勝敗
df["is_win"] = df["pips"] > 0

print("\n=== 全体 ===")
print(df["pips"].describe())

print("\n=== 勝率 ===")
print((df["pips"] > 0).mean() * 100)

# =========================
# ① entry_state別
# =========================
print("\n=== entry_market_state別 ===")
entry_summary = df.groupby("entry_market_state").agg(
    total=("pips", "count"),
    wins=("is_win", "sum"),
    avg_pips=("pips", "mean"),
)
entry_summary["win_rate"] = entry_summary["wins"] / entry_summary["total"] * 100
print(entry_summary.sort_values("total", ascending=False))

# =========================
# ② exit_state別
# =========================
print("\n=== exit_market_state別 ===")
exit_summary = df.groupby("exit_market_state").agg(
    total=("pips", "count"),
    avg_pips=("pips", "mean"),
)
print(exit_summary.sort_values("total", ascending=False))

# =========================
# ③ 早期失速（短時間負け）
# =========================
df["duration"] = pd.to_datetime(df["exit_time"]) - pd.to_datetime(df["entry_time"])
df["duration_min"] = df["duration"].dt.total_seconds() / 60

print("\n=== 短時間トレード（30分以内） ===")
short = df[df["duration_min"] <= 30]
print(short["pips"].describe())
print("勝率:", (short["pips"] > 0).mean() * 100)

# =========================
# ④ 負けトレード上位確認
# =========================
print("\n=== 大きめ負けサンプル ===")
losers = df.sort_values("pips").head(10)
print(
    losers[
        [
            "entry_time",
            "entry_market_state",
            "exit_market_state",
            "pips",
            "entry_signal_reason",
            "exit_signal_reason",
        ]
    ]
)