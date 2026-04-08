# scripts/split_csv_by_month.py
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


def extract_year_month(date_str: str) -> str:
    parts = date_str.strip().split(".")
    if len(parts) != 3:
        raise ValueError(f"日付形式が想定外です: {date_str!r}")
    year, month, _day = parts
    return f"{year}-{month}"


def split_csv_by_month(input_csv_path: str, output_dir: str | None = None) -> None:
    input_path = Path(input_csv_path)
    if not input_path.exists():
        raise FileNotFoundError(f"入力CSVが見つかりません: {input_path}")

    if output_dir is None:
        output_path = input_path.parent / f"{input_path.stem}_monthly"
    else:
        output_path = Path(output_dir)

    output_path.mkdir(parents=True, exist_ok=True)

    monthly_rows: dict[str, list[list[str]]] = defaultdict(list)

    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        for line_no, row in enumerate(reader, start=1):
            if not row:
                continue

            if len(row) < 2:
                raise ValueError(
                    f"{line_no}行目の列数が不足しています。少なくとも2列必要です: {row!r}"
                )

            date_str = row[0].strip()
            year_month = extract_year_month(date_str)
            monthly_rows[year_month].append(row)

    if not monthly_rows:
        print("データ行がありませんでした。")
        return

    for year_month in sorted(monthly_rows.keys()):
        out_file = output_path / f"{input_path.stem}_{year_month}.csv"
        with out_file.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(monthly_rows[year_month])

        print(f"saved: {out_file} rows={len(monthly_rows[year_month])}")

    print("完了しました。")


if __name__ == "__main__":
    input_csv = r"C:\WS\repos\mt4-python-bridge\data\USDJPY-cd5_20250521.csv"
    split_csv_by_month(input_csv)