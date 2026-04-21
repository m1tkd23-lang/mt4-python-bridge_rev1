# src/mt4_bridge/app_config.py
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class AppConfigError(Exception):
    """Raised when application configuration is invalid."""


@dataclass(frozen=True)
class BridgePathConfig:
    root: Path
    market_snapshot_filename: str
    runtime_status_filename: str
    position_snapshot_filename: str

    @property
    def market_snapshot_path(self) -> Path:
        return self.root / self.market_snapshot_filename

    @property
    def runtime_status_path(self) -> Path:
        return self.root / self.runtime_status_filename

    @property
    def position_snapshot_path(self) -> Path:
        return self.root / self.position_snapshot_filename

    @property
    def command_queue_path(self) -> Path:
        return self.root / "command_queue"

    @property
    def result_queue_path(self) -> Path:
        return self.root / "result_queue"


@dataclass(frozen=True)
class SnapshotConfig:
    market_stale_seconds: int
    runtime_stale_seconds: int


@dataclass(frozen=True)
class SignalConfig:
    enabled: bool
    strategy_name: str


@dataclass(frozen=True)
class RuntimeConfig:
    state_file: Path
    skip_if_pending_command: bool


@dataclass(frozen=True)
class AppConfig:
    bridge: BridgePathConfig
    snapshot: SnapshotConfig
    signal: SignalConfig
    runtime: RuntimeConfig


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists() or not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AppConfigError(f"Config file not found: {path}")
    if not path.is_file():
        raise AppConfigError(f"Config path is not a file: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise AppConfigError(f"Failed to read config file: {path}") from exc
    except yaml.YAMLError as exc:
        raise AppConfigError(f"Invalid YAML config: {path}") from exc

    if raw is None:
        raise AppConfigError(f"Config file is empty: {path}")
    if not isinstance(raw, dict):
        raise AppConfigError("Top-level config must be a mapping")

    return raw


def _require_mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise AppConfigError(f"Config section '{key}' must be a mapping")
    return value


def _env_or_default(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise AppConfigError(f"Invalid boolean value: {value}")


def _get_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _get_app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return _get_repo_root()


def _resolve_first_existing_path(candidates: list[Path]) -> Path | None:
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    return None


def _resolve_config_path(config_path: Path | None) -> Path:
    if config_path is not None:
        return config_path.resolve()

    env_config = os.environ.get("MT4_APP_CONFIG", "").strip()
    if env_config:
        return Path(env_config).expanduser().resolve()

    app_base_dir = _get_app_base_dir()
    repo_root = _get_repo_root()

    candidates = [
        app_base_dir / "config" / "app.yaml",
        repo_root / "config" / "app.yaml",
    ]

    resolved = _resolve_first_existing_path(candidates)
    if resolved is not None:
        return resolved

    return candidates[0]


def _resolve_env_path(env_path: Path | None, config_file_path: Path) -> Path:
    if env_path is not None:
        return env_path.resolve()

    env_env = os.environ.get("MT4_APP_ENV", "").strip()
    if env_env:
        return Path(env_env).expanduser().resolve()

    app_base_dir = _get_app_base_dir()
    repo_root = _get_repo_root()
    config_base_dir = config_file_path.parent.parent

    candidates = [
        app_base_dir / ".env",
        config_base_dir / ".env",
        repo_root / ".env",
    ]

    resolved = _resolve_first_existing_path(candidates)
    if resolved is not None:
        return resolved

    return candidates[0]


def load_app_config(
    config_path: Path | None = None,
    env_path: Path | None = None,
) -> AppConfig:
    resolved_config_path = _resolve_config_path(config_path)
    resolved_env_path = _resolve_env_path(env_path, resolved_config_path)

    _load_env_file(resolved_env_path)
    raw = _load_yaml(resolved_config_path)

    bridge_raw = _require_mapping(raw, "bridge")
    snapshot_raw = _require_mapping(raw, "snapshot")
    signal_raw = _require_mapping(raw, "signal")
    runtime_raw = _require_mapping(raw, "runtime")

    default_bridge_root = str(bridge_raw.get("root", "")).strip()
    bridge_root = _env_or_default("MT4_BRIDGE_ROOT", default_bridge_root)
    if not bridge_root:
        raise AppConfigError("bridge.root is required")

    market_snapshot_filename = str(
        bridge_raw.get("market_snapshot_filename", "market_snapshot.json")
    ).strip()
    runtime_status_filename = str(
        bridge_raw.get("runtime_status_filename", "runtime_status.json")
    ).strip()
    position_snapshot_filename = str(
        bridge_raw.get("position_snapshot_filename", "position_snapshot.json")
    ).strip()

    market_stale_seconds_raw = _env_or_default(
        "MT4_MARKET_STALE_SECONDS",
        str(snapshot_raw.get("market_stale_seconds", 10)),
    )
    runtime_stale_seconds_raw = _env_or_default(
        "MT4_RUNTIME_STALE_SECONDS",
        str(snapshot_raw.get("runtime_stale_seconds", 10)),
    )

    signal_enabled_raw = _env_or_default(
        "MT4_SIGNAL_ENABLED",
        str(signal_raw.get("enabled", True)),
    )
    signal_strategy_name = _env_or_default(
        "MT4_SIGNAL_STRATEGY_NAME",
        str(signal_raw.get("strategy_name", "close_compare_v1")),
    ).strip()

    default_state_file = str(runtime_raw.get("state_file", "runtime/state.json")).strip()
    state_file_raw = _env_or_default("MT4_RUNTIME_STATE_FILE", default_state_file)

    skip_if_pending_command_raw = _env_or_default(
        "MT4_SKIP_IF_PENDING_COMMAND",
        str(runtime_raw.get("skip_if_pending_command", True)),
    )

    try:
        market_stale_seconds = int(market_stale_seconds_raw)
        runtime_stale_seconds = int(runtime_stale_seconds_raw)
        signal_enabled = _parse_bool(signal_enabled_raw)
        skip_if_pending_command = _parse_bool(skip_if_pending_command_raw)
    except ValueError as exc:
        raise AppConfigError("Invalid numeric config value") from exc

    state_file = Path(state_file_raw)
    if not state_file.is_absolute():
        app_base_dir = _get_app_base_dir()
        state_file = app_base_dir / state_file

    return AppConfig(
        bridge=BridgePathConfig(
            root=Path(bridge_root),
            market_snapshot_filename=market_snapshot_filename,
            runtime_status_filename=runtime_status_filename,
            position_snapshot_filename=position_snapshot_filename,
        ),
        snapshot=SnapshotConfig(
            market_stale_seconds=market_stale_seconds,
            runtime_stale_seconds=runtime_stale_seconds,
        ),
        signal=SignalConfig(
            enabled=signal_enabled,
            strategy_name=signal_strategy_name,
        ),
        runtime=RuntimeConfig(
            state_file=state_file,
            skip_if_pending_command=skip_if_pending_command,
        ),
    )