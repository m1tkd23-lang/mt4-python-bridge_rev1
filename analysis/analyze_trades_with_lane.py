# TEST/analyze_trades_with_lane.py
import re
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).parent

TARGET_GLOB = "*_trades.csv"

MONTHLY_SUMMARY_CSV = BASE_DIR / "analysis_monthly_summary.csv"
SCORE_SUMMARY_CSV = BASE_DIR / "analysis_monthly_score_summary.csv"
DETAIL_CSV = BASE_DIR / "analysis_trades_with_scores.csv"

LANE_SUMMARY_CSV = BASE_DIR / "analysis_lane_summary.csv"
LANE_SCORE_SUMMARY_CSV = BASE_DIR / "analysis_lane_score_summary.csv"


def parse_flags(reason: str) -> tuple[bool, bool, bool]:
    m = re.search(r"risk_flags=\((.*?)\)", str(reason))
    if not m:
        return False, False, False

    raw = m.group(1).split(", ")
    parsed: dict[str, bool] = {}

    for item in raw:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parsed[key] = value == "True"

    return (
        parsed.get("bandwidth_expanding", False),
        parsed.get("distance_expanding", False),
        parsed.get("trend_slope_accelerating", False),
    )


def extract_period_label(file_path: Path) -> str:
    m = re.search(r"(\d{4}-\d{2})", file_path.stem)
    if m:
        return m.group(1)
    return file_path.stem


def resolve_lane_column(df: pd.DataFrame) -> str | None:
    if "lane" in df.columns:
        return "lane"
    if "entry_lane" in df.columns:
        return "entry_lane"
    return None


def analyze_one_file(
    csv_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(csv_path)

    required_columns = {"entry_signal_reason", "pips"}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"必要列が不足しています: {sorted(missing)}")

    period = extract_period_label(csv_path)

    flags = df["entry_signal_reason"].apply(parse_flags)
    df[["bandwidth", "distance", "trend"]] = pd.DataFrame(flags.tolist(), index=df.index)

    df["risk_score"] = (
        df["bandwidth"].astype(int)
        + df["distance"].astype(int)
        + df["trend"].astype(int)
    )

    df["is_win"] = df["pips"] > 0
    df["period"] = period
    df["source_file"] = csv_path.name

    lane_column = resolve_lane_column(df)
    if lane_column is not None:
        df["analysis_lane"] = df[lane_column].fillna("unknown").astype(str)
    else:
        df["analysis_lane"] = "unknown"

    monthly_summary = pd.DataFrame(
        [
            {
                "period": period,
                "source_file": csv_path.name,
                "total_trades": len(df),
                "wins": int(df["is_win"].sum()),
                "losses": int((~df["is_win"]).sum()),
                "win_rate": float(df["is_win"].mean() * 100) if len(df) > 0 else 0.0,
                "avg_pips": float(df["pips"].mean()) if len(df) > 0 else 0.0,
                "total_pips": float(df["pips"].sum()) if len(df) > 0 else 0.0,
            }
        ]
    )

    score_summary = (
        df.groupby("risk_score")
        .agg(
            total=("pips", "count"),
            wins=("is_win", "sum"),
            losses=("is_win", lambda x: int((~x).sum())),
            avg_pips=("pips", "mean"),
            total_pips=("pips", "sum"),
        )
        .reset_index()
    )

    score_summary["win_rate"] = score_summary["wins"] / score_summary["total"] * 100
    score_summary.insert(0, "period", period)
    score_summary.insert(1, "source_file", csv_path.name)

    lane_summary = (
        df.groupby("analysis_lane")
        .agg(
            total=("pips", "count"),
            wins=("is_win", "sum"),
            losses=("is_win", lambda x: int((~x).sum())),
            avg_pips=("pips", "mean"),
            total_pips=("pips", "sum"),
        )
        .reset_index()
        .rename(columns={"analysis_lane": "lane"})
    )
    lane_summary["win_rate"] = lane_summary["wins"] / lane_summary["total"] * 100
    lane_summary.insert(0, "period", period)
    lane_summary.insert(1, "source_file", csv_path.name)

    lane_score_summary = (
        df.groupby(["analysis_lane", "risk_score"])
        .agg(
            total=("pips", "count"),
            wins=("is_win", "sum"),
            losses=("is_win", lambda x: int((~x).sum())),
            avg_pips=("pips", "mean"),
            total_pips=("pips", "sum"),
        )
        .reset_index()
        .rename(columns={"analysis_lane": "lane"})
    )
    lane_score_summary["win_rate"] = (
        lane_score_summary["wins"] / lane_score_summary["total"] * 100
    )
    lane_score_summary.insert(0, "period", period)
    lane_score_summary.insert(1, "source_file", csv_path.name)

    return df, monthly_summary, score_summary, lane_summary, lane_score_summary


