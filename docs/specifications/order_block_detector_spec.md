# Order Block Detector Specification

**Document ID:** SMC-SPEC-006

**Version:** 1.0

**Status:** Draft

**Project:** Trading Intelligence Platform

**Module:** Market Structure Engine

---

# 1. Purpose

The Order Block Detector is responsible for identifying institutional Order Blocks that represent significant areas of buying or selling interest following confirmed structural events.

Order Blocks are derived from completed MarketBars in combination with confirmed Swing Events, BOS Events, CHOCH Events, and Liquidity Events.

The detector identifies high-probability institutional price zones that may act as future support, resistance, continuation, or reversal areas.

The Order Block Detector produces immutable Order Block Events and quantitative measurements for downstream components.

Confirmed Order Block Events provide structural context for:

- Fair Value Gap Engine
- Breaker Block Engine
- Mitigation Block Engine
- Feature Engineering
- Research Analytics
- Probability Engine

The detector operates deterministically and incrementally, ensuring identical outputs for identical historical market data.

The detector does not generate trading signals or trading decisions.

---

# 2. Scope

The Order Block Detector is responsible only for identifying confirmed institutional Order Blocks.

The detector SHALL:

- Detect Bullish Order Blocks
- Detect Bearish Order Blocks
- Validate structural context
- Validate liquidity interaction
- Detect Order Block mitigation
- Produce immutable Order Block Events
- Produce quantitative Order Block measurements
- Support historical replay
- Support live streaming execution

The detector SHALL NOT:

- Detect Swing Highs
- Detect Swing Lows
- Detect BOS
- Detect CHOCH
- Detect Liquidity
- Detect Fair Value Gaps
- Generate trading signals
- Calculate probabilities
- Manage trading risk

These responsibilities belong to other components.

---

# 3. Owner

## Owner Module

```
OrderBlockDetector
```

The Order Block Detector is the sole owner of:

- Order Block Events
- Order Block History
- Order Block Measurements
- Order Block Detector State

The detector does not own:

- Swing Events
- BOS Events
- CHOCH Events
- Liquidity Events
- Current Trend
- Protected Swing

These remain under their respective detectors.

---

# 4. Responsibilities

The Order Block Detector shall:

- Consume Swing Events
- Consume BOS Events
- Consume CHOCH Events
- Consume Liquidity Events
- Identify Bullish Order Blocks
- Identify Bearish Order Blocks
- Validate structural alignment
- Validate liquidity alignment
- Prevent duplicate Order Block Events
- Produce immutable Order Block Events
- Maintain detector runtime state
- Compute Order Block measurements
- Expose measurements for Feature Engineering
- Operate deterministically
- Operate incrementally
- Support historical replay
- Support continuous streaming execution

---

# 5. Dependencies

## Consumes

The Order Block Detector consumes:

- Completed MarketBar
- Swing Events
- BOS Events
- CHOCH Events
- Liquidity Events
- OrderBlockDetectorConfig
- Internal Order Block State

The detector does not consume Fair Value Gaps.

---

## Produces

The Order Block Detector produces:

- OrderBlockEvent
- Updated Order Block State
- Order Block Measurements
- Feature Engineering Inputs

These outputs are consumed by downstream structural detectors.

---

# 6. Inputs

The detector processes one completed MarketBar at a time.

Required inputs include:

- Completed MarketBar
- Swing Events
- BOS Events
- CHOCH Events
- Liquidity Events

Configuration parameters include:

- Minimum Displacement
- Minimum Candle Body Ratio
- Require BOS Confirmation
- Require Liquidity Confirmation
- Mitigation Validation
- ATR Validation
- ATR Period
- ATR Multiplier

All configuration shall be immutable after detector initialization.

---

# 7. Outputs

The Order Block Detector produces immutable Order Block Events.

Each Order Block Event shall include:

- Event ID
- Timestamp
- Order Block Type
- Direction
- Price Zone
- Origin Candle
- Trigger Event
- Mitigation Status
- Confirmation Bar

The detector also produces:

- Updated Order Block State
- Order Block Measurements
- Feature Engineering Inputs

