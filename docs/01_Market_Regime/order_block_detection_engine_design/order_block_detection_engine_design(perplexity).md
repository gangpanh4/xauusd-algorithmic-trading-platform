<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# You are a senior quantitative developer, institutional trader, and software architect.

We are building a professional Python algorithmic trading platform for XAUUSD.

Existing completed modules:

- Swing Detector
- BOS (Break of Structure) Detector
- CHOCH (Change of Character) Detector
- Liquidity Sweep Detector

Architecture:

Market Data
↓
Swing Detection
↓
BOS Detection
↓
CHOCH Detection
↓
Liquidity Detection
↓
Order Block Detection
↓
Fair Value Gap Detection
↓
Signal Generation
↓
Risk Management
↓
Execution

Your task:

Research and design a production-grade Order Block Detection Engine.

Do NOT focus on a simple trading indicator.
Design it as a modular component inside a quantitative trading platform.

Analyze:

1. What is an Order Block?
    - Institutional definition
    - Bullish Order Block
    - Bearish Order Block
    - Difference between real order blocks and random support/resistance
2. Detection Algorithm:
    - How to identify order blocks from price action
    - Relationship with:
        - Swing highs/lows
        - BOS
        - CHOCH
        - Liquidity sweeps
        - Market structure
    - Confirmation requirements
    - Avoiding repainting
3. Bullish Order Block Rules:
    - Exact conditions
    - Candle requirements
    - Structure requirements
    - Validation rules
4. Bearish Order Block Rules:
    - Exact conditions
    - Candle requirements
    - Structure requirements
    - Validation rules
5. Order Block Lifecycle:
    - Creation
    - Confirmation
    - Active state
    - Mitigation
    - Invalidity
    - Expiration
6. Data Model Design:
Suggest Python dataclasses:
    - OrderBlock
    - OrderBlockEvent
    - Required fields
7. State Management:
Design:
    - OrderBlockDetectorState
    - What data it owns
    - What data it consumes
8. Detector Architecture:
Design:

class OrderBlockDetector

Include:
    - Inputs
    - Outputs
    - Public methods
    - Private methods
9. Backtesting Considerations:
    - No future data leakage
    - No repainting
    - Historical replay compatibility
    - Live trading compatibility
10. Testing Strategy:
Suggest unit tests:

- Initialization
- Reset
- Bullish OB detection
- Bearish OB detection
- Invalid OB rejection
- Mitigation
- Duplicate protection

11. Give architectural recommendations:

- Should OrderBlockDetector consume BOS state?
- Should it consume CHOCH events?
- Should it consume LiquiditySweep events?
- What should it own?

Important:
Prioritize correctness, maintainability, and professional software architecture over creating many signals.

Below is a production-grade design for an **Order Block Detection Engine** as a modular component in a professional XAUUSD trading platform. The core idea is to treat an order block as a **confirmed structural footprint** created before displacement, not as a loose support/resistance zone. The detector should therefore be event-driven, stateful, non-repainting, and tightly integrated with BOS/CHOCH and liquidity context.[^1][^2][^3]

## 1) Institutional meaning

An order block is the last opposite candle or compact candle cluster before a strong directional displacement that breaks structure, suggesting institutional participation and unfinished order flow. In a bullish setup, the engine looks for a bearish candle or bearish cluster that precedes an impulsive upward move; in a bearish setup, it looks for a bullish candle or bullish cluster before a sharp downward move.[^2][^4][^1]

A **real order block** is not just a visually important level. It is a zone whose validity is supported by structural displacement, a subsequent BOS or CHOCH, and ideally a liquidity sweep or stop-run that precedes the move. Random support/resistance lacks that execution story and should not be promoted to an OB object.[^3]

## 2) Detection logic

The detector should only evaluate candidates after a **confirmed displacement** and **confirmed structure event**. That means it should consume swing state, BOS/CHOCH events, and optionally liquidity sweep events, then retrospectively mark the origin candle or candle cluster that preceded the impulse.[^3]

A robust identification sequence is:

1. Detect a swing high/low.
2. Detect a liquidity sweep or local stop run if available.
3. Detect BOS or CHOCH with close confirmation.
4. Find the last opposite candle or tight candle cluster before the impulse leg.
5. Validate that the candidate range has not already been invalidated.
6. Register the OB as active and non-repainting from that bar onward.

This keeps the detector aligned with market structure rather than with arbitrary candle patterns.

## 3) Bullish rules

