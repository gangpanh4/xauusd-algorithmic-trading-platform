# ADR-011: Market Structure Architecture

**Status:** Accepted

**Date:** 2026-07-19

**Decision Makers:** Trading Intelligence Platform Development Team

---

# Context

The Trading Intelligence Platform requires a deterministic, modular, and extensible Market Structure Engine capable of supporting:

- Historical replay
- Live streaming
- Feature engineering
- Research analytics
- Probability estimation
- Future machine learning integration

Early implementations tightly coupled detector logic, runtime state, and downstream consumers. Individual detectors exposed implementation-specific outputs, making integration difficult and increasing maintenance complexity.

A unified architecture was required to standardize communication between detectors while preserving detector independence.

---

# Decision

The Market Structure Engine shall adopt an event-driven architecture based on immutable shared contracts.

The architecture is composed of independent detectors that communicate only through standardized immutable objects.

The primary architectural flow is:

```text
Completed MarketBar
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
        ▼
Measurements
        │
        ▼
Feature Engineering
        │
        ▼
Market Structure API
```

---

# Architectural Principles

## Deterministic Processing

The Market Structure Engine shall be deterministic.

Identical historical market data shall always produce identical:

- Market Events
- Price Zones
- Measurements
- Features

Historical replay and live execution shall behave identically.

---

## Single Responsibility

Each detector owns exactly one structural concept.

Examples include:

- Swing Detector
- BOS Detector
- CHOCH Detector
- Liquidity Detector
- Order Block Detector
- Fair Value Gap Detector
- Breaker Block Detector
- Mitigation Block Detector

Detectors shall not perform responsibilities assigned to other detectors.

---

## Single Ownership

Every structural object has exactly one owner.

Examples include:

| Object | Owner |
|---------|-------|
| SwingEvent | Swing Detector |
| BOSEvent | BOS Detector |
| CHOCHEvent | CHOCH Detector |
| LiquidityStructure | Liquidity Detector |
| OrderBlockZone | Order Block Detector |
| FairValueGapZone | Fair Value Gap Detector |
| BreakerBlockZone | Breaker Block Detector |
| MitigationEvent | Mitigation Block Detector |

Ownership shall never transfer.

---

## Immutable Communication

Published objects are immutable.

The following objects shall never be modified after publication:

- Market Events
- Price Zones (geometry)
- Measurements
- Features

If new information becomes available, new objects shall be created instead of modifying historical objects.

---

## Event-Driven Communication

Detectors communicate through immutable published objects.

No detector may directly modify:

- Internal runtime state
- Private collections
- Candidate structures
- Processing buffers

Communication occurs only through shared contracts.

---

## Layered Architecture

The Market Structure Engine is divided into distinct layers.

```text
Market Structure Detection
        │
        ▼
Measurements
        │
        ▼
Feature Engineering
        │
        ▼
Probability Engine
```

Each layer has clearly defined responsibilities.

---

# Shared Contracts

The following shared contracts standardize communication throughout the engine.

## PriceZone

Represents persistent institutional price regions.

Examples:

- Liquidity Structure
- Order Block
- Fair Value Gap
- Breaker Block

---

## MarketEvent

Represents immutable historical structural facts.

Examples:

- SwingEvent
- BOSEvent
- CHOCHEvent
- LiquidityEvent
- OrderBlockEvent
- FairValueGapEvent
- BreakerBlockEvent
- MitigationEvent

---

## Measurement

Represents deterministic quantitative observations produced by detectors.

Measurements remain immutable after publication.

---

## Feature

Represents engineered analytical inputs derived from Measurements.

Feature Engineering owns all feature transformation.

Detectors shall never normalize, scale, or weight measurements.

---

# Feature Engineering

Feature Engineering is the only component responsible for:

- Feature extraction
- Feature transformation
- Feature normalization
- Composite feature generation
- Feature validation

Market Structure Detectors produce only raw Measurements.

---

# Market Structure API

The Market Structure API provides the public interface to the Market Structure Engine.

The API shall:

- Coordinate detector execution
- Publish immutable outputs
- Hide detector implementation details

The API shall not contain market structure business logic.

---

# Processing Model

Each completed MarketBar shall be processed exactly once.

Processing order is fixed.

No detector shall execute conditionally based upon runtime ordering.

Historical replay and live execution shall use the identical pipeline.

---

# Benefits

The adopted architecture provides:

- Deterministic historical replay
- Modular detector implementation
- Clear ownership boundaries
- Reduced coupling
- Stable public interfaces
- Easier testing
- Simplified feature engineering
- Improved maintainability
- Extensible detector pipeline
- Future machine learning compatibility

---

# Consequences

## Positive

- Detectors remain independent.
- Downstream modules consume standardized outputs.
- Historical analysis becomes reproducible.
- Feature Engineering becomes independent of detector implementation.
- Future structural detectors can be added without modifying existing detectors.
- API stability improves long-term maintainability.

## Trade-offs

- More shared abstractions must be maintained.
- Additional immutable objects increase object creation.
- Detector communication requires standardized contracts.
- Initial implementation complexity is higher than a tightly coupled design.

These trade-offs are accepted in exchange for long-term maintainability, scalability, and deterministic behavior.

---

# Alternatives Considered

## Direct Detector Coupling

Rejected.

Direct access to detector internals creates tight coupling and makes testing, maintenance, and future expansion significantly more difficult.

---

## Shared Mutable State

Rejected.

Shared mutable state introduces hidden dependencies, non-deterministic behavior, and replay inconsistencies.

---

## Detector-Specific Outputs

Rejected.

Allowing each detector to expose custom output formats increases integration complexity and prevents standardized downstream processing.

---

# Implementation Impact

The following architectural components shall conform to this decision:

- Swing Detector
- BOS Detector
- CHOCH Detector
- Liquidity Detector
- Order Block Detector
- Fair Value Gap Detector
- Breaker Block Detector
- Mitigation Block Detector

Shared infrastructure shall include:

- PriceZone
- MarketEvent
- Measurement
- Feature
- Market Structure API

Downstream modules shall consume only published immutable contracts.

---

# References

Related specifications:

- SMC-SPEC-001: Smart Money Concepts Foundation
- SMC-SPEC-002: Swing Detector
- SMC-SPEC-003: BOS Detector
- SMC-SPEC-004: CHOCH Detector
- SMC-SPEC-005: Liquidity Detector
- SMC-SPEC-006: Order Block Detector
- SMC-SPEC-007: Fair Value Gap Detector
- SMC-SPEC-008: Breaker Block Detector
- SMC-SPEC-009: Mitigation Block Detector
- SMC-SPEC-010: Price Zone
- SMC-SPEC-011: Market Event
- SMC-SPEC-012: Measurement
- SMC-SPEC-013: Feature Engineering
- SMC-SPEC-014: Market Structure API

---

# Status

Accepted.

This ADR defines the architectural foundation for the Market Structure Engine and shall guide future implementation and refactoring decisions.
