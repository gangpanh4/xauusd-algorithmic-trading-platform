# Breaker Block Detector Specification

**Document ID:** SMC-SPEC-008

**Version:** 1.0

**Status:** Draft

**Project:** Trading Intelligence Platform

**Module:** Market Structure Engine

---

# 1. Purpose

The Breaker Block Detector is responsible for identifying institutional Breaker Blocks formed from previously confirmed Order Blocks that have been invalidated by subsequent price action.

A Breaker Block represents a former institutional Order Block whose role has changed after structural invalidation and may become a future support or resistance zone.

The detector consumes completed MarketBars together with confirmed Swing Events, BOS Events, CHOCH Events, Liquidity Events, Order Block Events, and Fair Value Gap Events to identify valid Breaker Blocks.

The Breaker Block Detector produces immutable Breaker Block Events and quantitative measurements for downstream components.

Confirmed Breaker Block Events provide structural context for:

- Mitigation Block Engine
- Feature Engineering
- Research Analytics
- Probability Engine

The detector operates deterministically and incrementally, ensuring identical outputs for identical historical market data.

The detector does not generate trading signals or trading decisions.

---

# 2. Scope

The Breaker Block Detector is responsible only for identifying confirmed institutional Breaker Blocks.

The detector SHALL:

- Detect Bullish Breaker Blocks
- Detect Bearish Breaker Blocks
- Validate Order Block invalidation
- Validate structural confirmation
- Track Breaker lifecycle
- Detect Breaker retests
- Produce immutable Breaker Block Events
- Produce quantitative Breaker measurements
- Support historical replay
- Support live streaming execution

The detector SHALL NOT:

- Detect Swing Highs
- Detect Swing Lows
- Detect BOS
- Detect CHOCH
- Detect Liquidity
- Detect Order Blocks
- Detect Fair Value Gaps
- Generate trading signals
- Calculate probabilities
- Manage trading risk

These responsibilities belong to other components.

---

# 3. Owner

## Owner Module

```
BreakerBlockDetector
```

The Breaker Block Detector is the sole owner of:

- Breaker Block Events
- Breaker Block Zones
- Breaker Block History
- Breaker Block Measurements
- Breaker Block Detector State

The detector does not own:

- Swing Events
- BOS Events
- CHOCH Events
- Liquidity Events
- Order Block Events
- Fair Value Gap Events
- Current Trend
- Protected Swing

These remain under their respective detectors.

---

# 4. Responsibilities

The Breaker Block Detector shall:

- Consume Swing Events
- Consume BOS Events
- Consume CHOCH Events
- Consume Liquidity Events
- Consume Order Block Events
- Consume Fair Value Gap Events
- Identify Bullish Breaker Blocks
- Identify Bearish Breaker Blocks
- Validate structural invalidation
- Track Breaker lifecycle
- Detect Breaker retests
- Prevent duplicate Breaker Events
- Produce immutable Breaker Block Events
- Maintain detector runtime state
- Compute Breaker measurements
- Expose measurements for Feature Engineering
- Operate deterministically
- Operate incrementally
- Support historical replay
- Support continuous streaming execution

---

# 5. Dependencies

## Consumes

The Breaker Block Detector consumes:

- Completed MarketBar
- Swing Events
- BOS Events
- CHOCH Events
- Liquidity Events
- Order Block Events
- Fair Value Gap Events
- BreakerBlockDetectorConfig
- Internal Breaker State

The detector does not consume Mitigation Blocks.

---

## Produces

The Breaker Block Detector produces:

- BreakerBlockEvent
- Updated Breaker State
- Breaker Measurements
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
- Fair Value Gap Events

Configuration parameters include:

- Require Order Block Invalidation
- Require Structural Confirmation
- Require Retest
- ATR Validation
- ATR Period
- ATR Multiplier
- Maximum Breaker Age

All configuration shall be immutable after detector initialization.

---

# 7. Outputs

The Breaker Block Detector produces immutable Breaker Block Events.

Each Breaker Block Event shall include:

