# ADR-00X

# Break of Structure (BOS) Detector

## Status

✅ Approved

---

## Context

The Market Structure Engine requires a dedicated Break of Structure (BOS) detector to identify continuation events in market structure.

The platform already includes a streaming SwingDetector that produces confirmed SwingPoint objects. The BOS detector will consume these confirmed SwingPoints rather than performing its own swing detection.

The detector must operate consistently during both historical backtesting and live trading while remaining deterministic and non-repainting.

---

## Decision

The Break of Structure Detector shall:

- Consume confirmed SwingPoint objects as its primary structural input.
- Operate as a streaming detector that processes completed market data incrementally.
- Require candle-close confirmation before emitting a BOS event.
- Never repaint previously confirmed BOS events.
- Produce deterministic results for identical historical and live market data.
- Emit immutable BOSEvent objects.
- Maintain only the minimal runtime state required for structural analysis.
- Remain independent from CHoCH, Liquidity, Order Blocks, Fair Value Gaps, and Signal Generation.

---

## Rationale

Separating Swing Detection from BOS detection improves modularity and keeps each component responsible for a single task.

Using confirmed SwingPoints avoids duplicated swing logic throughout the Market Structure Engine.

Requiring candle-close confirmation reduces false structural breaks caused by temporary liquidity sweeps or intrabar volatility.

Maintaining deterministic behavior ensures identical results during historical replay and live execution, improving reliability and simplifying testing.

Keeping the BOS detector independent from higher-level trading logic allows other modules to consume BOS events without introducing unnecessary dependencies.

---

## Consequences

### Positive

- Clear separation of responsibilities.
- Streaming-friendly architecture.
- Deterministic historical and live behavior.
- Easier unit testing.
- Easier integration with downstream detectors.
- Reduced code duplication.

### Negative

- BOS confirmation occurs only after candle close.
- Intrabar structural breaks are intentionally ignored.
- Additional confirmation introduces slight detection latency.

---

## Out of Scope

The BOS detector will not:

- Detect SwingPoints.
- Detect Change of Character (CHoCH).
- Detect Liquidity Sweeps.
- Detect Order Blocks.
- Detect Fair Value Gaps.
- Generate trading signals.
- Execute trades.
- Perform risk management.
- Apply multi-timeframe analysis.

These responsibilities belong to separate modules within the trading platform.

---

## Related Components

Input:

- SwingDetector
- SwingPoint

Output:

- BOSEvent

Consumers:

- CHoCH Detector
- Liquidity Detector
- Order Block Detector
- Fair Value Gap Detector
- Signal Generator

---

## Implementation Notes

The detector will be implemented as a dedicated streaming component inside:

core/market_structure/bos_detector.py

The implementation will follow the project workflow:

Research

↓

ADR

↓

Technical Specification

↓

Implementation

↓

Code Review

↓

Testing

↓

Git Commit