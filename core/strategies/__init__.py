"""Explicit strategy-domain contracts and observational strategies."""

from .config import XAUUSDBOSCHOCHConfig
from .context import StrategyContext, StrategyObservation
from .enums import (
    EntryTriggerStatus,
    EntryTriggerType,
    PriceReferenceType,
    SetupDirection,
    SetupInvalidationReason,
    SetupStatus,
)
from .models import (
    CandidateTrade,
    EntryTrigger,
    PriceReference,
    TradingSetup,
)
from .state import XAUUSDBOSCHOCHState
from .xauusd_bos_choch import XAUUSDBOSCHOCHStrategy

__all__ = [
    "CandidateTrade",
    "EntryTrigger",
    "EntryTriggerStatus",
    "EntryTriggerType",
    "PriceReference",
    "PriceReferenceType",
    "SetupDirection",
    "SetupInvalidationReason",
    "SetupStatus",
    "StrategyContext",
    "StrategyObservation",
    "TradingSetup",
    "XAUUSDBOSCHOCHConfig",
    "XAUUSDBOSCHOCHState",
    "XAUUSDBOSCHOCHStrategy",
]