- Event ID
- Timestamp
- Breaker Type
- Direction
- Breaker Zone
- Source Order Block
- Trigger Event
- Retest Status
- Confirmation Bar

The detector also produces:

- Updated Breaker State
- Breaker Measurements
- Feature Engineering Inputs

When no Breaker Block is confirmed, the detector shall produce no event.

---

# 8. Configuration

The Breaker Block Detector shall support configuration through the BreakerBlockDetectorConfig object.

The following parameters shall be configurable.

| Parameter | Description |
|------------|-------------|
| Require Order Block Invalidation | Require confirmed invalidation before Breaker creation |
| Require Structural Confirmation | Require BOS or CHOCH alignment |
| Require Retest | Require confirmation retest |
| ATR Validation | Enable ATR filtering |
| ATR Period | ATR calculation period |
| ATR Multiplier | Minimum volatility requirement |
| Maximum Breaker Age | Maximum bars before expiration |

Configuration values adjust detector sensitivity but shall not alter ownership or detector responsibilities.

---

---

# 9. Detection Rules

The Breaker Block Detector shall identify institutional Breaker Blocks using completed MarketBars together with confirmed Swing Events, BOS Events, CHOCH Events, Liquidity Events, Order Block Events, and Fair Value Gap Events.

A Breaker Block represents a previously confirmed Order Block whose structural role has changed after invalidation.

The detector shall evaluate only completed MarketBars.

The detector shall never predict future price movement.

---

## 9.1 Bullish Breaker Block

A Bullish Breaker Block is confirmed when all of the following conditions are satisfied:

- A valid Bearish Order Block exists.
- The Bearish Order Block has been structurally invalidated.
- A bullish BOS or bullish CHOCH confirms the directional change.
- The invalidated Order Block is eligible for Breaker conversion.
- ATR validation succeeds (if enabled).
- All confirmation rules succeed.

Once confirmed:

- A Bullish Breaker Block Event shall be emitted.
- A Bullish Breaker Block Zone shall be created.
- The zone shall become Active.

---

## 9.2 Bearish Breaker Block

A Bearish Breaker Block is confirmed when all of the following conditions are satisfied:

- A valid Bullish Order Block exists.
- The Bullish Order Block has been structurally invalidated.
- A bearish BOS or bearish CHOCH confirms the directional change.
- The invalidated Order Block is eligible for Breaker conversion.
- ATR validation succeeds (if enabled).
- All confirmation rules succeed.

Once confirmed:

- A Bearish Breaker Block Event shall be emitted.
- A Bearish Breaker Block Zone shall be created.
- The zone shall become Active.

---

## 9.3 Order Block Invalidation

A Breaker Block shall never exist without a previously confirmed Order Block.

The detector shall validate:

- Source Order Block exists.
- Source Order Block has been invalidated.
- Invalidation satisfies configured structural requirements.

The originating Order Block shall remain immutable.

---

## 9.4 Structural Validation

Every Breaker Block shall be validated by market structure.

Valid structural confirmation includes:

- BOS
- CHOCH

Structure confirms the directional transition following Order Block invalidation.

---

## 9.5 Retest Validation

If enabled, the detector shall require price to retest the Breaker Block Zone before confirmation.

Retest validation may include:

- Initial touch
- Rejection
- Minimum penetration
- Configured confirmation rules

Retest confirmation increases Breaker confidence.

---

## 9.6 Fair Value Gap Alignment

If enabled, the detector shall validate alignment with a nearby Fair Value Gap.

Alignment may include:

- Shared directional bias
- Overlapping price zones
- Proximity within configured tolerance

Fair Value Gap alignment increases Breaker confidence.

---

## 9.7 Breaker Invalidation

A Breaker Block becomes invalid when:

- Price closes beyond the configured invalidation boundary.
- Structural invalidation rules succeed.

The detector shall:

- Preserve the immutable Breaker Block Event.
- Update the Breaker Block Zone state.
- Emit a Breaker Block Invalidated Event.

---

## 9.8 Duplicate Prevention

Before confirming a Breaker Block Event, the detector shall verify that an equivalent Breaker Block has not already been emitted.

Duplicate Breaker Block Events shall not be produced.

