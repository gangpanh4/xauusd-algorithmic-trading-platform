"""
Configuration for the Order Block Detection Engine.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class OrderBlockDetectorConfig:
    """
    Configuration for the Order Block Detection Engine.

    These parameters control detector behaviour only.
    They do not define trading strategy or execution rules.
    """

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    # Minimum displacement required after the origin candle
    # before an Order Block can be confirmed.
    minimum_displacement: float = 0.0
    
    # Minimum height required for an Order Block to be considered valid.
    minimum_block_height: float = 0.10

    # Minimum overall quality score required for a valid
    # Order Block.
    minimum_strength: float = 0.60

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    # Maximum number of processed bars an Order Block may
    # remain active before expiring.
    maximum_block_age: int = 500

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    # Include liquidity sweeps as a confidence bonus.
    # Liquidity is optional and should never be required
    # for a structurally valid Order Block.
    enable_liquidity_bonus: bool = True

    # Allow multiple nested Order Blocks.
    allow_nested_blocks: bool = False

    # Remove invalidated Order Blocks from the active list.
    # Historical records remain available in the detector state.
    remove_invalidated_blocks: bool = False

    # ------------------------------------------------------------------
    # Development
    # ------------------------------------------------------------------

    # Enable verbose detector logging.
    debug_logging: bool = False