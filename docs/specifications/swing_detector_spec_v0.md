# Swing Detector Technical Specification

Version: 1.0
Status: Draft
Sprint: Sprint 2 – Market Structure
Module: core/market_structure/swing_detector.py

---

# 1. Overview

## Purpose

The Swing Detection Engine is responsible for identifying confirmed Swing Highs and Swing Lows from completed market candles.

It is the foundation of the Market Structure Engine and provides reliable, deterministic swing points used by:

- Break of Structure (BOS)
- Change of Character (CHoCH)
- Liquidity Detection
- Order Block Detection
- Fair Value Gap (FVG) Validation
- Market Structure Analysis

---

## Scope

The engine SHALL:

- Process completed candles only.
- Detect confirmed Swing Highs.
- Detect confirmed Swing Lows.
- Operate in historical replay.
- Operate in live streaming mode.
- Produce deterministic results.
- Never repaint confirmed swings.
- Return immutable SwingPoint objects.

---

## Non-Scope

The engine SHALL NOT:

- Detect BOS.
- Detect CHoCH.
- Detect Order Blocks.
- Detect Liquidity Sweeps.
- Generate trading signals.
- Execute trades.
- Calculate risk.

These responsibilities belong to downstream modules.

---

# 2. Design Goals

The Swing Detection Engine SHALL be:

- Deterministic
- Non-repainting
- Streaming compatible
- Stateless from the caller's perspective
- Internally stateful
- Memory efficient
- Easy to unit test
- Production ready
- Independent from MT5
- Independent from indicators

---

# 3. Functional Requirements

The detector SHALL:

- Detect Swing Highs.
- Detect Swing Lows.
- Support Pivot-based detection.
- Validate swings using ATR filtering (optional).
- Ignore insignificant market noise.
- Process one completed candle at a time.
- Store confirmed swings.
- Return swings in chronological order.
- Reject duplicate swings.
- Handle equal highs.
- Handle equal lows.
- Support configurable pivot sizes.
- Support historical replay.
- Support live streaming.

---

# 4. Architecture

Trading Pipeline

↓

Market Data

↓

Swing Detection

↓

Break Of Structure

↓

CHoCH

↓

Liquidity

↓

Order Blocks

↓

Fair Value Gaps

↓

Signal Generator

↓

Risk Manager

↓

Execution Engine

The Swing Detector SHALL expose confirmed SwingPoint objects to downstream modules.

---

# 5. Detection Method

Primary Algorithm:

- Pivot-Based Detection

Confirmation:

- Right-side confirmation bars

Validation:

- ATR filter (optional)

Repainting:

- Forbidden

Output:

- Confirmed SwingPoint

# 6. Configuration

## SwingDetectorConfig

The Swing Detection Engine SHALL be fully configurable through the `SwingDetectorConfig` object.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| pivot_left | int | 3 | Number of completed candles required to the left of the pivot candidate. |
| pivot_right | int | 3 | Number of completed candles required to the right of the pivot candidate before confirmation. |
| minimum_swing_distance | float | 0.0 | Minimum distance required between consecutive swings. |
| equal_high_tolerance | float | 0.0 | Maximum allowed difference when comparing Equal Highs. |
| equal_low_tolerance | float | 0.0 | Maximum allowed difference when comparing Equal Lows. |
| atr_validation | bool | True | Enable ATR filtering. |
| atr_period | int | 14 | ATR calculation period. |
| atr_multiplier | float | 1.0 | Minimum ATR multiple required for swing validation. |
| maximum_history | int | 5000 | Maximum number of stored historical bars. |
| debug_logging | bool | False | Enable detailed debug logging. |

---

# 7. Data Models

## SwingType

Represents the type of swing.

Possible values:

- SWING_HIGH
- SWING_LOW

---

## PivotStrength

Represents confidence in the detected pivot.

Possible values:

- WEAK
- NORMAL
- STRONG

---

## SwingPoint

Represents one confirmed market swing.

Required fields:

- timestamp
- index
- price
- swing_type
- pivot_strength
- atr_value
- confirmation_index
- confirmed
- metadata

Once confirmed, a SwingPoint SHALL be immutable.

---

## SwingDetectorState

Maintains detector runtime state.

Contains:

- recent bars
- pending pivot
- confirmed swings
- last swing
- detector status

---

## SwingDetectorConfig

Configuration object containing all detector parameters.

Configuration SHALL be immutable after initialization.

# 8. Detector State Machine

The Swing Detection Engine SHALL operate as a deterministic finite state machine.

---

## State 1 – Waiting

Description:

The detector has been initialized but has not yet received enough completed candles to evaluate a pivot.

