# Measurement Specification

**Document ID:** SMC-SPEC-012

**Version:** 1.0

**Status:** Draft

**Project:** Trading Intelligence Platform

**Module:** Market Structure Engine

---

# 1. Purpose

The Measurement Specification defines the common representation of quantitative measurements produced by the Market Structure Engine.

A Measurement represents a deterministic numerical description of a confirmed market structure, event, or price zone.

Measurements provide standardized inputs for downstream analytical components while remaining independent of detector-specific implementation details.

This specification establishes the shared data model, ownership rules, lifecycle, and behavioral contract for all measurements generated within the Market Structure Engine.

Measurements provide a common interface for:

- Swing Measurements
- BOS Measurements
- CHOCH Measurements
- Liquidity Measurements
- Order Block Measurements
- Fair Value Gap Measurements
- Breaker Block Measurements
- Mitigation Measurements

This specification does not define detector-specific calculation algorithms.

Calculation logic remains the responsibility of the owning detector.

---

# 2. Scope

This specification defines the common behavior shared by every Measurement.

It SHALL define:

- Measurement ownership
- Measurement identifiers
- Measurement values
- Units of measurement
- Metadata
- References
- Immutability rules
- Common interfaces

It SHALL NOT define:

- Swing scoring algorithms
- BOS scoring algorithms
- CHOCH scoring algorithms
- Liquidity scoring algorithms
- Order Block scoring algorithms
- Fair Value Gap scoring algorithms
- Breaker Block scoring algorithms
- Mitigation scoring algorithms

These remain detector-specific responsibilities.

---

# 3. Owner

Every Measurement shall have exactly one owning detector.

Examples include:

| Measurement Type | Owner |
|------------------|-------|
| Swing Measurements | Swing Detector |
| BOS Measurements | BOS Detector |
| CHOCH Measurements | CHOCH Detector |
| Liquidity Measurements | Liquidity Detector |
| Order Block Measurements | Order Block Detector |
| Fair Value Gap Measurements | Fair Value Gap Detector |
| Breaker Block Measurements | Breaker Block Detector |
| Mitigation Measurements | Mitigation Block Detector |

Ownership shall never transfer.

No detector may modify a measurement owned by another detector.

---

# 4. Responsibilities

A Measurement represents a deterministic numerical description of a confirmed structural observation.

Every Measurement shall:

- Be deterministic.
- Be immutable after publication.
- Have a unique identifier.
- Record its source detector.
- Record its creation timestamp.
- Reference the originating Market Event or Price Zone.
- Support serialization.
- Support historical replay.

Measurements shall never generate trading signals or execute trading decisions.

---

# 5. Common Properties

Every Measurement shall expose the following immutable properties.

| Property | Description |
|----------|-------------|
| Measurement ID | Globally unique identifier |
| Measurement Name | Canonical measurement name |
| Measurement Type | Numeric classification |
| Value | Measured value |
| Unit | Measurement unit |
| Source Detector | Detector that produced the measurement |
| Timestamp | Creation timestamp |
| Version | Measurement schema version |

These properties shall never change after publication.

---

# 6. References

A Measurement may reference one or more structural objects using immutable identifiers.

Examples include:

- MarketEvent ID
- PriceZone ID
- SwingEvent ID
- BOSEvent ID
- CHOCHEvent ID
- LiquidityStructure ID
- OrderBlockZone ID
- FairValueGapZone ID
- BreakerBlockZone ID

Measurements shall reference objects by identifier only.

Referenced objects shall never be duplicated within a Measurement.

---

# 7. Outputs

Every Measurement provides:

- Immutable numerical values
- Immutable metadata
- Immutable references
- Standardized units

Measurements are consumed by:

- Feature Engineering
- Research Analytics
- Probability Engine
- Backtesting
- AI Models
- Visualization

---

# 8. Configuration

The Measurement abstraction has no configurable parameters.

Configuration belongs exclusively to the detector responsible for computing the measurement.

The Measurement abstraction shall remain independent of detector-specific configuration.

---

---

# 9. Measurement Lifecycle

Every Measurement shall follow a deterministic lifecycle.

Unlike runtime calculations, Measurements represent immutable snapshots of confirmed structural information.

Once published, a Measurement shall never be modified.

```text
Calculated
      │
      ▼
Validated
      │
      ▼
Published
      │
      ▼
Archived
```

