# src/backtest/simulator/snapshots.py
from __future__ import annotations

from datetime import datetime

from backtest.csv_loader import HistoricalBarRow
from backtest.simulator.models import SimulatedPosition
from mt4_bridge.models import Bar, MarketSnapshot, OpenPosition, PositionSnapshot

RANGE_MAGIC_NUMBER = 44001
TREND_MAGIC_NUMBER = 44002
LEGACY_MAGIC_NUMBER = 99999


class SnapshotBuilderMixin:
    def _build_bar(self, row: HistoricalBarRow) -> Bar:
        return Bar(
            time=row.time,
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            tick_volume=row.tick_volume,
            spread=0,
        )

    def _build_market_snapshot(
        self,
        rows: list[HistoricalBarRow],
        digits: int,
        point: float,
    ) -> MarketSnapshot:
        bars = [self._build_bar(row) for row in rows]
        latest = rows[-1]
        return MarketSnapshot(
            schema_version="backtest-1.0",
            generated_at=latest.time,
            symbol=self._symbol,
            timeframe=self._timeframe,
            bars_requested=len(rows),
            bars_copied=len(rows),
            bid=latest.close,
            ask=latest.close,
            spread_points=0,
            digits=digits,
            point=point,
            last_tick_time=latest.time,
            bars=bars,
        )

    def _build_market_snapshot_from_bars(
        self,
        bars: list[Bar],
        latest_row: HistoricalBarRow,
        digits: int,
        point: float,
    ) -> MarketSnapshot:
        return MarketSnapshot(
            schema_version="backtest-1.0",
            generated_at=latest_row.time,
            symbol=self._symbol,
            timeframe=self._timeframe,
            bars_requested=len(bars),
            bars_copied=len(bars),
            bid=latest_row.close,
            ask=latest_row.close,
            spread_points=0,
            digits=digits,
            point=point,
            last_tick_time=latest_row.time,
            bars=bars,
        )

    def _build_position_snapshot(
        self,
        *,
        range_position: SimulatedPosition | None,
        trend_position: SimulatedPosition | None,
        legacy_position: SimulatedPosition | None,
    ) -> PositionSnapshot:
        positions: list[OpenPosition] = []

        if legacy_position is not None:
            magic_number, comment = self._build_open_position_metadata(
                legacy_position
            )
            positions.append(
                OpenPosition(
                    ticket=legacy_position.ticket,
                    symbol=self._symbol,
                    position_type=legacy_position.position_type,
                    lots=0.01,
                    open_price=legacy_position.entry_price,
                    open_time=legacy_position.entry_time,
                    magic_number=magic_number,
                    comment=comment,
                )
            )

        if range_position is not None:
            positions.append(
                OpenPosition(
                    ticket=range_position.ticket,
                    symbol=self._symbol,
                    position_type=range_position.position_type,
                    lots=0.01,
                    open_price=range_position.entry_price,
                    open_time=range_position.entry_time,
                    magic_number=RANGE_MAGIC_NUMBER,
                    comment=self._build_position_comment(range_position),
                )
            )

        if trend_position is not None:
            positions.append(
                OpenPosition(
                    ticket=trend_position.ticket,
                    symbol=self._symbol,
                    position_type=trend_position.position_type,
                    lots=0.01,
                    open_price=trend_position.entry_price,
                    open_time=trend_position.entry_time,
                    magic_number=TREND_MAGIC_NUMBER,
                    comment=self._build_position_comment(trend_position),
                )
            )

        return PositionSnapshot(
            schema_version="backtest-1.0",
            generated_at=self._safe_generated_at(
                range_position=range_position,
                trend_position=trend_position,
                legacy_position=legacy_position,
            ),
            positions=positions,
        )

    def _build_open_position_metadata(
        self,
        simulated_position: SimulatedPosition,
    ) -> tuple[int, str]:
        lane = (simulated_position.lane or "legacy").strip().lower()

        if lane == "range":
            return RANGE_MAGIC_NUMBER, self._build_position_comment(simulated_position)

        if lane == "trend":
            return TREND_MAGIC_NUMBER, self._build_position_comment(simulated_position)

        return LEGACY_MAGIC_NUMBER, self._build_position_comment(simulated_position)

    def _build_position_comment(
        self,
        simulated_position: SimulatedPosition,
    ) -> str:
        lane = (simulated_position.lane or "legacy").strip().lower()
        parts = ["backtest", f"entry_bar_index={simulated_position.entry_bar_index}"]

        if lane == "range":
            parts.insert(0, "entry_lane=range")
            parts.insert(0, "lane:range")
        elif lane == "trend":
            parts.insert(0, "entry_lane=trend")
            parts.insert(0, "lane:trend")

        return "|".join(parts)

    def _safe_generated_at(
        self,
        *,
        range_position: SimulatedPosition | None,
        trend_position: SimulatedPosition | None,
        legacy_position: SimulatedPosition | None,
    ):
        if legacy_position is not None:
            return legacy_position.entry_time
        if range_position is not None:
            return range_position.entry_time
        if trend_position is not None:
            return trend_position.entry_time
        return datetime(2000, 1, 1, 0, 0, 0)