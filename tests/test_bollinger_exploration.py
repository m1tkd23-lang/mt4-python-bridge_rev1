"""Integration tests for bollinger exploration in exploration_loop.py.

Tests run_bollinger_exploration and run_bollinger_exploration_loop against
real CSV data in data/USDJPY-cd5_20250521_monthly/.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backtest.evaluator import (
    CrossMonthEvaluationResult,
    EvaluationResult,
    EvaluationVerdict,
    IntegratedEvaluationResult,
)
from backtest.aggregate_stats import AggregateStats
from backtest.exploration_loop import (
    BollingerExplorationConfig,
    BollingerExplorationResult,
    BollingerLoopConfig,
    BollingerLoopResult,
    run_bollinger_exploration,
    run_bollinger_exploration_loop,
    generate_bollinger_param_variations,
    BOLLINGER_PARAM_VARIATION_RANGES,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "USDJPY-cd5_20250521_monthly"
# Pick the first CSV alphabetically as the single-month representative.
FIRST_CSV = sorted(DATA_DIR.glob("*.csv"))[0]

VALID_VERDICTS = {"adopt", "improve", "discard"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_evaluation_result(er: EvaluationResult) -> None:
    """Check common structure of a single-month EvaluationResult."""
    assert isinstance(er, EvaluationResult)
    assert isinstance(er.verdict, EvaluationVerdict)
    assert er.verdict.value in VALID_VERDICTS
    assert isinstance(er.reasons, list)
    assert isinstance(er.stats_summary, dict)
    assert "total_pips" in er.stats_summary
    assert "profit_factor" in er.stats_summary
    assert "trades" in er.stats_summary


def _assert_cross_month(cm: CrossMonthEvaluationResult) -> None:
    assert isinstance(cm, CrossMonthEvaluationResult)
    assert cm.verdict.value in VALID_VERDICTS
    assert isinstance(cm.reasons, list)
    assert "month_count" in cm.stats_summary


def _assert_integrated(ie: IntegratedEvaluationResult) -> None:
    assert isinstance(ie, IntegratedEvaluationResult)
    assert ie.verdict.value in VALID_VERDICTS
    assert isinstance(ie.reasons, list)
    assert "total_pips" in ie.stats_summary
    assert "average_pips_per_month" in ie.stats_summary


# ===========================================================================
# run_bollinger_exploration tests
# ===========================================================================


class TestRunBollingerExploration:
    """Tests for run_bollinger_exploration (single cycle)."""

    def test_single_month_no_overrides(self) -> None:
        """Run with a single CSV, no parameter overrides — basic smoke test."""
        config = BollingerExplorationConfig(
            strategy_name="bollinger_range_v4_4",
            csv_path=str(FIRST_CSV),
            timeframe="M5",
            pip_size=0.01,
        )
        result = run_bollinger_exploration(config)

        assert isinstance(result, BollingerExplorationResult)
        assert result.strategy_name == "bollinger_range_v4_4"
        assert isinstance(result.param_overrides, dict)
        assert result.verdict in VALID_VERDICTS
        _assert_evaluation_result(result.evaluation)
        # No csv_dir → no cross-month / integrated
        assert result.cross_month_evaluation is None
        assert result.integrated_evaluation is None
        assert result.aggregate_stats is None

    def test_single_month_with_overrides(self) -> None:
        """Run with explicit param overrides on a single CSV."""
        overrides = {
            "mt4_bridge.strategies.bollinger_range_v4_4::BOLLINGER_PERIOD": 25,
            "mt4_bridge.strategies.bollinger_range_v4_4::BOLLINGER_SIGMA": 2.0,
        }
        config = BollingerExplorationConfig(
            strategy_name="bollinger_range_v4_4",
            csv_path=str(FIRST_CSV),
            timeframe="M5",
            pip_size=0.01,
            param_overrides=overrides,
        )
        result = run_bollinger_exploration(config)

        assert isinstance(result, BollingerExplorationResult)
        assert result.param_overrides == overrides
        assert result.verdict in VALID_VERDICTS
        _assert_evaluation_result(result.evaluation)

    def test_cross_month_with_csv_dir(self) -> None:
        """Run with csv_dir to trigger cross-month and integrated evaluation."""
        config = BollingerExplorationConfig(
            strategy_name="bollinger_range_v4_4",
            csv_path=str(FIRST_CSV),
            csv_dir=str(DATA_DIR),
            timeframe="M5",
            pip_size=0.01,
        )
        result = run_bollinger_exploration(config)

        assert isinstance(result, BollingerExplorationResult)
        assert result.verdict in VALID_VERDICTS

        # cross-month and integrated should be populated
        assert result.cross_month_evaluation is not None
        _assert_cross_month(result.cross_month_evaluation)

        assert result.integrated_evaluation is not None
        _assert_integrated(result.integrated_evaluation)

        assert result.aggregate_stats is not None
        assert isinstance(result.aggregate_stats, AggregateStats)
        assert result.aggregate_stats.month_count >= 2

        # When csv_dir is given, the final verdict comes from integrated eval
        assert result.verdict == result.integrated_evaluation.verdict.value


# ===========================================================================
# run_bollinger_exploration_loop tests
# ===========================================================================


class TestRunBollingerExplorationLoop:
    """Tests for run_bollinger_exploration_loop (multi-cycle)."""

    def test_loop_single_month_max2(self) -> None:
        """Loop with max_iterations=2 on single CSV, verifying structure."""
        config = BollingerLoopConfig(
            strategy_name="bollinger_range_v4_4",
            csv_path=str(FIRST_CSV),
            timeframe="M5",
            pip_size=0.01,
            max_iterations=2,
            max_improve_retries=1,
            max_param_variations=2,
            random_seed=42,
        )
        result = run_bollinger_exploration_loop(config)

        assert isinstance(result, BollingerLoopResult)
        assert result.iterations >= 1
        assert result.iterations <= 2
        assert isinstance(result.results, list)
        assert len(result.results) >= 1
        assert result.stopped_reason in ("adopt", "max_iterations")

        for r in result.results:
            assert isinstance(r, BollingerExplorationResult)
            assert r.strategy_name == "bollinger_range_v4_4"
            assert r.verdict in VALID_VERDICTS
            _assert_evaluation_result(r.evaluation)

    def test_loop_cross_month_max2(self) -> None:
        """Loop with csv_dir for cross-month eval, max_iterations=2."""
        config = BollingerLoopConfig(
            strategy_name="bollinger_range_v4_4",
            csv_path=str(FIRST_CSV),
            csv_dir=str(DATA_DIR),
            timeframe="M5",
            pip_size=0.01,
            max_iterations=2,
            max_improve_retries=1,
            max_param_variations=2,
            random_seed=42,
        )
        result = run_bollinger_exploration_loop(config)

        assert isinstance(result, BollingerLoopResult)
        assert result.iterations >= 1

        for r in result.results:
            assert isinstance(r, BollingerExplorationResult)
            assert r.verdict in VALID_VERDICTS
            # Each iteration with csv_dir should have cross-month eval
            assert r.cross_month_evaluation is not None
            assert r.integrated_evaluation is not None
            assert r.aggregate_stats is not None

    def test_loop_adopted_has_result(self) -> None:
        """If loop adopts, the adopted field should be populated."""
        config = BollingerLoopConfig(
            strategy_name="bollinger_range_v4_4",
            csv_path=str(FIRST_CSV),
            timeframe="M5",
            pip_size=0.01,
            max_iterations=3,
            random_seed=42,
        )
        result = run_bollinger_exploration_loop(config)

        if result.stopped_reason == "adopt":
            assert result.adopted is not None
            assert isinstance(result.adopted, BollingerExplorationResult)
            assert result.adopted.verdict == "adopt"
        else:
            # max_iterations reached — adopted may be None
            assert result.stopped_reason == "max_iterations"


# ===========================================================================
# generate_bollinger_param_variations tests
# ===========================================================================


class TestGenerateBollingerParamVariations:
    """Tests for the param variation generator."""

    def test_known_strategy(self) -> None:
        variations = generate_bollinger_param_variations(
            strategy_name="bollinger_range_v4_4",
            count=3,
        )
        assert isinstance(variations, list)
        assert len(variations) <= 3
        assert len(variations) >= 1
        for v in variations:
            assert isinstance(v, dict)
            for key in v:
                assert key in BOLLINGER_PARAM_VARIATION_RANGES["bollinger_range_v4_4"]

    def test_unknown_strategy_returns_empty(self) -> None:
        variations = generate_bollinger_param_variations(
            strategy_name="nonexistent_strategy",
            count=3,
        )
        assert variations == []

    def test_deterministic_with_same_seed(self) -> None:
        """Same random seed should produce identical variations."""
        import random
        random.seed(99)
        v1 = generate_bollinger_param_variations("bollinger_range_v4_4", count=3)
        random.seed(99)
        v2 = generate_bollinger_param_variations("bollinger_range_v4_4", count=3)
        assert v1 == v2
