# Market Structure API Specification

**Document ID:** SMC-SPEC-014

**Version:** 1.0

**Status:** Draft

**Project:** Trading Intelligence Platform

**Module:** Market Structure Engine

---

# 1. Purpose

The Market Structure API Specification defines the public interfaces used for communication within the Market Structure Engine.

The API provides a stable contract between detectors, shared infrastructure, and downstream analytical components.

Its objectives are to:

- Standardize detector interfaces.
- Standardize data exchange.
- Minimize coupling.
- Support deterministic processing.
- Enable future extensibility.

The API shall remain independent of detector-specific implementation details.

---

# 2. Scope

This specification defines the public contracts used throughout the Market Structure Engine.

It SHALL define:

- Public detector interfaces
- Shared data contracts
- Input contracts
- Output contracts
- Communication rules
- Ownership rules

It SHALL NOT define:

- Detection algorithms
- Trading logic
- Risk management
- Execution
- Portfolio management

Those responsibilities belong to other modules.

---

# 3. Architectural Principles

The Market Structure API is based on the following principles.

## Single Responsibility

Each detector owns only its own structural concept.

---

## Single Ownership

Every structural object has exactly one owner.

Examples:

- Swing Detector owns Swing Events.
- BOS Detector owns BOS Events.
- Liquidity Detector owns Liquidity Structures.
- Order Block Detector owns Order Block Zones.

Ownership never transfers.

---

## Immutable Communication

Communication between modules occurs using immutable objects.

Examples include:

- Market Events
- Measurements
- Features

Mutable runtime state shall never be shared.

---

## Deterministic Processing

Identical market data shall always produce identical outputs.

No detector may rely on hidden state or nondeterministic behavior.

---

## Incremental Processing

The API shall support streaming execution.

Each completed MarketBar shall be processed exactly once.

---

# 4. Public Inputs

The Market Structure API accepts the following public inputs.

Primary inputs include:

- Completed MarketBars
- Configuration
- Historical replay data

The API shall never consume partially completed MarketBars.

---

# 5. Public Outputs

The API exposes standardized outputs.

Primary outputs include:

- Price Zones
- Market Events
- Measurements
- Features

These outputs are immutable.

Consumers shall treat them as read-only.

---

# 6. Shared Contracts

The Market Structure API standardizes the following shared contracts.

- PriceZone
- MarketEvent
- Measurement
- Feature

These contracts are defined by their respective specifications.

The API shall never redefine those contracts.

---

# 7. API Consumers

Primary consumers include:

- Feature Engineering
- Research Analytics
- Probability Engine
- Strategy Evaluation
- Backtesting
- Visualization

Consumers shall depend only on the public API.

They shall not depend on detector internals.

---

# 8. Configuration

The API itself has no detector-specific configuration.

Configuration belongs exclusively to the owning detector.

The API remains implementation independent.

---

---

# 9. Processing Pipeline

The Market Structure API coordinates detector execution using a deterministic processing pipeline.

Each detector consumes immutable outputs from upstream detectors and produces immutable outputs for downstream consumers.

