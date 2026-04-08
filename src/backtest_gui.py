# src\backtest_gui.py
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtWidgets import QApplication

from backtest_gui_app.views.main_window import BacktestMainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = BacktestMainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())