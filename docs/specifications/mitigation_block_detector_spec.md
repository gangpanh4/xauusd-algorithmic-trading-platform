# Mitigation Block Detector Specification

**Document ID:** SMC-SPEC-009

**Version:** 1.0

**Status:** Draft

**Project:** Trading Intelligence Platform

**Module:** Market Structure Engine

---

# 1. Purpose

The Mitigation Block Detector is responsible for identifying institutional mitigation events where price revisits previously confirmed institutional price zones.

A Mitigation Block represents the interaction between current price and an existing institutional zone, such as an Order Block, Breaker Block, or Fair Value Gap.

The detector consumes completed MarketBars together with confirmed Swing Events, BOS Events, CHOCH Events, Liquidity Events, Order Block Events, Fair Value Gap Events, and Breaker Block Events.

The Mitigation Block Detector produces immutable Mitigation Events and quantitative measurements describing mitigation quality.

Confirmed Mitigation Events provide structural context for:

- Feature Engineering
- Research Analytics
- Probability Engine

The detector operates deterministically and incrementally, ensuring identical outputs for identical historical market data.

The detector does not generate trading signals or trading decisions.

---

# 2. Scope

The Mitigation Block Detector is responsible only for identifying confirmed mitigation interactions.

The detector SHALL:

- Detect Order Block mitigation
- Detect Breaker Block mitigation
- Detect Fair Value Gap mitigation
- Detect partial mitigation
- Detect full mitigation
- Measure mitigation quality
- Produce immutable Mitigation Events
- Produce quantitative mitigation measurements
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
- Detect Breaker Blocks
- Generate trading signals
- Calculate probabilities
- Manage trading risk

These responsibilities belong to other components.

---

# 3. Owner

## Owner Module

```
MitigationBlockDetector
```

The Mitigation Block Detector is the sole owner of:

- Mitigation Events
- Mitigation History
- Mitigation Measurements
- Mitigation Detector State

The detector does not own:

- Swing Events
- BOS Events
- CHOCH Events
- Liquidity Events
- Order Block Zones
- Fair Value Gap Zones
- Breaker Block Zones
- Current Trend
- Protected Swing

These remain under their respective detectors.

---

# 4. Responsibilities

The Mitigation Block Detector shall:

- Consume Swing Events
- Consume BOS Events
- Consume CHOCH Events
- Consume Liquidity Events
- Consume Order Block Zones
- Consume Fair Value Gap Zones
- Consume Breaker Block Zones
- Detect mitigation interactions
- Measure mitigation quality
- Prevent duplicate Mitigation Events
- Produce immutable Mitigation Events
- Maintain detector runtime state
- Compute mitigation measurements
- Expose measurements for Feature Engineering
- Operate deterministically
- Operate incrementally
- Support historical replay
- Support continuous streaming execution

---

# 5. Dependencies

## Consumes

The Mitigation Block Detector consumes:

- Completed MarketBar
- Swing Events
- BOS Events
- CHOCH Events
- Liquidity Events
- Order Block Zones
- Fair Value Gap Zones
- Breaker Block Zones
- MitigationBlockDetectorConfig
- Internal Mitigation State

---

## Produces

The Mitigation Block Detector produces:

- MitigationEvent
- Updated Mitigation State
- Mitigation Measurements
- Feature Engineering Inputs

These outputs are consumed by Feature Engineering, Research Analytics, and the Probability Engine.

---

# 6. Inputs

The detector processes one completed MarketBar at a time.

Required inputs include:

- Completed MarketBar
- Swing Events
- BOS Events
- CHOCH Events
- Liquidity Events
- Order Block Zones
- Fair Value Gap Zones
- Breaker Block Zones

Configuration parameters include:

- Minimum Penetration
- Full Mitigation Threshold
- Partial Mitigation Threshold
- ATR Validation
- ATR Period
- ATR Multiplier
- Maximum Zone Age

