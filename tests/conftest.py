"""Shared fixtures for backtest integration tests."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is on the import path so that backtest, mt4_bridge etc. resolve.
_src = str(Path(__file__).resolve().parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)