A bullish order block should be created only when the market shows bearish-to-bullish reversal evidence. The canonical condition is: a bearish candle, or the last bearish candle in a compact bearish base, is followed by a strong upward displacement that breaks a prior swing high or triggers a CHOCH/BOS in bullish direction.[^5][^3]

Recommended exact rules:

- The candidate candle must be bearish.
- The impulsive leg after it must close above a relevant swing high or internal structure high.
- The displacement should be larger than a configurable threshold, such as a multiple of ATR or recent average candle range.
- Preferably, the move should come after a liquidity sweep below a local low or equal lows.
- The OB zone is usually defined from the candle’s open to low, or full candle body plus wick policy configurable by mode.
- If multiple bearish candles form a base, choose the last bearish candle before displacement, or define a multi-candle zone if your platform supports clusters.

Validation rules:

- The zone must remain unbroken before the first mitigation.
- A bullish OB should be invalidated if price closes decisively below its low.
- It should be confirmed only after the BOS/CHOCH candle closes, never intrabar.


## 4) Bearish rules

A bearish order block is the mirror image. It is typically the last bullish candle, or last bullish cluster, before a strong downward displacement that breaks a prior swing low or confirms bearish CHOCH/BOS.[^5][^3]

Recommended exact rules:

- The candidate candle must be bullish.
- The next displacement leg must close below a relevant swing low or internal structure low.
- The impulse should exceed a minimum range threshold.
- Preferably, the move follows a liquidity sweep above a local high or equal highs.
- The OB zone is usually defined from the candle’s high to open, or body-based depending on the strictness setting.
- Multi-candle bases may be collapsed into one zone if the last bullish candle is not sufficiently clean.

Validation rules:

- The zone remains active until a confirming touch/mitigation or a close above its high invalidates it.
- Confirmation must be based on closed bars only.


## 5) Lifecycle

The OB should have a finite lifecycle with explicit states:

- **Created**: candidate identified from confirmed displacement.
- **Confirmed**: structure event validates the zone.
- **Active**: tradable and watchable.
- **Mitigated**: price revisits the zone and partially or fully fills the imbalance.
- **Invalid**: close beyond invalidation boundary occurs.
- **Expired**: timeout by age, session, or max bars without meaningful retest.

A professional engine should distinguish **mitigation touch** from **full invalidation**. A first touch may merely move the state to mitigated, while a decisive close through the boundary invalidates it. That distinction is important for signal generation and backtesting fidelity.[^3]

## 6) Data model

Use immutable event records and a mutable detector state.

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Literal, List

