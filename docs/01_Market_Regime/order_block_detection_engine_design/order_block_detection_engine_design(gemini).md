Designing a production-grade Order Block (OB) Detection Engine requires strict decoupling, deterministic state management, and an event-driven architecture. As this sits midway through your pipeline, it must consume upstream structural events (BOS, CHOCH, Liquidity) and emit actionable OB data for downstream signal generation.
Here is the architectural blueprint and quantitative specification for the Order Block Detection Engine.
1. What is an Order Block?
Institutional Definition
An order block represents a specific price footprint where large institutional participants accumulate or distribute significant volume before initiating an impulsive, structure-breaking market move.
Bullish Order Block
The last consecutive down-close candle(s) preceding an impulsive bullish expansion that breaks market structure to the upside. It represents the "sell to buy" institutional footprint.
Bearish Order Block
The last consecutive up-close candle(s) preceding an impulsive bearish expansion that breaks market structure to the downside. It represents the "buy to sell" footprint.
Difference from Retail Support/Resistance
Random support/resistance relies on historical price touches and psychological levels. Order blocks are defined strictly by structural validation. A block of price is only an OB if it actively caused displacement (Fair Value Gap) and a structural shift (BOS/CHOCH). Without these validations, it is merely a candlestick.
2. Detection Algorithm & Dependencies
The detection algorithm does not predict OBs in real-time; it identifies them retroactively upon structural confirmation.
Swing Highs/Lows: Provide the origin boundaries. An OB must originate near a validated swing point.
Liquidity Sweeps: A high-probability OB often sweeps a previous swing liquidity pool immediately before the impulsive move.
BOS & CHOCH: These are the catalysts. The OB engine listens for a BOS/CHOCH event, then looks backward in the price time-series to identify the origin candle of that specific price leg.
Market Structure: Ensures the OB aligns with the prevailing institutional order flow.
Confirmation Requirements: The impulsive move leaving the OB must create a Fair Value Gap (FVG), proving institutional displacement.
Avoiding Repainting: The engine must only process finalized upstream events triggered by candle closes. Intrabar price action is strictly for mitigation checks, never for OB creation.
3. Bullish Order Block Rules
Origin: Must occur at or immediately following a valid Swing Low.
Candle Requirements: The lowest down-close candle (or consecutive down candles) before the bullish impulse. The "zone" is defined by the high to the low of this candle.
Displacement: The move exiting the OB must leave a Bullish Fair Value Gap (FVG) within the next 1-3 candles.
Structural Validation: The subsequent move must result in a Bullish BOS or Bullish CHOCH.
Exact Conditions: High = Candle High, Low = Candle Low. If the preceding candle has a lower wick, the low of the block must encapsulate that wick to cover the true liquidity footprint.
4. Bearish Order Block Rules
Origin: Must occur at or immediately following a valid Swing High.
Candle Requirements: The highest up-close candle (or consecutive up candles) before the bearish impulse.
Displacement: The move exiting the OB must leave a Bearish Fair Value Gap (FVG).
Structural Validation: The subsequent move must result in a Bearish BOS or Bearish CHOCH.
Exact Conditions: High = Candle High, Low = Candle Low. If the preceding candle has a higher wick, the top of the block encapsulates that wick.
5. Order Block Lifecycle
Creation: An unconfirmed footprint is noted at a swing point (held in memory but not emitted).
Confirmation: A BOS/CHOCH event is received. The engine validates the FVG and emits the OB as ACTIVE.
Active State: The OB is resting in the market, waiting for price to retrace.
Mitigation: Price intersects the OB zone (touches the proximal line). The OB is considered mitigated. Institutional orders are presumed filled.
Invalidity: Price closes entirely beyond the distal line (below a Bullish OB, or above a Bearish OB). The OB is invalidated and discarded.
Expiration: Time-decay removal if the OB is left unmitigated after a massive structural shift (e.g., 200+ candles ago, or opposing higher-timeframe CHOCH).
6. Data Model Design
The data structures must be immutable and heavily typed to prevent accidental mutation downstream.



Python
from dataclasses import dataclass
from typing import Optional
from enum import Enum