Historical replay shall always reproduce identical Measurements.

---

## 9.1 Calculated

A Measurement enters the Calculated state when the owning detector computes one or more quantitative values.

At this stage:

- Values exist only within the detector.
- Validation has not completed.
- Measurements are not visible to downstream components.

Calculated measurements are temporary runtime objects.

---

## 9.2 Validated

The detector validates calculated measurements.

Validation may include:

- Numerical validation
- Range validation
- Unit validation
- Configuration validation
- Dependency validation

Validation rules remain detector-specific.

The Measurement abstraction does not define calculation algorithms.

---

## 9.3 Published

A Measurement becomes Published only after successful validation.

Upon publication:

- Measurement ID shall be assigned.
- Timestamp shall be recorded.
- Immutable properties shall be finalized.

Published measurements become available to:

- Feature Engineering
- Research Analytics
- Probability Engine
- Visualization
- Backtesting

Published Measurements shall never change.

---

## 9.4 Archived

Published Measurements become part of the permanent historical dataset.

Archived Measurements remain available for:

- Historical replay
- Analytics
- Machine learning
- Performance evaluation
- Research

Archiving does not modify measurement values.

---

# 10. State Management

Measurements are immutable after publication.

Mutable processing state exists only inside the owning detector during calculation.

After publication, Measurements expose read-only data.

---

## Runtime Processing

The owning detector may maintain temporary calculation state.

Examples include:

- Candidate BOS measurements
- Candidate Liquidity measurements
- Candidate Order Block measurements
- Candidate Mitigation measurements

Temporary calculation state shall never be exposed outside the detector.

Only Published Measurements become part of the public analytical dataset.

---

## Reset Behavior

Reset operations shall:

- Remove temporary calculation state.
- Preserve deterministic replay.
- Recompute identical Measurements from identical historical data.

Published Measurements shall always be reproducible.

---

# 11. Ownership Rules

Each Measurement has exactly one owner.

Ownership shall never transfer.

The owning detector is solely responsible for:

- Measurement calculation
- Validation
- Publication

After publication:

- No detector may modify the Measurement.
- No detector may delete the Measurement.
- No detector may change ownership.

Other components may consume Measurements but shall treat them as read-only.

---

## Ownership Matrix

| Measurement Type | Owner |
|------------------|-------|
| Swing Measurements | Swing Detector |
| BOS Measurements | BOS Detector |
| CHOCH Measurements | CHOCH Detector |
| Liquidity Measurements | Liquidity Detector |
| Order Block Measurements | Order Block Detector |
| Fair Value Gap Measurements | Fair Value Gap Detector |
| Breaker Block Measurements | Breaker Block Detector |
| Mitigation Measurements | Mitigation Block Detector |

Each detector owns only the measurements it produces.

---

# 12. Measurement Relationships

Measurements may reference confirmed structural objects using immutable identifiers.

Examples include:

- MarketEvent ID
- PriceZone ID
- SwingEvent ID
- BOSEvent ID
- CHOCHEvent ID
- LiquidityStructure ID
- OrderBlockZone ID
- FairValueGapZone ID
- BreakerBlockZone ID

Measurements shall never embed full structural objects.

Relationships shall be maintained through immutable identifiers.

This preserves normalization and avoids redundant data.

---

# 13. Deterministic Guarantees

The Measurement abstraction shall satisfy the following guarantees.

## Historical Replay

Identical historical market data shall always produce identical Measurements.

---

## Immutable Measurements

After publication, the following properties shall never change:

- Measurement ID
- Measurement Name
- Measurement Value
- Unit
- Source Detector
- Timestamp
- References
- Metadata

---

## Sequential Processing

Measurements shall be published in the same chronological order as their originating Market Events or Price Zones.

---

## Non-Recalculation

Published Measurements shall never be recalculated or overwritten.

If additional structural information becomes available, a new Measurement shall be produced rather than modifying an existing one.

---

## Idempotent Processing

Processing identical historical data multiple times shall always produce:

- Identical Measurements
- Identical Measurement IDs (if deterministic ID generation is used)
- Identical Values
- Identical References
- Identical Ordering

No detector shall modify Measurements owned by another detector.

---

---

# 14. Measurement Categories

Measurements shall be classified according to their purpose.

Standard categories include:

## Geometric Measurements

Describe the physical characteristics of structural objects.

Examples include:

- Height
- Width
- Midpoint
- Price Range
- Distance
- ATR Distance