All configuration shall be immutable after detector initialization.

---

# 7. Outputs

The Mitigation Block Detector produces immutable Mitigation Events.

Each Mitigation Event shall include:

- Event ID
- Timestamp
- Mitigation Type
- Source Zone
- Source Zone ID
- Penetration Depth
- Mitigation Status
- Confirmation Bar

The detector also produces:

- Updated Mitigation State
- Mitigation Measurements
- Feature Engineering Inputs

When no mitigation interaction is detected, the detector shall produce no event.

---

# 8. Configuration

The Mitigation Block Detector shall support configuration through the MitigationBlockDetectorConfig object.

The following parameters shall be configurable.

| Parameter | Description |
|------------|-------------|
| Minimum Penetration | Minimum penetration into a zone |
| Partial Mitigation Threshold | Minimum percentage for partial mitigation |
| Full Mitigation Threshold | Percentage required for full mitigation |
| ATR Validation | Enable ATR filtering |
| ATR Period | ATR calculation period |
| ATR Multiplier | Minimum volatility requirement |
| Maximum Zone Age | Maximum age of zones eligible for mitigation |

Configuration values adjust detector sensitivity but shall not alter ownership or detector responsibilities.

---

---

# 9. Detection Rules

The Mitigation Block Detector shall identify institutional mitigation events using completed MarketBars together with confirmed Swing Events, BOS Events, CHOCH Events, Liquidity Events, Order Block Zones, Fair Value Gap Zones, and Breaker Block Zones.

A Mitigation Event represents a confirmed interaction between price and an existing institutional price zone.

The detector shall evaluate only completed MarketBars.

The detector shall never predict future price movement.

---

## 9.1 Order Block Mitigation

An Order Block Mitigation is confirmed when all of the following conditions are satisfied:

- A valid Order Block Zone exists.
- Price revisits the Order Block Zone.
- Minimum penetration requirements are satisfied.
- ATR validation succeeds (if enabled).
- All confirmation rules succeed.

Once confirmed:

- A Mitigation Event shall be emitted.
- The referenced Order Block Zone shall update its lifecycle state.
- The original Order Block Event shall remain immutable.

---

## 9.2 Breaker Block Mitigation

A Breaker Block Mitigation is confirmed when all of the following conditions are satisfied:

- A valid Breaker Block Zone exists.
- Price revisits the Breaker Block Zone.
- Minimum penetration requirements are satisfied.
- ATR validation succeeds (if enabled).
- All confirmation rules succeed.

Once confirmed:

- A Mitigation Event shall be emitted.
- The referenced Breaker Block Zone shall update its lifecycle state.
- The original Breaker Block Event shall remain immutable.

---

## 9.3 Fair Value Gap Mitigation

A Fair Value Gap Mitigation is confirmed when all of the following conditions are satisfied:

- A valid Fair Value Gap Zone exists.
- Price enters the Fair Value Gap Zone.
- Fill validation succeeds.
- ATR validation succeeds (if enabled).
- All confirmation rules succeed.

Once confirmed:

- A Mitigation Event shall be emitted.
- The referenced Fair Value Gap Zone shall update its lifecycle state.
- The original Fair Value Gap Event shall remain immutable.

---

## 9.4 Partial Mitigation

A mitigation is classified as partial when price penetrates the source zone but does not satisfy the configured full mitigation threshold.

The detector shall:

- Emit a Partial Mitigation Event.
- Update the referenced zone lifecycle.
- Preserve all immutable historical events.

---

## 9.5 Full Mitigation

A mitigation is classified as full when price completely satisfies the configured mitigation threshold.

The detector shall:

- Emit a Full Mitigation Event.
- Update the referenced zone lifecycle.
- Preserve all immutable historical events.

---

## 9.6 Zone Validation

Before creating a Mitigation Event, the detector shall verify:

- Source Zone exists.
- Source Zone is Active.
- Source Zone has not expired.
- Source Zone is eligible for mitigation.

