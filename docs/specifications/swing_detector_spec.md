# Swing Detector Specification

**Document ID:** SMC-SPEC-002

**Version:** 1.0

**Status:** Draft

**Project:** Trading Intelligence Platform

**Module:** Market Structure Engine

---

# 1. Purpose

The Swing Detector is responsible for identifying confirmed Swing Highs and Swing Lows from a sequential stream of completed market bars.

Confirmed Swing Events represent the structural foundation of the Market Structure Engine and provide the primary structural inputs for downstream detectors including:

- Break of Structure (BOS)
- Change of Character (CHOCH)
- Liquidity Engine
- Order Block Engine
- Fair Value Gap Engine
- Premium / Discount Engine

The Swing Detector shall operate deterministically and incrementally, ensuring identical outputs for identical historical market data.

The detector does not generate trading signals or perform market analysis beyond confirming structural swing points.

---

# 2. Scope

The Swing Detector is responsible only for identifying confirmed Swing Highs and Swing Lows.

The detector SHALL:

- Process completed MarketBars.
- Detect confirmed Swing Highs.
- Detect confirmed Swing Lows.
- Maintain Swing Detector state.
- Produce immutable Swing Events.
- Produce quantitative swing measurements.
- Support historical replay.
- Support live streaming execution.

The detector SHALL NOT:

