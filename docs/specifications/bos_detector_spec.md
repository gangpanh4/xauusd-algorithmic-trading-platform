# Break of Structure (BOS) Detector Specification

**Document ID:** SMC-SPEC-003

**Version:** 1.0

**Status:** Draft

**Project:** Trading Intelligence Platform

**Module:** Market Structure Engine

---

# 1. Purpose

The Break of Structure (BOS) Detector is responsible for identifying confirmed continuation of the current market trend through structural breaks of previously confirmed Swing Events.

The BOS Detector consumes confirmed Swing Events produced by the Swing Detector and determines whether price has established a valid continuation of the existing market structure.

Confirmed BOS Events provide the structural foundation for downstream components including:

- Change of Character (CHOCH)
- Liquidity Engine
- Order Block Engine
- Fair Value Gap Engine
- Feature Engineering
- Research Analytics
- Probability Engine

The BOS Detector operates deterministically and incrementally, ensuring identical outputs for identical historical market data.

The detector does not generate trading signals or trading decisions.

---

# 2. Scope

The BOS Detector is responsible only for identifying confirmed Break of Structure events.

The detector SHALL:

- Consume confirmed Swing Events.
- Maintain the current market trend.
- Maintain the protected structural swing.
- Detect Bullish BOS.
- Detect Bearish BOS.
- Produce immutable BOS Events.
- Produce quantitative BOS measurements.
- Support historical replay.
- Support live streaming execution.

The detector SHALL NOT:

- Detect Swing Highs.
- Detect Swing Lows.
- Detect Change of Character.
- Detect Liquidity.
- Detect Order Blocks.
- Detect Fair Value Gaps.
- Generate trading signals.
- Calculate probabilities.
- Manage trading risk.

These responsibilities belong to downstream components.

---

# 3. Owner

## Owner Module

```
BOSDetector
```

The BOS Detector is the sole owner of:

- BOS Events
- Current Trend
- Protected Swing
- BOS History
- BOS Measurements
- BOS Detector State

No downstream module shall create, modify, or invalidate BOS Events.

Current Trend and Protected Swing are authoritative outputs of the BOS Detector.

---

# 4. Responsibilities

The BOS Detector shall:

- Consume confirmed Swing Events.
- Maintain Current Trend.
- Maintain Protected Swing.
- Detect Bullish BOS.
- Detect Bearish BOS.
- Prevent duplicate BOS Events.
- Produce immutable BOS Events.
- Maintain detector runtime state.
- Compute BOS measurements.
- Expose measurements for Feature Engineering.
- Operate deterministically.
- Operate incrementally.
- Support historical replay.
- Support continuous streaming execution.

---

# 5. Dependencies

## Consumes

The BOS Detector consumes:

- Completed MarketBar
- Confirmed Swing Events
- BOSDetectorConfig
- Internal BOS State

The BOS Detector does not consume CHOCH, Liquidity, Order Blocks, or Fair Value Gaps.

---

## Produces

The BOS Detector produces:

- BOSEvent
- Updated BOS Detector State
- Current Trend
- Protected Swing
- BOS Measurements
- Feature Engineering Inputs

---

# 6. Inputs

The detector processes one completed MarketBar at a time.

Required inputs include:

- Completed MarketBar
- Confirmed Swing Events

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

The BOS Detector produces immutable BOS Events.

Each BOS Event shall include:

- Event ID
- Timestamp
- Direction
- Break Price
- Broken Swing
- Confirmation Bar

The detector also produces:

- Updated Current Trend
- Updated Protected Swing
- Updated BOS State
- BOS Measurements
- Feature Engineering Inputs

When no BOS is confirmed the detector shall produce no event.

---

# 8. Configuration

The BOS Detector shall support configuration through the BOSDetectorConfig object.

The following parameters shall be configurable.

| Parameter | Description |
|------------|-------------|
| Minimum Break Distance | Minimum structural break distance required |
| Close Confirmation | Require candle close beyond protected swing |
| ATR Validation | Enable or disable ATR validation |
| ATR Period | ATR calculation period |
| ATR Multiplier | Minimum ATR requirement |
| Equal Break Tolerance | Tolerance for equal structural levels |

Configuration values define BOS sensitivity but shall not alter BOS ownership or detector responsibilities.

---

# 9. Detection Rules

The BOS Detector shall identify confirmed Break of Structure (BOS) events using confirmed Swing Events and completed MarketBars.

A BOS Event represents continuation of the current market trend through a decisive break of a protected structural swing.