---

# 10. Confirmation Rules

A Breaker Block shall only be confirmed after all applicable validation rules succeed.

Validation may include:

- Order Block invalidation
- Structural validation
- Retest validation
- Fair Value Gap validation
- ATR validation
- Duplicate validation

Once confirmed:

- Event ID shall never change.
- Direction shall never change.
- Breaker Zone shall never change.
- Source Order Block shall never change.
- Confirmation Timestamp shall never change.

Confirmed Breaker Block Events are immutable.

---

# 11. State Management

The Breaker Block Detector maintains only the runtime state required for deterministic Breaker Block detection.

The detector state includes:

- Active Breaker Block Zones
- Breaker Block History
- Last Confirmed Breaker Block
- Internal Processing State

The detector shall update its internal state incrementally after every completed MarketBar.

Reset operations shall restore the detector to its initial state.

---

## Breaker Block Lifecycle

Each Breaker Block Zone progresses through the following lifecycle.

```text
Detected
      │
      ▼
Confirmed
      │
      ▼
Active
      │
      ├── Retested
      │
      ├── Respected
      │
      ├── Invalidated
      │
      └── Expired
```

The lifecycle state shall be deterministic.

The original Breaker Block Event remains immutable throughout the lifecycle.

---

# 12. State Ownership

The Breaker Block Detector is the authoritative owner of:

- Breaker Block Events
- Breaker Block Zones
- Breaker Block Measurements
- Breaker Block History
- Internal Detector State

The Breaker Block Detector shall never modify:

- Swing Events
- BOS Events
- CHOCH Events
- Liquidity Events
- Order Block Events
- Fair Value Gap Events
- Current Trend
- Protected Swing

Communication between detectors shall occur exclusively through immutable events.

---

# 13. Deterministic Guarantees

The Breaker Block Detector shall satisfy the following guarantees.

## Historical Replay

Historical replay shall always produce identical Breaker Block Events for identical market data.

---

## Live Streaming

Live execution shall produce identical Breaker Block Events as historical replay.

---

## Non-Repainting

Confirmed Breaker Block Events shall never be modified after confirmation.

Lifecycle transitions (e.g., Active → Retested → Respected → Invalidated) shall update only the Breaker Block Zone state without modifying the immutable event.

---

## Sequential Processing

Completed MarketBars shall be processed strictly in chronological order.

---

## Idempotent Processing

Processing identical historical data multiple times shall always produce:

- Identical Breaker Block Events
- Identical Breaker Block Measurements
- Identical Detector State

The detector shall never modify state owned by Swing, BOS, CHOCH, Liquidity, Order Block, or Fair Value Gap detectors.

---

---

# 14. Measurements

The Breaker Block Detector shall expose quantitative measurements describing each confirmed Breaker Block.

Measurements provide objective inputs for Feature Engineering, Research Analytics, and the Probability Engine.

The detector shall not generate trading signals or trading decisions.

---

## 14.1 Price Measurements

The detector shall compute:

- Breaker Zone High
- Breaker Zone Low
- Breaker Zone Midpoint
- Breaker Zone Height
- Breaker Zone Width
- Distance From Current Price
- Distance (Points)
- Distance (ATR)
- Distance Percentage

These measurements describe the geometric properties of the Breaker Block Zone.

---

## 14.2 Structural Measurements

The detector shall compute:

- Source Order Block Reference
- Origin BOS Reference
- Origin CHOCH Reference
- Origin Liquidity Reference
- Origin Fair Value Gap Reference
- Structural Age
- Bars Since Creation
- Trend Alignment

These measurements describe the structural context of the Breaker Block.

---

## 14.3 Retest Measurements

The detector shall compute:

- Number of Retests
- First Retest Time
- Last Retest Time
- Retest Penetration
- Rejection Distance
- Rejection Strength

These measurements quantify market interaction with the Breaker Block.

---

## 14.4 Quality Measurements

The detector may compute:

- Breaker Strength
- Breaker Confidence
- Structural Quality
- Retest Quality
- Reaction Strength

