# Market Regime Detection Research

Version: v1.0
Status: Research
Feature: Market Regime Detection
Project: XAUUSD Signal Bot v2.3 DEV

---

# Purpose

This document collects all research related to Market Regime Detection.

The objective is to understand how professional trading systems classify
market conditions before generating trading signals.

This document contains research only.

No implementation decisions are made here.

---

# Research Sources

| Source | Status |
|---------|--------|
| Claude | ✔ |
| Manus AI | ✔ |
| Trading literature | Pending |
| Academic papers | Pending |
| Internal observations | Pending |

---

# Market Regime Overview

(Write summary)

---

# Indicator Research

## ADX

Purpose

...

Advantages

...

Disadvantages

...

Thresholds

...

Used for

...

---

## ATR

...

---

## EMA Slope

...

---

## Bollinger Band Width

...

---

## Choppiness Index

...

---

## GVZ

...

---

# XAUUSD Characteristics

...

---

# Observations

...

---

# Open Questions

...

---

# Future Research

...

## Research Session 1 – Objectives






### Source
Claude AI

### Key Findings

- The Market Regime Detector should act as a routing layer for the trading system rather than simply labeling market conditions.
- The detector should provide both a regime classification and a confidence score.
- Stability should be prioritized during normal market conditions, while stress regimes should be detected more quickly.
- Hysteresis and minimum persistence are recommended to prevent rapid regime switching.
- The detector should gracefully handle missing or stale data by maintaining the previous regime or entering a conservative fallback state.

### Ideas Adopted

✔ Regime as routing layer

✔ Confidence output

✔ Hysteresis

✔ Minimum persistence

✔ Graceful degradation

### Deferred for Future Versions

- Probabilistic regime distributions
- Portfolio execution logic
- Multi-asset universe selection