Invalid zones shall be rejected.

---

## 9.7 Duplicate Prevention

Before confirming a Mitigation Event, the detector shall verify that an equivalent mitigation has not already been emitted.

Duplicate Mitigation Events shall not be produced.

---

# 10. Confirmation Rules

A Mitigation Event shall only be confirmed after all applicable validation rules succeed.

Validation may include:

- Zone validation
- Penetration validation
- Partial mitigation validation
- Full mitigation validation
- ATR validation
- Duplicate validation

Once confirmed:

- Event ID shall never change.
- Source Zone shall never change.
- Mitigation Type shall never change.
- Confirmation Timestamp shall never change.

Confirmed Mitigation Events are immutable.

---

# 11. State Management

The Mitigation Block Detector maintains only the runtime state required for deterministic mitigation detection.

The detector state includes:

- Mitigation History
- Last Mitigation Event
- Internal Processing State

The detector shall update its internal state incrementally after every completed MarketBar.

Reset operations shall restore the detector to its initial state.

---

## Mitigation Lifecycle

Each mitigation interaction progresses through the following lifecycle.

```text
Detected
      │
      ▼
Confirmed
      │
      ▼
Recorded
```

Unlike structural detectors, Mitigation Events do not own price zones.

Instead, they record interactions with existing institutional zones.

---

# 12. State Ownership

The Mitigation Block Detector is the authoritative owner of:

- Mitigation Events
- Mitigation History
- Mitigation Measurements
- Internal Detector State

The Mitigation Block Detector shall never own:

- Order Block Zones
- Breaker Block Zones
- Fair Value Gap Zones

The detector shall never modify:

- Swing Events
- BOS Events
- CHOCH Events
- Liquidity Events
- Order Block Events
- Breaker Block Events
- Fair Value Gap Events
- Current Trend
- Protected Swing

Communication between detectors shall occur exclusively through immutable events.

Zone lifecycle updates shall be performed only through the owning detector.

---

# 13. Deterministic Guarantees

The Mitigation Block Detector shall satisfy the following guarantees.

## Historical Replay

Historical replay shall always produce identical Mitigation Events for identical market data.

---

## Live Streaming

Live execution shall produce identical Mitigation Events as historical replay.

---

## Non-Repainting

Confirmed Mitigation Events shall never be modified after confirmation.

If additional interactions occur with the same source zone, new Mitigation Events shall be emitted rather than modifying existing events.

---

## Sequential Processing

Completed MarketBars shall be processed strictly in chronological order.

---

## Idempotent Processing

Processing identical historical data multiple times shall always produce:

- Identical Mitigation Events
- Identical Mitigation Measurements
- Identical Detector State

The detector shall never modify state owned by Swing, BOS, CHOCH, Liquidity, Order Block, Fair Value Gap, or Breaker Block detectors.

---

---

# 14. Measurements

The Mitigation Block Detector shall expose quantitative measurements describing each confirmed Mitigation Event.

Measurements provide objective inputs for Feature Engineering, Research Analytics, and the Probability Engine.

The detector shall not generate trading signals or trading decisions.

---

## 14.1 Price Measurements

The detector shall compute:

- Mitigation Price
- Source Zone High
- Source Zone Low
- Penetration Depth
- Penetration Percentage
- Distance From Zone Midpoint
- Distance (Points)
- Distance (ATR)

These measurements describe how deeply price entered the institutional zone.

---

## 14.2 Structural Measurements

The detector shall compute:

- Source Zone Type
- Source Zone Reference
- Origin BOS Reference
- Origin CHOCH Reference
- Origin Liquidity Reference
- Bars Since Zone Creation
- Trend Alignment

These measurements describe the structural context of the mitigation.

---

## 14.3 Interaction Measurements

The detector shall compute:

- First Touch Time
- Number of Touches
- Maximum Penetration
- Time Inside Zone
- Exit Direction
- Exit Momentum

