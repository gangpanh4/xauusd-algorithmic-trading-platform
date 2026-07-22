"""
Timeframe Analyzer.

Runs the complete analysis pipeline for one timeframe and converts the
resulting market facts into a deterministic directional state.

Bars
  ↓
Market Structure Engine
  ↓
Price Action Engine
  ↓
Directional evidence agreement
  ↓
TimeframeState
"""

from __future__ import annotations

from collections.abc import Sequence
from math import isfinite
from typing import Any

from core.data.models import MarketBar
from core.market_structure.engine import MarketStructureEngine
from core.market_structure.models import BOSEvent, CHOCHEvent, MarketStructureResult
from core.price_action.engine import PriceActionEngine
from core.price_action.models import PriceActionResult

from .enums import MarketBias, Timeframe, TimeframeAlignment
from .models import TimeframeState


class TimeframeAnalyzer:
    """Execute the complete analytical pipeline for one timeframe.

    ``alignment`` represents agreement among the independent directional facts
    produced inside this timeframe. Cross-timeframe agreement remains the
    responsibility of :class:`MultiTimeframeEngine`.
    """

    _TREND_WEIGHT = 3.0
    _BREAK_WEIGHT = 2.0
    _ORDER_BLOCK_WEIGHT = 1.5
    _FVG_WEIGHT = 1.0

    def __init__(
        self,
        *,
        market_structure_engine: MarketStructureEngine | None = None,
        price_action_engine: PriceActionEngine | None = None,
        alignment_threshold: float = 0.75,
        minimum_aligned_sources: int = 2,
    ) -> None:
        if not isfinite(alignment_threshold):
            raise ValueError("alignment_threshold must be finite")
        if not 0.5 < alignment_threshold <= 1.0:
            raise ValueError(
                "alignment_threshold must be greater than 0.5 and at most 1.0"
            )
        if isinstance(minimum_aligned_sources, bool) or not isinstance(
            minimum_aligned_sources, int
        ):
            raise TypeError("minimum_aligned_sources must be an integer")
        if minimum_aligned_sources < 1:
            raise ValueError("minimum_aligned_sources must be at least 1")

        self.market_structure = market_structure_engine or MarketStructureEngine()
        self.price_action = price_action_engine or PriceActionEngine()
        self.alignment_threshold = float(alignment_threshold)
        self.minimum_aligned_sources = minimum_aligned_sources

        self._timeframe: Timeframe | None = None
        self._last_bars: tuple[MarketBar, ...] = ()
        self._last_state: TimeframeState | None = None

    def reset(self) -> None:
        """Reset all underlying engines and incremental snapshot state."""

        self._reset_engines()
        self._timeframe = None
        self._last_bars = ()
        self._last_state = None

    def _reset_engines(self) -> None:
        """Reset owned analytical engines without publishing cache state."""

        self.market_structure.reset()
        self.price_action.reset()

    def analyze(
        self,
        *,
        timeframe: Timeframe,
        bars: Sequence[MarketBar],
    ) -> TimeframeState:
        """Analyze completed bars while reusing valid streaming state.

        The first snapshot is replayed in full. Later snapshots process only bars
        newer than the last successfully analyzed timestamp when overlapping
        history is unchanged. If prior history is revised or chronology moves
        backward, the owned engines are rebuilt from the supplied snapshot.
        """

        if not isinstance(timeframe, Timeframe):
            raise TypeError("timeframe must be a Timeframe")

        validated_bars = self._validate_bars(bars)
        immutable_bars = tuple(validated_bars)

        if self._timeframe is not None and timeframe is not self._timeframe:
            raise ValueError(
                "A TimeframeAnalyzer instance may analyze only one timeframe; "
                f"expected {self._timeframe.value}, received {timeframe.value}."
            )

        if self._last_bars == immutable_bars and self._last_state is not None:
            return self._last_state

        analysis_mode, bars_to_process = self._resolve_update(immutable_bars)
        if analysis_mode == "rebuild":
            self._reset_engines()

        structure_result: MarketStructureResult | None = None
        for bar in bars_to_process:
            structure_result = self.market_structure.process(bar)

        if structure_result is None:
            if self._last_state is None:
                raise RuntimeError("MarketStructureEngine produced no result")
            structure_result = self._last_state.market_structure

        if structure_result is None:
            raise RuntimeError("MarketStructureEngine produced no result")

        break_event = self._latest_break(structure_result)
        price_action_result = self.price_action.process(
            bars=validated_bars,
            break_event=break_event,
            liquidity_event=structure_result.last_liquidity,
        )

        state = self._build_state(
            timeframe=timeframe,
            bars=validated_bars,
            structure_result=structure_result,
            price_action_result=price_action_result,
            break_event=break_event,
            analysis_mode=analysis_mode,
            processed_bar_count=len(bars_to_process),
        )

        self._timeframe = timeframe
        self._last_bars = immutable_bars
        self._last_state = state
        return state

    def _resolve_update(
        self,
        bars: tuple[MarketBar, ...],
    ) -> tuple[str, tuple[MarketBar, ...]]:
        """Return the required update mode and bars that must be processed."""

        if not self._last_bars:
            return "initial_replay", bars

        previous_latest = self._last_bars[-1].timestamp
        current_latest = bars[-1].timestamp

        if current_latest <= previous_latest:
            return "rebuild", bars

        previous_by_timestamp = {bar.timestamp: bar for bar in self._last_bars}
        for bar in bars:
            previous = previous_by_timestamp.get(bar.timestamp)
            if previous is not None and previous != bar:
                return "rebuild", bars

        appended = tuple(bar for bar in bars if bar.timestamp > previous_latest)
        if not appended:
            return "rebuild", bars

        return "incremental_append", appended

    def _build_state(
        self,
        *,
        timeframe: Timeframe,
        bars: list[MarketBar],
        structure_result: MarketStructureResult,
        price_action_result: PriceActionResult,
        break_event: BOSEvent | CHOCHEvent | None,
        analysis_mode: str,
        processed_bar_count: int,
    ) -> TimeframeState:
        directional_evidence = self._directional_evidence(
            structure_result=structure_result,
            price_action_result=price_action_result,
            break_event=break_event,
        )
        bias = self._resolve_bias(
            structure_result=structure_result,
            break_event=break_event,
            directional_evidence=directional_evidence,
        )
        alignment, agreement_ratio = self._resolve_alignment(
            bias=bias,
            directional_evidence=directional_evidence,
        )
        confidence = self._confidence(
            structure_result=structure_result,
            price_action_result=price_action_result,
            alignment=alignment,
        )

        bullish_weight = sum(
            weight
            for _, evidence_bias, weight in directional_evidence
            if evidence_bias is MarketBias.BULLISH
        )
        bearish_weight = sum(
            weight
            for _, evidence_bias, weight in directional_evidence
            if evidence_bias is MarketBias.BEARISH
        )

        return TimeframeState(
            timeframe=timeframe,
            timestamp=bars[-1].timestamp,
            bias=bias,
            alignment=alignment,
            confidence=confidence,
            market_structure=structure_result,
            price_action=price_action_result,
            metadata={
                "alignment_method": "INTRA_TIMEFRAME_DIRECTIONAL_EVIDENCE",
                "alignment_threshold": self.alignment_threshold,
                "agreement_ratio": agreement_ratio,
                "directional_source_count": len(directional_evidence),
                "bullish_weight": bullish_weight,
                "bearish_weight": bearish_weight,
                "directional_sources": {
                    source: evidence_bias.value
                    for source, evidence_bias, _ in directional_evidence
                },
                "latest_break_type": (
                    break_event.break_type.name if break_event is not None else None
                ),
                "latest_break_timestamp": (
                    break_event.timestamp if break_event is not None else None
                ),
                "analysis_mode": analysis_mode,
                "processed_bar_count": processed_bar_count,
            },
        )

    @staticmethod
    def _validate_bars(bars: Sequence[MarketBar]) -> list[MarketBar]:
        if isinstance(bars, (str, bytes)) or not isinstance(bars, Sequence):
            raise TypeError("bars must be a sequence of completed market bars")
        if not bars:
            raise ValueError("bars must not be empty")

        validated = list(bars)
        previous_timestamp = None

        for index, bar in enumerate(validated):
            required = ("timestamp", "open", "high", "low", "close")
            if any(not hasattr(bar, attribute) for attribute in required):
                raise TypeError(f"bars[{index}] is not a compatible MarketBar")

            timestamp = bar.timestamp
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError(f"bars[{index}].timestamp must be timezone-aware")
            if previous_timestamp is not None and timestamp <= previous_timestamp:
                raise ValueError("bar timestamps must be strictly increasing")
            previous_timestamp = timestamp

            prices = (bar.open, bar.high, bar.low, bar.close)
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(float(value))
                for value in prices
            ):
                raise ValueError(f"bars[{index}] contains a non-finite price")
            if bar.high < max(bar.open, bar.close) or bar.low > min(
                bar.open, bar.close
            ):
                raise ValueError(f"bars[{index}] contains malformed OHLC values")
            if bar.high < bar.low:
                raise ValueError(f"bars[{index}] high must be at least low")

        return validated

    @staticmethod
    def _latest_break(
        structure_result: MarketStructureResult,
    ) -> BOSEvent | CHOCHEvent | None:
        events = tuple(
            event
            for event in (structure_result.last_bos, structure_result.last_choch)
            if event is not None
        )
        if not events:
            return None
        return max(
            events,
            key=lambda event: (event.confirmation_index, event.timestamp),
        )

    def _directional_evidence(
        self,
        *,
        structure_result: MarketStructureResult,
        price_action_result: PriceActionResult,
        break_event: BOSEvent | CHOCHEvent | None,
    ) -> list[tuple[str, MarketBias, float]]:
        evidence: list[tuple[str, MarketBias, float]] = []

        trend_bias = self._bias_from_named_value(structure_result.current_trend)
        if trend_bias is not MarketBias.NEUTRAL:
            evidence.append(("current_trend", trend_bias, self._TREND_WEIGHT))

        if break_event is not None:
            break_bias = self._bias_from_named_value(break_event.direction)
            if break_bias is not MarketBias.NEUTRAL:
                evidence.append(("latest_break", break_bias, self._BREAK_WEIGHT))

        order_block = price_action_result.last_order_block
        if order_block is not None:
            block_bias = self._bias_from_named_value(order_block.block_type)
            if block_bias is not MarketBias.NEUTRAL:
                evidence.append(
                    ("order_block", block_bias, self._ORDER_BLOCK_WEIGHT)
                )

        fair_value_gap = price_action_result.last_fair_value_gap
        if fair_value_gap is not None:
            gap_bias = self._bias_from_named_value(fair_value_gap.gap_type)
            if gap_bias is not MarketBias.NEUTRAL:
                evidence.append(("fair_value_gap", gap_bias, self._FVG_WEIGHT))

        return evidence

    def _resolve_bias(
        self,
        *,
        structure_result: MarketStructureResult,
        break_event: BOSEvent | CHOCHEvent | None,
        directional_evidence: Sequence[tuple[str, MarketBias, float]],
    ) -> MarketBias:
        trend_bias = self._bias_from_named_value(structure_result.current_trend)
        if trend_bias is not MarketBias.NEUTRAL:
            return trend_bias

        if break_event is not None:
            break_bias = self._bias_from_named_value(break_event.direction)
            if break_bias is not MarketBias.NEUTRAL:
                return break_bias

        bullish_weight = sum(
            weight
            for _, evidence_bias, weight in directional_evidence
            if evidence_bias is MarketBias.BULLISH
        )
        bearish_weight = sum(
            weight
            for _, evidence_bias, weight in directional_evidence
            if evidence_bias is MarketBias.BEARISH
        )

        if bullish_weight > bearish_weight:
            return MarketBias.BULLISH
        if bearish_weight > bullish_weight:
            return MarketBias.BEARISH
        return MarketBias.NEUTRAL

    def _resolve_alignment(
        self,
        *,
        bias: MarketBias,
        directional_evidence: Sequence[tuple[str, MarketBias, float]],
    ) -> tuple[TimeframeAlignment, float]:
        if bias is MarketBias.NEUTRAL or not directional_evidence:
            return TimeframeAlignment.PARTIAL, 0.0

        agreeing_weight = sum(
            weight
            for _, evidence_bias, weight in directional_evidence
            if evidence_bias is bias
        )
        opposing_weight = sum(
            weight
            for _, evidence_bias, weight in directional_evidence
            if evidence_bias is not bias and evidence_bias is not MarketBias.NEUTRAL
        )
        total_weight = agreeing_weight + opposing_weight
        agreement_ratio = agreeing_weight / total_weight if total_weight > 0.0 else 0.0

        if opposing_weight == 0.0:
            if len(directional_evidence) >= self.minimum_aligned_sources:
                return TimeframeAlignment.ALIGNED, agreement_ratio
            return TimeframeAlignment.PARTIAL, agreement_ratio

        if agreement_ratio >= self.alignment_threshold:
            return TimeframeAlignment.PARTIAL, agreement_ratio

        return TimeframeAlignment.CONFLICT, agreement_ratio

    @staticmethod
    def _confidence(
        *,
        structure_result: MarketStructureResult,
        price_action_result: PriceActionResult,
        alignment: TimeframeAlignment,
    ) -> float:
        structure_confidence = TimeframeAnalyzer._bounded_confidence(
            structure_result.structure_confidence,
            field_name="structure_confidence",
        )
        price_action_confidence = TimeframeAnalyzer._bounded_confidence(
            price_action_result.price_action_confidence,
            field_name="price_action_confidence",
        )

        has_price_action = (
            price_action_result.last_order_block is not None
            or price_action_result.last_fair_value_gap is not None
        )
        if has_price_action:
            confidence = 0.70 * structure_confidence + 0.30 * price_action_confidence
        else:
            confidence = structure_confidence

        alignment_multiplier = {
            TimeframeAlignment.ALIGNED: 1.0,
            TimeframeAlignment.PARTIAL: 0.85,
            TimeframeAlignment.CONFLICT: 0.50,
        }[alignment]

        return max(0.0, min(1.0, confidence * alignment_multiplier))

    @staticmethod
    def _bounded_confidence(value: Any, *, field_name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{field_name} must be numeric")
        numeric = float(value)
        if not isfinite(numeric):
            raise ValueError(f"{field_name} must be finite")
        if not 0.0 <= numeric <= 1.0:
            raise ValueError(f"{field_name} must be between 0.0 and 1.0")
        return numeric

    @staticmethod
    def _bias_from_named_value(value: Any) -> MarketBias:
        if value is None:
            return MarketBias.NEUTRAL

        name = getattr(value, "name", None)
        if name is None:
            raw_value = getattr(value, "value", value)
            name = str(raw_value)

        normalized = str(name).upper()
        if "BULL" in normalized:
            return MarketBias.BULLISH
        if "BEAR" in normalized:
            return MarketBias.BEARISH
        return MarketBias.NEUTRAL
