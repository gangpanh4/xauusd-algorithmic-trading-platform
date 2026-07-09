"""
Custom exceptions for the Market Structure Engine.
"""


class MarketStructureError(Exception):
    """
    Base exception for all market structure errors.
    """


class SwingDetectorError(MarketStructureError):
    """
    Raised for SwingDetector-specific errors.
    """


class BOSDetectorError(MarketStructureError):
    """
    Raised for BOSDetector-specific errors.
    """