These measurements quantify price interaction with the institutional zone.

---

## 14.4 Quality Measurements

The detector may compute:

- Mitigation Strength
- Mitigation Confidence
- Zone Respect Score
- Rejection Strength
- Recovery Strength

These measurements describe the quality of the mitigation rather than simply its occurrence.

---

# 15. Feature Engineering Outputs

The Mitigation Block Detector exposes quantitative features for downstream statistical analysis and machine learning.

Typical exported features include:

- mitigation_depth
- mitigation_percentage
- mitigation_strength
- mitigation_confidence
- penetration_atr
- touch_count
- rejection_strength
- recovery_strength
- structural_age
- trend_alignment
- zone_respect_score

Feature Engineering is responsible for:

- Feature normalization
- Scaling
- Weighting
- Selection
- Transformation

The Mitigation Block Detector shall not perform these operations.

---

# 16. Failure Cases

The Mitigation Block Detector shall safely handle the following conditions.

## Missing Source Zone

If no valid institutional zone exists:

- No Mitigation Event shall be emitted.
- Detector state shall remain valid.

---

## Expired Source Zone

If the referenced zone has expired:

- The mitigation candidate shall be rejected.

---

## Insufficient Penetration

If penetration does not satisfy the configured threshold:

- No Mitigation Event shall be confirmed.

---

## ATR Validation Failure

If ATR validation is enabled and fails:

- No Mitigation Event shall be confirmed.

---

## Duplicate Mitigation

Duplicate Mitigation Events shall be rejected.

---

## Historical Replay

Historical replay shall always reproduce identical Mitigation Events.

---

## Detector Reset

Reset operations shall clear runtime state while preserving deterministic behavior for future processing.

---

# 17. Performance Requirements

The Mitigation Block Detector shall satisfy the following requirements.

## Processing

- Incremental execution
- One completed MarketBar per update
- Streaming compatible

---

## Memory

The detector shall maintain only the runtime state required for deterministic mitigation analysis.

Historical storage shall respect configured limits.

---

## Determinism

Identical historical market data shall always produce:

- Identical Mitigation Events
- Identical Mitigation Measurements
- Identical Detector State

---

## Scalability

The detector shall support:

- Long historical replay
- Continuous live execution
- High-frequency market updates

---

# 18. Integration

The Mitigation Block Detector is the final stage of the Market Structure Engine.

Its outputs are consumed by downstream analytical components.

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
      ▼
Mitigation Block Detector
      │
      ├── Feature Engineering
      ├── Research Analytics
      └── Probability Engine
```

The Mitigation Block Detector is the authoritative owner of:

- Mitigation Events
- Mitigation History
- Mitigation Measurements

The Mitigation Block Detector shall never own or modify:

- Order Block Zones
- Fair Value Gap Zones
- Breaker Block Zones
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

- Order Block mitigation detection
- Fair Value Gap mitigation detection
- Breaker Block mitigation detection
- Partial mitigation detection
- Full mitigation detection
- Duplicate prevention

---

## Validation Tests

- Source zone validation
- Penetration validation
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
- Multiple simultaneous mitigations
- Repeated zone interactions

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

- Multi-Timeframe Mitigation Analysis
- Volume-assisted Mitigation Validation
- Zone Efficiency Scoring
- Institutional Reaction Classification
- Mitigation Sequence Analysis
- Machine Learning Assisted Mitigation Classification

Future enhancements shall remain backward compatible with this specification.

---

# 21. Acceptance Criteria

The Mitigation Block Detector shall be considered production-ready only when:

- All unit tests pass.
- Integration tests pass.
- Historical replay is deterministic.
- Live execution is deterministic.
- Confirmed Mitigation Events never repaint.
- All measurements are deterministic.
- All performance requirements are satisfied.
- Documentation is complete.
- Code review is approved.
- Integration with the Market Structure Engine is verified.

---

# End of Specification