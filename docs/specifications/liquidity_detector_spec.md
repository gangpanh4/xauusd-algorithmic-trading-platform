# Liquidity Detector Specification

**Document ID:** SMC-SPEC-005

**Version:** 1.0

**Status:** Draft

**Project:** Trading Intelligence Platform

**Module:** Market Structure Engine

---

# 1. Purpose

The Liquidity Detector is responsible for identifying institutional liquidity areas within market structure.

Liquidity represents locations where resting orders are likely to accumulate and where price is likely to react through sweeps, grabs, or engineered stop hunts.

The detector consumes completed MarketBars, confirmed Swing Events, BOS Events, and CHOCH Events to identify objective liquidity structures.

The Liquidity Detector produces immutable Liquidity Events and quantitative measurements for downstream components.

Confirmed Liquidity Events provide structural context for:

- Order Block Engine
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

The Liquidity Detector is responsible only for identifying institutional liquidity structures.

The detector SHALL:

- Detect Buy-side Liquidity
- Detect Sell-side Liquidity
- Detect Equal High Liquidity
- Detect Equal Low Liquidity
- Detect Liquidity Clusters
- Detect Liquidity Sweeps
- Produce immutable Liquidity Events
- Produce quantitative Liquidity measurements
- Support historical replay
- Support live streaming execution

The detector SHALL NOT:

- Detect Swing Highs
- Detect Swing Lows
- Detect BOS
- Detect CHOCH
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
LiquidityDetector
```

The Liquidity Detector is the sole owner of:

- Liquidity Events
- Liquidity History
- Liquidity Measurements
- Liquidity Detector State

The detector does not own:

- Swing Events
- BOS Events
- CHOCH Events
- Current Trend
- Protected Swing

These remain under their respective detectors.

---

# 4. Responsibilities

The Liquidity Detector shall:

- Consume Swing Events
- Consume BOS Events
- Consume CHOCH Events
- Identify Buy-side Liquidity
- Identify Sell-side Liquidity
- Identify Equal High Liquidity
- Identify Equal Low Liquidity
- Detect Liquidity Sweeps
- Prevent duplicate Liquidity Events
- Produce immutable Liquidity Events
- Maintain detector runtime state
- Compute Liquidity measurements
- Expose measurements for Feature Engineering
- Operate deterministically
- Operate incrementally
- Support historical replay
- Support continuous streaming execution

---

# 5. Dependencies

## Consumes

The Liquidity Detector consumes:

- Completed MarketBar
- Swing Events
- BOS Events
- CHOCH Events
- LiquidityDetectorConfig
- Internal Liquidity State

The detector does not consume Order Blocks or Fair Value Gaps.

---

## Produces

The Liquidity Detector produces:

- LiquidityEvent
- Updated Liquidity State
- Liquidity Measurements
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

Configuration parameters include:

- Equal Level Tolerance
- Minimum Liquidity Cluster Size
- Maximum Cluster Width
- ATR Validation
- ATR Period
- ATR Multiplier
- Sweep Confirmation

All configuration shall be immutable after detector initialization.

---

# 7. Outputs

The Liquidity Detector produces immutable Liquidity Events.

Each Liquidity Event shall include:

- Event ID
- Timestamp
- Liquidity Type
- Direction
- Price Level
- Source Structure
- Sweep Status
- Confirmation Bar

The detector also produces:

- Updated Liquidity State
- Liquidity Measurements
- Feature Engineering Inputs

When no Liquidity Event is detected, the detector shall produce no event.

---

# 8. Configuration

The Liquidity Detector shall support configuration through the LiquidityDetectorConfig object.

The following parameters shall be configurable.

| Parameter | Description |
|------------|-------------|
| Equal Level Tolerance | Maximum price deviation between equal highs/lows |
| Minimum Liquidity Cluster Size | Minimum number of matching levels |
| Maximum Cluster Width | Maximum allowable cluster range |
| ATR Validation | Enable volatility filtering |
| ATR Period | ATR calculation period |
| ATR Multiplier | Minimum volatility requirement |
| Sweep Confirmation | Require close beyond liquidity level |

Configuration values adjust detector sensitivity but shall not alter ownership or detector responsibilities.

---

---

# 9. Detection Rules

The Liquidity Detector shall identify institutional liquidity structures using completed MarketBars, confirmed Swing Events, BOS Events, and CHOCH Events.

A Liquidity Event represents a price level or price region where resting orders are likely to accumulate or where liquidity has been consumed.

The detector shall evaluate only completed MarketBars.

The detector shall never predict future price movement.

---

## 9.1 Buy-side Liquidity

Buy-side Liquidity represents resting buy-stop orders positioned above significant market highs.

The detector shall identify Buy-side Liquidity when one or more of the following conditions exist:

- Equal Highs
- Multiple Swing Highs within tolerance
- Liquidity Cluster above current price
- Unclaimed Swing High
- Previous Structural High

Once confirmed:

- A Buy-side Liquidity Event shall be emitted.
- The event shall be immutable.

---

## 9.2 Sell-side Liquidity

Sell-side Liquidity represents resting sell-stop orders positioned below significant market lows.

The detector shall identify Sell-side Liquidity when one or more of the following conditions exist:

- Equal Lows
- Multiple Swing Lows within tolerance
- Liquidity Cluster below current price
- Unclaimed Swing Low
- Previous Structural Low

Once confirmed:

- A Sell-side Liquidity Event shall be emitted.
- The event shall be immutable.

---

## 9.3 Equal High Liquidity

Equal High Liquidity exists when multiple significant highs occur within the configured Equal Level Tolerance.

The detector shall group qualifying highs into a single liquidity structure.

Equal High Liquidity shall remain valid until:

- Swept
- Invalidated
- Expired according to configuration

---

## 9.4 Equal Low Liquidity

Equal Low Liquidity exists when multiple significant lows occur within the configured Equal Level Tolerance.

The detector shall group qualifying lows into a single liquidity structure.

Equal Low Liquidity shall remain valid until:

- Swept
- Invalidated
- Expired according to configuration

---

## 9.5 Liquidity Clusters

Liquidity Clusters represent concentrated areas of resting liquidity.

The detector shall identify clusters using:

- Swing density
- Price proximity
- Equal structural levels
- Configured cluster width

A Liquidity Cluster may contain:

- Equal Highs
- Equal Lows
- Mixed structural levels

Clusters shall be treated as single liquidity objects.

---

## 9.6 Liquidity Sweep

A Liquidity Sweep occurs when price temporarily trades through a valid liquidity structure before returning.

Sweep confirmation may require:

- Price penetration
- Candle close validation
- ATR validation (if enabled)

When confirmed:

- Existing Liquidity Event shall be marked as Swept.
- A Liquidity Sweep Event shall be emitted.

The original Liquidity Event remains immutable.

---

## 9.7 Liquidity Consumption

A liquidity structure is considered consumed when:

- Price permanently breaks through the liquidity zone.
- The configured confirmation rules succeed.
- The liquidity can no longer influence future market structure.

Consumed liquidity shall be marked accordingly.

---

## 9.8 Duplicate Prevention

Before confirming a Liquidity Event, the detector shall verify that an equivalent Liquidity Event has not already been emitted.

Duplicate Liquidity Events shall not be produced.

---

# 10. Confirmation Rules

A Liquidity Event shall only be confirmed after all applicable validation rules succeed.

Validation may include:

- Equal Level validation
- Cluster validation
- Minimum member count
- ATR validation
- Sweep confirmation
- Duplicate validation

Once confirmed:

- Event ID shall never change.
- Liquidity Type shall never change.
- Price Level shall never change.
- Source Structure shall never change.
- Confirmation Timestamp shall never change.

Confirmed Liquidity Events are immutable.

---

# 11. State Management

The Liquidity Detector maintains only the runtime state required for deterministic liquidity detection.

The detector state includes:

- Active Liquidity Structures
- Liquidity History
- Last Liquidity Event
- Internal Processing State

The detector shall update its internal state incrementally after every completed MarketBar.

Reset operations shall restore the detector to its initial state.

---

## Active Liquidity Lifecycle

Each liquidity structure progresses through the following lifecycle:

```text
Detected
      │
      ▼
