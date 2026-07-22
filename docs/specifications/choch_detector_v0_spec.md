# Change of Character (CHoCH) Detector Specification

## Overview

The Change of Character (CHoCH) Detector identifies the first confirmed structural reversal after an established market trend.

Unlike a Break of Structure (BOS), which confirms continuation of the current trend, a CHoCH confirms a potential trend reversal.

The detector is a component of the Market Structure Engine and operates only on confirmed market structure.

---

# Inputs

The detector consumes:

* Confirmed SwingPoint objects
* Confirmed BOSEvent objects
* Current MarketTrend

The detector never processes raw market bars directly.

---

# Outputs

The detector emits immutable CHOCHEvent objects.

Each event contains:

* timestamp
* break_type (CHOCH)
* swing_point
* confirmation_index

---

# Runtime State

The detector owns its runtime state.

The state stores:

* confirmed_swings
* confirmed_changes
* last_change
* CHOCH consumes current_trend from BOS.
* protected_swing
* detector_status
* processed_swing_count

No detection logic is stored inside the state object.

---

# Public API

The detector exposes:

```python
CHOCHDetector()

reset()

process()

get_last_change()

get_changes()

get_state()
```

---

# Detection Rules

## Bullish CHoCH

Requirements:

* confirmed Lower Low
* confirmed Lower High
* break above previous Lower High

When confirmed:

* emit CHOCHEvent

---

## Bearish CHoCH

Requirements:

* confirmed Higher High
* confirmed Higher Low
* break below previous Higher Low

When confirmed:

* emit CHOCHEvent

---

# Trend Transition

The detector maintains one of three trend states:

* UNKNOWN
* BULLISH
* BEARISH

A confirmed BOS establishes or continues the current trend.

A confirmed CHoCH reverses the current trend.

Only one confirmed CHoCH may occur for a protected swing.

---

# Validation

Version 1 performs:

* duplicate protection
* confirmation using confirmed swings only

Version 1 does **not** perform:

* liquidity confirmation
* volume confirmation
* multi-timeframe confirmation
* order block confirmation
* fair value gap confirmation

---

# Duplicate Protection

The detector shall never emit two identical CHOCHEvent objects for the same confirmed SwingPoint.

---

# Performance

The detector operates sequentially.

Memory usage grows only with confirmed market structure history.

The detector performs no look-ahead.

---

# Error Handling

Invalid input returns:

* None

The detector never raises exceptions during normal operation.

---

# Testing Requirements

The detector must be validated with unit tests covering:

* initialization
* reset
* insufficient swings
* bullish CHoCH
* bearish CHoCH
* duplicate protection
* previous structure lookup
* public getters

Target:

10–15 passing unit tests.

---

# Version 1 Constraints

Version 1 intentionally excludes:

* Liquidity Sweep confirmation
* Order Block confirmation
* Fair Value Gap confirmation
* Volume analysis
* ATR filtering
* Multi-timeframe confirmation
* Market Structure Shift (MSS)

These capabilities belong to later Market Structure modules.
