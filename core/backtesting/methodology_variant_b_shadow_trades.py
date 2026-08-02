"""Executable research-only shadow trades for frozen SMC Variant B."""

from __future__ import annotations

import csv
import json
from bisect import bisect_right
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path
from typing import Final

from core.strategies.methodology_models import MethodologyDirection

from .config import BacktestConfig
from .methodology_observer import MethodologyObservation


@dataclass(frozen=True, slots=True)
class VariantBShadowTrade:
    target_r: float
    observation_timestamp: datetime
    entry_timestamp: datetime
    exit_timestamp: datetime
    entry_price: float
    stop_loss: float
    take_profit: float
    exit_price: float
    exit_reason: str
    holding_bars: int
    gross_r: float
    net_r: float
    gross_profit: float
    net_profit: float
    spread_cost: float
    slippage_cost: float
    commission_cost: float
    maximum_favorable_excursion: float
    maximum_adverse_excursion: float
    session: str
    regime: str


class MethodologyVariantBShadowTrades:
    """Simulate frozen Variant B without signal or trade authority."""

    VARIANT: Final[str] = "VARIANT_B_BEARISH_EXCLUDE_COMPATIBLE_SWEEP"
    STOP_DISTANCE: Final[float] = 2.5
    TARGET_R_MULTIPLES: Final[tuple[float, ...]] = (1.0, 1.5, 2.0)
    MAXIMUM_HOLDING_BARS: Final[int] = 24
    POSITION_SIZE_LOTS: Final[float] = 1.0

    _CSV_COLUMNS: Final[tuple[str, ...]] = (
        "Variant",
        "Target R",
        "Observation Timestamp",
        "Entry Timestamp",
        "Exit Timestamp",
        "Entry Price",
        "Stop Loss",
        "Take Profit",
        "Exit Price",
        "Exit Reason",
        "Holding Bars",
        "Gross R",
        "Net R",
        "Gross Profit",
        "Net Profit",
        "Spread Cost",
        "Slippage Cost",
        "Commission Cost",
        "Maximum Favorable Excursion",
        "Maximum Adverse Excursion",
        "Session",
        "Regime",
    )

    def __init__(
        self,
        config: BacktestConfig,
        output_directory: str | Path = "output/backtests",
        *,
        tick_size: float = 0.01,
        tick_value_per_lot: float = 1.0,
    ) -> None:
        if not isinstance(config, BacktestConfig):
            raise TypeError("config must be BacktestConfig")
        self.config = config
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.tick_size = self._positive(tick_size, "tick_size")
        self.tick_value_per_lot = self._positive(
            tick_value_per_lot,
            "tick_value_per_lot",
        )

    def export(
        self,
        observations: Sequence[MethodologyObservation],
        m5_bars: Sequence[object],
        *,
        window_metadata: Mapping[str, object] | None = None,
    ) -> tuple[Path, Path]:
        payload, trades = self.calculate(
            observations,
            m5_bars,
            window_metadata=window_metadata,
        )
        csv_path = (
            self.output_directory
            / "methodology_variant_b_shadow_trades.csv"
        )
        with csv_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=list(self._CSV_COLUMNS),
                extrasaction="raise",
            )
            writer.writeheader()
            writer.writerows(self._trade_row(trade) for trade in trades)

        json_path = (
            self.output_directory
            / "methodology_variant_b_shadow_trades.json"
        )
        json_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return csv_path, json_path

    def calculate(
        self,
        observations: Sequence[MethodologyObservation],
        m5_bars: Sequence[object],
        *,
        window_metadata: Mapping[str, object] | None = None,
    ) -> tuple[dict[str, object], tuple[VariantBShadowTrade, ...]]:
        candidates = tuple(
            item
            for item in sorted(
                observations,
                key=lambda value: value.timestamp,
            )
            if self._is_candidate(item)
        )
        bars = tuple(
            sorted(
                m5_bars,
                key=lambda value: self._bar_timestamp(value),
            )
        )
        bar_timestamps = tuple(
            self._bar_timestamp(bar)
            for bar in bars
        )
        self._validate_chronology(bar_timestamps)

        all_trades: list[VariantBShadowTrade] = []
        scenario_payloads: list[dict[str, object]] = []

        for target_r in self.TARGET_R_MULTIPLES:
            trades: list[VariantBShadowTrade] = []
            skipped_while_open = 0
            unavailable_entry = 0
            active_until: datetime | None = None

            for candidate in candidates:
                if (
                    active_until is not None
                    and candidate.timestamp <= active_until
                ):
                    skipped_while_open += 1
                    continue

                entry_index = bisect_right(
                    bar_timestamps,
                    candidate.timestamp.astimezone(UTC),
                )
                if entry_index >= len(bars):
                    unavailable_entry += 1
                    continue

                trade = self._simulate_candidate(
                    candidate=candidate,
                    bars=bars,
                    entry_index=entry_index,
                    target_r=target_r,
                )
                if trade is None:
                    unavailable_entry += 1
                    continue
                trades.append(trade)
                all_trades.append(trade)
                active_until = trade.exit_timestamp

            scenario_payloads.append(
                self._summarize_scenario(
                    target_r=target_r,
                    candidates=len(candidates),
                    trades=trades,
                    skipped_while_open=skipped_while_open,
                    unavailable_entry=unavailable_entry,
                )
            )

        zero_cost = all(
            value == 0.0
            for value in (
                self.config.spread_points,
                self.config.slippage_points,
                self.config.commission_per_trade,
                self.config.commission_per_lot,
            )
        )
        payload = {
            "variant": self.VARIANT,
            "direction": MethodologyDirection.BEARISH.value,
            "entry_policy": "NEXT_COMPLETED_M5_BAR_OPEN",
            "stop_distance_price_units": self.STOP_DISTANCE,
            "target_r_multiples": list(self.TARGET_R_MULTIPLES),
            "maximum_holding_bars": self.MAXIMUM_HOLDING_BARS,
            "same_bar_stop_target_policy": "CONSERVATIVE_STOP_FIRST",
            "position_policy": "ONE_SHADOW_POSITION_PER_TARGET_SCENARIO",
            "position_size_lots": self.POSITION_SIZE_LOTS,
            "candidate_count": len(candidates),
            "scenarios": scenario_payloads,
            "execution_economics": {
                "classification": (
                    "ZERO_COST_RESEARCH_SCENARIO"
                    if zero_cost
                    else "CONFIGURED_COST_RESEARCH_SCENARIO"
                ),
                "tick_size": self.tick_size,
                "tick_value_per_lot": self.tick_value_per_lot,
                "spread_points": self.config.spread_points,
                "slippage_points": self.config.slippage_points,
                "commission_per_trade": self.config.commission_per_trade,
                "commission_per_lot": self.config.commission_per_lot,
            },
            "window_metadata": dict(window_metadata or {}),
            "observational_only": True,
            "trade_authority": False,
            "signal_authority": False,
            "approval_authority": False,
            "position_sizing_authority": False,
            "active_decision_modified": False,
            "active_pipeline_modified": False,
            "future_information_used_for_research_only": True,
        }
        return payload, tuple(all_trades)

    def _simulate_candidate(
        self,
        *,
        candidate: MethodologyObservation,
        bars: tuple[object, ...],
        entry_index: int,
        target_r: float,
    ) -> VariantBShadowTrade | None:
        entry_bar = bars[entry_index]
        reference_entry = self._number(entry_bar, "open")
        entry_slippage = (
            self.config.slippage_points * self.tick_size
        )
        entry_price = reference_entry - entry_slippage
        stop_loss = reference_entry + self.STOP_DISTANCE
        take_profit = reference_entry - self.STOP_DISTANCE * target_r

        risk_currency = (
            self.STOP_DISTANCE
            / self.tick_size
            * self.tick_value_per_lot
            * self.POSITION_SIZE_LOTS
        )
        spread_cost = (
            self.config.spread_points
            * self.tick_value_per_lot
            * self.POSITION_SIZE_LOTS
        )
        commission_cost = (
            self.config.commission_per_trade
            + self.config.commission_per_lot
            * self.POSITION_SIZE_LOTS
        )

        lowest = entry_price
        highest = entry_price
        final_index = min(
            len(bars) - 1,
            entry_index + self.MAXIMUM_HOLDING_BARS - 1,
        )

        exit_reason = "TIME_EXIT"
        exit_reference = self._number(bars[final_index], "close")
        exit_index = final_index
        applies_exit_slippage = True

        for index in range(entry_index, final_index + 1):
            bar = bars[index]
            high = self._number(bar, "high")
            low = self._number(bar, "low")
            highest = max(highest, high)
            lowest = min(lowest, low)

            stop_hit = high >= stop_loss
            target_hit = low <= take_profit
            if stop_hit:
                exit_reason = "STOP_LOSS"
                exit_reference = stop_loss
                exit_index = index
                applies_exit_slippage = True
                break
            if target_hit:
                exit_reason = "TAKE_PROFIT"
                exit_reference = take_profit
                exit_index = index
                applies_exit_slippage = False
                break

        exit_slippage = (
            self.config.slippage_points * self.tick_size
            if applies_exit_slippage
            else 0.0
        )
        exit_price = exit_reference + exit_slippage
        slippage_cost = (
            (entry_slippage + exit_slippage)
            / self.tick_size
            * self.tick_value_per_lot
            * self.POSITION_SIZE_LOTS
        )
        gross_profit = (
            (entry_price - exit_price)
            / self.tick_size
            * self.tick_value_per_lot
            * self.POSITION_SIZE_LOTS
        )
        net_profit = (
            gross_profit
            - spread_cost
            - commission_cost
        )
        gross_r = gross_profit / risk_currency
        net_r = net_profit / risk_currency

        return VariantBShadowTrade(
            target_r=target_r,
            observation_timestamp=candidate.timestamp.astimezone(UTC),
            entry_timestamp=self._bar_timestamp(entry_bar),
            exit_timestamp=self._bar_timestamp(bars[exit_index]),
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            exit_price=exit_price,
            exit_reason=exit_reason,
            holding_bars=exit_index - entry_index + 1,
            gross_r=gross_r,
            net_r=net_r,
            gross_profit=gross_profit,
            net_profit=net_profit,
            spread_cost=spread_cost,
            slippage_cost=slippage_cost,
            commission_cost=commission_cost,
            maximum_favorable_excursion=max(0.0, entry_price - lowest),
            maximum_adverse_excursion=max(0.0, highest - entry_price),
            session=candidate.context.session_name,
            regime=candidate.context.regime_name,
        )

    @staticmethod
    def _is_candidate(item: MethodologyObservation) -> bool:
        return (
            item.smc.direction is MethodologyDirection.BEARISH
            and any(
                condition.code == "LIQUIDITY_SWEEP_COMPATIBLE"
                for condition in item.smc.failed_conditions
            )
        )

    def _summarize_scenario(
        self,
        *,
        target_r: float,
        candidates: int,
        trades: Sequence[VariantBShadowTrade],
        skipped_while_open: int,
        unavailable_entry: int,
    ) -> dict[str, object]:
        wins = sum(trade.net_r > 0.0 for trade in trades)
        losses = sum(trade.net_r < 0.0 for trade in trades)
        breakevens = len(trades) - wins - losses
        positive = sum(trade.net_r for trade in trades if trade.net_r > 0.0)
        negative = -sum(trade.net_r for trade in trades if trade.net_r < 0.0)

        equity = 0.0
        peak = 0.0
        max_drawdown = 0.0
        for trade in trades:
            equity += trade.net_r
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)

        return {
            "target_r": target_r,
            "candidate_count": candidates,
            "executed_shadow_trade_count": len(trades),
            "candidates_skipped_while_shadow_position_open": (
                skipped_while_open
            ),
            "candidates_without_next_bar_entry": unavailable_entry,
            "winning_trades": wins,
            "losing_trades": losses,
            "breakeven_trades": breakevens,
            "win_rate": wins / len(trades) if trades else None,
            "average_net_r": (
                sum(trade.net_r for trade in trades) / len(trades)
                if trades
                else None
            ),
            "total_net_r": sum(trade.net_r for trade in trades),
            "profit_factor_r": (
                positive / negative
                if negative > 0.0
                else None
            ),
            "maximum_drawdown_r": max_drawdown,
            "average_mfe_price_units": (
                sum(
                    trade.maximum_favorable_excursion
                    for trade in trades
                )
                / len(trades)
                if trades
                else None
            ),
            "average_mae_price_units": (
                sum(
                    trade.maximum_adverse_excursion
                    for trade in trades
                )
                / len(trades)
                if trades
                else None
            ),
            "exit_reason_counts": dict(
                sorted(
                    Counter(
                        trade.exit_reason
                        for trade in trades
                    ).items()
                )
            ),
        }

    def _trade_row(
        self,
        trade: VariantBShadowTrade,
    ) -> dict[str, object]:
        return {
            "Variant": self.VARIANT,
            "Target R": trade.target_r,
            "Observation Timestamp": trade.observation_timestamp.isoformat(),
            "Entry Timestamp": trade.entry_timestamp.isoformat(),
            "Exit Timestamp": trade.exit_timestamp.isoformat(),
            "Entry Price": trade.entry_price,
            "Stop Loss": trade.stop_loss,
            "Take Profit": trade.take_profit,
            "Exit Price": trade.exit_price,
            "Exit Reason": trade.exit_reason,
            "Holding Bars": trade.holding_bars,
            "Gross R": trade.gross_r,
            "Net R": trade.net_r,
            "Gross Profit": trade.gross_profit,
            "Net Profit": trade.net_profit,
            "Spread Cost": trade.spread_cost,
            "Slippage Cost": trade.slippage_cost,
            "Commission Cost": trade.commission_cost,
            "Maximum Favorable Excursion": (
                trade.maximum_favorable_excursion
            ),
            "Maximum Adverse Excursion": (
                trade.maximum_adverse_excursion
            ),
            "Session": trade.session,
            "Regime": trade.regime,
        }

    @staticmethod
    def _bar_timestamp(bar: object) -> datetime:
        value = getattr(bar, "timestamp", None)
        if not isinstance(value, datetime):
            raise TypeError("every M5 bar must expose a datetime timestamp")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("M5 bar timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @staticmethod
    def _number(bar: object, name: str) -> float:
        value = getattr(bar, name, None)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"every M5 bar must expose numeric {name}")
        result = float(value)
        if not isfinite(result) or result <= 0.0:
            raise ValueError(f"M5 bar {name} must be positive and finite")
        return result

    @staticmethod
    def _validate_chronology(
        timestamps: tuple[datetime, ...],
    ) -> None:
        if any(
            current <= previous
            for previous, current in zip(timestamps, timestamps[1:])
        ):
            raise ValueError(
                "M5 bar timestamps must be strictly increasing"
            )

    @staticmethod
    def _positive(value: float, name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be numeric")
        result = float(value)
        if not isfinite(result) or result <= 0.0:
            raise ValueError(f"{name} must be positive and finite")
        return result