Confirmed
      │
      ▼
Active
      │
      ├── Swept
      │
      ├── Consumed
      │
      └── Expired
```

The lifecycle state shall be deterministic and immutable once transitioned.

---

# 12. State Ownership

The Liquidity Detector is the authoritative owner of:

- Liquidity Events
- Liquidity History
- Liquidity Measurements
- Active Liquidity Structures
- Internal Detector State

The Liquidity Detector shall never modify:

- Swing Events
- BOS Events
- CHOCH Events
- Current Trend
- Protected Swing

Communication between detectors shall occur exclusively through immutable events.

---

# 13. Deterministic Guarantees

The Liquidity Detector shall satisfy the following guarantees.

## Historical Replay

Historical replay shall always produce identical Liquidity Events for identical market data.

---

## Live Streaming

Live execution shall produce identical Liquidity Events as historical replay.

---

## Non-Repainting

Confirmed Liquidity Events shall never be modified after confirmation.

Lifecycle transitions (e.g., Active → Swept → Consumed) shall update detector state without altering the original immutable event.

---

## Sequential Processing

Completed MarketBars shall be processed strictly in chronological order.

---

## Idempotent Processing

Processing identical historical data multiple times shall always produce:

- Identical Liquidity Events
- Identical Liquidity Measurements
- Identical Detector State

The detector shall never modify the state owned by Swing, BOS, or CHOCH detectors.

---

# 14. Measurements

The Liquidity Detector shall expose quantitative measurements describing each confirmed Liquidity Event.

Measurements provide objective information for Feature Engineering, Research Analytics, and the Probability Engine.

The detector shall not generate trading signals or trading decisions.

---

## 14.1 Price Measurements

The detector shall compute:

- Liquidity Price Level
- Cluster High
- Cluster Low
- Cluster Width
- Distance From Current Price
- Distance (Points)
- Distance (ATR)
- Distance Percentage

These measurements describe the spatial characteristics of the liquidity structure.

---

## 14.2 Structural Measurements

The detector shall compute:

- Number of Contributing Swings
- Cluster Density
- Structural Age
- Swing Distribution
- Liquidity Type

These measurements describe the composition of the liquidity structure.

---

## 14.3 Sweep Measurements

When a Liquidity Sweep occurs, the detector shall compute:

- Sweep Distance
- Sweep Depth
- Sweep Duration
- Recovery Distance
- Recovery Time
- Sweep ATR Multiple

These measurements quantify the quality of the liquidity sweep.

---

## 14.4 Quality Measurements

The detector may compute:

- Liquidity Strength
- Liquidity Confidence
- Cluster Quality
- Sweep Quality
- Reaction Strength

These measurements describe the quality of the liquidity structure rather than simply its existence.

---

# 15. Feature Engineering Outputs

The Liquidity Detector exposes quantitative features for downstream statistical analysis and machine learning.

Typical exported features include:

- liquidity_distance
- liquidity_distance_atr
- liquidity_strength
- liquidity_confidence
- cluster_density
- cluster_width
- liquidity_age
- sweep_distance
- sweep_depth
- sweep_quality
- reaction_strength

Feature Engineering is responsible for:

- Feature normalization
- Scaling
- Weighting
- Selection
- Transformation

The Liquidity Detector shall not perform these operations.

---

# 16. Failure Cases

The Liquidity Detector shall safely handle the following conditions.

## No Valid Swing Events

If no confirmed Swing Events exist:

- No Liquidity Event shall be emitted.
- Detector state shall remain valid.

---

## Insufficient Cluster Members

If a liquidity cluster does not satisfy the configured minimum cluster size:

- The cluster shall not be confirmed.

---

## Equal Level Validation Failure

If candidate levels exceed the configured Equal Level Tolerance:

- The candidate structure shall be rejected.

---

## ATR Validation Failure

If ATR validation is enabled and fails:

- The Liquidity Event shall not be confirmed.

---

## Invalid Sweep

If price briefly exceeds a liquidity level but confirmation requirements fail:

- No Liquidity Sweep Event shall be emitted.

The original Liquidity Structure shall remain active.

---

## Duplicate Liquidity

Duplicate Liquidity Events shall be rejected.

---

## Historical Replay

Historical replay shall always reproduce identical Liquidity Events.

---

## Detector Reset

Reset operations shall clear runtime state while preserving deterministic behavior for future processing.

---

# 17. Performance Requirements

The Liquidity Detector shall satisfy the following requirements.

## Processing

- Incremental execution
- One completed MarketBar per update
- Streaming compatible

---

## Memory

The detector shall maintain only the runtime state required for deterministic liquidity analysis.

Historical storage shall respect configured limits.

---

## Determinism

Identical historical market data shall always produce:

- Identical Liquidity Events
- Identical Liquidity Measurements
- Identical Detector State

---

## Scalability

The detector shall support:

- Long historical replay
- Continuous live execution
- High-frequency market updates

---

# 18. Integration

The Liquidity Detector is the fourth stage of the Market Structure Engine.

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
      ├── Order Block Engine
      ├── Fair Value Gap Engine
      ├── Breaker Block Engine
      ├── Mitigation Block Engine
      ├── Feature Engineering
      ├── Research Analytics
      └── Probability Engine
```

