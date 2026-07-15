# ADR-00X

# Title

Order Block Detection Engine Architecture

---

## Status

Accepted

---

# Context

The XAUUSD Algorithmic Trading Platform requires a deterministic Order Block
Detection Engine capable of identifying institutional order blocks for both
historical replay and live trading.

The platform already contains:

- Swing Detector
- BOS Detector
- CHOCH Detector
- Liquidity Detector

The Order Block Detector extends this market structure pipeline.

Research from multiple independent AI systems (Claude, Gemini, Perplexity,
Goal, and NotebookLM) was reviewed before making architectural decisions.

---

# Decision

The platform will implement the Order Block Detector as an independent,
event-driven component.

The detector will consume confirmed structural information from upstream
detectors and emit immutable OrderBlockEvent objects.

The detector will not generate trading signals or perform execution.

---

# Architectural Decisions

## 1. Pipeline Position

The detector shall execute after:

- Swing Detector
- BOS Detector
- CHOCH Detector
- Liquidity Detector

and before:

- Fair Value Gap Detector
- Signal Generator

This ordering ensures structural information is available before Order Block
analysis.

---

## 2. Dependency Model

The detector consumes:

- Confirmed Swing Points
- BOS Events
- CHOCH Events

Optionally:

- Liquidity Sweep Events

The detector owns only its own runtime state.

No downstream module may mutate detector state.

---

## 3. Liquidity Usage

Liquidity sweeps improve confidence.

Liquidity is not required to create an Order Block.

This decision prevents the rejection of structurally valid order blocks that
occur without a preceding liquidity sweep.

---

## 4. Fair Value Gap Independence

The detector shall not depend upon Fair Value Gap detection.

Fair Value Gaps are detected later in the pipeline.

Signal generation may combine both concepts.

This prevents circular dependencies.

---

## 5. Immutable Domain Models

OrderBlock

and

OrderBlockEvent

are immutable domain objects.

Runtime lifecycle information is stored exclusively inside
OrderBlockDetectorState.

This separation improves:

- replay consistency
- testing
- serialization
- thread safety

---

## 6. Lifecycle Ownership

Lifecycle transitions belong to the detector.

The lifecycle consists of:

CREATED

↓

CONFIRMED

↓

ACTIVE

↓

MITIGATED

↓

INVALIDATED

↓

EXPIRED

Only the detector may transition lifecycle state.

---

## 7. Deterministic Processing

The detector operates only on confirmed information.

No future bars may influence historical decisions.

Backtesting and live trading must produce identical outputs when provided the
same input sequence.

---

## 8. Non-Repainting

Historical Order Blocks are immutable after confirmation.

The detector shall never modify historical structural decisions.

---

## 9. Duplicate Prevention

Duplicate Order Blocks shall not be emitted.

Duplicate lifecycle events shall be rejected.

This ensures deterministic downstream processing.

---

## 10. Separation of Responsibilities

The detector is responsible for:

- Order Block identification
- Validation
- Lifecycle management
- Mitigation
- Invalidation

The detector is not responsible for:

- Entries
- Exits
- Risk Management
- Position sizing
- Execution

These responsibilities belong to downstream modules.

---

# Consequences

Advantages

- Deterministic behaviour
- Non-repainting
- Modular architecture
- Replay consistency
- Easy unit testing
- Clean separation of responsibilities
- Extensible lifecycle management

Trade-offs

- Additional state management complexity
- Requires upstream structural detectors
- More components than a monolithic implementation

These trade-offs are acceptable because they improve correctness,
maintainability, and long-term extensibility.

---

# Future Work

Future versions may add:

- Multi-timeframe Order Blocks
- Volume confirmation
- Institutional footprint scoring
- Machine-learning confidence models
- Session-aware filtering

These enhancements shall remain compatible with this architecture.