When no Order Block is confirmed, the detector shall produce no event.

---

# 8. Configuration

The Order Block Detector shall support configuration through the OrderBlockDetectorConfig object.

The following parameters shall be configurable.

| Parameter | Description |
|------------|-------------|
| Minimum Displacement | Minimum impulsive movement required |
| Minimum Candle Body Ratio | Minimum body-to-range ratio |
| Require BOS Confirmation | Require confirmed BOS before OB creation |
| Require Liquidity Confirmation | Require liquidity interaction |
| Mitigation Validation | Enable mitigation tracking |
| ATR Validation | Enable ATR filtering |
| ATR Period | ATR calculation period |
| ATR Multiplier | Minimum volatility requirement |

Configuration values adjust detector sensitivity but shall not alter ownership or detector responsibilities.

---

---

# 9. Detection Rules

The Order Block Detector shall identify institutional Order Blocks using completed MarketBars, confirmed Swing Events, BOS Events, CHOCH Events, and Liquidity Events.

An Order Block represents a validated institutional price zone from which a significant impulsive movement originated.

The detector shall evaluate only completed MarketBars.

The detector shall never predict future price movement.

---

## 9.1 Bullish Order Block

A Bullish Order Block is confirmed when all of the following conditions are satisfied:

- A valid Bullish BOS or Bullish CHOCH exists.
- A valid displacement move follows.
- The originating bearish candle (or defined price zone) is identified.
- Liquidity interaction requirements are satisfied (if enabled).
- ATR validation succeeds (if enabled).
- All confirmation rules succeed.

Once confirmed:

- A Bullish Order Block Event shall be emitted.
- A Bullish Order Block Zone shall be created.
- The zone shall become Active.

---

## 9.2 Bearish Order Block

A Bearish Order Block is confirmed when all of the following conditions are satisfied:

- A valid Bearish BOS or Bearish CHOCH exists.
- A valid displacement move follows.
- The originating bullish candle (or defined price zone) is identified.
- Liquidity interaction requirements are satisfied (if enabled).
- ATR validation succeeds (if enabled).
- All confirmation rules succeed.

Once confirmed:

- A Bearish Order Block Event shall be emitted.
- A Bearish Order Block Zone shall be created.
- The zone shall become Active.

---

## 9.3 Structural Validation

An Order Block shall never be created without confirmed market structure.

Valid structural confirmation includes:

- BOS
- CHOCH

Structure provides directional context for Order Block creation.

---

## 9.4 Displacement Validation

Every Order Block shall be validated by displacement.

Displacement validation may include:

- Large candle body
- Strong momentum
- ATR expansion
- Consecutive impulsive candles
- Configured displacement threshold

Weak movements shall not produce Order Blocks.

---

## 9.5 Liquidity Validation

If enabled, the detector shall require evidence of liquidity interaction before confirming an Order Block.

Liquidity interaction may include:

- Buy-side sweep
- Sell-side sweep
- Liquidity consumption
- Liquidity cluster interaction

Liquidity confirmation increases Order Block confidence.

---

## 9.6 Mitigation Detection

A previously confirmed Order Block may later be revisited by price.

When price returns to the Order Block Zone, the detector shall classify the interaction as:

- Partial Mitigation
- Full Mitigation

Mitigation shall not modify the original Order Block Event.

Instead:

- Zone state shall be updated.
- A Mitigation Event may be emitted by the Mitigation Block Detector.

---

## 9.7 Invalid Order Block

An Order Block becomes invalid when:

- Price closes beyond the invalidation boundary.
- Configured invalidation rules succeed.

The detector shall:

- Preserve the original immutable Order Block Event.
- Update the Order Block Zone state.
- Emit an Order Block Invalidated Event.

---

## 9.8 Duplicate Prevention

Before confirming an Order Block Event, the detector shall verify that an equivalent Order Block has not already been emitted.

Duplicate Order Block Events shall not be produced.

---

# 10. Confirmation Rules

An Order Block shall only be confirmed after all applicable validation rules succeed.

Validation may include:

- BOS confirmation
- CHOCH confirmation
- Displacement validation
- Liquidity validation
- ATR validation
- Duplicate validation

Once confirmed:

- Event ID shall never change.
- Direction shall never change.
- Price Zone shall never change.
- Origin Candle shall never change.
- Confirmation Timestamp shall never change.

Confirmed Order Block Events are immutable.

---

# 11. State Management

The Order Block Detector maintains only the runtime state required for deterministic Order Block detection.

The detector state includes:

- Active Order Block Zones
- Order Block History
- Last Confirmed Order Block
- Internal Processing State

The detector shall update its internal state incrementally after every completed MarketBar.

Reset operations shall restore the detector to its initial state.

---

## Order Block Lifecycle

Each Order Block Zone progresses through the following lifecycle.

```text
Detected
      │
      ▼
Confirmed
      │
      ▼
Active
      │
      ├── Partially Mitigated
      │
      ├── Fully Mitigated
      │
      ├── Invalidated
      │
      └── Expired
```

The lifecycle state shall be deterministic.

The original Order Block Event remains immutable throughout the lifecycle.

---

# 12. State Ownership

The Order Block Detector is the authoritative owner of:

- Order Block Events
- Order Block Zones
- Order Block Measurements
- Order Block History
- Internal Detector State

The Order Block Detector shall never modify:

- Swing Events
- BOS Events
- CHOCH Events
- Liquidity Events
- Current Trend
- Protected Swing

Communication between detectors shall occur exclusively through immutable events.

---

# 13. Deterministic Guarantees

The Order Block Detector shall satisfy the following guarantees.

## Historical Replay

Historical replay shall always produce identical Order Block Events for identical market data.

---

## Live Streaming

Live execution shall produce identical Order Block Events as historical replay.

---

## Non-Repainting

Confirmed Order Block Events shall never be modified after confirmation.

Lifecycle transitions (e.g., Active → Mitigated → Invalidated) shall update only the Order Block Zone state without modifying the immutable event.

---

## Sequential Processing

Completed MarketBars shall be processed strictly in chronological order.

---

## Idempotent Processing

Processing identical historical data multiple times shall always produce:

- Identical Order Block Events
- Identical Order Block Measurements
- Identical Detector State

The detector shall never modify state owned by Swing, BOS, CHOCH, or Liquidity detectors.

---

# 14. Measurements

The Order Block Detector shall expose quantitative measurements describing each confirmed Order Block.

Measurements provide objective inputs for Feature Engineering, Research Analytics, and the Probability Engine.

The detector shall not generate trading signals or trading decisions.

---

## 14.1 Price Measurements

The detector shall compute:

- Order Block High
- Order Block Low
- Order Block Midpoint
- Order Block Height
- Zone Width
- Distance From Current Price
- Distance (Points)
- Distance (ATR)
- Distance Percentage

These measurements describe the spatial characteristics of the Order Block Zone.

---

## 14.2 Structural Measurements

The detector shall compute:

- Origin BOS Reference
- Origin CHOCH Reference
- Origin Liquidity Reference
- Structural Age
- Bars Since Creation
- Trend Alignment

These measurements describe the structural context of the Order Block.

---

## 14.3 Displacement Measurements

The detector shall compute:

- Displacement Distance
- Displacement ATR
- Displacement Strength
- Impulse Duration
- Body Expansion Ratio
- Consecutive Impulse Count

These measurements quantify the strength of the move that created the Order Block.

---

## 14.4 Quality Measurements

The detector may compute:

- Order Block Strength
- Order Block Confidence
- Institutional Quality
- Mitigation Probability
- Reaction Strength

These measurements describe the quality of the Order Block rather than simply its existence.

---

# 15. Feature Engineering Outputs

The Order Block Detector exposes quantitative features for downstream statistical analysis and machine learning.

Typical exported features include:

- order_block_height
- order_block_width
- order_block_distance
- order_block_distance_atr
- order_block_strength
- order_block_confidence
- displacement_strength
- displacement_distance
- structural_age
- trend_alignment
- reaction_strength

Feature Engineering is responsible for:

- Feature normalization
- Scaling
- Weighting
- Selection
- Transformation