The detector shall evaluate only completed MarketBars.

The detector shall never predict or anticipate future price movement.

---

## 9.1 Bullish BOS

A Bullish BOS is confirmed when all of the following conditions are satisfied:

- The current market trend is Bullish.
- A protected Swing High exists.
- Price closes above the protected Swing High.
- The minimum break distance requirement is satisfied.
- ATR validation succeeds (if enabled).
- All confirmation rules succeed.

Once confirmed:

- A Bullish BOS Event shall be emitted.
- Current Trend remains Bullish.
- Protected Swing shall be updated according to the new market structure.

---

## 9.2 Bearish BOS

A Bearish BOS is confirmed when all of the following conditions are satisfied:

- The current market trend is Bearish.
- A protected Swing Low exists.
- Price closes below the protected Swing Low.
- The minimum break distance requirement is satisfied.
- ATR validation succeeds (if enabled).
- All confirmation rules succeed.

Once confirmed:

- A Bearish BOS Event shall be emitted.
- Current Trend remains Bearish.
- Protected Swing shall be updated according to the new market structure.

---

## 9.3 Protected Swing

The Protected Swing represents the structural level whose violation would invalidate the current market trend.

The BOS Detector is the sole owner of the Protected Swing.

The Protected Swing shall be updated only after a confirmed structural event.

Downstream modules shall consume the Protected Swing but shall never modify it.

---

## 9.4 Trend Continuation

A confirmed BOS indicates continuation of the existing market trend.

A BOS Event shall never reverse the current trend.

Trend reversal is the responsibility of the CHOCH Detector.

---

## 9.5 Duplicate Prevention

Before confirming a BOS Event, the detector shall verify that an equivalent BOS Event has not already been emitted.

Duplicate BOS Events shall not be produced.

---

## 9.6 Equal Structure Levels

Equal Highs and Equal Lows shall be evaluated using the configured Equal Break Tolerance.

Tolerance values affect comparison logic only.

They shall not modify the definition of a confirmed BOS Event.

---

# 10. Confirmation Rules

A BOS Event shall only be confirmed after all of the following requirements are satisfied:

- A valid Protected Swing exists.
- Price breaks the Protected Swing.
- Close Confirmation succeeds (if enabled).
- Minimum Break Distance validation succeeds.
- ATR validation succeeds (if enabled).
- Duplicate validation succeeds.

Once confirmed:

- Event ID shall never change.
- Direction shall never change.
- Break Price shall never change.
- Confirmation Timestamp shall never change.

Confirmed BOS Events are immutable.

---

# 11. State Management

The BOS Detector maintains only the runtime state required for deterministic execution.

The detector state includes:

- Current Trend
- Protected Swing
- BOS History
- Last Confirmed BOS
- Internal Processing State

The detector shall update its state incrementally after every completed MarketBar.

Reset operations shall restore the detector to its initial state.

---

# 12. State Ownership

The BOS Detector is the authoritative owner of the following state:

- Current Trend
- Protected Swing
- BOS History
- Last Confirmed BOS
- BOS Measurements
- Internal Detector State

The Swing Detector owns Swing Events.

The CHOCH Detector consumes Current Trend from the BOS Detector.

No downstream component shall modify BOS Detector state.

---

# 13. Deterministic Guarantees

The BOS Detector shall satisfy the following guarantees.

## Historical Replay

Historical replay shall always produce identical BOS Events for identical market data.

---

## Live Streaming

Live execution shall produce identical BOS Events as historical replay.

---

## Non-Repainting

Confirmed BOS Events shall never be modified after confirmation.

---

## Sequential Processing

Completed MarketBars shall be processed strictly in chronological order.

---

## Idempotent Processing

Processing identical historical data multiple times shall always produce:

- Identical BOS Events
- Identical Current Trend
- Identical Protected Swing
- Identical BOS Measurements
- Identical Detector State

---

# 14. Measurements

The BOS Detector shall expose quantitative measurements describing each confirmed Break of Structure event.

Measurements provide objective information for downstream Feature Engineering, Research Analytics, and the Probability Engine.

The BOS Detector shall not generate trading signals or trading decisions.

---

## 14.1 Break Measurements

The detector shall compute:

- Break Price
- Protected Swing Price
- Break Distance
- Break Distance (Points)
- Break Distance (ATR)
- Break Percentage

These measurements quantify the magnitude of the structural break.

---

## 14.2 Time Measurements

The detector shall compute:

- Time Since Protected Swing
- Bars Since Protected Swing
- BOS Duration
- Confirmation Delay

These measurements describe the temporal characteristics of the structural continuation.

---

## 14.3 Momentum Measurements

The detector may compute:

- Break Momentum
- Close Strength
- Candle Body Ratio
- Candle Range
- Relative Expansion

Momentum measurements describe the quality of the structural break rather than simply its existence.

---

## 14.4 Structure Quality Measurements

The detector may compute:

- BOS Strength
- Break Efficiency
- Structure Confidence
- Structural Expansion
- Follow-through Strength

These measurements represent the quality of the continuation event.

They are intended for downstream Feature Engineering and Research Analytics.

---

# 15. Feature Engineering Outputs

The BOS Detector exposes quantitative features for downstream statistical analysis and machine learning.

Typical exported features include:

- bos_break_distance
- bos_break_atr
- bos_strength
- structure_confidence
- break_efficiency
- follow_through_strength
- bars_since_protected_swing
- break_momentum

Feature Engineering is responsible for:

- Feature scaling
- Normalization
- Weighting
- Selection
- Transformation

The BOS Detector shall not perform these operations.

---

# 16. Failure Cases

The BOS Detector shall safely handle the following conditions.

## No Protected Swing

If no valid Protected Swing exists:

- No BOS Event shall be emitted.
- Detector state shall remain valid.

---

## Invalid Swing Event

If the received Swing Event is invalid:

- The event shall be rejected.
- BOS state shall remain unchanged.

---

## Insufficient Break Distance

If the break distance is below the configured threshold:

- No BOS Event shall be emitted.

---

## ATR Validation Failure

If ATR validation is enabled and fails:

- The structural break shall not be confirmed.

---

## Duplicate BOS

Duplicate BOS Events shall be rejected.

---

## Historical Replay

Historical replay shall always reproduce identical BOS Events.

---

## Detector Reset

Reset operations shall clear runtime state while preserving deterministic behavior for future processing.

---

# 17. Performance Requirements

The BOS Detector shall satisfy the following requirements.

## Processing

- Incremental execution
- One completed MarketBar per update
- Streaming compatible

---

## Memory

The detector shall maintain only the state required for deterministic structural analysis.

Historical storage shall respect configured limits.

---

## Determinism

Identical historical market data shall always produce:

- Identical BOS Events
- Identical Current Trend
- Identical Protected Swing
- Identical BOS Measurements

---

## Scalability

The detector shall support:

- Long historical replay
- Continuous live execution
- High-frequency structural updates

---

# 18. Integration

The BOS Detector is the second stage of the Market Structure Engine.

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
      ├── CHOCH Detector
      ├── Liquidity Engine
      ├── Order Block Engine
      ├── Fair Value Gap Engine
      ├── Feature Engineering
      ├── Research Analytics
      └── Probability Engine
```

The BOS Detector is the authoritative owner of:

- Current Trend
- Protected Swing
- BOS Events

When a confirmed CHOCH Event is received, the BOS Detector is responsible for performing the controlled market trend transition.

The CHOCH Detector never modifies Current Trend or Protected Swing directly.

Downstream components shall consume these outputs without modification.

---

# 19. Unit Test Requirements

The implementation shall include automated tests covering the following categories.

## Functional Tests

- Bullish BOS detection
- Bearish BOS detection
- Protected Swing updates
- Trend continuation
- Duplicate prevention

---

## Validation Tests

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
- False breakouts

---

## Determinism Tests

The detector shall verify:

- Non-repainting
- Identical replay results
- Stable event ordering
- Stable Current Trend
- Stable Protected Swing

---

# 20. Future Enhancements

Potential future enhancements include:

- Multi-Timeframe BOS Confirmation
- Adaptive Break Thresholds
- Volatility-adjusted Break Validation
- Volume-assisted BOS Confirmation
- Statistical BOS Quality Classification
- Machine Learning Assisted Structure Evaluation

Future enhancements shall remain backward compatible with this specification.

---

# 21. Acceptance Criteria

The BOS Detector shall be considered production-ready only when:

- All unit tests pass.
- Integration tests pass.
- Historical replay is deterministic.
- Live execution is deterministic.
- Confirmed BOS Events never repaint.
- Current Trend remains internally consistent.
- Protected Swing is updated correctly.
- Performance requirements are satisfied.
- Documentation is complete.
- Code review is approved.
- Integration with the Market Structure Engine is verified.

---

# End of Specification