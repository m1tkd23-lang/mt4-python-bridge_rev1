# src\explore_gui_app\services\month_selection.py
from __future__ import annotations

from pathlib import Path


def list_csv_files(csv_dir: str) -> list[Path]:
    p = Path(csv_dir)
    if not p.exists():
        return []

    files = [f for f in p.glob("*.csv") if f.is_file()]
    files.sort()
    return files


def select_latest_n(files: list[Path], n: int) -> list[Path]:
    if not files:
        return []
    return files[-n:]