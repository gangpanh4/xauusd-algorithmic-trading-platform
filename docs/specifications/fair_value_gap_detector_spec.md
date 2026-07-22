# Fair Value Gap Detector Specification

**Document ID:** SMC-SPEC-007

**Version:** 1.0

**Status:** Draft

**Project:** Trading Intelligence Platform

**Module:** Market Structure Engine

---

# 1. Purpose

The Fair Value Gap (FVG) Detector is responsible for identifying institutional price imbalances created by aggressive directional displacement.

A Fair Value Gap represents an inefficient price delivery where trading activity leaves a gap between consecutive candles.

The detector consumes completed MarketBars together with confirmed Swing Events, BOS Events, CHOCH Events, Liquidity Events, and Order Block Events to identify high-quality Fair Value Gaps.

The Fair Value Gap Detector produces immutable Fair Value Gap Events and quantitative measurements for downstream components.

Confirmed Fair Value Gap Events provide structural context for:

- Breaker Block Engine
- Mitigation Block Engine
- Feature Engineering
- Research Analytics
- Probability Engine

The detector operates deterministically and incrementally, ensuring identical outputs for identical historical market data.

The detector does not generate trading signals or trading decisions.

---

# 2. Scope

The Fair Value Gap Detector is responsible only for identifying institutional Fair Value Gaps.

The detector SHALL:

- Detect Bullish Fair Value Gaps
- Detect Bearish Fair Value Gaps
- Validate displacement quality
- Validate structural context
- Detect partial fills
- Detect full fills
- Produce immutable Fair Value Gap Events
- Produce quantitative Fair Value Gap measurements
- Support historical replay
- Support live streaming execution

The detector SHALL NOT:

- Detect Swing Highs
- Detect Swing Lows
- Detect BOS
- Detect CHOCH
- Detect Liquidity
- Detect Order Blocks
- Generate trading signals
- Calculate probabilities
- Manage trading risk

These responsibilities belong to other components.

---

# 3. Owner

## Owner Module

```
FairValueGapDetector
```

The Fair Value Gap Detector is the sole owner of:

- Fair Value Gap Events
- Fair Value Gap Zones
- Fair Value Gap History
- Fair Value Gap Measurements
- Fair Value Gap Detector State

The detector does not own:

- Swing Events
- BOS Events
- CHOCH Events
- Liquidity Events
- Order Block Events
- Current Trend
- Protected Swing

These remain under their respective detectors.

---

# 4. Responsibilities

The Fair Value Gap Detector shall:

- Consume Swing Events
- Consume BOS Events
- Consume CHOCH Events
- Consume Liquidity Events
- Consume Order Block Events
- Identify Bullish Fair Value Gaps
- Identify Bearish Fair Value Gaps
- Track Fair Value Gap lifecycle
- Detect partial fills
- Detect full fills
- Prevent duplicate Fair Value Gap Events
- Produce immutable Fair Value Gap Events
- Maintain detector runtime state
- Compute Fair Value Gap measurements
- Expose measurements for Feature Engineering
- Operate deterministically
- Operate incrementally
- Support historical replay
- Support continuous streaming execution

---

# 5. Dependencies

## Consumes

The Fair Value Gap Detector consumes:

- Completed MarketBar
- Swing Events
- BOS Events
- CHOCH Events
- Liquidity Events
- Order Block Events
- FairValueGapDetectorConfig
- Internal Fair Value Gap State

The detector does not consume Breaker Blocks or Mitigation Blocks.

---

## Produces

The Fair Value Gap Detector produces:

- FairValueGapEvent
- Updated Fair Value Gap State
- Fair Value Gap Measurements
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
- Order Block Events

Configuration parameters include:

- Minimum Gap Size
- Minimum Gap ATR
- Require Structural Confirmation
- Require Order Block Confirmation
- Fill Validation
- ATR Validation
- ATR Period
- ATR Multiplier

All configuration shall be immutable after detector initialization.

---

# 7. Outputs

The Fair Value Gap Detector produces immutable Fair Value Gap Events.

Each Fair Value Gap Event shall include:

- Event ID
- Timestamp
- Gap Type
- Direction
- Gap Zone
- Origin Candle
- Trigger Event
- Fill Status
- Confirmation Bar

