# Price Zone Specification

**Document ID:** SMC-SPEC-010

**Version:** 1.0

**Status:** Draft

**Project:** Trading Intelligence Platform

**Module:** Market Structure Engine

---

# 1. Purpose

The Price Zone Specification defines the common representation of institutional price zones used throughout the Market Structure Engine.

A Price Zone represents a bounded price region identified by one or more structural detectors.

The specification establishes a shared data model, lifecycle, ownership rules, and behavioral contract for all zone-based detectors.

Price Zones provide a consistent interface for:

- Liquidity Structures
- Order Blocks
- Fair Value Gaps
- Breaker Blocks
- Future institutional zone types

This specification does not define how individual zones are detected.

Detection logic remains the responsibility of the owning detector.

---

# 2. Scope

This specification defines the common behavior shared by every institutional price zone.

It SHALL define:

- Common zone properties
- Common lifecycle
- Ownership model
- Zone state
- Zone measurements
- Zone identifiers
- Common interfaces

It SHALL NOT define:

- Swing detection
- BOS detection
- CHOCH detection
- Liquidity algorithms
- Order Block algorithms
- Fair Value Gap algorithms
- Breaker algorithms

These remain detector-specific responsibilities.

---

# 3. Owner

Each Price Zone shall have exactly one owning detector.

Examples include:

| Zone Type | Owner |
|-----------|-------|
| Liquidity Structure | Liquidity Detector |
| Order Block Zone | Order Block Detector |
| Fair Value Gap Zone | Fair Value Gap Detector |
| Breaker Block Zone | Breaker Block Detector |

No detector may modify the state of a Price Zone owned by another detector.

---

# 4. Responsibilities

A Price Zone shall provide a common representation of institutional price regions.

Every Price Zone shall:

- Store immutable creation information.
- Store immutable geometric information.
- Maintain lifecycle state.
- Maintain measurements.
- Expose identifiers.
- Support deterministic replay.
- Support incremental updates.

Price Zones shall never generate trading signals.

---

# 5. Common Properties

Every Price Zone shall expose the following immutable properties.

| Property | Description |
|----------|-------------|
| Zone ID | Globally unique identifier |
| Zone Type | Liquidity, Order Block, FVG, Breaker |
| Direction | Bullish or Bearish |
| High | Upper boundary |
| Low | Lower boundary |
| Midpoint | Zone midpoint |
| Height | Zone height |
| Created Time | Creation timestamp |
| Source Detector | Detector that created the zone |

These values shall never change after creation.

---

# 6. Mutable Properties

The owning detector may update the following properties.

| Property | Description |
|----------|-------------|
| Lifecycle State | Active, Filled, Invalidated, Expired |
| Last Interaction | Most recent interaction |
| Interaction Count | Number of interactions |
| Last Updated | Last lifecycle update |

Only the owning detector may modify these fields.

---

# 7. Outputs

A Price Zone provides:

- Immutable geometry
- Immutable identifiers
- Mutable lifecycle state
- Quantitative measurements
- References to originating events

Price Zones are consumed by downstream detectors and analytical components.

---

# 8. Configuration

The Price Zone abstraction itself has no configurable parameters.

Configuration belongs exclusively to the detector responsible for creating the zone.

The Price Zone shall remain independent of detector-specific configuration.

---

---

# 9. Lifecycle

Every Price Zone shall progress through a deterministic lifecycle.

The lifecycle represents the operational state of the zone throughout its existence.

Each zone type may omit unsupported states, but the lifecycle model remains identical.

```text
Created
    │
    ▼
Confirmed
    │
    ▼
Active
    │
    ├── Tested
    │
    ├── Partially Filled
    │
    ├── Fully Filled
    │
    ├── Mitigated
    │
    ├── Invalidated
    │
    └── Expired
```

Lifecycle transitions shall occur only through the owning detector.

Historical lifecycle transitions shall remain reproducible.

---

## 9.1 Created

A Price Zone enters the Created state immediately after successful detection.

The Created state indicates:

- Geometry has been established.
- Zone identifier has been assigned.
- Initial measurements have been computed.

No trading significance is implied until confirmation succeeds.

---

## 9.2 Confirmed

A zone becomes Confirmed after satisfying all detector-specific validation rules.

Confirmation requirements are defined by the owning detector.

After confirmation:

- Zone geometry becomes immutable.
- Zone identifier becomes immutable.
- Creation timestamp becomes immutable.

---

## 9.3 Active

A Confirmed Price Zone enters the Active state.

Active zones are eligible for:

