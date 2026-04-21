# TEST/analyze_band_walk.py
from __future__ import annotations

from pathlib import Path

import pandas as pd


INPUT_PATH = Path("TEST/analysis_trades_with_scores.csv")
OUTPUT_DIR = Path("TEST")
OUTPUT_DIR.mkdir(exist_ok=True)

SUMMARY_CSV = OUTPUT_DIR / "analysis_band_walk_summary.csv"
MONTHLY_CSV = OUTPUT_DIR / "analysis_band_walk_monthly.csv"
THRESHOLD_CSV = OUTPUT_DIR / "analysis_band_walk_thresholds.csv"


def summarize(df: pd.DataFrame, label: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            [
                {
                    "label": label,
                    "total": 0,
                    "wins": 0,
                    "losses": 0,
                    "win_rate": 0.0,
                    "avg_pips": 0.0,
                    "total_pips": 0.0,
                }
            ]
        )

    total = len(df)
    wins = int(df["is_win"].sum())
    losses = int((~df["is_win"]).sum())
    win_rate = (wins / total) * 100.0 if total > 0 else 0.0
    avg_pips = float(df["pips"].mean()) if total > 0 else 0.0
    total_pips = float(df["pips"].sum()) if total > 0 else 0.0

    return pd.DataFrame(
        [
            {
                "label": label,
                "total": total,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "avg_pips": avg_pips,
                "total_pips": total_pips,
            }
        ]
    )


def ensure_required_columns(df: pd.DataFrame) -> None:
    required_columns = {
        "position_type",
        "pips",
        "is_win",
        "period",
        "entry_upper_band_walk",
        "entry_lower_band_walk",
        "entry_upper_band_walk_hits",
        "entry_lower_band_walk_hits",
        "entry_dangerous_for_buy",
        "entry_dangerous_for_sell",
        "entry_risk_score",
    }
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"必要列が不足しています: {sorted(missing)}")


def normalize_bool_column(df: pd.DataFrame, column: str) -> None:
    if column not in df.columns:
        return

    normalized = (
        df[column]
        .astype(str)
        .str.strip()
        .str.lower()
        .map(
            {
                "true": True,
                "false": False,
                "1": True,
                "0": False,
                "nan": False,
                "none": False,
                "": False,
            }
        )
        .fillna(False)
    )
    df[column] = normalized.astype(bool)


def normalize_int_column(df: pd.DataFrame, column: str) -> None:
    if column not in df.columns:
        return
    df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0).astype(int)