class OrderBlockSide(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"

class OrderBlockStatus(str, Enum):
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    ACTIVE = "active"
    MITIGATED = "mitigated"
    INVALID = "invalid"
    EXPIRED = "expired"

@dataclass(frozen=True)
class OrderBlock:
    id: str
    symbol: str
    timeframe: str
    side: OrderBlockSide
    status: OrderBlockStatus
    created_index: int
    created_time: float
    confirmed_index: Optional[int]
    confirmed_time: Optional[float]
    source_candle_index: int
    zone_low: float
    zone_high: float
    body_low: float
    body_high: float
    wick_policy: str
    displacement_start_index: int
    displacement_end_index: int
    structure_event_id: Optional[str]
    liquidity_event_id: Optional[str]
    swing_reference_index: Optional[int]
    mitigation_count: int
    first_mitigated_index: Optional[int]
    first_mitigated_time: Optional[float]
    invalidated_index: Optional[int]
    invalidated_time: Optional[float]
    expired_index: Optional[int]
    metadata: dict = field(default_factory=dict)

@dataclass(frozen=True)
class OrderBlockEvent:
    event_type: str
    ob_id: str
    symbol: str
    timeframe: str
    side: OrderBlockSide
    index: int
    timestamp: float
    price: float
    info: dict = field(default_factory=dict)
```


## 7) State management

`OrderBlockDetectorState` should own only detector-local memory, not full market history. It should maintain:

- Active and historical OB registries by ID.
- A short rolling window of recent candles.
- The latest consumed swing/BOS/CHOCH/liquidity event IDs.
- A deduplication set for candidate fingerprints.
- Configurable thresholds and policy flags.
- Last processed bar index to enforce replay ordering.

It should consume:

- OHLCV bars.
- Swing highs/lows from SwingDetector.
- BOS and CHOCH events.
- Liquidity sweep events.
- Optional ATR or volatility context.

It should not own execution logic, position sizing, or trade management. That belongs downstream.

## 8) Detector architecture

```python
class OrderBlockDetector:
    def __init__(self, config, state=None):
        ...

    def reset(self) -> None:
        ...

    def update_bar(self, bar, swing_events=None, structure_events=None, liquidity_events=None) -> list[OrderBlockEvent]:
        ...

    def get_active_blocks(self, side=None) -> list[OrderBlock]:
        ...

    def get_block_by_id(self, ob_id: str) -> Optional[OrderBlock]:
        ...

    def serialize_state(self) -> dict:
        ...

    def load_state(self, payload: dict) -> None:
        ...
```

Private methods should include:

- `_update_active_blocks`.
- `_evaluate_new_candidates`.
- `_find_bullish_candidate`.
- `_find_bearish_candidate`.
- `_confirm_candidate`.
- `_invalidate_block`.
- `_mark_mitigated`.
- `_is_duplicate_candidate`.
- `_meets_displacement_threshold`.
- `_meets_structure_requirements`.

Inputs:

- Sequential bars.
- Structure events.
- Liquidity sweep events.
- Optional volatility context.

Outputs:

- OB creation, confirmation, mitigation, invalidation, expiration events.
- Current active OB snapshot.


## 9) Backtesting safety

To avoid future leakage, the detector must only use information available on or before the current closed bar. Confirmation should occur only after the confirming candle closes, not during its formation. That means the OB can be *identified retrospectively* from past bars, but it becomes tradable only when the confirming event is closed and known.[^3]

For historical replay, the detector should process bars strictly in order and reject out-of-sequence timestamps. For live trading, it should support incremental updates and idempotent re-processing of the latest closed bar so duplicate feed events do not create duplicate OBs. A fingerprint based on symbol, timeframe, side, source index, and displacement index is useful for deduplication.

## 10) Testing strategy

Recommended unit tests:

- Initialization returns empty active registry.
- Reset clears active/historical state.
- Bullish OB detection creates one confirmed bullish block after valid BOS/CHOCH.
- Bearish OB detection creates one confirmed bearish block after valid BOS/CHOCH.
- Invalid OB rejection when displacement is insufficient.
- Invalid OB rejection when structure is not broken.
- Mitigation changes status correctly on first touch.
- Full invalidation occurs only on close beyond boundary.
- Duplicate protection prevents the same OB from being emitted twice.
- Out-of-order bar rejection in replay mode.
- Serialization round-trip preserves state.

A strong test suite should include synthetic candle sequences that isolate structure, displacement, sweep, mitigation, and invalidation separately.

## 11) Architectural recommendations

Yes, `OrderBlockDetector` should consume **BOS state**. That is the primary structural confirmation for a valid OB. Yes, it should also consume **CHOCH events**, because CHOCH is often the earlier reversal cue that identifies the best candidate zones.[^3]

It should consume **LiquiditySweep events** as a filter, not as a hard requirement. Sweeps improve quality, but making them mandatory can reduce coverage too much in live markets. The detector should own zone construction, validation, lifecycle transitions, and deduplication. It should not own swing detection, BOS logic, execution, or risk management.

## Suggested design principle

Treat order blocks as **stateful structure-derived zones** with explicit confirmation rules, not as chart annotations. That makes the engine suitable for backtesting, live trading, and future strategy composition, especially on XAUUSD where volatility and liquidity raids are frequent.[^4][^3]
<span style="display:none">[^10][^6][^7][^8][^9]</span>

<div align="center">⁂</div>

[^1]: https://acy.com/en/market-news/education/order-block-trading-institutional-footprint-j-o-20251110-115425/

[^2]: https://tradingstrategyguides.com/lecture-5-order-blocks-101-what-they-are-how-to-identify-them-role-in-institutional-trading/

[^3]: https://www.youtube.com/watch?v=tJJErpsUyac

[^4]: https://www.binance.com/en/square/post/33421881846497

[^5]: https://innercircletrader.net/tutorials/ict-order-block/

[^6]: https://www.slideshare.net/slideshow/institutionaltradingpdf/252497831

[^7]: https://www.luxalgo.com/blog/ict-trader-concepts-order-blocks-unpacked/

[^8]: https://www.youtube.com/watch?v=NHwvZ0iFO6s

[^9]: https://www.quantum-algo.com/blog/order-blocks-playbook/

[^10]: https://www.scribd.com/document/706380168/Order-Block-Institutional-Trading-Practical-Guide-by-James-J-King

