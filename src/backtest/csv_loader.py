# src\backtest\csv_loader.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import csv


class CsvLoadError(Exception):
    """Raised when historical bar CSV cannot be loaded safely."""


@dataclass(frozen=True)
class HistoricalBarRow:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: int


@dataclass(frozen=True)
class HistoricalBarDataset:
    rows: list[HistoricalBarRow]
    digits: int
    point: float


_MT4_DATE_FORMAT = "%Y.%m.%d %H:%M"


def _is_header_row(row: list[str]) -> bool:
    if not row:
        return False
    first = row[0].strip().lower()
    return first in {"date", "<date>", "time", "<time>", "datetime", "<datetime>"}


def _split_line(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped:
        return []

    if "\t" in stripped:
        return [part.strip() for part in stripped.split("\t")]

    reader = csv.reader([stripped])
    return [part.strip() for part in next(reader)]


def _count_decimals(raw: str) -> int:
    text = raw.strip()
    if "." not in text:
        return 0
    return len(text.rsplit(".", 1)[1])


def _parse_row(parts: list[str], line_number: int) -> tuple[HistoricalBarRow, int]:
    if len(parts) < 7:
        raise CsvLoadError(
            f"CSV row must have at least 7 columns at line {line_number}: {parts}"
        )

    date_text = parts[0]
    time_text = parts[1]
    open_text = parts[2]
    high_text = parts[3]
    low_text = parts[4]
    close_text = parts[5]
    volume_text = parts[6]

    try:
        row_time = datetime.strptime(f"{date_text} {time_text}", _MT4_DATE_FORMAT)
        row = HistoricalBarRow(
            time=row_time,
            open=float(open_text),
            high=float(high_text),
            low=float(low_text),
            close=float(close_text),
            tick_volume=int(float(volume_text)),
        )
    except ValueError as exc:
        raise CsvLoadError(
            f"Failed to parse CSV row at line {line_number}: {parts}"
        ) from exc

    digits = max(
        _count_decimals(open_text),
        _count_decimals(high_text),
        _count_decimals(low_text),
        _count_decimals(close_text),
    )
    return row, digits


def load_historical_bars_csv(path: Path) -> HistoricalBarDataset:
    if not path.exists():
        raise CsvLoadError(f"CSV file not found: {path}")
    if not path.is_file():
        raise CsvLoadError(f"CSV path is not a file: {path}")

    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise CsvLoadError(f"Failed to read CSV file: {path}") from exc

    rows: list[HistoricalBarRow] = []
    detected_digits = 0

    for index, raw_line in enumerate(lines, start=1):
        parts = _split_line(raw_line)
        if not parts:
            continue
        if _is_header_row(parts):
            continue

        row, row_digits = _parse_row(parts, index)
        rows.append(row)
        detected_digits = max(detected_digits, row_digits)

    if not rows:
        raise CsvLoadError(f"No historical bars loaded from CSV: {path}")

    rows.sort(key=lambda item: item.time)
    point = 10 ** (-detected_digits) if detected_digits > 0 else 1.0

    return HistoricalBarDataset(
        rows=rows,
        digits=detected_digits,
        point=point,
    )


def load_historical_bars_csv_multi(
    paths: list[Path],
) -> HistoricalBarDataset:
    """複数の CSV ファイルを時系列連結して 1 つの HistoricalBarDataset を返す。

    - 時刻が重複する行は後勝ち(ただし複数ファイル間で同一時刻の bar は通常無い)
    - digits は全ファイル最大値、point はそれに合わせる
    - 月跨ぎ BT でウォームアップ/強制決済の人工的不連続を排除するために使う
    """
    if not paths:
        raise CsvLoadError("load_historical_bars_csv_multi requires at least one path")

    all_rows: dict[datetime, HistoricalBarRow] = {}
    detected_digits = 0

    for path in paths:
        ds = load_historical_bars_csv(path)
        detected_digits = max(detected_digits, ds.digits)
        for row in ds.rows:
            all_rows[row.time] = row

    merged = sorted(all_rows.values(), key=lambda item: item.time)
    if not merged:
        raise CsvLoadError("No historical bars loaded from provided CSV list")

    point = 10 ** (-detected_digits) if detected_digits > 0 else 1.0
    return HistoricalBarDataset(
        rows=merged,
        digits=detected_digits,
        point=point,
    )