These measurements describe the quality of the Breaker Block rather than simply its existence.

---

# 15. Feature Engineering Outputs

The Breaker Block Detector exposes quantitative features for downstream statistical analysis and machine learning.

Typical exported features include:

- breaker_height
- breaker_width
- breaker_distance
- breaker_distance_atr
- breaker_strength
- breaker_confidence
- retest_count
- retest_penetration
- rejection_strength
- structural_age
- trend_alignment
- reaction_strength

Feature Engineering is responsible for:

- Feature normalization
- Scaling
- Weighting
- Selection
- Transformation

The Breaker Block Detector shall not perform these operations.

---

# 16. Failure Cases

The Breaker Block Detector shall safely handle the following conditions.

## Missing Source Order Block

If no confirmed Order Block exists:

- No Breaker Block shall be created.
- Detector state shall remain valid.

---

## Order Block Not Invalidated

If the source Order Block has not been structurally invalidated:

- The candidate Breaker Block shall be rejected.

---

## Structural Validation Failure

If BOS or CHOCH validation fails:

- No Breaker Block shall be confirmed.

---

## Fair Value Gap Validation Failure

If Fair Value Gap validation is enabled and fails:

- No Breaker Block shall be emitted.

---

## ATR Validation Failure

If ATR validation is enabled and fails:

- No Breaker Block shall be confirmed.

---

## Duplicate Breaker Block

Duplicate Breaker Block Events shall be rejected.

---

## Historical Replay

Historical replay shall always reproduce identical Breaker Block Events.

---

## Detector Reset

Reset operations shall clear runtime state while preserving deterministic behavior for future processing.

---

# 17. Performance Requirements

The Breaker Block Detector shall satisfy the following requirements.

## Processing

- Incremental execution
- One completed MarketBar per update
- Streaming compatible

---

## Memory

The detector shall maintain only the runtime state required for deterministic Breaker Block detection.

Historical storage shall respect configured limits.

---

## Determinism

Identical historical market data shall always produce:

- Identical Breaker Block Events
- Identical Breaker Block Measurements
- Identical Detector State

---

## Scalability

The detector shall support:

- Long historical replay
- Continuous live execution
- High-frequency market updates

---

# 18. Integration

The Breaker Block Detector is the seventh stage of the Market Structure Engine.

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
      ▼
Breaker Block Detector
      │
      ├── Mitigation Block Detector
      ├── Feature Engineering
      ├── Research Analytics
      └── Probability Engine
```

The Breaker Block Detector is the authoritative owner of:

- Breaker Block Events
- Breaker Block Zones
- Breaker Block Measurements
- Breaker Block History

The Breaker Block Detector shall never modify:

- Swing Events
- BOS Events
- CHOCH Events
- Liquidity Events
- Order Block Events
- Fair Value Gap Events
- Current Trend
- Protected Swing

Communication between detectors shall occur exclusively through immutable events.

---

# 19. Unit Test Requirements

The implementation shall include automated tests covering the following categories.

## Functional Tests

- Bullish Breaker Block detection
- Bearish Breaker Block detection
- Order Block invalidation
- Structural validation
- Retest detection
- Fair Value Gap alignment
- Duplicate prevention

---

## Validation Tests

- Source Order Block validation
- BOS validation
- CHOCH validation
- ATR validation
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
- Multiple active Breaker Blocks
- Repeated retests

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

- Multi-Timeframe Breaker Detection
- Breaker Ranking
- Dynamic Zone Refinement
- Volume-assisted Breaker Validation
- Breaker Cluster Analysis
- Machine Learning Assisted Breaker Classification

Future enhancements shall remain backward compatible with this specification.

---

# 21. Acceptance Criteria

The Breaker Block Detector shall be considered production-ready only when:

- All unit tests pass.
- Integration tests pass.
- Historical replay is deterministic.
- Live execution is deterministic.
- Confirmed Breaker Block Events never repaint.
- Breaker Block lifecycle transitions are deterministic.
- All performance requirements are satisfied.
- Documentation is complete.
- Code review is approved.
- Integration with the Market Structure Engine is verified.

---

# End of Specification