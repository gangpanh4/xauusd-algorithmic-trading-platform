# ADR-008

# Market Structure V2

Status: Approved

---

## Motivation

Research and backtesting showed that the current Market Structure
implementation rarely produces CHOCH events.

The bottleneck is not the Probability Engine.

The bottleneck is the semantic definition of market structure.

This ADR freezes the intended behaviour before implementation.

---

# Principles

Market Structure is responsible only for identifying structural events.

It does NOT:

- score trades
- manage risk
- decide entries
- calculate probability

Those belong to downstream modules.

---

# Pipeline

Completed Candle

↓

Swing Detection

↓

Break Of Structure (BOS)

↓

Change Of Character (CHOCH)

↓

Liquidity

↓

MarketStructureResult

---

# Swing

A swing is confirmed only after the configured confirmation period.

Each swing contains

- timestamp
- price
- swing type
- confirmation index

---

# Break Of Structure

A BOS represents continuation.

Bullish BOS

- close above protected high

Bearish BOS

- close below protected low

A wick alone is NOT sufficient.

Future implementation will use candle close confirmation.

---

# Protected Swing

Protected Swing is NOT simply the most recent opposite swing.

Protected Swing is

"The structural swing whose violation invalidates the current trend."

Protected Swing remains fixed until a new confirmed BOS establishes a
new trend.

---

# Trend

Trend changes only after confirmed BOS.

Trend never changes because of CHOCH.

CHOCH indicates possible reversal.

BOS confirms continuation.

---

# CHOCH

CHOCH represents loss of trend.

Bullish CHOCH

- bearish trend
- protected high broken

Bearish CHOCH

- bullish trend
- protected low broken

Future implementation will require candle close confirmation.

---

# Liquidity

Liquidity is evaluated after structure.

Liquidity confirms structure.

Liquidity never creates structure.

---

# Multi Timeframe

Higher timeframe determines directional bias.

Lower timeframe may only trade in the direction of higher timeframe bias.

This belongs to Market Structure V2.

---

# Premium / Discount

Premium and Discount zones are calculated from the active higher timeframe range.

Feature Engineering will receive

- equilibrium
- premium
- discount

Probability Engine decides their importance.

---

# Probability

Probability never creates structure.

Probability only evaluates structure.

---

# Decision

Decision never creates structure.

Decision only evaluates probability.

---

# Risk

Risk Manager validates

- position size
- RR
- stop placement
- exposure

Risk never changes structure.

---

# Research

Every structural modification requires

- unit tests
- backtest
- feature separation
- probability distribution
- experiment comparison

Only improvements supported by research are promoted.