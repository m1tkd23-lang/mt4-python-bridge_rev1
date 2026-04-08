# src/app_watch.py
from __future__ import annotations

import threading
import time
from collections.abc import Callable

from mt4_bridge.logging_utils import setup_logging

import app_cli


WATCH_INTERVAL_SECONDS = 1.0

logger = setup_logging()

OutputFunc = Callable[[str], None]


def _default_output(message: str) -> None:
    print(message)


def run_watch(
    *,
    stop_event: threading.Event | None = None,
    output_func: OutputFunc | None = None,
) -> int:
    resolved_stop_event = stop_event or threading.Event()
    out = output_func or _default_output

    logger.info(
        "app_watch start: interval_seconds=%s",
        WATCH_INTERVAL_SECONDS,
    )
    out(f"Watch started. Interval: {WATCH_INTERVAL_SECONDS:.1f}s")
    out("Press Stop to stop.")

    cycle = 0

    try:
        while not resolved_stop_event.is_set():
            cycle += 1
            logger.info("watch cycle start: cycle=%s", cycle)
            out(f"\n----- watch cycle {cycle} -----")

            try:
                return_code = app_cli.main(output_func=out)
                logger.info(
                    "watch cycle end: cycle=%s return_code=%s",
                    cycle,
                    return_code,
                )
            except Exception:
                logger.exception("watch cycle failed: cycle=%s", cycle)
                out("[ERROR] watch cycle failed unexpectedly.")

            logger.info(
                "watch sleep: cycle=%s seconds=%s",
                cycle,
                WATCH_INTERVAL_SECONDS,
            )

            if resolved_stop_event.wait(WATCH_INTERVAL_SECONDS):
                break

    except KeyboardInterrupt:
        logger.info("app_watch stopped by user")
        out("\nWatch stopped by user.")
        return 0

    logger.info("app_watch stopped")
    out("\nWatch stopped.")
    return 0


def main() -> int:
    return run_watch()


if __name__ == "__main__":
    raise SystemExit(main())