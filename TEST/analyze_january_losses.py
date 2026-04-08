# C:\WS\repos\mt4-python-bridge\TEST\analyze_january_losses.py
import pandas as pd
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent

# 対象ファイル（1月）
csv_path = BASE_DIR / "bollinger_range_v4_4_guarded__USDJPY-cd5_20250521_2026-01__trades.csv"

df = pd.read_csv(csv_path)

# =========================
# 共通処理
# =========================

def parse_flags(reason):
    m = re.search(r"risk_flags=\((.*?)\)", str(reason))
    if not m:
        return False, False, False

    parts = m.group(1).split(", ")
    d = {}
    for p in parts:
        if "=" not in p:
            continue
        k, v = p.split("=")
        d[k] = v == "True"

    return (
        d.get("bandwidth_expanding", False),
        d.get("distance_expanding", False),
        d.get("trend_slope_accelerating", False),
    )

flags = df["entry_signal_reason"].apply(parse_flags)
df[["bandwidth", "distance", "trend"]] = pd.DataFrame(flags.tolist(), index=df.index)

df["risk_score"] = (
    df["bandwidth"].astype(int) +
    df["distance"].astype(int) +
    df["trend"].astype(int)
)

df["is_win"] = df["pips"] > 0

# =========================
# ① 連敗構造
# =========================

df["loss_streak"] = 0
streak = 0

for i in range(len(df)):
    if df.loc[i, "pips"] < 0:
        streak += 1
    else:
        streak = 0
    df.loc[i, "loss_streak"] = streak

print("\n=== 最大連敗 ===")
print(df["loss_streak"].max())

# =========================
# ② 時間帯分析
# =========================

# entry_time がある前提（なければ open_time などに変更）
time_col = None
for col in ["entry_time", "open_time", "time"]:
    if col in df.columns:
        time_col = col
        break

if time_col:
    df["hour"] = pd.to_datetime(df[time_col]).dt.hour

    hourly = df.groupby("hour").agg(
        total=("pips", "count"),
        wins=("is_win", "sum"),
        avg_pips=("pips", "mean"),
    )

    hourly["win_rate"] = hourly["wins"] / hourly["total"] * 100

    print("\n=== 時間帯別 ===")
    print(hourly.sort_index())
else:
    print("\n時間カラムが見つかりません")

# =========================
# ③ risk_score別
# =========================

score = df.groupby("risk_score").agg(
    total=("pips", "count"),
    wins=("is_win", "sum"),
    avg_pips=("pips", "mean"),
)

score["win_rate"] = score["wins"] / score["total"] * 100

print("\n=== risk_score別 ===")
print(score)

# =========================
# ④ 負けトレード詳細
# =========================

losers = df[df["pips"] < 0]

print("\n=== 負けトレード上位（ワースト10） ===")
print(losers.sort_values("pips").head(10)[
    ["pips", "risk_score", "entry_signal_reason"]
])

# =========================
# ⑤ 負け原因の頻出
# =========================

reason_counts = losers["entry_signal_reason"].value_counts().head(10)

print("\n=== 負け理由 TOP10 ===")
print(reason_counts)