The Order Block Detector shall not perform these operations.

---

# 16. Failure Cases

The Order Block Detector shall safely handle the following conditions.

## No Structural Confirmation

If neither a confirmed BOS nor CHOCH exists:

- No Order Block shall be created.
- Detector state shall remain valid.

---

## Insufficient Displacement

If displacement fails the configured requirements:

- No Order Block shall be confirmed.

---

## Liquidity Validation Failure

If Liquidity validation is enabled and fails:

- No Order Block shall be emitted.

---

## ATR Validation Failure

If ATR validation is enabled and fails:

- No Order Block shall be confirmed.

---

## Invalid Origin Candle

If the originating candle cannot be uniquely identified:

- The candidate Order Block shall be rejected.

---

## Duplicate Order Block

Duplicate Order Block Events shall be rejected.

---

## Historical Replay

Historical replay shall always reproduce identical Order Block Events.

---

## Detector Reset

Reset operations shall clear runtime state while preserving deterministic behavior for future processing.

---

# 17. Performance Requirements

The Order Block Detector shall satisfy the following requirements.

## Processing

- Incremental execution
- One completed MarketBar per update
- Streaming compatible

---

## Memory

The detector shall maintain only the runtime state required for deterministic Order Block detection.

Historical storage shall respect configured limits.

---

## Determinism

Identical historical market data shall always produce:

- Identical Order Block Events
- Identical Order Block Measurements
- Identical Detector State

---

## Scalability

The detector shall support:

- Long historical replay
- Continuous live execution
- High-frequency market updates

---

# 18. Integration

The Order Block Detector is the fifth stage of the Market Structure Engine.

Its outputs are consumed by downstream components.

```text
MarketBar
      │
      ▼
Swing Detector
      │
      ▼
BOS Detector
      │
      ▼
CHOCH Detector
      │
      ▼
Liquidity Detector
      │
      ▼
Order Block Detector
      │
      ├── Fair Value Gap Detector
      ├── Breaker Block Detector
      ├── Mitigation Block Detector
      ├── Feature Engineering
      ├── Research Analytics
      └── Probability Engine
```

The Order Block Detector is the authoritative owner of:

- Order Block Events
- Order Block Zones
- Order Block Measurements
- Order Block History

The Order Block Detector shall never modify:

- Swing Events
- BOS Events
- CHOCH Events
- Liquidity Events
- Current Trend
- Protected Swing

Communication between detectors shall occur exclusively through immutable events.

---

# 19. Unit Test Requirements

The implementation shall include automated tests covering the following categories.

## Functional Tests

- Bullish Order Block detection
- Bearish Order Block detection
- Structural validation
- Displacement validation
- Liquidity validation
- Mitigation tracking
- Duplicate prevention

---

## Validation Tests

- BOS validation
- CHOCH validation
- ATR validation
- Configuration validation
- Origin candle validation

---

## Streaming Tests

- Sequential processing
- Continuous live execution
- Historical replay
- Detector reset

---

## Market Condition Tests

- Trending markets
- Ranging markets
- High volatility
- Low volatility
- Strong displacement
- Weak displacement
- Multiple active Order Blocks

---

## Determinism Tests

The detector shall verify:

- Non-repainting
- Stable replay results
- Stable event ordering
- Stable detector state

---

# 20. Future Enhancements

Potential future enhancements include:

- Multi-Timeframe Order Block Detection
- Order Block Ranking
- Volume-assisted Order Block Validation
- Dynamic Zone Refinement
- Order Block Overlap Analysis
- Machine Learning Assisted Order Block Classification

Future enhancements shall remain backward compatible with this specification.

---

# 21. Acceptance Criteria

The Order Block Detector shall be considered production-ready only when:

- All unit tests pass.
- Integration tests pass.
- Historical replay is deterministic.
- Live execution is deterministic.
- Confirmed Order Block Events never repaint.
- Order Block lifecycle transitions are deterministic.
- All performance requirements are satisfied.
- Documentation is complete.
- Code review is approved.
- Integration with the Market Structure Engine is verified.

---

# End of Specification