"""Dukascopy から USDJPY 5 分足を取得し本プロジェクト形式で月別 CSV 出力する。

前提:
    pip install -r requirements.txt  (dukascopy-python / pandas が入る)

使い方:
    PYTHONPATH=src .venv/Scripts/python.exe scripts/fetch_dukascopy_data.py \
        --start 2024-01-01 --end 2024-12-31

出力:
    data/USDJPY-cd5_dukascopy_monthly/USDJPY-cd5_dukascopy_{YYYY-MM}.csv

仕様:
    - Dukascopy の tick → 5 分足(bid side)を取得。日曜は market closed で自然に除外される。
    - timestamp は Dukascopy から UTC で返る → FXTF サーバー時刻 (EET/EEST, Europe/Athens)
      に変換して naive datetime で保存。DST 切替は自動(pytz / zoneinfo)。
    - CSV 書式は既存 data/USDJPY-cd5_20250521_monthly/*.csv と同一:
        YYYY.MM.DD,HH:MM,O,H,L,C,volume
    - 本プロジェクトの戦術フィルタ (A {5,7,13} / B {4,8,10}) は broker hour 前提なので、
      ここで Europe/Athens に変換すれば MT4 サーバー時刻と整合する。

依存:
    - dukascopy-python (fetch, INSTRUMENT_FX_MAJORS_USD_JPY, INTERVAL_MIN_5, OFFER_SIDE_BID)
    - pandas (DataFrame groupby)
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
try:
    from zoneinfo import ZoneInfo
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "zoneinfo is not available. Use Python 3.9+."
    ) from exc


def _resolve_broker_tz() -> "ZoneInfo":
    """Windows の zoneinfo は tzdata パッケージを必要とする。

    tzdata 未インストールなら手順を表示して exit する。
    """
    try:
        return ZoneInfo("Europe/Athens")
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(
            "\n".join(
                [
                    "[error] Could not load timezone 'Europe/Athens'.",
                    "On Windows, zoneinfo requires the 'tzdata' PyPI package.",
                    "Run: pip install tzdata   (or: pip install -r requirements.txt)",
                    f"Underlying error: {type(exc).__name__}: {exc}",
                ]
            )
        ) from exc


# FXTF MT4 サーバー時刻と一致する TZ (EET 冬 +2h / EEST 夏 +3h の自動切替)
# 実体参照は main() 冒頭で解決する
FXTF_BROKER_TZ: "ZoneInfo | None" = None

# 出力先 (自動作成)
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "USDJPY-cd5_dukascopy_monthly"

# CSV 書式: USDJPY は 3 digit 想定 (既存 CSV と一致)
PRICE_DECIMALS = 3


def _parse_date(text: str) -> datetime:
    """YYYY-MM-DD を UTC の datetime に変換。"""
    dt = datetime.strptime(text, "%Y-%m-%d")
    return dt.replace(tzinfo=timezone.utc)


def fetch_and_save(start_utc: datetime, end_utc: datetime) -> None:
    # import はここで遅延(依存を必要な時だけ読む)
    import dukascopy_python
    from dukascopy_python import fetch
    from dukascopy_python.instruments import INSTRUMENT_FX_MAJORS_USD_JPY
    import pandas as pd

    print(f"[fetch] Dukascopy USDJPY M5: {start_utc.isoformat()} -> {end_utc.isoformat()} (UTC)")
    df: "pd.DataFrame" = fetch(
        instrument=INSTRUMENT_FX_MAJORS_USD_JPY,
        interval=dukascopy_python.INTERVAL_MIN_5,
        offer_side=dukascopy_python.OFFER_SIDE_BID,
        start=start_utc,
        end=end_utc,
    )
    if df is None or df.empty:
        print("[warn] No data returned from Dukascopy.")
        return

    # index (UTC) → Europe/Athens (FXTF broker 時刻) に変換して naive にする
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    broker_tz = FXTF_BROKER_TZ or _resolve_broker_tz()
    df.index = df.index.tz_convert(broker_tz).tz_localize(None)

    # カラム名ゆらぎ吸収
    df.columns = [c.lower() for c in df.columns]
    for required in ("open", "high", "low", "close"):
        if required not in df.columns:
            raise RuntimeError(
                f"Expected column '{required}' missing. Got: {list(df.columns)}"
            )
    if "volume" not in df.columns:
        df["volume"] = 0

    # 月別にグループ化
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    grouped = df.groupby([df.index.year, df.index.month])
    for (year, month), group in grouped:
        out_path = OUTPUT_DIR / f"USDJPY-cd5_dukascopy_{year:04d}-{month:02d}.csv"
        _write_month_csv(out_path, group)
        print(f"[write] {out_path.name}  {len(group)} bars")


def _write_month_csv(out_path: Path, group) -> None:
    fmt = f"{{:.{PRICE_DECIMALS}f}}"
    lines = []
    for ts, row in group.iterrows():
        date_part = ts.strftime("%Y.%m.%d")
        time_part = ts.strftime("%H:%M")
        lines.append(
            ",".join(
                [
                    date_part,
                    time_part,
                    fmt.format(float(row["open"])),
                    fmt.format(float(row["high"])),
                    fmt.format(float(row["low"])),
                    fmt.format(float(row["close"])),
                    str(int(float(row.get("volume", 0) or 0))),
                ]
            )
        )
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch USDJPY M5 from Dukascopy and save as project-format monthly CSVs."
    )
    parser.add_argument("--start", required=True, help="YYYY-MM-DD (UTC, inclusive)")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD (UTC, inclusive)")
    args = parser.parse_args(argv)

    # 早期に TZ 解決(tzdata 未インストール時は分かりやすいエラーで exit)
    global FXTF_BROKER_TZ
    FXTF_BROKER_TZ = _resolve_broker_tz()

    start_utc = _parse_date(args.start)
    # end の日の終わりまで取得する
    end_utc = _parse_date(args.end).replace(hour=23, minute=59, second=59)

    if end_utc <= start_utc:
        print("[error] --end must be after --start", file=sys.stderr)
        return 1

    fetch_and_save(start_utc=start_utc, end_utc=end_utc)
    print(f"[done] output dir: {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