class OBType(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"

class OBStatus(Enum):
    ACTIVE = "ACTIVE"
    MITIGATED = "MITIGATED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"

@dataclass(frozen=True)
class OrderBlock:
    id: str
    ob_type: OBType
    proximal_price: float
    distal_price: float
    creation_time: int
    confirmation_time: int
    volume_at_creation: float
    liquidity_swept: bool

@dataclass(frozen=True)
class OrderBlockEvent:
    timestamp: int
    order_block: OrderBlock
    status: OBStatus
    trigger_price: Optional[float] = None


7. State Management
The detector state must be cleanly isolated to allow for deterministic replays in your backtester.
OrderBlockDetectorState: A mutable container class managed exclusively by the detector.
Owned Data: Dictionary of active_obs, list of historical_obs, and a localized circular buffer of recent candles (e.g., last 50 bars) to look back for the origin candle upon a BOS/CHOCH event.
Consumed Data (Read-Only): The latest OHLCV bar, upstream Event queues (BOS, CHOCH, Liquidity).
8. Detector Architecture
The interface must follow a strict initialization and update loop.



Python
class OrderBlockDetector:
    def __init__(self, fvg_threshold: float, expiration_bars: int):
        self._state = OrderBlockDetectorState()
        self._fvg_threshold = fvg_threshold
        self._expiration_bars = expiration_bars

    # Public Methods
    def on_bar(self, bar: Bar, upstream_events: list[Event]) -> list[OrderBlockEvent]:
        # Main entry point per bar loop
        pass

    def reset(self) -> None:
        # Clears state for new backtest runs
        pass

    def get_active_blocks(self) -> list[OrderBlock]:
        # Accessed by downstream signal generators
        pass

    # Private Methods
    def _process_structural_events(self, events: list[Event]) -> None:
        # Listens for BOS/CHOCH and triggers _find_origin_block
        pass

    def _find_origin_block(self, event: Event) -> Optional[OrderBlock]:
        # Looks backward in the price buffer for the institutional candle
        pass

    def _check_mitigations(self, bar: Bar) -> list[OrderBlockEvent]:
        # Checks if current bar intersects active OBs
        pass


9. Backtesting Considerations
No Future Data Leakage: Ensure the on_bar method only processes OB confirmation after the structural break candle has fully closed.
No Repainting: The distal and proximal lines of the OB must never be adjusted once confirmed. If price action alters the view, invalidate the old OB and create a new one.
Historical Replay Compatibility: The reset() method must clear all internal states completely. The engine must produce the exact same sequence of OrderBlockEvent objects whether run in a batch vector operation or a tick-by-tick live loop.
10. Testing Strategy
Implement pytest unit tests with mocked OHLCV arrays targeting these specific scenarios:
Initialization & Reset: Ensure the local candle buffer and active dictionaries drop to zero upon reset.
Bullish/Bearish Detection: Provide a static array containing a clear impulse and BOS. Assert the detector accurately captures the exact high/low of the correct origin candle.
Invalid OB Rejection: Provide an impulse that breaks structure but lacks an FVG. Assert the engine ignores it.
Mitigation Boundary: Feed a bar whose low exactly matches the proximal line. Assert a MITIGATED event is fired.
Invalidation Boundary: Feed a bar that closes 1 pip below the distal line of a Bullish OB. Assert an INVALIDATED event is fired.
Duplicate Protection: Feed the same BOS event twice. Assert only one OB is created.
11. Architectural Recommendations
Component Decoupling is Critical:
The OrderBlockDetector should absolutely not calculate Swings, BOS, or CHOCH internally. Doing so creates tightly coupled "god classes" that are impossible to maintain.
Data Flow:
It must purely consume immutable event objects (BOSEvent, CHOCHEvent, LiquiditySweepEvent) injected from upstream modules. This allows you to hot-swap or upgrade your BOS logic in the future without touching the OB engine.
Ownership:
The OB Engine owns strictly the calculation of the price zone (proximal/distal), the validation of the displacement (FVG check), and the lifecycle (mitigation tracking) of the block itself. Downstream modules (Signal Generation, Risk Management) will consume the OB events to dictate entry pricing and stop-loss placement.