Entry Conditions:

- Engine startup
- Engine reset

Exit Conditions:

- Sufficient completed candles available

---

## State 2 – Collecting Bars

Description:

The detector continuously receives completed market candles and stores them in the rolling history buffer.

Responsibilities:

- Store completed bars
- Maintain rolling history
- Remove bars exceeding maximum_history
- Monitor for pivot candidates

Transition:

Collecting Bars → Potential Pivot

---

## State 3 – Potential Pivot

Description:

A candle satisfies the initial left-side pivot requirements.

Responsibilities:

- Mark candidate pivot
- Begin confirmation process
- Wait for right-side candles

Transition:

Potential Pivot → Pending Confirmation

---

## State 4 – Pending Confirmation

Description:

The detector waits until enough right-side candles have completed.

Responsibilities:

- Count confirmation candles
- Continue buffering bars
- Reject invalidated pivots
- Confirm valid pivots

Possible transitions:

Pending Confirmation → Confirmed Swing

Pending Confirmation → Collecting Bars

---

## State 5 – Confirmed Swing

Description:

A Swing High or Swing Low has been fully confirmed.

Responsibilities:

- Create immutable SwingPoint
- Store in history
- Publish event
- Update detector state

Transition:

Confirmed Swing → Collecting Bars

---

## State Transition Diagram

Waiting

↓

Collecting Bars

↓

Potential Pivot

↓

Pending Confirmation

↓

Confirmed Swing

↓

Collecting Bars

The detector SHALL never skip state transitions.

All transitions SHALL be deterministic.

---

# 9. Detection Algorithm

## Processing Model

The detector SHALL process exactly one completed candle at a time.

No partially formed candle SHALL be evaluated.

---

## Step 1 – Receive Candle

Receive a completed OHLCV candle.

Append it to the historical buffer.

---

## Step 2 – Buffer Validation

Verify:

- Candle timestamp is valid
- Candle order is chronological
- OHLC values are valid
- Volume is non-negative

Invalid candles SHALL be rejected.

---

## Step 3 – Left Pivot Validation

Determine whether the candidate candle is greater (Swing High) or lower (Swing Low) than the configured number of candles on the left.

If validation fails:

Return to Collecting Bars.

---

## Step 4 – Right Pivot Confirmation

Wait until the configured number of right-side candles have completed.

If any candle invalidates the pivot:

Discard the candidate.

Return to Collecting Bars.

---

## Step 5 – Equal High / Equal Low Handling

If two pivots are equal within the configured tolerance:

- Treat as Equal High or Equal Low
- Do not create duplicate SwingPoints
- Preserve deterministic ordering

---

## Step 6 – ATR Validation

If ATR validation is enabled:

- Calculate ATR
- Compare swing distance against ATR multiplier

If below threshold:

Reject the swing.

---

## Step 7 – Duplicate Prevention

Before storing a SwingPoint:

Verify:

- Timestamp uniqueness
- Index uniqueness
- Price uniqueness within tolerance

Duplicate swings SHALL be ignored.

---

## Step 8 – Confirm Swing

Create an immutable SwingPoint.

Populate all required metadata.

Append to confirmed swing history.

---

## Step 9 – Publish Result

Return the confirmed SwingPoint to downstream modules.

Notify:

- BOS Detector
- CHoCH Detector
- Liquidity Detector
- Order Block Detector
- Fair Value Gap Detector

---

## Step 10 – Continue Streaming

Resume monitoring the next completed candle.

The detector SHALL never stop after detecting a swing.

Streaming execution SHALL continue indefinitely.

---

## Non-Repainting Guarantee

Once a SwingPoint has been confirmed:

- Price SHALL never change.
- Timestamp SHALL never change.
- Swing type SHALL never change.
- Confirmation SHALL never be revoked.

Confirmed swings are immutable.

# 10. Public API

## SwingDetector

The Swing Detection Engine SHALL expose a single public detector interface.

---

### Constructor

Purpose:

Initialize the detector with a valid SwingDetectorConfig.

Inputs:

- SwingDetectorConfig

Outputs:

- SwingDetector

Exceptions:

- InvalidConfigurationError

---

### update(bar)

Purpose:

Process one completed MarketBar.

Inputs:

- MarketBar

Outputs:

- Optional[SwingPoint]

Behavior:

- Validate the input bar.
- Update internal state.
- Detect potential pivots.
- Confirm valid swings.
- Return a confirmed SwingPoint if one is detected.
- Otherwise return None.

---

### process_bar(bar)

Purpose:

Alias for update() to support TradingPipeline integration.

Inputs:

