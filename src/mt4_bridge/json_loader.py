# src\mt4_bridge\json_loader.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonLoadError(Exception):
    """Raised when a JSON file cannot be loaded safely."""


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise JsonLoadError(f"JSON file not found: {path}")

    if not path.is_file():
        raise JsonLoadError(f"Path is not a file: {path}")

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as exc:
            raise JsonLoadError(f"Failed to decode JSON file: {path}") from exc
    except OSError as exc:
        raise JsonLoadError(f"Failed to read JSON file: {path}") from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise JsonLoadError(f"Invalid JSON content: {path}") from exc

    if not isinstance(data, dict):
        raise JsonLoadError(f"Top-level JSON must be an object: {path}")

    return data