# src\backtest_gui_app\helpers.py
from __future__ import annotations

from pathlib import Path


def list_strategy_names(strategies_dir: Path) -> list[str]:
    if not strategies_dir.exists() or not strategies_dir.is_dir():
        return []

    names: list[str] = []
    for path in sorted(strategies_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        names.append(path.stem)
    return names


def list_csv_paths(data_dir: Path) -> list[Path]:
    if not data_dir.exists() or not data_dir.is_dir():
        return []

    csv_paths = sorted(data_dir.rglob("*.csv"))
    return [path for path in csv_paths if path.is_file()]