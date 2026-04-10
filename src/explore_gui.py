# src/explore_gui.py
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtWidgets import QApplication

from explore_gui_app.views.main_window import ExploreMainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = ExploreMainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
