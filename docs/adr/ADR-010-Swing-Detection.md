# Architecture Decision Record

---

## ADR-010

### Title

Swing Detection Engine

### Status

✅ Approved

### Date

2026-07-07

---

# Context

The XAUUSD Algorithmic Trading Platform requires a deterministic market structure engine capable of identifying significant swing highs and swing lows from streaming market data.

Swing detection is the foundation of all higher-level Smart Money Concept (SMC) and ICT analysis.

The following platform components depend directly on reliable swing detection:

- Break of Structure (BOS)
- Change of Character (CHoCH)
- Liquidity Detection
- Liquidity Sweep Detection
- Order Block Detection
- Fair Value Gap (FVG) Analysis
- Confluence Engine
- Signal Generator

An incorrect swing detection algorithm would propagate errors throughout the entire trading pipeline.

Therefore, the platform requires a production-grade implementation optimized for live trading rather than indicator visualization.

---

# Decision

The platform SHALL implement a Pivot-Based Swing Detection Engine.

Swing confirmation SHALL require both left-side and right-side candle confirmation.

ATR SHALL NOT define swings.

ATR MAY be used as an optional validation filter to reject insignificant pivots.

Confirmed swing points SHALL NEVER be modified after confirmation.

The implementation SHALL operate incrementally on streaming market bars.

---

# Motivation

The selected approach satisfies the project's primary engineering goals:

- Deterministic
- Non-Repainting
- Low computational cost
- Suitable for streaming execution
- Compatible with institutional market structure analysis
- Easily testable
- Stable in historical backtesting
- Stable in live trading

---

# Evaluated Alternatives

## Option 1 — Pivot-Based Detection

Description

A swing high exists when the current high exceeds the highs of a configurable number of candles on both sides.

Likewise, a swing low exists when the current low is lower than neighboring lows.

Advantages

- Deterministic
- Simple
- O(n)
- Stable
- Non-Repainting after confirmation
- Industry standard
- Excellent compatibility with BOS and CHoCH

Disadvantages

- Confirmation delay
- Cannot identify the newest swing immediately

Decision

✅ Accepted

---

## Option 2 — ZigZag

Description

Uses percentage or point deviation to identify swing points.

Advantages

- Smooth market structure
- Easy visualization

Disadvantages

- Repaints
- Future-dependent
- Unsuitable for live execution
- Historical results differ from live results

Decision

❌ Rejected

Reason

The platform prioritizes live trading accuracy over visual smoothness.

---

## Option 3 — Fractal-Based Detection

Description

Uses fixed candle formations such as five-bar fractals.

Advantages

- Deterministic
- Widely known

Disadvantages

- Fixed confirmation window
- Less configurable
- Limited flexibility

Decision

❌ Rejected as primary algorithm

May be supported later as an optional detection mode.

---

## Option 4 — ATR-Based Detection

Description

Defines swings using volatility thresholds.

Advantages

- Adaptive to volatility

Disadvantages

- Measures volatility rather than market structure
- Cannot reliably identify institutional swing points

Decision

❌ Rejected as primary algorithm

ATR SHALL only be used as an optional validation filter.

---

# Engineering Requirements

The Swing Detection Engine SHALL satisfy all of the following requirements.

## Deterministic

Given identical market data, identical swing points SHALL always be produced.

---

## Non-Repainting

Once a swing has been confirmed, it SHALL NEVER change.

---

## Streaming

The detector SHALL process one completed market bar at a time.

No historical recalculation SHALL be required.

---

## Computational Complexity

Time Complexity

O(n)

Memory Complexity

O(n)

---

## Configurable Parameters

The implementation SHALL support:

- Pivot Left Bars
- Pivot Right Bars
- Minimum Swing Distance
- Equal High Tolerance
- Equal Low Tolerance
- ATR Validation (optional)
- ATR Multiplier

---

# Output Model

The detector SHALL produce immutable SwingPoint objects.

Each SwingPoint SHALL contain:

- Timestamp
- Price
- Swing Type
- Pivot Strength
- Confirmation Index
- Confirmation Time

---

# Integration

The Swing Detection Engine SHALL become the first stage of the Market Structure Engine.

Trading Pipeline

Market Data

↓

Swing Detection

↓

Break of Structure

↓

Change of Character

↓

Liquidity Detection

↓

Order Blocks

↓

Fair Value Gaps

↓

Confluence Engine

↓

Signal Generator

↓

Risk Manager

↓

Execution

---

# Testing Requirements

The implementation SHALL include automated unit tests covering:

- Swing High
- Swing Low
- Equal Highs
- Equal Lows
- Strong Trend
- Sideways Market
- News Volatility
- ATR Filter Enabled
- ATR Filter Disabled
- Streaming Updates
- Historical Replay
- No Repainting Verification

---

# Consequences

The platform gains:

- Stable market structure
- Deterministic execution
- Consistent historical and live behavior
- Reliable foundation for Sprint 2

The platform accepts:

- Delayed confirmation of swings
- Additional waiting period before BOS confirmation

These trade-offs are considered acceptable because they eliminate repainting and improve trading reliability.

---

# Future Work

Following approval of this ADR, the following components SHALL be implemented:

ADR-011 — Break of Structure (BOS)

ADR-012 — Change of Character (CHoCH)

ADR-013 — Liquidity Detection

ADR-014 — Order Block Detection

ADR-015 — Fair Value Gap Detection

ADR-016 — Confluence Engine

---

# Approval

Status

✅ Approved

Decision Owner

XAUUSD Algorithmic Trading Platform Architecture