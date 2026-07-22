# Change of Character (CHOCH) Detector Specification

**Document ID:** SMC-SPEC-004

**Version:** 1.0

**Status:** Draft

**Project:** Trading Intelligence Platform

**Module:** Market Structure Engine

---

# 1. Purpose

The Change of Character (CHOCH) Detector is responsible for identifying potential reversals of the current market trend through violations of the Protected Swing maintained by the BOS Detector.

The CHOCH Detector consumes the Current Trend, Protected Swing, confirmed Swing Events, and completed MarketBars to determine whether the existing market structure has been invalidated.

A confirmed CHOCH Event indicates that continuation is no longer valid and that a trend transition may occur.

Confirmed CHOCH Events provide structural inputs for downstream components including:

- Liquidity Engine
- Order Block Engine
- Fair Value Gap Engine
- Feature Engineering
- Research Analytics
- Probability Engine

The CHOCH Detector operates deterministically and incrementally, ensuring identical outputs for identical historical market data.

The detector does not generate trading signals or execute trend changes.

---

# 2. Scope

The CHOCH Detector is responsible only for identifying confirmed Change of Character events.

The detector SHALL:

- Consume Current Trend from the BOS Detector.
- Consume Protected Swing from the BOS Detector.
- Consume confirmed Swing Events.
- Detect Bullish CHOCH.
- Detect Bearish CHOCH.
- Produce immutable CHOCH Events.
- Produce quantitative CHOCH measurements.
- Support historical replay.
- Support live streaming execution.

The detector SHALL NOT:

- Detect Swing Highs.
- Detect Swing Lows.
- Detect Break of Structure.
- Own Current Trend.
- Own Protected Swing.
- Detect Liquidity.
- Detect Order Blocks.
- Detect Fair Value Gaps.
- Generate trading signals.
- Calculate probabilities.
- Manage trading risk.

These responsibilities belong to other components.

---

# 3. Owner

## Owner Module

```
CHOCHDetector
```

The CHOCH Detector is the sole owner of:

- CHOCH Events
- CHOCH History
- CHOCH Measurements
- CHOCH Detector State

The CHOCH Detector does not own:

- Current Trend
- Protected Swing

These values remain under the exclusive ownership of the BOS Detector.

A confirmed CHOCH Event is an immutable notification that the current market structure has been invalidated.

Market trend transitions are performed only by the BOS Detector.

The CHOCH Detector does not own Current Trend or Protected Swing.

These are authoritative outputs of the BOS Detector.

---

# 4. Responsibilities

The CHOCH Detector shall:

- Consume Current Trend.
- Consume Protected Swing.
- Consume confirmed Swing Events.
- Detect Bullish CHOCH.
- Detect Bearish CHOCH.
- Prevent duplicate CHOCH Events.
- Produce immutable CHOCH Events.
- Maintain detector runtime state.
- Compute CHOCH measurements.
- Expose measurements for Feature Engineering.
- Operate deterministically.
- Operate incrementally.
- Support historical replay.
- Support continuous streaming execution.

---

# 5. Dependencies

## Consumes

The CHOCH Detector consumes:

- Completed MarketBar
- Confirmed Swing Events
- Current Trend
- Protected Swing
- CHOCHDetectorConfig
- Internal CHOCH State

The CHOCH Detector does not consume Liquidity, Order Blocks, or Fair Value Gaps.

---

## Produces

The CHOCH Detector produces:

- CHOCHEvent
- Updated CHOCH Detector State
- CHOCH Measurements
- Feature Engineering Inputs

A confirmed CHOCH Event represents a confirmed structural reversal signal.

The CHOCH Detector shall emit the event without modifying market state.

The BOS Detector consumes the CHOCH Event and performs the controlled update of:

- Current Trend
- Protected Swing

This preserves a single authoritative owner for market trend state.

---

# 6. Inputs

The detector processes one completed MarketBar at a time.

Required inputs include:

- Completed MarketBar
- Confirmed Swing Events
- Current Trend
- Protected Swing

Configuration parameters include:

- Minimum Break Distance
- Close Confirmation
- ATR Validation
- ATR Period
- ATR Multiplier
- Equal Break Tolerance

All configuration shall be immutable after detector initialization.

---

# 7. Outputs

The CHOCH Detector produces immutable CHOCH Events.

Each CHOCH Event shall include:

- Event ID
- Timestamp
- Direction
- Break Price
- Broken Protected Swing
- Previous Trend
- Confirmation Bar

The detector also produces:

- Updated CHOCH State
- CHOCH Measurements
- Feature Engineering Inputs

When no CHOCH is confirmed, the detector shall produce no event.

---

# 8. Configuration

The CHOCH Detector shall support configuration through the CHOCHDetectorConfig object.

The following parameters shall be configurable.

| Parameter | Description |
|------------|-------------|
| Minimum Break Distance | Minimum structural break required |
| Close Confirmation | Require candle close beyond Protected Swing |
| ATR Validation | Enable or disable ATR validation |
| ATR Period | ATR calculation period |
| ATR Multiplier | Minimum ATR requirement |
| Equal Break Tolerance | Tolerance for equal structural levels |

