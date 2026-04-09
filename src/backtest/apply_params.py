# src/backtest/apply_params.py
"""CLI tool to write adopted strategy parameters back to strategy module files.

This provides *permanent* writes to strategy .py files, as opposed to the
temporary runtime overrides in ``strategy_params.py``.

Usage examples
--------------
# Preview changes (dry-run):
python -m backtest.apply_params \
    --strategy bollinger_combo_AB \
    --set "mt4_bridge.strategies.bollinger_range_v4_4::BOLLINGER_PERIOD=25" \
    --set "mt4_bridge.strategies.bollinger_range_v4_4::BOLLINGER_SIGMA=2.5" \
    --set "mt4_bridge.strategies.bollinger_trend_B::TREND_SLOPE_THRESHOLD=0.00003" \
    --dry-run

# Apply with backup:
python -m backtest.apply_params \
    --strategy bollinger_combo_AB \
    --set "mt4_bridge.strategies.bollinger_range_v4_4::BOLLINGER_PERIOD=25" \
    --backup

# Change LANE_A / LANE_B strategy names in combo file:
python -m backtest.apply_params \
    --strategy bollinger_combo_AB \
    --lane-a bollinger_range_A_guarded \
    --lane-b bollinger_trend_B3_weak_start

# List available parameters for a strategy:
python -m backtest.apply_params --strategy bollinger_combo_AB --list
"""
from __future__ import annotations

import argparse
import importlib
import re
import shutil
import sys
from pathlib import Path

# Ensure src/ is on sys.path when run as script
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest_gui_app.services.strategy_params import (
    StrategyParamSpec,
    get_param_specs,
)


def _module_path_to_file(module_path: str) -> Path:
    """Convert a dotted module path to a .py file path relative to src/."""
    src_dir = Path(__file__).resolve().parents[1]
    rel = module_path.replace(".", "/") + ".py"
    return src_dir / rel


def _parse_set_arg(raw: str) -> tuple[str, str, str]:
    """Parse ``module::NAME=VALUE`` into (module_path, const_name, raw_value)."""
    if "::" not in raw or "=" not in raw:
        raise ValueError(
            f"Invalid --set format: {raw!r}. "
            "Expected 'module.path::CONST_NAME=VALUE'."
        )
    qualified, value = raw.split("=", 1)
    module_path, const_name = qualified.rsplit("::", 1)
    return module_path, const_name, value.strip()


def _format_float(value: float, old_value_str: str) -> str:
    """Format a float preserving the style of the old value (decimal vs scientific)."""
    # If the old value used scientific notation, allow it
    if "e" in old_value_str.lower():
        return str(value)
    # Otherwise, preserve decimal style: count decimal places from old value
    if "." in old_value_str:
        decimal_part = old_value_str.split(".")[1]
        # Count significant trailing digits
        decimals = len(decimal_part)
        # Use enough decimals to represent the new value without scientific notation
        # At minimum, use the same number of decimals as the old value
        candidate = f"{value:.{decimals}f}"
        # If this loses precision, increase decimals
        if float(candidate) != value:
            for d in range(decimals + 1, 20):
                candidate = f"{value:.{d}f}"
                if float(candidate) == value:
                    break
        return candidate
    return str(value)