The Liquidity Detector is the authoritative owner of:

- Liquidity Events
- Liquidity Structures
- Liquidity Measurements
- Liquidity History

The Liquidity Detector shall never modify:

- Swing Events
- BOS Events
- CHOCH Events
- Current Trend
- Protected Swing

Communication between detectors shall occur exclusively through immutable events.

---

# 19. Unit Test Requirements

The implementation shall include automated tests covering the following categories.

## Functional Tests

- Buy-side Liquidity detection
- Sell-side Liquidity detection
- Equal High detection
- Equal Low detection
- Liquidity Cluster detection
- Liquidity Sweep detection
- Duplicate prevention

---

## Validation Tests

- Equal Level validation
- Cluster validation
- ATR validation
- Sweep confirmation
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
- Multiple liquidity clusters
- Failed liquidity sweeps

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

- Multi-Timeframe Liquidity Analysis
- Liquidity Heat Maps
- Liquidity Probability Estimation
- Dynamic Cluster Formation
- Volume-assisted Liquidity Detection
- Machine Learning Assisted Liquidity Classification

Future enhancements shall remain backward compatible with this specification.

---

# 21. Acceptance Criteria

The Liquidity Detector shall be considered production-ready only when:

- All unit tests pass.
- Integration tests pass.
- Historical replay is deterministic.
- Live execution is deterministic.
- Confirmed Liquidity Events never repaint.
- Liquidity lifecycle transitions are deterministic.
- All performance requirements are satisfied.
- Documentation is complete.
- Code review is approved.
- Integration with the Market Structure Engine is verified.

---

# End of Specification