Configuration values define CHOCH sensitivity but shall not alter ownership or detector responsibilities.

---

# 9. Detection Rules

The CHOCH Detector shall identify confirmed Change of Character (CHOCH) events using completed MarketBars, confirmed Swing Events, the Current Trend, and the Protected Swing provided by the BOS Detector.

A CHOCH Event represents a confirmed structural invalidation of the current market trend.

The detector shall evaluate only completed MarketBars.

The detector shall never predict or anticipate future price movement.

---

## 9.1 Bullish CHOCH

A Bullish CHOCH is confirmed when all of the following conditions are satisfied:

- The Current Trend is Bearish.
- A valid Protected Swing Low exists.
- Price closes above the structural invalidation level.
- The minimum break distance requirement is satisfied.
- ATR validation succeeds (if enabled).
- All confirmation rules succeed.

Once confirmed:

- A Bullish CHOCH Event shall be emitted.
- The detector shall not modify Current Trend.
- The detector shall not modify Protected Swing.

The BOS Detector is responsible for processing the CHOCH Event and performing any required trend transition.

---

## 9.2 Bearish CHOCH

A Bearish CHOCH is confirmed when all of the following conditions are satisfied:

- The Current Trend is Bullish.
- A valid Protected Swing High exists.
- Price closes below the structural invalidation level.
- The minimum break distance requirement is satisfied.
- ATR validation succeeds (if enabled).
- All confirmation rules succeed.

Once confirmed:

- A Bearish CHOCH Event shall be emitted.
- The detector shall not modify Current Trend.
- The detector shall not modify Protected Swing.

The BOS Detector is responsible for processing the CHOCH Event and performing any required trend transition.

---

## 9.3 Structural Invalidation

A CHOCH Event represents structural invalidation of the existing trend.

A confirmed CHOCH does not establish a new trend.

Instead, it indicates that the previous trend can no longer be considered valid.

Trend establishment remains the responsibility of the BOS Detector.

---

## 9.4 Reversal Detection

The CHOCH Detector identifies potential market reversals through violations of the Protected Swing.

A confirmed CHOCH shall indicate that continuation conditions are no longer satisfied.

The detector shall not determine whether the new market trend is confirmed.

---

## 9.5 Duplicate Prevention

Before confirming a CHOCH Event, the detector shall verify that an equivalent CHOCH Event has not already been emitted.

Duplicate CHOCH Events shall not be produced.

---

## 9.6 Equal Structure Levels

Equal structural levels shall be evaluated using the configured Equal Break Tolerance.

Tolerance values affect comparison logic only.

They shall not modify the definition of a confirmed CHOCH Event.

---

# 10. Confirmation Rules

A CHOCH Event shall only be confirmed after all of the following requirements are satisfied:

- A valid Current Trend exists.
- A valid Protected Swing exists.
- The Protected Swing has been structurally violated.
- Close Confirmation succeeds (if enabled).
- Minimum Break Distance validation succeeds.
- ATR validation succeeds (if enabled).
- Duplicate validation succeeds.

Once confirmed:

- Event ID shall never change.
- Direction shall never change.
- Break Price shall never change.
- Previous Trend shall never change.
- Confirmation Timestamp shall never change.

Confirmed CHOCH Events are immutable.

---

# 11. State Management

The CHOCH Detector maintains only the runtime state required for deterministic reversal detection.

The detector state includes:

- CHOCH History
- Last Confirmed CHOCH
- Internal Processing State

The detector shall not maintain ownership of:

- Current Trend
- Protected Swing

These values are read-only inputs supplied by the BOS Detector.

The detector shall update its internal state incrementally after every completed MarketBar.

Reset operations shall restore the detector to its initial state.

---

# 12. State Ownership

The CHOCH Detector is the authoritative owner of:

- CHOCH History
- Last Confirmed CHOCH
- CHOCH Measurements
- Internal Detector State

The BOS Detector exclusively owns:

- Current Trend
- Protected Swing

The CHOCH Detector shall never modify BOS-owned state.

Communication between the BOS Detector and CHOCH Detector shall occur exclusively through immutable CHOCH Events.

---

# 13. Deterministic Guarantees

The CHOCH Detector shall satisfy the following guarantees.

## Historical Replay

Historical replay shall always produce identical CHOCH Events for identical market data.

---

## Live Streaming

Live execution shall produce identical CHOCH Events as historical replay.

---

## Non-Repainting

Confirmed CHOCH Events shall never be modified after confirmation.

---

## Sequential Processing

Completed MarketBars shall be processed strictly in chronological order.

---

## Idempotent Processing

Processing identical historical data multiple times shall always produce:

- Identical CHOCH Events
- Identical CHOCH Measurements
- Identical Detector State

The detector shall not modify Current Trend or Protected Swing during processing.

---

# 14. Measurements

The CHOCH Detector shall expose quantitative measurements describing each confirmed Change of Character event.

