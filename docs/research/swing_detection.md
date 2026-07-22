# Swing Detection Research

Version: 1.0

Status: Research Complete

Sprint: Sprint 2 – Market Structure Engine

---

# 1. Overview

Swing Detection is the process of identifying significant turning points in market price action. These turning points define market structure and form the foundation for higher-level analysis such as Break of Structure (BOS), Change of Character (CHoCH), Liquidity Detection, Order Blocks, and Fair Value Gaps (FVG).

For institutional-style trading and Smart Money Concepts (SMC), reliable swing detection is one of the most critical components of the trading system.

---

# 2. Objectives

The Swing Detection Engine should:

- Identify significant Swing Highs.
- Identify significant Swing Lows.
- Ignore insignificant market noise.
- Operate on completed candles only.
- Support both historical replay and live trading.
- Produce deterministic results.
- Never repaint confirmed swings.
- Integrate with downstream market structure modules.

---

# 3. Market Structure

Market structure consists of alternating Swing Highs and Swing Lows.

Example:

Higher High (HH)

↓

Higher Low (HL)

↓

Higher High (HH)

↓

Higher Low (HL)

This sequence represents an uptrend.

Likewise:

Lower High (LH)

↓

Lower Low (LL)

↓

Lower High (LH)

↓

Lower Low (LL)

represents a downtrend.

---

# 4. What Is a Swing High?

A Swing High is a local maximum where price is higher than surrounding candles.

It represents temporary buying exhaustion before sellers regain control.

Swing Highs are used to identify:

- Resistance
- Liquidity
- BOS
- CHoCH
- Order Blocks

---

# 5. What Is a Swing Low?

A Swing Low is a local minimum where price is lower than surrounding candles.

It represents temporary selling exhaustion before buyers regain control.

Swing Lows are used to identify:

- Support
- Liquidity
- BOS
- CHoCH
- Order Blocks

---

# 6. Swing Detection Algorithms

Several approaches are commonly used.

## Pivot-Based

A candle becomes a Swing High if its High is greater than a configurable number of candles on both the left and right.

Advantages:

- Deterministic
- Simple
- Non-repainting after confirmation
- Excellent for live trading

Disadvantages:

- Confirmation delay

---

## Fractal-Based

Uses a fixed candle pattern, commonly five candles.

Advantages:

- Simple
- Deterministic

Disadvantages:

- Fixed confirmation window
- Less configurable

---

## ZigZag

Detects swings using percentage or point deviation.

Advantages:

- Smooth visualization
- Easy to understand

Disadvantages:

- Repaints
- Unsuitable for live execution
- Depends on future data

---

## ATR Adaptive

Uses Average True Range (ATR) to filter insignificant price movements.

Advantages:

- Adapts to volatility
- Reduces noise

Disadvantages:

- Measures volatility rather than market structure
- Best used as a validation filter rather than the primary detection method

---

# 7. Algorithm Comparison

| Method | Live Trading | Historical Replay | Repainting | Complexity |
|---------|--------------|-------------------|------------|------------|
| Pivot | Excellent | Excellent | No | O(n) |
| Fractal | Good | Good | No (after confirmation) | O(n) |
| ZigZag | Poor | Excellent | Yes | O(n) |
| ATR Adaptive | Good | Good | No | O(n) |

---

# 8. Selected Approach

The project adopts:

**Primary Detection**

- Pivot-Based Swing Detection

**Secondary Validation**

- ATR Filter (optional)

Reasoning:

Pivot detection provides deterministic market structure.

ATR validation removes insignificant swings without redefining market structure.

---

# 9. ICT / Smart Money Concepts

Within ICT/SMC methodology, confirmed swings are the basis for:

- External Structure
- Internal Structure
- Break of Structure (BOS)
- Change of Character (CHoCH)
- Liquidity Pools
- Liquidity Sweeps
- Order Blocks
- Fair Value Gaps

Without reliable swing detection, these concepts cannot be consistently identified.

---

# 10. XAUUSD Considerations

Gold (XAUUSD) has characteristics that influence swing detection:

- High volatility
- Frequent liquidity sweeps
- Strong reactions during London and New York sessions
- News-driven spikes
- Large intraday ranges

The detector should prioritize structural significance over minor price fluctuations.

---

# 11. Edge Cases

The detector should correctly handle:

- Equal Highs
- Equal Lows
- Inside Bars
- Outside Bars
- Weekend gaps
- News spikes
- Flash crashes
- Sideways markets
- Strong trends
- Low volatility environments
- High volatility environments

---

# 12. Non-Repainting Requirement

A confirmed SwingPoint must never change.

Once confirmed:

- Price remains fixed.
- Timestamp remains fixed.
- Swing type remains fixed.
- Confirmation status remains fixed.

Only unconfirmed candidate pivots may change while awaiting confirmation.

---

# 13. Performance Requirements

The detector should:

- Operate incrementally.
- Process one completed candle at a time.
- Support streaming execution.
- Support historical replay.
- Achieve O(n) time complexity.
- Maintain low memory usage.

---

# 14. Future Dependencies

The Swing Detection Engine provides input to:

- Break of Structure (BOS)
- Change of Character (CHoCH)
- Liquidity Detection
- Liquidity Sweep Detection
- Order Block Detection
- Fair Value Gap Detection
- Confluence Engine
- Signal Generator

These modules depend on accurate, deterministic SwingPoint generation.

---

# 15. Conclusion

Swing Detection forms the foundation of the Market Structure Engine.

After evaluating multiple algorithms, the project adopts a Pivot-Based approach with optional ATR validation due to its deterministic behavior, non-repainting characteristics, streaming compatibility, and suitability for institutional-style market structure analysis.

This decision establishes a stable foundation for all subsequent Sprint 2 components.