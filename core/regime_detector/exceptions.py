"""
Market Regime Detection - Exception Hierarchy

All public exceptions raised by the Market Regime Detection module
inherit from MarketRegimeError.
"""


class MarketRegimeError(Exception):
    """
    Base exception for the Market Regime Detection module.
    """

    pass


class ConfigValidationError(MarketRegimeError):
    """
    Raised when the configuration fails validation.
    """

    pass


class CalibrationValidationError(MarketRegimeError):
    """
    Raised when a calibration artifact is invalid.
    """

    pass


class DataQualityError(MarketRegimeError):
    """
    Raised when market data fails validation.
    """

    pass


class StaleInputError(MarketRegimeError):
    """
    Raised when incoming market data timestamps are stale
    or not strictly increasing.
    """

    pass


class ChronologyError(MarketRegimeError):
    """
    Raised when historical bars are not in chronological order.
    """

    pass


class LogWriteError(MarketRegimeError):
    """
    Raised when a critical transition log cannot be written.
    """

    pass


class DetectorStateError(MarketRegimeError):
    """
    Raised when the detector enters an invalid internal state.
    """

    pass


class SnapshotError(MarketRegimeError):
    """
    Raised when snapshot serialization or restoration fails.
    """

    pass


class InitializationError(MarketRegimeError):
    """
    Raised when detector initialization fails.
    """

    pass