Measurements provide objective inputs for Feature Engineering, Research Analytics, and the Probability Engine.

The detector shall not generate trading decisions or trading signals.

---

## 14.1 Break Measurements

The detector shall compute:

- Break Price
- Broken Protected Swing Price
- Break Distance
- Break Distance (Points)
- Break Distance (ATR)
- Break Percentage

These measurements quantify the magnitude of the structural invalidation.

---

## 14.2 Time Measurements

The detector shall compute:

- Time Since Protected Swing
- Bars Since Protected Swing
- CHOCH Formation Duration
- Confirmation Delay

These measurements describe the temporal characteristics of the reversal.

---

## 14.3 Momentum Measurements

The detector may compute:

- Break Momentum
- Close Strength
- Candle Body Ratio
- Candle Range
- Relative Expansion

Momentum measurements describe the conviction behind the structural reversal.

---

## 14.4 Reversal Quality Measurements

The detector may compute:

- CHOCH Strength
- Reversal Confidence
- Break Efficiency
- Structural Expansion
- Follow-through Strength

These measurements quantify the quality of the detected reversal rather than merely its occurrence.

---

# 15. Feature Engineering Outputs

The CHOCH Detector exposes quantitative features for downstream statistical analysis and machine learning.

Typical exported features include:

- choch_break_distance
- choch_break_atr
- choch_strength
- reversal_confidence
- break_efficiency
- follow_through_strength
- bars_since_protected_swing
- reversal_momentum

Feature Engineering is responsible for:

- Feature normalization
- Scaling
- Weighting
- Selection
- Transformation

The CHOCH Detector shall not perform these operations.

---

# 16. Failure Cases

The CHOCH Detector shall safely handle the following conditions.

## No Current Trend

If no Current Trend exists:

- No CHOCH Event shall be emitted.
- Detector state shall remain valid.

---

## No Protected Swing

If no valid Protected Swing exists:

- No CHOCH Event shall be emitted.

---

## Invalid Swing Event

If the supplied Swing Event is invalid:

- The event shall be rejected.
- Detector state shall remain unchanged.

---

## Insufficient Break Distance

If the structural break does not satisfy the configured minimum break distance:

- No CHOCH Event shall be emitted.

---

## ATR Validation Failure

If ATR validation is enabled and fails:

- The structural reversal shall not be confirmed.

---

## Duplicate CHOCH

Duplicate CHOCH Events shall be rejected.

---

## Historical Replay

Historical replay shall always reproduce identical CHOCH Events.

---

## Detector Reset

Reset operations shall clear runtime state while preserving deterministic behavior for future processing.

---

# 17. Performance Requirements

The CHOCH Detector shall satisfy the following requirements.

## Processing

- Incremental execution
- One completed MarketBar per update
- Streaming compatible

---

## Memory

The detector shall maintain only the runtime state required for deterministic reversal detection.

Historical storage shall respect configured limits.

---

## Determinism

Identical historical market data shall always produce:

- Identical CHOCH Events
- Identical CHOCH Measurements
- Identical Detector State

---

## Scalability

The detector shall support:

- Long historical replay
- Continuous live execution
- High-frequency market updates

---

# 18. Integration

The CHOCH Detector is the third stage of the Market Structure Engine.

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
      ├── Liquidity Engine
      ├── Order Block Engine
      ├── Fair Value Gap Engine
      ├── Feature Engineering
      ├── Research Analytics
      └── Probability Engine
```

The CHOCH Detector is the authoritative owner of:

- CHOCH Events
- CHOCH History
- CHOCH Measurements

The CHOCH Detector shall never modify:

- Current Trend
- Protected Swing

These remain under the exclusive ownership of the BOS Detector.

Communication between detectors shall occur exclusively through immutable events.

---

# 19. Unit Test Requirements

The implementation shall include automated tests covering the following categories.

## Functional Tests

- Bullish CHOCH detection
- Bearish CHOCH detection
- Structural invalidation
- Duplicate prevention
- Event generation

---

## Validation Tests

- Current Trend validation
- Protected Swing validation
- Minimum Break Distance
- Close Confirmation
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

- Strong trends
- Weak trends
- Sideways markets
- High volatility
- Low volatility
- Failed reversals

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

- Multi-Timeframe CHOCH Confirmation
- Internal vs External CHOCH Detection
- Market Structure Shift (MSS) Integration
- Volatility-adaptive Reversal Thresholds
- Volume-assisted Reversal Confirmation
- Machine Learning Assisted Reversal Quality Classification

Future enhancements shall remain backward compatible with this specification.

---

# 21. Acceptance Criteria

The CHOCH Detector shall be considered production-ready only when:

- All unit tests pass.
- Integration tests pass.
- Historical replay is deterministic.
- Live execution is deterministic.
- Confirmed CHOCH Events never repaint.
- Current Trend is never modified by the CHOCH Detector.
- Protected Swing is never modified by the CHOCH Detector.
- All performance requirements are satisfied.
- Documentation is complete.
- Code review is approved.
- Integration with the Market Structure Engine is verified.

---

# End of Specification