- Interaction
- Feature extraction
- Visualization
- Research analysis

Only Active zones may participate in downstream processing.

---

## 9.4 Tested

A zone becomes Tested when price interacts with the zone without satisfying fill, mitigation, or invalidation requirements.

Testing records market interaction while preserving zone validity.

Multiple tests may occur during the zone lifetime.

---

## 9.5 Partially Filled

Applicable to zone types supporting fill behavior.

Examples include:

- Fair Value Gaps
- Liquidity Structures

Partial fill indicates that price has entered the zone without completely traversing it.

---

## 9.6 Fully Filled

A zone becomes Fully Filled when configured fill requirements are satisfied.

The owning detector determines:

- Fill percentage
- Fill threshold
- Completion rules

---

## 9.7 Mitigated

A zone becomes Mitigated when a confirmed mitigation interaction occurs.

Mitigation shall be determined using immutable Mitigation Events.

Only the owning detector may update the lifecycle state.

---

## 9.8 Invalidated

A zone becomes Invalidated when market structure permanently invalidates its intended purpose.

Invalidation rules are detector-specific.

Zone geometry shall remain immutable.

---

## 9.9 Expired

A zone becomes Expired when it exceeds its configured lifetime or expiration criteria.

Expiration does not remove the zone from historical records.

Expired zones remain available for:

- Historical replay
- Analytics
- Feature engineering

---

# 10. State Management

Each Price Zone maintains runtime state required for deterministic processing.

Runtime state includes:

- Lifecycle State
- Interaction Count
- Last Interaction Timestamp
- Last Updated Timestamp

Runtime state shall be mutable only by the owning detector.

Historical state transitions shall remain reproducible.

---

## Runtime Updates

Lifecycle updates shall occur only when:

- New completed MarketBars are processed.
- Detector validation succeeds.
- Valid interaction events occur.

Incomplete market data shall never modify zone state.

---

## Reset Behavior

Reset operations shall:

- Clear runtime state.
- Reinitialize active zone collections.
- Preserve deterministic behavior during replay.

Historical zone definitions remain reproducible after reset.

---

# 11. Ownership Rules

Each Price Zone has exactly one owner.

Ownership shall never transfer between detectors.

The owning detector is solely responsible for:

- Zone creation
- Lifecycle transitions
- Runtime state updates
- Zone retirement

Other detectors may consume Price Zones but shall never modify them.

---

## Ownership Matrix

| Zone Type | Owner |
|------------|-------|
| Liquidity Structure | Liquidity Detector |
| Order Block Zone | Order Block Detector |
| Fair Value Gap Zone | Fair Value Gap Detector |
| Breaker Block Zone | Breaker Block Detector |

Mitigation Block Detector does not own Price Zones.

---

# 12. Interaction Rules

Price Zones are passive structural objects.

Interactions are represented by immutable events.

Examples include:

- Mitigation Event
- Fill Event
- Retest Event
- Sweep Event

Interaction events reference Price Zones using immutable identifiers.

Price Zones shall not own interaction history directly.

Interaction history belongs to the detector that owns the interaction event.

---

# 13. Deterministic Guarantees

The Price Zone abstraction shall satisfy the following guarantees.

## Historical Replay

Identical historical market data shall always produce identical Price Zones.

---

## Immutable Geometry

After confirmation:

- High
- Low
- Midpoint
- Height
- Identifier
- Creation Timestamp

shall never change.

---

## Deterministic Lifecycle

Lifecycle transitions shall occur only through deterministic detector logic.

Identical replay shall produce identical transitions.

---

## Sequential Processing

Completed MarketBars shall be processed strictly in chronological order.

---

## Idempotent Processing

Processing identical historical data multiple times shall always produce:

- Identical Price Zones
- Identical lifecycle transitions
- Identical measurements
- Identical runtime state

No detector shall modify Price Zones owned by another detector.

---

---

# 14. Measurements

Every Price Zone shall expose quantitative measurements describing its geometric, structural, and lifecycle characteristics.

Measurements provide standardized inputs for:

- Feature Engineering
- Research Analytics
- Probability Engine
- Visualization

The Price Zone abstraction shall not perform trading analysis or signal generation.

---

## 14.1 Geometric Measurements

Every Price Zone shall compute:

- Zone High
- Zone Low
- Zone Midpoint
- Zone Height
- Zone Width
- Price Range
- Distance From Current Price
- Distance (Points)
- Distance (ATR)
- Distance Percentage

These measurements describe the physical geometry of the zone.

---

## 14.2 Structural Measurements

Every Price Zone shall expose:

- Zone Type
- Direction
- Source Detector
- Creation Timestamp
- Structural Age
- Bars Since Creation
- Lifecycle State

These measurements describe the structural context of the zone.

---

## 14.3 Interaction Measurements

The owning detector may update interaction statistics including:

- Interaction Count
- First Interaction Timestamp
- Last Interaction Timestamp
- Last Update Timestamp

The Price Zone itself shall not determine interaction quality.

Interaction quality remains the responsibility of the detector that owns the interaction event.

---

## 14.4 Quality Measurements

The owning detector may compute detector-specific quality measurements.

Examples include:

- Liquidity Strength
- Order Block Strength
- Fair Value Gap Strength
- Breaker Strength

The Price Zone abstraction shall not define quality algorithms.

---

# 15. Common Interfaces

Every Price Zone implementation shall expose a common public interface.

Required properties include:

- Zone Identifier
- Zone Type
- Direction
- High
- Low
- Midpoint
- Height
- Lifecycle State
- Creation Timestamp

Required behaviors include:

- Retrieve geometry
- Retrieve lifecycle state
- Retrieve measurements
- Determine whether the zone is active
- Determine whether the zone is expired

Detector-specific behaviors shall remain outside the common interface.

---

# 16. Failure Cases

The Price Zone abstraction shall safely handle the following conditions.

## Invalid Geometry

If the upper boundary is less than or equal to the lower boundary:

- Zone creation shall fail.

---

## Invalid Identifier

If a unique identifier cannot be assigned:

- Zone creation shall fail.

---

## Invalid Lifecycle Transition

If an illegal lifecycle transition is attempted:

- The transition shall be rejected.
- Current state shall remain unchanged.

---

## Duplicate Zone

If a detector attempts to create an equivalent zone that already exists:

- Duplicate handling shall be performed by the owning detector.

---

## Historical Replay

Historical replay shall always reproduce identical Price Zones.

---

## Reset

Reset operations shall restore runtime state without affecting deterministic replay.

---

# 17. Performance Requirements

The Price Zone abstraction shall satisfy the following requirements.

## Processing

- Incremental updates
- Streaming compatible
- Low-overhead lifecycle management

---

## Memory

The Price Zone shall store only the information required to represent:

- Geometry
- Lifecycle
- Measurements
- References

Historical storage limits shall be configurable by the owning detector.

---

## Determinism

Identical historical market data shall always produce:

- Identical Price Zones
- Identical lifecycle states
- Identical measurements

---

## Scalability

The abstraction shall support:

- Long historical replay
- Continuous live execution
- Thousands of concurrent active zones

---

# 18. Integration

The Price Zone abstraction is shared across all zone-based detectors.

```text
                 PriceZone
                     │
      ┌──────────────┼──────────────┐
      │              │              │
      ▼              ▼              ▼
Liquidity      Order Block     Fair Value Gap
Structure         Zone              Zone
                                      │
                                      ▼
                              Breaker Block
                                   Zone
```

All downstream components consume the common Price Zone interface.

These include:

- Mitigation Block Detector
- Feature Engineering
- Research Analytics
- Probability Engine
- Visualization

The Price Zone abstraction does not depend on any detector implementation.

---

# 19. Unit Test Requirements

The implementation shall include automated tests covering the following categories.

## Geometry Tests

- Boundary validation
- Midpoint calculation
- Height calculation
- Width calculation

---

## Lifecycle Tests

- Valid lifecycle transitions
- Invalid lifecycle transitions
- State persistence
- State restoration

---

## Ownership Tests

- Single ownership enforcement
- Read-only access by non-owning detectors
- Immutable geometry after confirmation

---

## Replay Tests

- Historical replay
- Incremental updates
- Deterministic state transitions

---

## Serialization Tests

- Save and restore zone state
- Stable identifiers
- Measurement persistence

---

# 20. Future Enhancements

Potential future enhancements include:

- Hierarchical Price Zones
- Composite Zone Groups
- Multi-Timeframe Zone Relationships
- Zone Clustering
- Dynamic Zone Compression
- Machine Learning Assisted Zone Ranking

Future enhancements shall remain backward compatible with this specification.

---

# 21. Acceptance Criteria

The Price Zone abstraction shall be considered production-ready only when:

- All unit tests pass.
- Geometry is immutable after confirmation.
- Lifecycle transitions are deterministic.
- Ownership rules are enforced.
- Historical replay produces identical results.
- Serialization is stable.
- Documentation is complete.
- Code review is approved.
- Integration with all zone-based detectors is verified.

---

# End of Specification