def normalize_input(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    normalize_bool_column(df, "is_win")
    normalize_bool_column(df, "entry_upper_band_walk")
    normalize_bool_column(df, "entry_lower_band_walk")
    normalize_bool_column(df, "entry_dangerous_for_buy")
    normalize_bool_column(df, "entry_dangerous_for_sell")

    normalize_int_column(df, "entry_upper_band_walk_hits")
    normalize_int_column(df, "entry_lower_band_walk_hits")
    normalize_int_column(df, "entry_risk_score")

    df["position_type"] = df["position_type"].astype(str).str.strip().str.lower()
    df["period"] = df["period"].astype(str)

    return df


def analyze_thresholds(df: pd.DataFrame) -> pd.DataFrame:
    results: list[pd.DataFrame] = []

    results.append(summarize(df, "ALL"))

    sell_df = df[df["position_type"] == "sell"]
    buy_df = df[df["position_type"] == "buy"]

    for threshold in [1, 2, 3, 4]:
        results.append(
            summarize(
                sell_df[sell_df["entry_upper_band_walk_hits"] >= threshold],
                f"SELL upper_hits>={threshold}",
            )
        )
        results.append(
            summarize(
                buy_df[buy_df["entry_lower_band_walk_hits"] >= threshold],
                f"BUY lower_hits>={threshold}",
            )
        )

    results.append(
        summarize(
            sell_df[sell_df["entry_upper_band_walk"]],
            "SELL entry_upper_band_walk=True",
        )
    )
    results.append(
        summarize(
            buy_df[buy_df["entry_lower_band_walk"]],
            "BUY entry_lower_band_walk=True",
        )
    )

    results.append(
        summarize(
            buy_df[buy_df["entry_dangerous_for_buy"]],
            "BUY entry_dangerous_for_buy=True",
        )
    )
    results.append(
        summarize(
            sell_df[sell_df["entry_dangerous_for_sell"]],
            "SELL entry_dangerous_for_sell=True",
        )
    )

    for score in sorted(df["entry_risk_score"].dropna().unique().tolist()):
        score_df = df[df["entry_risk_score"] == score]
        results.append(summarize(score_df, f"risk_score={score}"))

    threshold_df = pd.concat(results, ignore_index=True)
    threshold_df.to_csv(THRESHOLD_CSV, index=False, encoding="utf-8-sig")
    return threshold_df


def analyze_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []

    rows.append(summarize(df, "ALL"))
    rows.append(
        summarize(
            df[df["entry_upper_band_walk"] | df["entry_lower_band_walk"]],
            "any_band_walk=True",
        )
    )
    rows.append(
        summarize(
            df[df["entry_dangerous_for_buy"] | df["entry_dangerous_for_sell"]],
            "any_dangerous=True",
        )
    )
    rows.append(
        summarize(
            df[
                (df["position_type"] == "sell")
                & (df["entry_upper_band_walk_hits"] >= 3)
            ],
            "SELL upper_hits>=3",
        )
    )
    rows.append(
        summarize(
            df[
                (df["position_type"] == "buy")
                & (df["entry_lower_band_walk_hits"] >= 3)
            ],
            "BUY lower_hits>=3",
        )
    )
    rows.append(
        summarize(
            df[
                (df["position_type"] == "sell")
                & (df["entry_dangerous_for_sell"])
            ],
            "SELL dangerous_for_sell=True",
        )
    )
    rows.append(
        summarize(
            df[
                (df["position_type"] == "buy")
                & (df["entry_dangerous_for_buy"])
            ],
            "BUY dangerous_for_buy=True",
        )
    )

    summary_df = pd.concat(rows, ignore_index=True)
    summary_df.to_csv(SUMMARY_CSV, index=False, encoding="utf-8-sig")
    return summary_df


def analyze_monthly(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []

    for period, group in df.groupby("period"):
        rows.append(summarize(group, f"{period}_ALL"))
        rows.append(
            summarize(
                group[
                    (group["position_type"] == "sell")
                    & (group["entry_upper_band_walk_hits"] >= 3)
                ],
                f"{period}_SELL_upper_hits>=3",
            )
        )
        rows.append(
            summarize(
                group[
                    (group["position_type"] == "buy")
                    & (group["entry_lower_band_walk_hits"] >= 3)
                ],
                f"{period}_BUY_lower_hits>=3",
            )
        )
        rows.append(
            summarize(
                group[
                    (group["position_type"] == "sell")
                    & (group["entry_dangerous_for_sell"])
                ],
                f"{period}_SELL_dangerous=True",
            )
        )
        rows.append(
            summarize(
                group[
                    (group["position_type"] == "buy")
                    & (group["entry_dangerous_for_buy"])
                ],
                f"{period}_BUY_dangerous=True",
            )
        )

    monthly_df = pd.concat(rows, ignore_index=True)
    monthly_df.to_csv(MONTHLY_CSV, index=False, encoding="utf-8-sig")
    return monthly_df


def main() -> None:
    if not INPUT_PATH.exists():
        print(f"File not found: {INPUT_PATH}")
        return

    df = pd.read_csv(INPUT_PATH)
    ensure_required_columns(df)
    df = normalize_input(df)

    print(f"Loaded rows: {len(df)}")

    summary_df = analyze_summary(df)
    threshold_df = analyze_thresholds(df)
    monthly_df = analyze_monthly(df)

    print("\n=== Band Walk Summary ===")
    print(summary_df.to_string(index=False))

    print("\n=== Band Walk Thresholds ===")
    print(threshold_df.to_string(index=False))

    print("\n=== Monthly Band Walk ===")
    print(monthly_df.to_string(index=False))

    print("\n=== Saved Files ===")
    print(SUMMARY_CSV.name)
    print(THRESHOLD_CSV.name)
    print(MONTHLY_CSV.name)


if __name__ == "__main__":
    main()