- Determine market trend.
- Detect Break of Structure.
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
SwingDetector
```

The Swing Detector is the sole owner of:

- Confirmed Swing Events
- Swing History
- Swing Measurements
- Swing Detector State

No downstream module shall create, modify, or invalidate Swing Events.

All downstream modules consume confirmed Swing Events produced by the Swing Detector.

---

# 4. Responsibilities

The Swing Detector shall:

- Process completed MarketBars sequentially.
- Maintain rolling market history.
- Detect confirmed Swing Highs.
- Detect confirmed Swing Lows.
- Prevent duplicate Swing Events.
- Produce immutable Swing Events.
- Maintain detector runtime state.
- Compute swing measurements.
- Expose measurements for Feature Engineering.
- Operate deterministically.
- Operate incrementally.
- Support historical replay.
- Support continuous streaming execution.

---

# 5. Dependencies

## Consumes

The Swing Detector consumes:

- Completed MarketBar
- SwingDetectorConfig
- Internal Detector State

The Swing Detector does not depend on any downstream Market Structure component.

---

## Produces

The Swing Detector produces:

- SwingEvent
- Updated Swing Detector State
- Swing Measurements
- Feature Engineering Inputs

---

# 6. Inputs

The detector processes one completed MarketBar at a time.

Each MarketBar shall contain:

- Timestamp
- Open
- High
- Low
- Close
- Tick Volume

Configuration parameters include:

- Pivot Left
- Pivot Right
- Minimum Swing Distance
- Equal High Tolerance
- Equal Low Tolerance
- ATR Validation
- ATR Period
- ATR Multiplier
- Maximum History

All configuration shall be immutable after detector initialization.

---

# 7. Outputs

The Swing Detector produces immutable Swing Events.

Each Swing Event shall include:

- Event ID
- Timestamp
- Swing Type
- Swing Price
- Confirmation Bar
- Bar Index

The detector also produces:

- Updated Swing State
- Swing Measurements
- Feature Engineering Inputs

When no swing is confirmed the detector shall produce no event.

---

# 8. Configuration

The Swing Detector shall support configuration through the SwingDetectorConfig object.

The following parameters shall be configurable.

| Parameter | Description |
|------------|-------------|
| Pivot Left | Number of completed bars required before the pivot candidate |
| Pivot Right | Number of completed bars required after the pivot candidate |
| Minimum Swing Distance | Minimum distance between consecutive swings |
| Equal High Tolerance | Tolerance used when comparing Equal Highs |
| Equal Low Tolerance | Tolerance used when comparing Equal Lows |
| ATR Validation | Enable or disable ATR filtering |
| ATR Period | ATR calculation period |
| ATR Multiplier | Minimum ATR requirement |
| Maximum History | Maximum historical MarketBars maintained by the detector |

Configuration values define detector sensitivity but do not alter detector behavior.

---

# 9. Detection Rules

The Swing Detector shall identify confirmed Swing Highs and Swing Lows using deterministic pivot-based detection.

A Swing Event shall only be confirmed after all confirmation requirements have been satisfied.

The detector shall never evaluate incomplete MarketBars.

---

## 9.1 Swing High Detection

A Swing High is confirmed when:

- The candidate High is greater than all configured Pivot Left Highs.
- The candidate High is greater than all configured Pivot Right Highs.
- The required number of Pivot Right MarketBars has completed.
- All validation rules succeed.

Once confirmed, the Swing High becomes immutable.

---

## 9.2 Swing Low Detection

A Swing Low is confirmed when:

- The candidate Low is lower than all configured Pivot Left Lows.
- The candidate Low is lower than all configured Pivot Right Lows.
- The required number of Pivot Right MarketBars has completed.
- All validation rules succeed.

Once confirmed, the Swing Low becomes immutable.

---

## 9.3 Pivot Confirmation

The Swing Detector shall never confirm a pivot before sufficient right-side MarketBars exist.

Every Swing Event represents a fully confirmed market structure point.

The detector shall never anticipate future MarketBars.

---

## 9.4 Duplicate Prevention

Before confirming a Swing Event the detector shall verify that an equivalent Swing Event has not already been confirmed.

Duplicate Swing Events shall not be emitted.

---

## 9.5 Equal Highs and Equal Lows

Equal Highs and Equal Lows shall be evaluated using the configured tolerance values.

Tolerance values affect comparison logic only.

They shall not modify the definition of a confirmed Swing Event.

---

# 10. Confirmation Rules

A Swing Event shall only be confirmed after:

- All Pivot Left requirements are satisfied.
- All Pivot Right requirements are satisfied.
- Minimum Swing Distance validation succeeds.
- ATR validation succeeds (if enabled).
- Duplicate validation succeeds.

Once confirmed:

- Timestamp shall never change.
- Swing Price shall never change.
- Swing Type shall never change.
- Event ID shall never change.

Confirmed Swing Events are immutable.

---

# 11. State Management

The Swing Detector maintains only the runtime state required for deterministic operation.

The detector state includes:

- Rolling MarketBar History
- Pending Pivot Candidate
- Confirmed Swing History
- Last Confirmed Swing
- Internal Processing Buffer

The detector shall update its state incrementally after every completed MarketBar.

The detector shall support reset operations without affecting historical determinism.

---

# 12. State Ownership

The Swing Detector is the authoritative owner of all Swing-related state.

The following state is owned exclusively by the Swing Detector:

- Confirmed Swing History
- Last Confirmed Swing
- Pending Pivot Candidate
- Swing Measurements
- Internal Detector Buffer

No downstream Market Structure component shall modify Swing Detector state.

Downstream modules consume Swing Events without recomputing or altering them.

---

# 13. Deterministic Guarantees

The Swing Detector shall satisfy the following guarantees.

## Historical Replay

Historical replay shall produce identical Swing Events for identical market data.

---

## Live Streaming

Live streaming execution shall produce the same confirmed Swing Events as historical replay.

---

## Non-Repainting

Confirmed Swing Events shall never be modified after confirmation.

---

## Sequential Processing

MarketBars shall be processed strictly in chronological order.

---

## Idempotent Processing

Processing identical historical data multiple times shall produce identical Swing Events and identical detector state.

---

# 14. Measurements

The Swing Detector shall expose quantitative measurements describing each confirmed Swing Event.

Measurements provide objective information for downstream analysis and shall not contain trading decisions.

## Price Measurements

The detector shall compute:

- Swing Price
- Price Distance from Previous Swing
- Price Expansion

---

## Time Measurements

The detector shall compute:

- Swing Duration
- Bars Since Previous Swing
- Time Since Previous Swing

---

## Volatility Measurements

When ATR validation is enabled, the detector shall compute:

- ATR Value
- ATR Multiple
- Relative Volatility

---

## Quality Measurements

The detector may compute:

- Swing Strength
- Pivot Strength
- Local Price Expansion
- Confirmation Delay

These measurements are intended for downstream Feature Engineering and Research Analytics.

The Swing Detector shall not calculate trading probability.

---

# 15. Feature Engineering Outputs

The Swing Detector exposes quantitative features for downstream machine learning and statistical analysis.

Typical features include:

- swing_distance
- swing_duration
- swing_strength
- atr_multiple
- price_velocity
- bars_since_last_swing

Feature Engineering is responsible for transforming these measurements into model-ready features.

The Swing Detector shall not perform feature scaling, normalization, weighting, or selection.

---

# 16. Failure Cases

The Swing Detector shall safely handle the following conditions.

## Insufficient MarketBars

If insufficient MarketBars exist to evaluate a pivot:

- No Swing Event shall be emitted.
- Detector state shall remain valid.

---

## Duplicate Swings

Duplicate Swing Events shall be rejected.

---

## Equal Highs / Equal Lows

Equal price levels shall be evaluated using configured tolerance values.

---

## Invalid Market Data

Invalid MarketBars shall be rejected according to platform validation rules.

---

## Detector Reset

Reset operations shall clear runtime state while preserving deterministic behavior for future processing.

---

## Historical Replay

Historical replay shall always reproduce identical Swing Events.

---

# 17. Performance Requirements

The Swing Detector shall satisfy the following requirements.

## Processing

- Incremental execution
- One completed MarketBar per update
- Streaming compatible

---

## Memory

The detector shall maintain only the history required for deterministic processing.

Historical storage shall respect Maximum History configuration.

---

## Determinism

Identical historical data shall always produce:

- Identical Swing Events
- Identical Measurements
- Identical Detector State

---

## Scalability

The detector shall support:

- Large historical datasets
- Continuous live execution
- Extended replay sessions

---

# 18. Integration

The Swing Detector is the first stage of the Market Structure Engine.

Its outputs are consumed by downstream components.

```text
MarketBar
      │
      ▼
