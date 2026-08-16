"""Presentation-only enumerations for the Aurum read model."""

from __future__ import annotations

from enum import StrEnum


class AurumDataMode(StrEnum):
    """Supported Aurum read-model data modes."""

    REAL_READ_ONLY = "REAL_READ_ONLY"
    RESEARCH_REPLAY = "RESEARCH_REPLAY"
    MOCK = "MOCK"


class AurumOperatorState(StrEnum):
    """Operator-facing readiness state; never execution authorization."""

    HOLD = "HOLD"
    READY_BUY = "READY_BUY"
    READY_SELL = "READY_SELL"
    BLOCKED = "BLOCKED"
