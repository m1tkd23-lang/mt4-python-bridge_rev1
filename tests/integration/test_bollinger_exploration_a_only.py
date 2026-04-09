# tests/integration/test_bollinger_exploration_a_only.py
"""Integration test: A-only (bollinger_range) exploration with real CSV data.

TASK-0062: Validates the exploration_loop bollinger flow (stage 1)
using actual USDJPY CSV data. Confirms:
- apply_strategy_overrides() runtime override works
- Single-month backtest + evaluation completes
- Cross-month (csv_dir) backtest + evaluation completes
- Bollinger exploration loop (small iteration) completes
- generate_strategy_file() is NOT called
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import patch

# Ensure src is importable
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from backtest.exploration_loop import (
    BollingerExplorationConfig,
    BollingerLoopConfig,
    run_bollinger_exploration,
    run_bollinger_exploration_loop,
    generate_bollinger_param_variations,
    BOLLINGER_PARAM_VARIATION_RANGES,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

CSV_DIR = _REPO_ROOT / "data" / "USDJPY-cd5_20250521_monthly"
STRATEGY_NAME = "bollinger_range_v4_4"


def _first_csv() -> Path:
    csvs = sorted(CSV_DIR.glob("*.csv"))
    assert csvs, f"No CSV files in {CSV_DIR}"
    return csvs[0]


def test_single_month_exploration():
    """Test 1: Single-month bollinger exploration (no overrides = baseline)."""
    logger.info("=== Test 1: Single-month baseline (no overrides) ===")
    csv_path = _first_csv()

    config = BollingerExplorationConfig(
        strategy_name=STRATEGY_NAME,
        csv_path=str(csv_path),
        pip_size=0.01,
    )

    result = run_bollinger_exploration(config)

    logger.info("  strategy_name: %s", result.strategy_name)
    logger.info("  param_overrides: %s", result.param_overrides)
    logger.info("  verdict: %s", result.verdict)
    logger.info("  evaluation reasons: %s", result.evaluation.reasons)
    logger.info("  stats_summary: %s", result.evaluation.stats_summary)

    assert result.strategy_name == STRATEGY_NAME
    assert result.verdict in ("adopt", "improve", "discard")
    assert result.param_overrides == {}
    return result


def test_single_month_with_overrides():
    """Test 2: Single-month with param overrides via apply_strategy_overrides."""
    logger.info("=== Test 2: Single-month with overrides ===")
    csv_path = _first_csv()

    overrides = {
        "mt4_bridge.strategies.bollinger_range_v4_4::BOLLINGER_PERIOD": 25.0,
        "mt4_bridge.strategies.bollinger_range_v4_4::BOLLINGER_SIGMA": 2.5,
    }

    config = BollingerExplorationConfig(
        strategy_name=STRATEGY_NAME,
        csv_path=str(csv_path),
        pip_size=0.01,
        param_overrides=overrides,
    )

    result = run_bollinger_exploration(config)

    logger.info("  verdict: %s", result.verdict)
    logger.info("  param_overrides applied: %s", result.param_overrides)
    logger.info("  stats_summary: %s", result.evaluation.stats_summary)

    assert result.param_overrides == overrides
    assert result.verdict in ("adopt", "improve", "discard")
    return result


def test_cross_month_exploration():
    """Test 3: Cross-month exploration using csv_dir (all 12 months)."""
    logger.info("=== Test 3: Cross-month (csv_dir) exploration ===")
    csv_path = _first_csv()

    config = BollingerExplorationConfig(
        strategy_name=STRATEGY_NAME,
        csv_path=str(csv_path),
        pip_size=0.01,
        csv_dir=str(CSV_DIR),
    )

    result = run_bollinger_exploration(config)

    logger.info("  verdict: %s", result.verdict)
    logger.info("  cross_month_evaluation: %s", result.cross_month_evaluation)
    logger.info("  integrated_evaluation: %s", result.integrated_evaluation)
    if result.aggregate_stats:
        logger.info("  aggregate month_count: %d", result.aggregate_stats.month_count)
        logger.info("  aggregate total_pips: %.1f", result.aggregate_stats.total_pips)
        logger.info(
            "  aggregate avg_pips/month: %.1f",
            result.aggregate_stats.average_pips_per_month,
        )

    assert result.cross_month_evaluation is not None
    assert result.integrated_evaluation is not None
    assert result.aggregate_stats is not None
    assert result.aggregate_stats.month_count >= 2
    return result


def test_param_variation_generation():
    """Test 4: generate_bollinger_param_variations produces valid overrides."""
    logger.info("=== Test 4: Param variation generation ===")
    variations = generate_bollinger_param_variations(
        strategy_name=STRATEGY_NAME,
        base_overrides=None,
        count=3,
    )

    logger.info("  generated %d variations", len(variations))
    for i, v in enumerate(variations):
        logger.info("  variation %d: %s", i, v)

    assert len(variations) > 0
    assert len(variations) <= 3

    expected_keys = set(BOLLINGER_PARAM_VARIATION_RANGES[STRATEGY_NAME].keys())
    for v in variations:
        assert set(v.keys()) == expected_keys
    return variations


def test_bollinger_loop_small():
    """Test 5: Bollinger exploration loop with max_iterations=2."""
    logger.info("=== Test 5: Bollinger exploration loop (2 iterations) ===")
    csv_path = _first_csv()

    config = BollingerLoopConfig(
        strategy_name=STRATEGY_NAME,
        csv_path=str(csv_path),
        pip_size=0.01,
        max_iterations=2,
        max_improve_retries=1,
        max_param_variations=2,
        csv_dir=str(CSV_DIR),
    )

    loop_result = run_bollinger_exploration_loop(config)

    logger.info("  iterations: %d", loop_result.iterations)
    logger.info("  stopped_reason: %s", loop_result.stopped_reason)
    logger.info("  results count: %d", len(loop_result.results))
    if loop_result.adopted:
        logger.info("  adopted overrides: %s", loop_result.adopted.param_overrides)

    assert loop_result.iterations >= 1
    assert loop_result.stopped_reason in ("adopt", "max_iterations")
    return loop_result


def test_generate_strategy_file_not_called():
    """Test 6: Verify generate_strategy_file is NOT invoked by bollinger path."""
    logger.info("=== Test 6: Verify generate_strategy_file NOT called ===")
    csv_path = _first_csv()

    with patch(
        "mt4_bridge.strategy_generator.generate_strategy_file",
        side_effect=AssertionError("generate_strategy_file must NOT be called"),
    ) as mock_gen:
        config = BollingerExplorationConfig(
            strategy_name=STRATEGY_NAME,
            csv_path=str(csv_path),
            pip_size=0.01,
        )
        result = run_bollinger_exploration(config)

        assert mock_gen.call_count == 0, "generate_strategy_file was called!"
        logger.info("  PASS: generate_strategy_file was NOT called (count=%d)", mock_gen.call_count)
    return result


def main():
    results = {}
    tests = [
        ("single_month_baseline", test_single_month_exploration),
        ("single_month_overrides", test_single_month_with_overrides),
        ("cross_month", test_cross_month_exploration),
        ("param_variations", test_param_variation_generation),
        ("loop_small", test_bollinger_loop_small),
        ("no_generate_strategy_file", test_generate_strategy_file_not_called),
    ]

    passed = 0
    failed = 0
    for name, func in tests:
        try:
            results[name] = func()
            logger.info("  >> %s: PASS\n", name)
            passed += 1
        except Exception as e:
            logger.error("  >> %s: FAIL - %s\n", name, e, exc_info=True)
            results[name] = str(e)
            failed += 1

    logger.info("=" * 60)
    logger.info("Results: %d passed, %d failed out of %d tests", passed, failed, len(tests))
    logger.info("=" * 60)

    return passed, failed, results


if __name__ == "__main__":
    passed, failed, results = main()
    sys.exit(1 if failed > 0 else 0)
