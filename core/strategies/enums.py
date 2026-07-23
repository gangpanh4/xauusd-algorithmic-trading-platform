"""Enumerations for explicit trading-setup and entry lifecycles."""

from __future__ import annotations

from enum import StrEnum


class SetupDirection(StrEnum):
    """Allowed directional thesis for a setup."""

    BUY = "BUY"
    SELL = "SELL"


class SetupStatus(StrEnum):
    """Lifecycle of one strategy setup."""

    DETECTED = "DETECTED"
    ACTIVE = "ACTIVE"
    TRIGGERED = "TRIGGERED"
    CONSUMED = "CONSUMED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class SetupInvalidationReason(StrEnum):
    """Why an otherwise valid setup stopped being tradable."""

    STRUCTURE_BROKEN = "STRUCTURE_BROKEN"
    BIAS_CHANGED = "BIAS_CHANGED"
    PRICE_CROSSED_INVALIDATION = "PRICE_CROSSED_INVALIDATION"
    SETUP_EXPIRED = "SETUP_EXPIRED"
    SESSION_CLOSED = "SESSION_CLOSED"
    DATA_INVALID = "DATA_INVALID"
    MANUAL_CANCEL = "MANUAL_CANCEL"


class EntryTriggerType(StrEnum):
    """Deterministic event that converts an active setup into a candidate."""

    CONFIRMATION_CLOSE = "CONFIRMATION_CLOSE"
    RETRACEMENT_TOUCH = "RETRACEMENT_TOUCH"
    LIQUIDITY_RECLAIM = "LIQUIDITY_RECLAIM"
    BOS_CONFIRMATION = "BOS_CONFIRMATION"
    CHOCH_CONFIRMATION = "CHOCH_CONFIRMATION"


class EntryTriggerStatus(StrEnum):
    """Lifecycle of an entry trigger."""

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class PriceReferenceType(StrEnum):
    """Trading reason represented by an absolute price reference."""

    PROTECTED_SWING = "PROTECTED_SWING"
    SETUP_INVALIDATION = "SETUP_INVALIDATION"
    LIQUIDITY_EXTREME = "LIQUIDITY_EXTREME"
    OPPOSING_LIQUIDITY = "OPPOSING_LIQUIDITY"
    PREVIOUS_SWING = "PREVIOUS_SWING"
    HIGHER_TIMEFRAME_LEVEL = "HIGHER_TIMEFRAME_LEVEL"
    FIXED_R_MULTIPLE = "FIXED_R_MULTIPLE"
    ATR_FALLBACK = "ATR_FALLBACK"