The detector also produces:

- Updated Fair Value Gap State
- Fair Value Gap Measurements
- Feature Engineering Inputs

When no Fair Value Gap is confirmed, the detector shall produce no event.

---

# 8. Configuration

The Fair Value Gap Detector shall support configuration through the FairValueGapDetectorConfig object.

The following parameters shall be configurable.

| Parameter | Description |
|------------|-------------|
| Minimum Gap Size | Minimum gap height required |
| Minimum Gap ATR | Minimum ATR-normalized gap size |
| Require Structural Confirmation | Require BOS or CHOCH confirmation |
| Require Order Block Confirmation | Require nearby Order Block |
| Fill Validation | Enable fill tracking |
| ATR Validation | Enable ATR filtering |
| ATR Period | ATR calculation period |
| ATR Multiplier | Minimum volatility requirement |

Configuration values adjust detector sensitivity but shall not alter ownership or detector responsibilities.

---

---

# 9. Detection Rules

The Fair Value Gap Detector shall identify institutional Fair Value Gaps using completed MarketBars together with confirmed Swing Events, BOS Events, CHOCH Events, Liquidity Events, and Order Block Events.

A Fair Value Gap represents an inefficient price delivery created by aggressive displacement.

The detector shall evaluate only completed MarketBars.

The detector shall never predict future price movement.

---

## 9.1 Bullish Fair Value Gap

A Bullish Fair Value Gap is confirmed when all of the following conditions are satisfied:

- A valid bullish displacement move exists.
- A three-candle bullish imbalance is identified.
- The low of the third candle is above the high of the first candle.
- Structural confirmation succeeds (if enabled).
- Order Block validation succeeds (if enabled).
- ATR validation succeeds (if enabled).

Once confirmed:

- A Bullish Fair Value Gap Event shall be emitted.
- A Bullish Fair Value Gap Zone shall be created.
- The zone shall become Active.

---

## 9.2 Bearish Fair Value Gap

A Bearish Fair Value Gap is confirmed when all of the following conditions are satisfied:

- A valid bearish displacement move exists.
- A three-candle bearish imbalance is identified.
- The high of the third candle is below the low of the first candle.
- Structural confirmation succeeds (if enabled).
- Order Block validation succeeds (if enabled).
- ATR validation succeeds (if enabled).

Once confirmed:

- A Bearish Fair Value Gap Event shall be emitted.
- A Bearish Fair Value Gap Zone shall be created.
- The zone shall become Active.

---

## 9.3 Structural Validation

A Fair Value Gap shall never be confirmed without valid directional context.

Valid structural confirmation includes:

- BOS
- CHOCH

Structure provides directional alignment for Fair Value Gap creation.

---

## 9.4 Displacement Validation

Every Fair Value Gap shall be validated by displacement.

Displacement validation may include:

- Large candle body
- Strong momentum
- ATR expansion
- Consecutive impulsive candles
- Configured displacement threshold

Weak or insignificant movements shall not produce Fair Value Gaps.

---

## 9.5 Order Block Validation

If enabled, the detector shall require the Fair Value Gap to originate from or align with a confirmed Order Block.

Order Block validation increases Fair Value Gap confidence.

---

## 9.6 Partial Fill Detection

A Fair Value Gap is considered partially filled when price enters the gap zone but does not completely traverse it.

When confirmed:

- The Fair Value Gap Zone state shall become Partially Filled.
- The original Fair Value Gap Event shall remain immutable.

---

## 9.7 Full Fill Detection

A Fair Value Gap is considered fully filled when price completely traverses the gap zone.

When confirmed:

- The Fair Value Gap Zone state shall become Fully Filled.
- A Fair Value Gap Filled Event may be emitted.

The original Fair Value Gap Event remains immutable.

---

## 9.8 Invalid Fair Value Gap

A Fair Value Gap becomes invalid when:

- Configured invalidation rules succeed.
- Market conditions permanently invalidate the imbalance.

The detector shall:

- Preserve the immutable Fair Value Gap Event.
- Update the Fair Value Gap Zone state.
- Emit a Fair Value Gap Invalidated Event.

---

## 9.9 Duplicate Prevention

Before confirming a Fair Value Gap Event, the detector shall verify that an equivalent Fair Value Gap has not already been emitted.

