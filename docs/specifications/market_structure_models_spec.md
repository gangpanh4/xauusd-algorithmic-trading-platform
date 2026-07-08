# Market Structure Models Specification

**Status:** Draft

**Sprint:** 2

**Module:** core/market_structure

---

# Purpose

This document defines the shared data models used by every market
structure component.

These models are intentionally independent of any specific detection
algorithm.

They serve as the common language between:

- Swing Detection
- Break of Structure (BOS)
- Change of Character (CHoCH)
- Liquidity Detection
- Order Blocks
- Fair Value Gaps

No business logic belongs in these models.

---

# Design Principles

The models must be:

- immutable where possible
- lightweight
- reusable
- serializable
- independent from MT5
- independent from pandas
- independent from NumPy
- independent from indicators

Models describe data only.

Algorithms belong in detector modules.

---

# Model Dependency

SwingPoint

↓

StructureBreak

↓

LiquidityLevel

↓

OrderBlock

↓

FairValueGap

Each model builds upon previously confirmed information.

No model should depend on future detector output.

---

# Initial Models

Version 1 defines only one model.

## SwingPoint

Represents one confirmed swing high or swing low.

The model must not contain trading logic.

The model must not determine whether a swing is valid.

Validation belongs to Swing Detection.

Required information:

- candle index
- timestamp
- swing price
- swing type
- confirmation status

Future versions may extend this model only through backward-compatible
changes.

---

# Out of Scope

This specification does not define:

- BOS algorithms
- CHoCH algorithms
- Liquidity algorithms
- Order Block algorithms
- Fair Value Gap algorithms

Those receive their own specifications.

---

# Compatibility

The models must be usable by:

Historical Backtesting

Live Trading

Research Framework

Reporting

Future AI modules

without modification.

---

# Implementation Rules

Models:

✔ dataclasses

✔ strongly typed

✔ documented

✔ deterministic

No detector may modify historical SwingPoint objects after confirmation.