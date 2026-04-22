# analysis/middle_already_crossed_scan.py
# Phase 1: エントリーバー時点で既に中央バンドを越えていたトレードを抽出して
# 件数・月別分布・平均 pips・exit 内訳を実測する。
#
# 入力: analysis/out/A_opt_duk_tradelog/*.jsonl
#        analysis/out/A_opt_brk_tradelog/*.jsonl
# 出力: 標準出力 (サマリテーブル)
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATASETS = [
    ("DUK", REPO / "analysis/out/A_opt_duk_tradelog"),
    ("BRK", REPO / "analysis/out/A_opt_brk_tradelog"),
]

_RE_LATEST_CLOSE = re.compile(r"(?<![a-zA-Z_])latest_close=([\-\d.]+)")
_RE_MIDDLE = re.compile(r"(?<![a-zA-Z_])middle=([\-\d.]+)")


def _parse_float(pattern: re.Pattern, text: str) -> float | None:
    m = pattern.search(text)
    return float(m.group(1)) if m else None


def _is_already_crossed(position_type: str, latest_close: float, middle: float) -> bool:
    if position_type == "buy":
        return latest_close >= middle
    if position_type == "sell":
        return latest_close <= middle
    return False


def _month_of(entry_time_str: str) -> str:
    # "2024-01-02 03:40:00" -> "2024-01"
    return entry_time_str[:7]


def scan_dir(label: str, d: Path) -> list[dict]:
    rows: list[dict] = []
    entries: dict[str, dict] = {}
    for path in sorted(d.glob("*.jsonl")):
        with path.open(encoding="utf-8") as f:
            for line in f:
                ev = json.loads(line)
                ev_type = ev.get("event_type")
                if ev_type == "ENTRY":
                    reason = ev.get("entry_signal_reason") or ""
                    latest_close = _parse_float(_RE_LATEST_CLOSE, reason)
                    middle = _parse_float(_RE_MIDDLE, reason)
                    if latest_close is None or middle is None:
                        continue
                    entries[ev["trade_id"]] = {
                        "dataset": label,
                        "month": _month_of(ev["entry_time"]),
                        "position_type": ev["position_type"],
                        "entry_price": ev["entry_price"],
                        "latest_close": latest_close,
                        "middle": middle,
                        "already_crossed": _is_already_crossed(
                            ev["position_type"], latest_close, middle
                        ),
                        "dist_from_middle_pips": round(
                            abs(latest_close - middle) * 100, 2
                        ),
                    }
                elif ev_type in {"SL_HIT", "TP_HIT", "SIGNAL_CLOSE", "FORCED_END", "EXIT"}:
                    trade_id = ev.get("trade_id")
                    if trade_id and trade_id in entries:
                        entries[trade_id]["exit_event"] = ev_type
                        entries[trade_id]["exit_reason_code"] = ev.get("reason_code")
                        entries[trade_id]["pips"] = ev.get("pips")
                        entries[trade_id]["holding_bars"] = ev.get("holding_bars")
                        rows.append(entries.pop(trade_id))
    # leftover entries (no exit) are ignored
    return rows


def summarize(rows: list[dict], tag: str) -> None:
    total = len(rows)
    crossed = [r for r in rows if r["already_crossed"]]
    not_crossed = [r for r in rows if not r["already_crossed"]]

    def _pips_stats(xs: list[dict]) -> str:
        ps = [r["pips"] for r in xs if r.get("pips") is not None]
        if not ps:
            return "n=0"
        avg = sum(ps) / len(ps)
        wins = sum(1 for p in ps if p > 0)
        total_pips = sum(ps)
        return (
            f"n={len(ps):>3} "
            f"avg={avg:+6.2f} "
            f"sum={total_pips:+7.1f} "
            f"win_rate={wins/len(ps)*100:5.1f}%"
        )

    print(f"\n=== {tag} ===")
    print(f"  total entries     : {total}")
    print(f"  already_crossed   : {len(crossed):>3} ({len(crossed)/total*100:.1f}%)" if total else "  (empty)")
    print(f"  not_crossed       : {len(not_crossed):>3}")
    print(f"  crossed  stats    : {_pips_stats(crossed)}")
    print(f"  ncross   stats    : {_pips_stats(not_crossed)}")

    if crossed:
        # distance bucket (pips from middle at entry)
        buckets: dict[str, list[dict]] = defaultdict(list)
        for r in crossed:
            d = r["dist_from_middle_pips"]
            if d < 1:
                key = "0-1"
            elif d < 2:
                key = "1-2"
            elif d < 3:
                key = "2-3"
            elif d < 5:
                key = "3-5"
            else:
                key = "5+"
            buckets[key].append(r)
        print(f"  dist buckets (pips past middle at entry):")
        for k in ["0-1", "1-2", "2-3", "3-5", "5+"]:
            xs = buckets.get(k, [])
            if xs:
                print(f"    {k:>5}: {_pips_stats(xs)}")

        # exit code breakdown
        by_exit: dict[str, list[dict]] = defaultdict(list)
        for r in crossed:
            by_exit[r.get("exit_reason_code") or "?"].append(r)
        print(f"  exit breakdown (crossed trades):")
        for code, xs in sorted(by_exit.items(), key=lambda kv: -len(kv[1])):
            print(f"    {code:<30}: {_pips_stats(xs)}")

        # month breakdown
        by_month: dict[str, list[dict]] = defaultdict(list)
        for r in crossed:
            by_month[r["month"]].append(r)
        print(f"  month breakdown (crossed trades):")
        for m in sorted(by_month):
            xs = by_month[m]
            ps = [r["pips"] for r in xs if r.get("pips") is not None]
            avg = sum(ps) / len(ps) if ps else 0.0
            total_pips = sum(ps)
            print(f"    {m}: n={len(xs):>2} sum={total_pips:+7.1f} avg={avg:+6.2f}")


def main() -> None:
    all_rows: list[dict] = []
    for label, d in DATASETS:
        if not d.exists():
            print(f"[SKIP] {label}: {d} does not exist")
            continue
        rows = scan_dir(label, d)
        all_rows.extend(rows)
        summarize(rows, label)

    summarize(all_rows, "ALL (DUK + BRK)")


if __name__ == "__main__":
    main()