---

## Structural Measurements

Describe market structure characteristics.

Examples include:

- Swing Strength
- BOS Distance
- CHOCH Strength
- Liquidity Depth
- Structural Age
- Trend Alignment

---

## Temporal Measurements

Describe time-based characteristics.

Examples include:

- Bar Index
- Bars Since Creation
- Bars Since Confirmation
- Event Duration
- Zone Lifetime

---

## Quality Measurements

Describe confidence or quality.

Examples include:

- Confidence Score
- Quality Score
- Strength Score
- Reliability Score

Quality algorithms remain detector-specific.

---

# 15. Common Interfaces

Every Measurement implementation shall expose a common public interface.

Required properties include:

- Measurement Identifier
- Measurement Name
- Measurement Category
- Numeric Value
- Measurement Unit
- Source Detector
- Timestamp
- References

Required behaviors include:

- Retrieve metadata
- Retrieve value
- Retrieve unit
- Retrieve references
- Serialize
- Deserialize

Measurements shall expose no mutable operations.

---

# 16. Failure Cases

The Measurement abstraction shall safely handle the following conditions.

## Invalid Value

If a calculated value is invalid (NaN, infinite, or otherwise undefined):

- Validation shall fail.
- The Measurement shall not be published.

---

## Invalid Unit

If the unit is unsupported or inconsistent with the measurement type:

- Validation shall fail.

---

## Missing Required Reference

If a required Market Event or Price Zone reference cannot be resolved:

- Publication shall fail.

Optional references may remain unset.

---

## Duplicate Measurement

If an equivalent published Measurement already exists:

- Duplicate handling shall be performed by the owning detector.

---

## Historical Replay

Historical replay shall always reproduce identical Measurements.

---

## Reset

Reset operations shall remove temporary calculation state while preserving deterministic replay behavior.

---

# 17. Performance Requirements

The Measurement abstraction shall satisfy the following requirements.

## Processing

- Incremental calculation
- Streaming compatible
- Low-overhead publication

---

## Memory

Measurements shall remain lightweight.

They shall contain only:

- Metadata
- Numeric values
- References
- Units

Large datasets shall not be embedded inside Measurements.

---

## Determinism

Identical historical market data shall always produce:

- Identical Measurements
- Identical Values
- Identical References
- Identical Ordering

---

## Scalability

The abstraction shall support:

- Long historical replay
- Continuous live execution
- Millions of historical measurements

---

# 18. Integration

Measurements provide the quantitative bridge between Market Structure and analytical components.

```text
Market Structure
       │
       ▼
 Measurements
       │
       ├── Feature Engineering
       ├── Research Analytics
       ├── Probability Engine
       ├── Backtesting
       ├── Machine Learning
       └── Visualization
```

Measurements shall remain detector-independent.

All downstream systems consume the common Measurement interface rather than detector-specific implementations.

Measurements shall never contain business logic for:

- Trading decisions
- Risk management
- Position sizing
- Strategy execution

Those responsibilities belong to downstream modules.

---

# 19. Unit Test Requirements

The implementation shall include automated tests covering the following categories.

## Calculation Tests

- Numeric calculation
- Unit assignment
- Metadata assignment
- Reference assignment

---

## Validation Tests

- Value validation
- Unit validation
- Reference validation
- Duplicate detection

---

## Immutability Tests

- Read-only values
- Immutable metadata
- Immutable references
- Stable serialization

---

## Replay Tests

- Historical replay
- Deterministic values
- Stable ordering
- Stable identifiers

---

## Integration Tests

- Feature Engineering consumption
- Research Analytics consumption
- Probability Engine consumption
- Serialization compatibility

---

# 20. Future Enhancements

Potential future enhancements include:

- Composite Measurements
- Multi-Timeframe Measurements
- Measurement Aggregation
- Statistical Confidence Intervals
- Measurement Compression
- Distributed Measurement Storage

Future enhancements shall remain backward compatible with this specification.

---

# 21. Acceptance Criteria

The Measurement abstraction shall be considered production-ready only when:

- All unit tests pass.
- Measurements are immutable after publication.
- Ownership rules are enforced.
- Historical replay is deterministic.
- Serialization is stable.
- Measurement ordering is deterministic.
- Documentation is complete.
- Code review is approved.
- Integration with all Market Structure detectors is verified.

---

# End of Specification