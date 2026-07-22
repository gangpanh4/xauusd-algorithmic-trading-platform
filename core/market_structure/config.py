"""Configuration models for the market-structure package.

The package owns four independent detector configurations and one composed
``MarketStructureConfig`` used by :class:`MarketStructureEngine`.

``MarketStructureConfig`` keeps backward compatibility with the former alias to
``SwingDetectorConfig``: legacy swing keyword arguments such as
``pivot_left=1`` are still accepted and exposed as read-only properties.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Final


_MINIMUM_HISTORY: Final[int] = 1


def _require_bool(name: str, value: bool) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a bool")


def _require_integer_at_least(name: str, value: int, minimum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int")
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")


def _require_finite_non_negative(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    if not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite")
    if value < 0.0:
        raise ValueError(f"{name} must be >= 0")


def _require_finite_positive(name: str, value: float) -> None:
    _require_finite_non_negative(name, value)
    if value <= 0.0:
        raise ValueError(f"{name} must be > 0")


@dataclass(slots=True, frozen=True)
class SwingDetectorConfig:
    """Immutable configuration for confirmed swing detection."""

    pivot_left: int = 3
    pivot_right: int = 3
    minimum_swing_distance: float = 0.0
    equal_high_tolerance: float = 0.0
    equal_low_tolerance: float = 0.0
    atr_validation: bool = True
    atr_period: int = 14
    atr_multiplier: float = 1.0
    maximum_history: int = 5000
    debug_logging: bool = False

    # Structure-evaluation weights remain here for legacy compatibility.
    swing_confidence_weight: float = 0.20
    bos_confidence_weight: float = 0.35
    choch_confidence_weight: float = 0.20
    liquidity_confidence_weight: float = 0.25

    def __post_init__(self) -> None:
        _require_integer_at_least("pivot_left", self.pivot_left, 1)
        _require_integer_at_least("pivot_right", self.pivot_right, 1)
        _require_finite_non_negative(
            "minimum_swing_distance",
            self.minimum_swing_distance,
        )
        _require_finite_non_negative(
            "equal_high_tolerance",
            self.equal_high_tolerance,
        )
        _require_finite_non_negative(
            "equal_low_tolerance",
            self.equal_low_tolerance,
        )
        _require_bool("atr_validation", self.atr_validation)
        _require_integer_at_least("atr_period", self.atr_period, 1)
        _require_finite_positive("atr_multiplier", self.atr_multiplier)
        _require_integer_at_least(
            "maximum_history",
            self.maximum_history,
            _MINIMUM_HISTORY,
        )
        _require_bool("debug_logging", self.debug_logging)

        weights = {
            "swing_confidence_weight": self.swing_confidence_weight,
            "bos_confidence_weight": self.bos_confidence_weight,
            "choch_confidence_weight": self.choch_confidence_weight,
            "liquidity_confidence_weight": self.liquidity_confidence_weight,
        }
        for name, value in weights.items():
            _require_finite_non_negative(name, value)

        if self.maximum_confidence_score <= 0.0:
            raise ValueError("at least one structure confidence weight must be > 0")

    @property
    def maximum_confidence_score(self) -> float:
        """Return the sum of configured structure-evaluation weights."""

        return (
            self.swing_confidence_weight
            + self.bos_confidence_weight
            + self.choch_confidence_weight
            + self.liquidity_confidence_weight
        )


@dataclass(slots=True, frozen=True)
class BOSDetectorConfig:
    """Immutable configuration for Break of Structure detection."""

    require_close_break: bool = True
    allow_wick_break: bool = False
    minimum_break_distance: float = 0.0
    minimum_break_atr_multiple: float = 0.0
    break_tolerance: float = 0.0
    protected_swing_only: bool = True
    maximum_history: int = 5000
    debug_logging: bool = False

    def __post_init__(self) -> None:
        _require_bool("require_close_break", self.require_close_break)
        _require_bool("allow_wick_break", self.allow_wick_break)
        if not self.require_close_break and not self.allow_wick_break:
            raise ValueError(
                "BOS detection must permit a close break or a wick break"
            )
        _require_finite_non_negative(
            "minimum_break_distance",
            self.minimum_break_distance,
        )
        _require_finite_non_negative(
            "minimum_break_atr_multiple",
            self.minimum_break_atr_multiple,
        )
        _require_finite_non_negative("break_tolerance", self.break_tolerance)
        _require_bool("protected_swing_only", self.protected_swing_only)
        _require_integer_at_least(
            "maximum_history",
            self.maximum_history,
            _MINIMUM_HISTORY,
        )
        _require_bool("debug_logging", self.debug_logging)


@dataclass(slots=True, frozen=True)
class CHOCHDetectorConfig:
    """Immutable configuration for Change of Character detection."""

    require_close_break: bool = True
    allow_wick_break: bool = False
    minimum_break_distance: float = 0.0
    minimum_break_atr_multiple: float = 0.0
    require_trend_change: bool = True
    maximum_history: int = 5000
    debug_logging: bool = False

    def __post_init__(self) -> None:
        _require_bool("require_close_break", self.require_close_break)
        _require_bool("allow_wick_break", self.allow_wick_break)
        if not self.require_close_break and not self.allow_wick_break:
            raise ValueError(
                "CHOCH detection must permit a close break or a wick break"
            )
        _require_finite_non_negative(
            "minimum_break_distance",
            self.minimum_break_distance,
        )
        _require_finite_non_negative(
            "minimum_break_atr_multiple",
            self.minimum_break_atr_multiple,
        )
        _require_bool("require_trend_change", self.require_trend_change)
        _require_integer_at_least(
            "maximum_history",
            self.maximum_history,
            _MINIMUM_HISTORY,
        )
        _require_bool("debug_logging", self.debug_logging)


MarketStructureCHOCHConfig = CHOCHDetectorConfig


@dataclass(slots=True, frozen=True)
class LiquidityDetectorConfig:
    """Immutable configuration for liquidity sweep-and-reclaim detection."""

    minimum_sweep_distance: float = 0.0
    minimum_sweep_atr_multiple: float = 0.0
    allow_equal_levels: bool = True
    require_reclaim_close: bool = True
    maximum_history: int = 5000
    debug_logging: bool = False

    def __post_init__(self) -> None:
        _require_finite_non_negative(
            "minimum_sweep_distance",
            self.minimum_sweep_distance,
        )
        _require_finite_non_negative(
            "minimum_sweep_atr_multiple",
            self.minimum_sweep_atr_multiple,
        )
        _require_bool("allow_equal_levels", self.allow_equal_levels)
        _require_bool("require_reclaim_close", self.require_reclaim_close)
        _require_integer_at_least(
            "maximum_history",
            self.maximum_history,
            _MINIMUM_HISTORY,
        )
        _require_bool("debug_logging", self.debug_logging)


@dataclass(slots=True, frozen=True, init=False)
class MarketStructureConfig:
    """Composed configuration for the complete market-structure engine.

    The previous implementation exposed ``MarketStructureConfig`` as an alias
    of :class:`SwingDetectorConfig`. To avoid breaking existing callers, this
    class still accepts all legacy swing keyword arguments and exposes matching
    read-only properties. New code should prefer the explicit ``swing``,
    ``bos``, ``choch`` and ``liquidity`` components.
    """

    swing: SwingDetectorConfig
    bos: BOSDetectorConfig
    choch: CHOCHDetectorConfig
    liquidity: LiquidityDetectorConfig
    maximum_bos_age_bars: int
    maximum_choch_age_bars: int
    maximum_liquidity_age_bars: int
    freshness_decay_bars: int
    expire_stale_events: bool
    maximum_bar_history: int
    debug_logging: bool

    def __init__(
        self,
        *,
        swing: SwingDetectorConfig | None = None,
        bos: BOSDetectorConfig | None = None,
        choch: CHOCHDetectorConfig | None = None,
        liquidity: LiquidityDetectorConfig | None = None,
        maximum_bos_age_bars: int = 16,
        maximum_choch_age_bars: int = 16,
        maximum_liquidity_age_bars: int = 32,
        freshness_decay_bars: int = 8,
        expire_stale_events: bool = True,
        maximum_bar_history: int = 5000,
        debug_logging: bool = False,
        # Legacy SwingDetectorConfig keyword compatibility.
        pivot_left: int | None = None,
        pivot_right: int | None = None,
        minimum_swing_distance: float | None = None,
        equal_high_tolerance: float | None = None,
        equal_low_tolerance: float | None = None,
        atr_validation: bool | None = None,
        atr_period: int | None = None,
        atr_multiplier: float | None = None,
        maximum_history: int | None = None,
        swing_confidence_weight: float | None = None,
        bos_confidence_weight: float | None = None,
        choch_confidence_weight: float | None = None,
        liquidity_confidence_weight: float | None = None,
    ) -> None:
        legacy_values = {
            "pivot_left": pivot_left,
            "pivot_right": pivot_right,
            "minimum_swing_distance": minimum_swing_distance,
            "equal_high_tolerance": equal_high_tolerance,
            "equal_low_tolerance": equal_low_tolerance,
            "atr_validation": atr_validation,
            "atr_period": atr_period,
            "atr_multiplier": atr_multiplier,
            "maximum_history": maximum_history,
            "swing_confidence_weight": swing_confidence_weight,
            "bos_confidence_weight": bos_confidence_weight,
            "choch_confidence_weight": choch_confidence_weight,
            "liquidity_confidence_weight": liquidity_confidence_weight,
        }
        supplied_legacy_values = {
            name: value
            for name, value in legacy_values.items()
            if value is not None
        }

        if swing is not None and supplied_legacy_values:
            names = ", ".join(sorted(supplied_legacy_values))
            raise ValueError(
                "swing cannot be combined with legacy swing overrides: "
                f"{names}"
            )

        if swing is None:
            defaults = SwingDetectorConfig()
            swing = SwingDetectorConfig(
                pivot_left=(
                    defaults.pivot_left if pivot_left is None else pivot_left
                ),
                pivot_right=(
                    defaults.pivot_right if pivot_right is None else pivot_right
                ),
                minimum_swing_distance=(
                    defaults.minimum_swing_distance
                    if minimum_swing_distance is None
                    else minimum_swing_distance
                ),
                equal_high_tolerance=(
                    defaults.equal_high_tolerance
                    if equal_high_tolerance is None
                    else equal_high_tolerance
                ),
                equal_low_tolerance=(
                    defaults.equal_low_tolerance
                    if equal_low_tolerance is None
                    else equal_low_tolerance
                ),
                atr_validation=(
                    defaults.atr_validation
                    if atr_validation is None
                    else atr_validation
                ),
                atr_period=(
                    defaults.atr_period if atr_period is None else atr_period
                ),
                atr_multiplier=(
                    defaults.atr_multiplier
                    if atr_multiplier is None
                    else atr_multiplier
                ),
                maximum_history=(
                    defaults.maximum_history
                    if maximum_history is None
                    else maximum_history
                ),
                debug_logging=debug_logging,
                swing_confidence_weight=(
                    defaults.swing_confidence_weight
                    if swing_confidence_weight is None
                    else swing_confidence_weight
                ),
                bos_confidence_weight=(
                    defaults.bos_confidence_weight
                    if bos_confidence_weight is None
                    else bos_confidence_weight
                ),
                choch_confidence_weight=(
                    defaults.choch_confidence_weight
                    if choch_confidence_weight is None
                    else choch_confidence_weight
                ),
                liquidity_confidence_weight=(
                    defaults.liquidity_confidence_weight
                    if liquidity_confidence_weight is None
                    else liquidity_confidence_weight
                ),
            )

        if not isinstance(swing, SwingDetectorConfig):
            raise TypeError("swing must be a SwingDetectorConfig")
        if bos is not None and not isinstance(bos, BOSDetectorConfig):
            raise TypeError("bos must be a BOSDetectorConfig")
        if choch is not None and not isinstance(choch, CHOCHDetectorConfig):
            raise TypeError("choch must be a CHOCHDetectorConfig")
        if liquidity is not None and not isinstance(
            liquidity,
            LiquidityDetectorConfig,
        ):
            raise TypeError("liquidity must be a LiquidityDetectorConfig")

        resolved_bos = bos or BOSDetectorConfig(debug_logging=debug_logging)
        resolved_choch = choch or CHOCHDetectorConfig(
            debug_logging=debug_logging,
        )
        resolved_liquidity = liquidity or LiquidityDetectorConfig(
            debug_logging=debug_logging,
        )

        _require_integer_at_least(
            "maximum_bos_age_bars",
            maximum_bos_age_bars,
            1,
        )
        _require_integer_at_least(
            "maximum_choch_age_bars",
            maximum_choch_age_bars,
            1,
        )
        _require_integer_at_least(
            "maximum_liquidity_age_bars",
            maximum_liquidity_age_bars,
            1,
        )
        _require_integer_at_least(
            "freshness_decay_bars",
            freshness_decay_bars,
            1,
        )
        _require_bool("expire_stale_events", expire_stale_events)
        _require_integer_at_least(
            "maximum_bar_history",
            maximum_bar_history,
            1,
        )
        _require_bool("debug_logging", debug_logging)

        object.__setattr__(self, "swing", swing)
        object.__setattr__(self, "bos", resolved_bos)
        object.__setattr__(self, "choch", resolved_choch)
        object.__setattr__(self, "liquidity", resolved_liquidity)
        object.__setattr__(
            self,
            "maximum_bos_age_bars",
            maximum_bos_age_bars,
        )
        object.__setattr__(
            self,
            "maximum_choch_age_bars",
            maximum_choch_age_bars,
        )
        object.__setattr__(
            self,
            "maximum_liquidity_age_bars",
            maximum_liquidity_age_bars,
        )
        object.__setattr__(
            self,
            "freshness_decay_bars",
            freshness_decay_bars,
        )
        object.__setattr__(self, "expire_stale_events", expire_stale_events)
        object.__setattr__(self, "maximum_bar_history", maximum_bar_history)
        object.__setattr__(self, "debug_logging", debug_logging)

    # Legacy SwingDetectorConfig read-only properties.
    @property
    def pivot_left(self) -> int:
        return self.swing.pivot_left

    @property
    def pivot_right(self) -> int:
        return self.swing.pivot_right

    @property
    def minimum_swing_distance(self) -> float:
        return self.swing.minimum_swing_distance

    @property
    def equal_high_tolerance(self) -> float:
        return self.swing.equal_high_tolerance

    @property
    def equal_low_tolerance(self) -> float:
        return self.swing.equal_low_tolerance

    @property
    def atr_validation(self) -> bool:
        return self.swing.atr_validation

    @property
    def atr_period(self) -> int:
        return self.swing.atr_period

    @property
    def atr_multiplier(self) -> float:
        return self.swing.atr_multiplier

    @property
    def maximum_history(self) -> int:
        return self.swing.maximum_history

    @property
    def swing_confidence_weight(self) -> float:
        return self.swing.swing_confidence_weight

    @property
    def bos_confidence_weight(self) -> float:
        return self.swing.bos_confidence_weight

    @property
    def choch_confidence_weight(self) -> float:
        return self.swing.choch_confidence_weight

    @property
    def liquidity_confidence_weight(self) -> float:
        return self.swing.liquidity_confidence_weight

    @property
    def maximum_confidence_score(self) -> float:
        return self.swing.maximum_confidence_score
