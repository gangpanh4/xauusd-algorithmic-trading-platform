"""Configuration for the observational XAUUSD BOS/CHOCH strategy."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from core.multi_timeframe.enums import Timeframe


@dataclass(slots=True, frozen=True)
class XAUUSDBOSCHOCHConfig:
    """Deterministic timeframe and lifecycle rules for strategy v1."""

    strategy_id: str = "XAUUSD_BOS_CHOCH_V1"
    bias_timeframes: tuple[Timeframe, Timeframe] = (
        Timeframe.H4,
        Timeframe.H1,
    )
    setup_timeframe: Timeframe = Timeframe.M15
    trigger_timeframe: Timeframe = Timeframe.M5
    setup_expiry_bars: int = 3
    maximum_structure_event_age_bars: int = 2
    minimum_target_reward_risk: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.strategy_id, str) or not self.strategy_id.strip():
            raise ValueError("strategy_id must be a non-empty string")
        if self.bias_timeframes != (Timeframe.H4, Timeframe.H1):
            raise ValueError("bias_timeframes must be exactly (H4, H1)")
        if self.setup_timeframe is not Timeframe.M15:
            raise ValueError("setup_timeframe must be M15")
        if self.trigger_timeframe is not Timeframe.M5:
            raise ValueError("trigger_timeframe must be M5")
        for name in (
            "setup_expiry_bars",
            "maximum_structure_event_age_bars",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer")
            if value < 1:
                raise ValueError(f"{name} must be at least 1")
        value = self.minimum_target_reward_risk
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("minimum_target_reward_risk must be numeric")
        if not isfinite(float(value)) or value <= 0.0:
            raise ValueError(
                "minimum_target_reward_risk must be finite and positive"
            )
