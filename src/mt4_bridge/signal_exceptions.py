# src\mt4_bridge\signal_exceptions.py
from __future__ import annotations


class SignalEngineError(Exception):
    """Raised when signal evaluation cannot be performed safely."""