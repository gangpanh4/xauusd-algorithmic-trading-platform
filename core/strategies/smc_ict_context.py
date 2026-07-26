"""Immutable SMC/ICT market-context contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite

from core.fair_value_gap_detector.models import FairValueGap, FairValueGapCandidate
from core.market_structure.enums import TrendDirection
from core.market_structure.models import (
    BOSEvent,
    CHOCHEvent,
    LiquidityLevel,
    LiquiditySweepEvent,
    StructureState,
)
from core.multi_timeframe.enums import MarketBias, Timeframe
from core.order_block_detector.models import OrderBlock


class PriceLocation(str, Enum):
    PREMIUM = "premium"
    EQUILIBRIUM = "equilibrium"
    DISCOUNT = "discount"
    UNKNOWN = "unknown"


@dataclass(slots=True, frozen=True)
class SMCICTContext:
    """Objective facts for methodology evaluation; never trade authorization."""

    timestamp: datetime
    current_bar_index: int
    current_price: float
    higher_timeframe_bias: MarketBias
    h4_structure: StructureState | None
    h1_structure: StructureState | None
    m15_structure: StructureState | None
    m5_structure: StructureState | None
    latest_structure_event: BOSEvent | CHOCHEvent | None
    latest_liquidity_sweep: LiquiditySweepEvent | None
    opposing_liquidity_level: LiquidityLevel | None
    active_fair_value_gap: FairValueGap | FairValueGapCandidate | None
    active_order_block: OrderBlock | None
    latest_structure_event_timeframe: Timeframe | None = None
    latest_liquidity_sweep_timeframe: Timeframe | None = None
    opposing_liquidity_timeframe: Timeframe | None = None
    active_fair_value_gap_timeframe: Timeframe | None = None
    active_order_block_timeframe: Timeframe | None = None
    dealing_range_high: float | None = None
    dealing_range_low: float | None = None
    dealing_range_equilibrium: float | None = None
    dealing_range_timeframe: Timeframe | None = None
    price_location: PriceLocation = PriceLocation.UNKNOWN
    displacement_present: bool | None = None
    displacement_direction: TrendDirection | None = None
    displacement_timeframe: Timeframe | None = None
    displacement_atr_multiple: float | None = None
    session_name: str | None = None
    regime_name: str | None = None
    regime_confidence: float | None = None
    regime_observation_timestamp: datetime | None = None
    missing_capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.timestamp, datetime):
            raise TypeError("timestamp must be a datetime")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        if isinstance(self.current_bar_index, bool) or not isinstance(
            self.current_bar_index, int
        ):
            raise TypeError("current_bar_index must be an integer")
        if self.current_bar_index < 0:
            raise ValueError("current_bar_index cannot be negative")
        if isinstance(self.current_price, bool) or not isinstance(
            self.current_price, (int, float)
        ):
            raise TypeError("current_price must be numeric")
        if not isfinite(float(self.current_price)) or self.current_price <= 0:
            raise ValueError("current_price must be finite and positive")
        if not isinstance(self.higher_timeframe_bias, MarketBias):
            raise TypeError("higher_timeframe_bias must be a MarketBias")
        if not isinstance(self.price_location, PriceLocation):
            raise TypeError("price_location must be a PriceLocation")

        for name, value in (
            ("h4_structure", self.h4_structure),
            ("h1_structure", self.h1_structure),
            ("m15_structure", self.m15_structure),
            ("m5_structure", self.m5_structure),
        ):
            self._validate_optional_type(name, value, StructureState)

        self._validate_optional_union(
            "latest_structure_event",
            self.latest_structure_event,
            (BOSEvent, CHOCHEvent),
        )
        self._validate_optional_type(
            "latest_liquidity_sweep",
            self.latest_liquidity_sweep,
            LiquiditySweepEvent,
        )
        self._validate_optional_type(
            "opposing_liquidity_level",
            self.opposing_liquidity_level,
            LiquidityLevel,
        )
        self._validate_optional_union(
            "active_fair_value_gap",
            self.active_fair_value_gap,
            (FairValueGap, FairValueGapCandidate),
        )
        self._validate_optional_type(
            "active_order_block",
            self.active_order_block,
            OrderBlock,
        )

        self._validate_provenance_pair(
            "latest_structure_event",
            self.latest_structure_event,
            self.latest_structure_event_timeframe,
        )
        self._validate_provenance_pair(
            "latest_liquidity_sweep",
            self.latest_liquidity_sweep,
            self.latest_liquidity_sweep_timeframe,
        )
        self._validate_provenance_pair(
            "opposing_liquidity_level",
            self.opposing_liquidity_level,
            self.opposing_liquidity_timeframe,
        )
        self._validate_provenance_pair(
            "active_fair_value_gap",
            self.active_fair_value_gap,
            self.active_fair_value_gap_timeframe,
        )
        self._validate_provenance_pair(
            "active_order_block",
            self.active_order_block,
            self.active_order_block_timeframe,
        )
        self._validate_dealing_range()

        if self.displacement_present is not None and not isinstance(
            self.displacement_present, bool
        ):
            raise TypeError("displacement_present must be a boolean or None")

        for name, value in (
            ("session_name", self.session_name),
            ("regime_name", self.regime_name),
        ):
            if value is not None and (
                not isinstance(value, str) or not value.strip()
            ):
                raise ValueError(f"{name} must be a non-empty string or None")
        self._validate_regime()

        if not isinstance(self.missing_capabilities, tuple):
            raise TypeError("missing_capabilities must be a tuple")
        if any(
            not isinstance(item, str) or not item.strip()
            for item in self.missing_capabilities
        ):
            raise ValueError(
                "missing_capabilities must contain non-empty strings"
            )
        if len(self.missing_capabilities) != len(set(self.missing_capabilities)):
            raise ValueError("missing_capabilities cannot contain duplicates")




    def _validate_regime(self) -> None:
        if self.regime_confidence is not None:
            if isinstance(self.regime_confidence, bool) or not isinstance(
                self.regime_confidence,
                (int, float),
            ):
                raise TypeError("regime_confidence must be numeric or None")
            confidence = float(self.regime_confidence)
            if not isfinite(confidence) or not 0.0 <= confidence <= 1.0:
                raise ValueError(
                    "regime_confidence must be finite and between 0.0 and 1.0"
                )

        if self.regime_observation_timestamp is not None:
            if not isinstance(self.regime_observation_timestamp, datetime):
                raise TypeError(
                    "regime_observation_timestamp must be datetime or None"
                )
            if (
                self.regime_observation_timestamp.tzinfo is None
                or self.regime_observation_timestamp.utcoffset() is None
            ):
                raise ValueError(
                    "regime_observation_timestamp must be timezone-aware"
                )
            if self.regime_observation_timestamp > self.timestamp:
                raise ValueError(
                    "regime_observation_timestamp cannot be after context timestamp"
                )

        provenance = (
            self.regime_confidence,
            self.regime_observation_timestamp,
        )
        if self.regime_name is None:
            if any(value is not None for value in provenance):
                raise ValueError(
                    "regime provenance must be absent when regime_name is None"
                )
            return

        # Preserve compatibility with existing direct methodology-test contexts,
        # which may supply only regime_name. Builder-derived regime facts include
        # both confidence and the exact observation timestamp.
        if any(value is not None for value in provenance) and not all(
            value is not None for value in provenance
        ):
            raise ValueError(
                "builder-derived regime provenance must be complete"
            )

    def _validate_displacement(self) -> None:
        if self.displacement_present is not None and not isinstance(
            self.displacement_present,
            bool,
        ):
            raise TypeError("displacement_present must be a boolean or None")

        if (
            self.displacement_direction is not None
            and not isinstance(self.displacement_direction, TrendDirection)
        ):
            raise TypeError(
                "displacement_direction must be TrendDirection or None"
            )
        if (
            self.displacement_timeframe is not None
            and not isinstance(self.displacement_timeframe, Timeframe)
        ):
            raise TypeError(
                "displacement_timeframe must be Timeframe or None"
            )
        if self.displacement_atr_multiple is not None:
            if isinstance(self.displacement_atr_multiple, bool) or not isinstance(
                self.displacement_atr_multiple,
                (int, float),
            ):
                raise TypeError(
                    "displacement_atr_multiple must be numeric or None"
                )
            value = float(self.displacement_atr_multiple)
            if not isfinite(value) or value <= 0.0:
                raise ValueError(
                    "displacement_atr_multiple must be finite and positive"
                )

        provenance = (
            self.displacement_direction,
            self.displacement_timeframe,
            self.displacement_atr_multiple,
        )
        if self.displacement_present is None:
            if any(value is not None for value in provenance):
                raise ValueError(
                    "displacement provenance must be absent when "
                    "displacement_present is None"
                )
            return

        # Preserve the existing public contract: callers may provide only the
        # boolean result. Builder-derived results include all provenance fields.
        if any(value is not None for value in provenance) and not all(
            value is not None for value in provenance
        ):
            raise ValueError(
                "builder-derived displacement provenance must be complete"
            )

    def _validate_dealing_range(self) -> None:
        values = (
            self.dealing_range_high,
            self.dealing_range_low,
            self.dealing_range_equilibrium,
        )
        supplied = tuple(value is not None for value in values)

        if any(supplied) and not all(supplied):
            raise ValueError(
                "dealing-range prices must either all be present or all be None"
            )
        if not any(supplied):
            if self.dealing_range_timeframe is not None:
                raise ValueError(
                    "dealing_range_timeframe must be None when the range is absent"
                )
            # Preserve the existing public contract: callers may provide a known
            # price-location classification without dealing-range provenance.
            # The builder added in this milestone supplies range provenance when
            # it performs the classification itself.
            return

        if not isinstance(self.dealing_range_timeframe, Timeframe):
            raise TypeError(
                "dealing_range_timeframe must be Timeframe when the range is present"
            )

        high, low, equilibrium = (float(value) for value in values)
        if not all(isfinite(value) for value in (high, low, equilibrium)):
            raise ValueError("dealing-range prices must be finite")
        if low <= 0 or high <= 0 or equilibrium <= 0:
            raise ValueError("dealing-range prices must be positive")
        if high <= low:
            raise ValueError("dealing_range_high must be greater than dealing_range_low")

        expected_equilibrium = (high + low) / 2.0
        if equilibrium != expected_equilibrium:
            raise ValueError(
                "dealing_range_equilibrium must equal the range midpoint"
            )
        if self.price_location is PriceLocation.UNKNOWN:
            raise ValueError(
                "price_location cannot be UNKNOWN when the dealing range is present"
            )

    @staticmethod
    def _validate_optional_type(
        name: str,
        value: object | None,
        expected_type: type,
    ) -> None:
        if value is not None and not isinstance(value, expected_type):
            raise TypeError(f"{name} must be {expected_type.__name__} or None")

    @staticmethod
    def _validate_optional_union(
        name: str,
        value: object | None,
        expected_types: tuple[type, ...],
    ) -> None:
        if value is not None and not isinstance(value, expected_types):
            expected = " or ".join(item.__name__ for item in expected_types)
            raise TypeError(f"{name} must be {expected} or None")

    @staticmethod
    def _validate_provenance_pair(
        fact_name: str,
        fact: object | None,
        timeframe: Timeframe | None,
    ) -> None:
        if timeframe is not None and not isinstance(timeframe, Timeframe):
            raise TypeError(f"{fact_name}_timeframe must be Timeframe or None")
        if fact is None and timeframe is not None:
            raise ValueError(
                f"{fact_name}_timeframe must be None when {fact_name} is None"
            )
        if fact is not None and timeframe is None:
            raise ValueError(
                f"{fact_name}_timeframe is required when {fact_name} is present"
            )