Swing Detector
      │
      ├── BOS Detector
      ├── CHOCH Detector
      ├── Liquidity Engine
      ├── Order Block Engine
      ├── Fair Value Gap Engine
      ├── Feature Engineering
      ├── Research Analytics
      └── Probability Engine
```

No downstream component shall independently recompute Swing Events.

The Swing Detector is the authoritative source of confirmed market swings.

---

# 19. Unit Test Requirements

The implementation shall include automated tests covering the following categories.

## Functional Tests

- Swing High detection
- Swing Low detection
- Pivot confirmation
- Duplicate prevention
- Equal High handling
- Equal Low handling

---

## Validation Tests

- ATR validation
- Minimum Swing Distance
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
- Sideways markets
- High volatility
- Low volatility
- Price gaps

---

## Determinism Tests

The detector shall verify:

- Non-repainting
- Identical replay results
- Stable event ordering

---

# 20. Future Enhancements

Potential future enhancements include:

- Adaptive Pivot Length
- Volatility-adjusted Swing Detection
- Multi-Timeframe Swing Alignment
- Swing Quality Classification
- Statistical Swing Confidence
- Machine Learning Assisted Swing Evaluation

Future enhancements shall remain backward compatible with this specification.

---

# 21. Acceptance Criteria

The Swing Detector shall be considered production-ready only when:

- All unit tests pass.
- Integration tests pass.
- Historical replay is deterministic.
- Live execution is deterministic.
- Confirmed Swing Events never repaint.
- Performance requirements are satisfied.
- Documentation is complete.
- Code review is approved.
- Integration with the Market Structure Engine is verified.

---

# End of Specification