The default processing sequence is:

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
```

Each detector shall execute exactly once for each completed MarketBar.

The API shall preserve processing order.

---

# 10. Detector Interface

Every detector shall expose a common public interface.

Required operations include:

- Initialize
- Reset
- Process completed MarketBar
- Retrieve detector state
- Retrieve generated Market Events
- Retrieve generated Price Zones
- Retrieve Measurements

Detector implementations may expose additional internal methods, but those methods shall not be part of the public API.

---

## Detector Inputs

Every detector receives only immutable inputs.

Typical inputs include:

- Completed MarketBar
- Market Events
- Price Zones
- Configuration

Detectors shall never consume mutable runtime state from another detector.

---

## Detector Outputs

Every detector publishes immutable outputs.

Outputs include:

- Market Events
- Price Zones
- Measurements

Downstream detectors shall consume these outputs through the API.

---

# 11. Communication Rules

Communication between detectors shall occur exclusively through the public API.

Detectors shall never directly access:

- Internal variables
- Private collections
- Runtime caches
- Processing queues

Communication shall occur only through immutable shared contracts.

---

## Allowed Communication

Examples include:

- Swing Detector → BOSEvent
- BOS Detector → CHOCHEvent
- Liquidity Detector → OrderBlockZone
- Order Block Detector → BreakerBlockZone
- Breaker Block Detector → MitigationEvent

Communication always occurs through published objects.

---

## Prohibited Communication

The following behaviors are prohibited:

- Direct modification of another detector's state
- Reading another detector's private runtime variables
- Modifying another detector's collections
- Circular detector dependencies

---

# 12. State Isolation

Every detector owns its own runtime state.

Runtime state shall remain private.

Examples include:

- Candidate structures
- Processing buffers
- Temporary calculations
- Validation state

The API shall never expose mutable detector state.

---

# 13. Deterministic Guarantees

The Market Structure API shall satisfy the following guarantees.

## Historical Replay

Identical historical market data shall always produce identical API outputs.

---

## Sequential Execution

Detectors shall execute in a fixed processing order.

The execution order shall never depend on runtime conditions.

---

## Immutable Communication

Published objects shall never be modified after publication.

Immutable objects include:

- Price Zones
- Market Events
- Measurements
- Features

---

## Idempotent Processing

Processing identical historical data multiple times shall always produce:

- Identical Market Events
- Identical Price Zones
- Identical Measurements
- Identical Features

---

## Streaming Compatibility

The API shall support continuous live processing.

Each completed MarketBar shall be processed exactly once.

Partially completed MarketBars shall never be processed.

---

---

# 14. Public API Surface

The Market Structure API shall expose a minimal, stable public interface.

Consumers shall interact only through this interface.

The public API shall provide access to:

- Published Market Events
- Active Price Zones
- Published Measurements
- Published Features
- Detector execution results
- Processing metadata

Internal detector implementation details shall remain hidden.

---

# 15. API Versioning

The Market Structure API shall support explicit versioning.

Each public contract shall include:

- API Version
- Schema Version
- Compatibility Information

Backward-compatible changes shall preserve existing interfaces.

Breaking changes shall require a new API version.

Historical replay shall remain reproducible regardless of API version evolution.

---

# 16. Error Handling

The API shall handle processing failures deterministically.

## Detector Failure

If a detector encounters an unrecoverable error:

- The failure shall be reported.
- Processing metadata shall record the failure.
- Downstream consumers shall receive a deterministic result.

The API shall not silently suppress errors.

---

## Validation Failure

If detector validation fails:

- Invalid outputs shall not be published.
- The detector shall remain responsible for validation reporting.

---

## Configuration Failure

Invalid configuration shall prevent processing from starting.

Configuration errors shall be reported before runtime execution.

---

## Replay Failure

Replay failures shall provide sufficient diagnostic information to reproduce the issue.

---

# 17. Performance Requirements

The Market Structure API shall satisfy the following requirements.

## Streaming

Support continuous real-time processing.

Each completed MarketBar shall be processed exactly once.

---

## Historical Replay

Support efficient historical replay over large datasets.

Replay shall produce deterministic outputs.

---

## Memory

The API shall avoid unnecessary duplication of:

- Market Events
- Price Zones
- Measurements
- Features

Shared objects shall be referenced rather than copied.

---

## Scalability

The API shall support:

- Multi-year historical replay
- High-frequency market data
- Large numbers of active structural objects
- Continuous live execution

---

# 18. Integration

The Market Structure API provides the single public interface to the Market Structure Engine.

```text
                Trading Pipeline
                       │
                       ▼
             Market Structure API
                       │
       ┌───────────────┼────────────────┐
       │               │                │
       ▼               ▼                ▼
  Market Events   Price Zones    Measurements
                       │
                       ▼
              Feature Engineering
                       │
                       ▼
                   Features
                       │
       ┌───────────────┼────────────────┐
       ▼               ▼                ▼
Probability      Research        Backtesting
 Engine          Analytics
```

All consumers shall interact with the Market Structure Engine exclusively through the Market Structure API.

Direct access to detector implementations is prohibited.

---

# 19. Unit Test Requirements

The implementation shall include automated tests covering the following categories.

## Interface Tests

- Public API availability
- Detector interface compliance
- Shared contract compatibility

---

## Processing Tests

- Sequential detector execution
- Streaming execution
- Historical replay
- Reset behavior

---

## Error Handling Tests

- Detector failures
- Validation failures
- Configuration failures
- Replay failures

---

## Integration Tests

- Feature Engineering integration
- Probability Engine integration
- Research Analytics integration
- Backtesting integration
- Visualization integration

---

## Determinism Tests

Verify that:

- Identical inputs produce identical outputs.
- Processing order remains stable.
- Published objects remain immutable.

---

# 20. Future Enhancements

Potential future enhancements include:

- Parallel detector execution where dependencies permit
- Distributed Market Structure processing
- Incremental snapshot persistence
- Event subscription interfaces
- Plugin-based detector registration
- Multi-symbol processing support

Future enhancements shall remain backward compatible with this specification whenever practical.

---

# 21. Acceptance Criteria

The Market Structure API shall be considered production-ready only when:

- All unit tests pass.
- Public interfaces are stable.
- Shared contracts are consistently implemented.
- Historical replay is deterministic.
- Streaming execution is deterministic.
- Detector isolation is enforced.
- API versioning is implemented.
- Documentation is complete.
- Code review is approved.
- Integration with the Trading Pipeline is verified.

---

# End of Specification