def _rewrite_constant(
    file_path: Path,
    const_name: str,
    new_value_str: str,
    param_type: str | None,
    *,
    dry_run: bool = False,
) -> tuple[bool, str, str]:
    """Rewrite a single module-level constant in a .py file.

    Returns (changed, old_line, new_line).
    """
    text = file_path.read_text(encoding="utf-8")

    # Match: CONST_NAME = <value>  with optional inline comment
    pattern = re.compile(
        rf"^({re.escape(const_name)}\s*=\s*)(.+?)(\s*#.*)?$",
        re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        raise ValueError(
            f"Constant {const_name!r} not found in {file_path}"
        )

    old_line = match.group(0)
    old_value_str = match.group(2).strip()

    # Format new value
    if param_type == "int":
        formatted = str(int(float(new_value_str)))
    elif param_type == "float":
        formatted = _format_float(float(new_value_str), old_value_str)
    else:
        # Auto-detect from old value format
        if "." in old_value_str or "e" in old_value_str.lower():
            formatted = _format_float(float(new_value_str), old_value_str)
        else:
            try:
                formatted = str(int(new_value_str))
            except ValueError:
                formatted = _format_float(float(new_value_str), old_value_str)

    # Preserve inline comment
    comment = match.group(3) or ""
    new_line = f"{match.group(1)}{formatted}{comment}"

    if old_line == new_line:
        return False, old_line, new_line

    if not dry_run:
        new_text = text[: match.start()] + new_line + text[match.end() :]
        file_path.write_text(new_text, encoding="utf-8")

    return True, old_line, new_line


def _rewrite_string_constant(
    file_path: Path,
    const_name: str,
    new_value: str,
    *,
    dry_run: bool = False,
) -> tuple[bool, str, str]:
    """Rewrite a string constant like LANE_A_STRATEGY = "..." in a .py file."""
    text = file_path.read_text(encoding="utf-8")

    pattern = re.compile(
        rf'^({re.escape(const_name)}\s*=\s*)"([^"]*)"(.*)$',
        re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        raise ValueError(
            f"String constant {const_name!r} not found in {file_path}"
        )

    old_line = match.group(0)
    new_line = f'{match.group(1)}"{new_value}"{match.group(3)}'

    if old_line == new_line:
        return False, old_line, new_line

    if not dry_run:
        new_text = text[: match.start()] + new_line + text[match.end() :]
        file_path.write_text(new_text, encoding="utf-8")

    return True, old_line, new_line


def _build_spec_index(
    specs: list[StrategyParamSpec],
) -> dict[str, StrategyParamSpec]:
    """Build a lookup dict keyed by 'module_path::name'."""
    return {f"{s.module_path}::{s.name}": s for s in specs}


def list_params(strategy_name: str) -> None:
    """Print available parameters for a strategy."""
    specs = get_param_specs(strategy_name)
    if not specs:
        print(f"No parameter specs found for strategy '{strategy_name}'.")
        return

    # Also show current values
    print(f"Parameters for '{strategy_name}':")
    print(f"  {'Qualified Key':<60} {'Type':<6} {'Current':<12} {'Default':<12}")
    print("  " + "-" * 90)
    for spec in specs:
        key = f"{spec.module_path}::{spec.name}"
        try:
            mod = importlib.import_module(spec.module_path)
            current = getattr(mod, spec.name, "?")
        except ImportError:
            current = "?"
        print(f"  {key:<60} {spec.param_type:<6} {current!s:<12} {spec.default!s:<12}")

    # Show combo file lane info
    try:
        combo_mod = importlib.import_module(
            f"mt4_bridge.strategies.{strategy_name}"
        )
        lane_a = getattr(combo_mod, "LANE_A_STRATEGY", None)
        lane_b = getattr(combo_mod, "LANE_B_STRATEGY", None)
        if lane_a is not None:
            print(f"\n  LANE_A_STRATEGY = \"{lane_a}\"")
        if lane_b is not None:
            print(f"  LANE_B_STRATEGY = \"{lane_b}\"")
    except ImportError:
        pass


def apply_params(
    strategy_name: str,
    set_args: list[str],
    lane_a: str | None = None,
    lane_b: str | None = None,
    *,
    dry_run: bool = False,
    backup: bool = False,
) -> list[dict]:
    """Apply parameter changes. Returns list of change records."""
    specs = get_param_specs(strategy_name)
    spec_index = _build_spec_index(specs)
    changes: list[dict] = []
    backed_up: set[Path] = set()

    def _ensure_backup(fp: Path) -> None:
        if backup and fp not in backed_up:
            bak = fp.with_suffix(".py.bak")
            if not dry_run:
                shutil.copy2(fp, bak)
            backed_up.add(fp)
            print(f"  [backup] {fp} -> {bak}")

    # Apply numeric parameter changes
    for raw in set_args:
        try:
            module_path, const_name, raw_value = _parse_set_arg(raw)
        except ValueError as exc:
            print(f"  [ERROR] {exc}")
            changes.append({"key": raw, "status": "error", "reason": str(exc)})
            continue
        qualified = f"{module_path}::{const_name}"
        spec = spec_index.get(qualified)
        param_type = spec.param_type if spec else None

        file_path = _module_path_to_file(module_path)
        if not file_path.exists():
            print(f"  [ERROR] File not found: {file_path}")
            changes.append({
                "key": qualified,
                "status": "error",
                "reason": f"file not found: {file_path}",
            })
            continue

        _ensure_backup(file_path)

        try:
            changed, old_line, new_line = _rewrite_constant(
                file_path, const_name, raw_value, param_type, dry_run=dry_run,
            )
        except ValueError as exc:
            print(f"  [ERROR] {exc}")
            changes.append({
                "key": qualified,
                "status": "error",
                "reason": str(exc),
            })
            continue

        tag = "[DRY-RUN] " if dry_run else ""
        if changed:
            print(f"  {tag}{qualified}")
            print(f"    old: {old_line.strip()}")
            print(f"    new: {new_line.strip()}")
            changes.append({
                "key": qualified,
                "status": "changed" if not dry_run else "would_change",
                "old": old_line.strip(),
                "new": new_line.strip(),
            })
        else:
            print(f"  {tag}{qualified} (no change)")
            changes.append({"key": qualified, "status": "no_change"})

    # Apply LANE_A / LANE_B changes
    combo_file = _module_path_to_file(f"mt4_bridge.strategies.{strategy_name}")
    if not combo_file.exists():
        if lane_a or lane_b:
            print(f"  [ERROR] Combo file not found: {combo_file}")
    else:
        for lane_const, lane_value in [
            ("LANE_A_STRATEGY", lane_a),
            ("LANE_B_STRATEGY", lane_b),
        ]:
            if lane_value is None:
                continue
            _ensure_backup(combo_file)
            try:
                changed, old_line, new_line = _rewrite_string_constant(
                    combo_file, lane_const, lane_value, dry_run=dry_run,
                )
            except ValueError as exc:
                print(f"  [ERROR] {exc}")
                changes.append({
                    "key": lane_const,
                    "status": "error",
                    "reason": str(exc),
                })
                continue

            tag = "[DRY-RUN] " if dry_run else ""
            if changed:
                print(f"  {tag}{lane_const} in {combo_file.name}")
                print(f"    old: {old_line.strip()}")
                print(f"    new: {new_line.strip()}")
                changes.append({
                    "key": lane_const,
                    "file": str(combo_file.name),
                    "status": "changed" if not dry_run else "would_change",
                    "old": old_line.strip(),
                    "new": new_line.strip(),
                })
            else:
                print(f"  {tag}{lane_const} (no change)")
                changes.append({"key": lane_const, "status": "no_change"})

    return changes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Write adopted strategy parameters to strategy module files. "
            "This is a permanent write, unlike the GUI runtime overrides."
        ),
    )
    parser.add_argument(
        "--strategy",
        required=True,
        help="Strategy name, e.g. bollinger_combo_AB or bollinger_combo_AB_v1.",
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        dest="set_args",
        metavar="MODULE::NAME=VALUE",
        help=(
            "Set a parameter. Format: 'module.path::CONST_NAME=VALUE'. "
            "Can be specified multiple times."
        ),
    )
    parser.add_argument(
        "--lane-a",
        help="Set LANE_A_STRATEGY in the combo file.",
    )
    parser.add_argument(
        "--lane-b",
        help="Set LANE_B_STRATEGY in the combo file.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_params",
        help="List available parameters for the strategy and exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files.",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create .py.bak backup before writing.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.list_params:
        list_params(args.strategy)
        return 0

    if not args.set_args and args.lane_a is None and args.lane_b is None:
        print("[ERROR] No changes specified. Use --set, --lane-a, or --lane-b.")
        parser.print_help()
        return 1

    mode = "DRY-RUN" if args.dry_run else "APPLY"
    print(f"[{mode}] Applying parameters for strategy '{args.strategy}':")

    changes = apply_params(
        strategy_name=args.strategy,
        set_args=args.set_args,
        lane_a=args.lane_a,
        lane_b=args.lane_b,
        dry_run=args.dry_run,
        backup=args.backup,
    )

    errors = [c for c in changes if c.get("status") == "error"]
    if errors:
        print(f"\n[WARN] {len(errors)} error(s) occurred.")
        return 1

    if args.dry_run:
        print("\n[DRY-RUN] No files were modified.")
    else:
        applied = [c for c in changes if c.get("status") == "changed"]
        print(f"\n[DONE] {len(applied)} parameter(s) written.")
        print(
            "Verify by re-running the backtest:\n"
            f"  python -m backtest.runner --csv-dir data/USDJPY-cd5_20250521_monthly "
            f"--strategy {args.strategy} --pip-size 0.01 --compare-ab"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