Duplicate Fair Value Gap Events shall not be produced.

---

# 10. Confirmation Rules

A Fair Value Gap shall only be confirmed after all applicable validation rules succeed.

Validation may include:

- Three-candle validation
- Structural validation
- Order Block validation
- Displacement validation
- ATR validation
- Duplicate validation

Once confirmed:

- Event ID shall never change.
- Direction shall never change.
- Gap Zone shall never change.
- Origin Candle shall never change.
- Confirmation Timestamp shall never change.

Confirmed Fair Value Gap Events are immutable.

---

# 11. State Management

The Fair Value Gap Detector maintains only the runtime state required for deterministic Fair Value Gap detection.

The detector state includes:

- Active Fair Value Gap Zones
- Fair Value Gap History
- Last Confirmed Fair Value Gap
- Internal Processing State

The detector shall update its internal state incrementally after every completed MarketBar.

Reset operations shall restore the detector to its initial state.

---

## Fair Value Gap Lifecycle

Each Fair Value Gap Zone progresses through the following lifecycle.

```text
Detected
      │
      ▼
Confirmed
      │
      ▼
Active
      │
      ├── Partially Filled
      │
      ├── Fully Filled
      │
      ├── Invalidated
      │
      └── Expired
```

The lifecycle state shall be deterministic.

The original Fair Value Gap Event remains immutable throughout the lifecycle.

---

# 12. State Ownership

The Fair Value Gap Detector is the authoritative owner of:

- Fair Value Gap Events
- Fair Value Gap Zones
- Fair Value Gap Measurements
- Fair Value Gap History
- Internal Detector State

The Fair Value Gap Detector shall never modify:

- Swing Events
- BOS Events
- CHOCH Events
- Liquidity Events
- Order Block Events
- Current Trend
- Protected Swing

Communication between detectors shall occur exclusively through immutable events.

---

# 13. Deterministic Guarantees

The Fair Value Gap Detector shall satisfy the following guarantees.

## Historical Replay

Historical replay shall always produce identical Fair Value Gap Events for identical market data.

---

## Live Streaming

Live execution shall produce identical Fair Value Gap Events as historical replay.

---

## Non-Repainting

Confirmed Fair Value Gap Events shall never be modified after confirmation.

Lifecycle transitions (e.g., Active → Partially Filled → Fully Filled → Invalidated) shall update only the Fair Value Gap Zone state without modifying the immutable event.

---

## Sequential Processing

Completed MarketBars shall be processed strictly in chronological order.

---

## Idempotent Processing

Processing identical historical data multiple times shall always produce:

- Identical Fair Value Gap Events
- Identical Fair Value Gap Measurements
- Identical Detector State

The detector shall never modify state owned by Swing, BOS, CHOCH, Liquidity, or Order Block detectors.

---

---

# 14. Measurements

The Fair Value Gap Detector shall expose quantitative measurements describing each confirmed Fair Value Gap.

Measurements provide objective inputs for Feature Engineering, Research Analytics, and the Probability Engine.

The detector shall not generate trading signals or trading decisions.

---

## 14.1 Price Measurements

The detector shall compute:

- Gap High
- Gap Low
- Gap Midpoint
- Gap Height
- Gap Width
- Distance From Current Price
- Distance (Points)
- Distance (ATR)
- Distance Percentage

These measurements describe the geometric properties of the Fair Value Gap Zone.

---

## 14.2 Structural Measurements

The detector shall compute:

- Origin BOS Reference
- Origin CHOCH Reference
- Origin Liquidity Reference
- Origin Order Block Reference
- Structural Age
- Bars Since Creation
- Trend Alignment

These measurements describe the structural context of the Fair Value Gap.

---

## 14.3 Fill Measurements

The detector shall compute:

- Fill Percentage
- Fill Distance
- Fill Depth
- Fill Duration
- Time Until First Touch
- Time Until Full Fill

These measurements quantify how price interacts with the Fair Value Gap.

---

## 14.4 Quality Measurements

The detector may compute:

- Fair Value Gap Strength
- Fair Value Gap Confidence
- Displacement Quality
- Fill Probability
- Reaction Strength

These measurements describe the quality of the imbalance rather than simply its existence.

---