def main() -> None:
    csv_files = sorted(BASE_DIR.glob(TARGET_GLOB))

    if not csv_files:
        print(f"対象CSVが見つかりません: {BASE_DIR} / pattern={TARGET_GLOB}")
        return

    print("=== 対象ファイル ===")
    for path in csv_files:
        print(path.name)

    all_details: list[pd.DataFrame] = []
    all_monthly_summaries: list[pd.DataFrame] = []
    all_score_summaries: list[pd.DataFrame] = []
    all_lane_summaries: list[pd.DataFrame] = []
    all_lane_score_summaries: list[pd.DataFrame] = []

    print("\n=== 月別分析開始 ===")
    for csv_path in csv_files:
        print(f"\n--- {csv_path.name} ---")
        try:
            detail_df, monthly_df, score_df, lane_df, lane_score_df = analyze_one_file(csv_path)
        except Exception as e:
            print(f"skip: {csv_path.name} | reason: {e}")
            continue

        all_details.append(detail_df)
        all_monthly_summaries.append(monthly_df)
        all_score_summaries.append(score_df)
        all_lane_summaries.append(lane_df)
        all_lane_score_summaries.append(lane_score_df)

        period = monthly_df.iloc[0]["period"]
        total_trades = int(monthly_df.iloc[0]["total_trades"])
        wins = int(monthly_df.iloc[0]["wins"])
        losses = int(monthly_df.iloc[0]["losses"])
        win_rate = float(monthly_df.iloc[0]["win_rate"])
        avg_pips = float(monthly_df.iloc[0]["avg_pips"])
        total_pips = float(monthly_df.iloc[0]["total_pips"])

        print(
            f"period={period} | 件数={total_trades} | 勝ち={wins} | 負け={losses} | "
            f"勝率={win_rate:.2f}% | 平均pips={avg_pips:.2f} | 合計pips={total_pips:.2f}"
        )

        print("\n[risk_score別]")
        print(
            score_df[
                ["risk_score", "total", "wins", "losses", "win_rate", "avg_pips", "total_pips"]
            ].to_string(index=False)
        )

        print("\n[lane別]")
        print(
            lane_df[
                ["lane", "total", "wins", "losses", "win_rate", "avg_pips", "total_pips"]
            ].to_string(index=False)
        )

        print("\n[lane × risk_score]")
        print(
            lane_score_df[
                ["lane", "risk_score", "total", "wins", "losses", "win_rate", "avg_pips", "total_pips"]
            ].to_string(index=False)
        )

    if not all_monthly_summaries:
        print("\n有効な分析対象ファイルがありませんでした。")
        return

    merged_details = pd.concat(all_details, ignore_index=True)
    merged_monthly = pd.concat(all_monthly_summaries, ignore_index=True)
    merged_score = pd.concat(all_score_summaries, ignore_index=True)
    merged_lane = pd.concat(all_lane_summaries, ignore_index=True)
    merged_lane_score = pd.concat(all_lane_score_summaries, ignore_index=True)

    merged_monthly = merged_monthly.sort_values("period").reset_index(drop=True)
    merged_score = merged_score.sort_values(["period", "risk_score"]).reset_index(drop=True)
    merged_lane = merged_lane.sort_values(["period", "lane"]).reset_index(drop=True)
    merged_lane_score = merged_lane_score.sort_values(
        ["period", "lane", "risk_score"]
    ).reset_index(drop=True)

    merged_details.to_csv(DETAIL_CSV, index=False, encoding="utf-8-sig")
    merged_monthly.to_csv(MONTHLY_SUMMARY_CSV, index=False, encoding="utf-8-sig")
    merged_score.to_csv(SCORE_SUMMARY_CSV, index=False, encoding="utf-8-sig")
    merged_lane.to_csv(LANE_SUMMARY_CSV, index=False, encoding="utf-8-sig")
    merged_lane_score.to_csv(LANE_SCORE_SUMMARY_CSV, index=False, encoding="utf-8-sig")

    print("\n=== 全体サマリ（月別） ===")
    print(
        merged_monthly[
            ["period", "total_trades", "wins", "losses", "win_rate", "avg_pips", "total_pips"]
        ].to_string(index=False)
    )

    overall = pd.DataFrame(
        [
            {
                "total_trades": len(merged_details),
                "wins": int(merged_details["is_win"].sum()),
                "losses": int((~merged_details["is_win"]).sum()),
                "win_rate": float(merged_details["is_win"].mean() * 100),
                "avg_pips": float(merged_details["pips"].mean()),
                "total_pips": float(merged_details["pips"].sum()),
            }
        ]
    )

    print("\n=== 全体サマリ（全ファイル合算） ===")
    print(overall.to_string(index=False))

    print("\n=== 保存ファイル ===")
    print(DETAIL_CSV.name)
    print(MONTHLY_SUMMARY_CSV.name)
    print(SCORE_SUMMARY_CSV.name)
    print(LANE_SUMMARY_CSV.name)
    print(LANE_SCORE_SUMMARY_CSV.name)


if __name__ == "__main__":
    main()