- MarketBar

Outputs:

- Optional[SwingPoint]

---

### get_last_swing()

Purpose:

Return the most recently confirmed SwingPoint.

Outputs:

- SwingPoint
- None if no swings exist.

---

### get_swings()

Purpose:

Return all confirmed SwingPoints.

Outputs:

- List[SwingPoint]

---

### reset()

Purpose:

Reset detector state.

Behavior:

- Clear internal history.
- Clear pending pivots.
- Clear confirmed swings.
- Return to Waiting state.

---

### get_state()

Purpose:

Return current detector runtime state.

Outputs:

- SwingDetectorState

---

# 11. Validation Rules

The detector SHALL enforce the following validation rules.

## Market Data Validation

- Completed candles only.
- Chronological timestamps.
- Valid OHLC values.
- Non-negative volume.

---

## Swing Validation

- Left pivot confirmation.
- Right pivot confirmation.
- Minimum swing distance.
- Equal High tolerance.
- Equal Low tolerance.
- ATR validation (optional).

---

## Duplicate Prevention

Duplicate SwingPoints SHALL NOT be created when:

- Timestamp matches.
- Index matches.
- Price matches within tolerance.

---

## Confirmation Rules

A swing SHALL NOT be confirmed until:

- All required right-side candles exist.
- ATR validation succeeds (if enabled).
- Duplicate validation succeeds.

---

# 12. Performance Requirements

The Swing Detection Engine SHALL satisfy the following requirements.

Time Complexity

- O(n)

Memory Complexity

- O(n)

Streaming

- Process one completed candle at a time.

Historical Replay

- Sequential replay without recalculation.

Latency Target

- Less than 1 millisecond per candle under normal operating conditions.

Scalability

- Support datasets exceeding one million candles.

Determinism

- Identical input SHALL always produce identical output.

---

# 13. Integration Requirements

The detector SHALL integrate with:

## Market Data

Consumes:

- Completed MarketBar objects.

Produces:

- Confirmed SwingPoint objects.

---

## Break of Structure

Consumes confirmed SwingPoints.

---

## CHoCH

Consumes confirmed SwingPoints.

---

## Liquidity Detection

Uses SwingPoints to identify liquidity pools.

---

## Order Block Detection

Uses confirmed SwingPoints as structural anchors.

---

## Fair Value Gap Detection

Uses market structure context from confirmed swings.

---

## Trading Pipeline

The TradingPipeline SHALL call:

update(bar)

for every completed candle.

---

## Backtesting Engine

Historical replay SHALL use the same detector implementation as live trading.

No separate backtesting implementation SHALL exist.

---

# 14. Error Handling

Recoverable Errors

- Invalid candle.
- Missing candle.
- Duplicate candle.
- Out-of-order candle.

Fatal Errors

- Invalid configuration.
- Corrupted detector state.
- Unsupported data type.

Behavior

Recoverable errors SHALL be logged.

Fatal errors SHALL raise exceptions.

The detector SHALL never silently ignore fatal failures.

---

# 15. Logging Requirements

The detector SHALL support structured logging.

Events include:

- Detector initialized.
- Detector reset.
- Candle processed.
- Potential pivot detected.
- Swing confirmed.
- Swing rejected.
- Duplicate ignored.
- ATR validation failed.
- Replay started.
- Replay completed.
- Configuration loaded.

Debug logging SHALL be configurable.

---

# 16. Testing Requirements

The implementation SHALL include automated unit tests covering:

## Functional Tests

- Swing High detection.
- Swing Low detection.
- Equal High handling.
- Equal Low handling.
- Duplicate prevention.
- ATR validation.
- Pivot confirmation.

---

## Streaming Tests

- Continuous streaming.
- Replay processing.
- Restart recovery.

---

## Market Condition Tests

- Strong uptrend.
- Strong downtrend.
- Sideways market.
- High volatility.
- Low volatility.
- News spikes.
- Weekend gaps.
- Flash crashes.

---

## Performance Tests

- One million candle replay.
- Memory usage.
- Latency benchmark.

---

## Validation Tests

- No repaint verification.
- Deterministic output.
- Configuration validation.

---

# 17. Acceptance Criteria

The Swing Detection Engine SHALL be considered production-ready only when:

- All unit tests pass.
- Integration tests pass.
- Historical replay produces deterministic results.
- Live streaming produces deterministic results.
- No confirmed swing repaints.
- Performance requirements are satisfied.
- Documentation is complete.
- Code review is approved.
- Integration with the TradingPipeline is verified.
- The detector successfully provides SwingPoint objects for downstream Market Structure modules.

---

# End of Specification