# 15. Feature Engineering Outputs

The Fair Value Gap Detector exposes quantitative features for downstream statistical analysis and machine learning.

Typical exported features include:

- fair_value_gap_height
- fair_value_gap_width
- fair_value_gap_distance
- fair_value_gap_distance_atr
- fair_value_gap_strength
- fair_value_gap_confidence
- displacement_strength
- fill_percentage
- fill_duration
- structural_age
- trend_alignment
- reaction_strength

Feature Engineering is responsible for:

- Feature normalization
- Scaling
- Weighting
- Selection
- Transformation

The Fair Value Gap Detector shall not perform these operations.

---

# 16. Failure Cases

The Fair Value Gap Detector shall safely handle the following conditions.

## No Structural Confirmation

If structural confirmation is required but unavailable:

- No Fair Value Gap shall be created.
- Detector state shall remain valid.

---

## Invalid Three-Candle Pattern

If the required three-candle imbalance does not exist:

- The candidate Fair Value Gap shall be rejected.

---

## Insufficient Gap Size

If the gap size is below the configured minimum:

- The candidate Fair Value Gap shall not be confirmed.

---

## Order Block Validation Failure

If Order Block validation is enabled and fails:

- No Fair Value Gap shall be emitted.

---

## ATR Validation Failure

If ATR validation is enabled and fails:

- No Fair Value Gap shall be confirmed.

---

## Duplicate Fair Value Gap

Duplicate Fair Value Gap Events shall be rejected.

---

## Historical Replay

Historical replay shall always reproduce identical Fair Value Gap Events.

---

## Detector Reset

Reset operations shall clear runtime state while preserving deterministic behavior for future processing.

---

# 17. Performance Requirements

The Fair Value Gap Detector shall satisfy the following requirements.

## Processing

- Incremental execution
- One completed MarketBar per update
- Streaming compatible

---

## Memory

The detector shall maintain only the runtime state required for deterministic Fair Value Gap detection.

Historical storage shall respect configured limits.

---

## Determinism

Identical historical market data shall always produce:

- Identical Fair Value Gap Events
- Identical Fair Value Gap Measurements
- Identical Detector State

---

## Scalability

The detector shall support:

- Long historical replay
- Continuous live execution
- High-frequency market updates

---

# 18. Integration

The Fair Value Gap Detector is the sixth stage of the Market Structure Engine.

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
      ▼
Fair Value Gap Detector
      │
      ├── Breaker Block Detector
      ├── Mitigation Block Detector
      ├── Feature Engineering
      ├── Research Analytics
      └── Probability Engine
```

The Fair Value Gap Detector is the authoritative owner of:

- Fair Value Gap Events
- Fair Value Gap Zones
- Fair Value Gap Measurements
- Fair Value Gap History

The Fair Value Gap Detector shall never modify:

- Swing Events
- BOS Events
- CHOCH Events
- Liquidity Events
- Order Block Events
- Current Trend
- Protected Swing

Communication between detectors shall occur exclusively through immutable events.

---

# 19. Unit Test Requirements

The implementation shall include automated tests covering the following categories.

## Functional Tests

- Bullish Fair Value Gap detection
- Bearish Fair Value Gap detection
- Three-candle validation
- Displacement validation
- Partial fill detection
- Full fill detection
- Duplicate prevention

---

## Validation Tests

- Structural validation
- Order Block validation
- ATR validation
- Gap size validation
- Configuration validation

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
- Multiple active Fair Value Gaps

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

- Multi-Timeframe Fair Value Gap Detection
- Fair Value Gap Ranking
- Dynamic Gap Refinement
- Volume-assisted Gap Validation
- Gap Overlap Analysis
- Machine Learning Assisted Fair Value Gap Classification

Future enhancements shall remain backward compatible with this specification.

---

# 21. Acceptance Criteria

The Fair Value Gap Detector shall be considered production-ready only when:

- All unit tests pass.
- Integration tests pass.
- Historical replay is deterministic.
- Live execution is deterministic.
- Confirmed Fair Value Gap Events never repaint.
- Fair Value Gap lifecycle transitions are deterministic.
- All performance requirements are satisfied.
- Documentation is complete.
- Code review is approved.
- Integration with the Market Structure Engine is verified.

---

# End of Specification