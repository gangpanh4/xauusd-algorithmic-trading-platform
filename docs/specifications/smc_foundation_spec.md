# Smart Money Concepts (SMC) Foundation Specification

**Document ID:** SMC-SPEC-001

**Version:** 1.0

**Status:** Draft

**Project:** Trading Intelligence Platform

**Module:** Market Structure Engine

---

# 1. Purpose

The Smart Money Concepts (SMC) Foundation defines the architectural principles, ownership model, and common standards used by every Smart Money Concepts component within the Trading Intelligence Platform.

Its purpose is to establish a deterministic, objective, and machine-detectable framework for market structure analysis that supports professional algorithmic trading.

This document is the authoritative reference for all Smart Money Concepts implementations within the project.

---

# 2. Scope

This specification applies to every component of the Market Structure Engine.

The concepts covered by this specification include:

- Swing High
- Swing Low
- Break of Structure (BOS)
- Change of Character (CHOCH)
- Liquidity
- Liquidity Sweep
- Order Block
- Fair Value Gap (FVG)
- Breaker Block
- Mitigation Block
- Premium / Discount
- Equal Highs / Equal Lows
- Inducement

This specification defines architecture, responsibilities, ownership, and design principles.

It does **not** define trading strategies or entry/exit rules.

---

# 3. Objectives

The Smart Money Concepts architecture shall:

- Detect market structure deterministically.
- Produce identical outputs for identical inputs.
- Operate incrementally on streaming market data.
- Never repaint confirmed events.
- Expose quantitative measurements.
- Support feature engineering.
- Support research analytics.
- Support probability estimation.
- Remain independent from trading decisions.

---

# 4. Design Principles

## 4.1 Deterministic Detection

Every detector shall produce identical outputs when given identical inputs.

No detector shall rely on subjective interpretation.

---

## 4.2 Single Responsibility

Each detector owns exactly one Smart Money Concept.

Responsibilities shall never overlap.

---

## 4.3 Event-Driven Architecture

Market structure evolves through confirmed events.

Each detector consumes confirmed upstream events and produces new downstream events.

---

## 4.4 Incremental Processing

Every detector processes one completed MarketBar at a time.

Historical replay shall produce identical results to live execution.

---

## 4.5 Non-Repainting

Once an event has been confirmed, it shall never change.

Historical outputs are immutable.

---

## 4.6 Separation of Responsibilities

Each layer of the Trading Intelligence Platform has a distinct responsibility.

| Layer | Responsibility |
|-------|----------------|
| Market Structure | Detect structural events |
| Feature Engineering | Convert measurements into numerical features |
| Research Analytics | Evaluate feature performance |
| Probability Engine | Estimate trading probability |
| Risk Manager | Build trade plans |
| Trading Pipeline | Make trading decisions |
| Execution Adapter | Execute approved trades |

---

## 4.7 Measurement-First Design

Every detector shall expose quantitative measurements.

Binary events alone are insufficient.

Measurements are consumed by Feature Engineering and the Probability Engine.

---

## 4.8 Testability

Every detector shall be independently testable.

Unit tests shall verify deterministic behavior.

---

# 5. Ownership Model

Each Smart Money Concept has exactly one owner.

Only the owning detector may create, update, or invalidate that concept.

Downstream modules consume upstream outputs without recomputing them.

| Concept | Owner |
|----------|-------|
| Swing Events | Swing Detector |
| BOS Events | BOS Detector |
| Current Trend | BOS Detector |
| Protected Swing | BOS Detector |
| CHOCH Events | CHOCH Detector |
| Liquidity Registry | Liquidity Engine |
| Liquidity Sweep Events | Liquidity Sweep Detector |
| Order Blocks | Order Block Engine |
| Fair Value Gaps | Fair Value Gap Engine |
| Breaker Blocks | Breaker Block Engine |
| Mitigation Blocks | Mitigation Block Engine |
| Premium / Discount | Premium Discount Engine |
| Equal Highs / Equal Lows | Equal Levels Detector |
| Inducement Events | Inducement Detector |

---

# 6. Market Structure Pipeline

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
Liquidity Engine
      │
      ▼
Liquidity Sweep Detector
      │
      ▼
Order Block Engine
      │
      ▼
Fair Value Gap Engine
      │
      ▼
Premium / Discount Engine
      │
      ▼
Feature Engineering
      │
      ▼
Research Analytics
      │
      ▼
Probability Engine
      │
      ▼
Risk Manager
      │
      ▼
Trading Pipeline
      │
      ▼
Execution Adapter
```

---

# 7. Common Inputs

Every detector may consume one or more of the following:

- Completed MarketBar
- Detector Configuration
- Detector State
- Confirmed Swing Events
- Confirmed BOS Events
- Confirmed CHOCH Events
- Liquidity Registry
- Order Block Registry
- Fair Value Gap Registry

---

# 8. Common Outputs

Every detector may produce one or more of the following:

- Confirmed Events
- Quantitative Measurements
- Updated Detector State
- Feature Engineering Inputs

---

# 9. Common Requirements

Every detector shall satisfy the following requirements.

## Functional Requirements

- Deterministic
- Incremental
- Streaming compatible
- Historical replay compatible
- Non-repainting
- Unit testable
- Configurable
- Production ready

---

## Performance Requirements

Every detector shall:

- Process one completed MarketBar at a time.
- Avoid unnecessary memory allocation.
- Support large historical datasets.
- Produce identical live and replay results.

---

# 10. Standard Specification Template

Every Smart Money Concept specification shall contain the following sections.

1. Purpose
2. Scope
3. Owner
4. Responsibilities
5. Dependencies
6. Inputs
7. Outputs
8. Configuration
9. Detection Rules
10. Confirmation Rules
11. State Management
12. State Ownership
13. Measurements
14. Feature Engineering Outputs
15. Failure Cases
16. Performance Requirements
17. Integration
18. Unit Test Requirements
19. Future Enhancements
20. Acceptance Criteria

---

# 11. Smart Money Concepts

The following specifications define the implementation details of each Smart Money Concept.

| Specification | Status |
|--------------|--------|
| Swing Detector | Planned |
| BOS Detector | Planned |
| CHOCH Detector | Planned |
| Liquidity Engine | Planned |
| Liquidity Sweep Detector | Planned |
| Order Block Engine | Planned |
| Fair Value Gap Engine | Planned |
| Breaker Block Engine | Planned |
| Mitigation Block Engine | Planned |
| Premium / Discount Engine | Planned |
| Equal Levels Detector | Planned |
| Inducement Detector | Planned |

---

# 12. Document Relationships

This specification defines the common architecture for the Market Structure Engine.

Detailed implementation requirements are documented separately.

```
smc_foundation_spec.md
        │
        ├── swing_detector_spec.md
        ├── bos_detector_spec.md
        ├── choch_detector_spec.md
        ├── liquidity_detector_spec.md
        ├── order_block_detector_spec.md
        ├── market_structure_models_spec.md
        └── ...
```

Each specification shall comply with the architecture and principles defined in this document.

---

## 13. Trend State Ownership

The Market Structure Engine maintains a single authoritative owner of market trend state.

The BOS Detector exclusively owns:

- Current Trend
- Protected Swing

The CHOCH Detector shall never modify either value.

Instead, the CHOCH Detector emits immutable CHOCH Events describing a confirmed structural reversal.

The BOS Detector consumes confirmed CHOCH Events and performs all market trend transitions.

This ensures:

- Single ownership
- Deterministic execution
- No conflicting trend state
- Clear separation of responsibilities

# End of Specification