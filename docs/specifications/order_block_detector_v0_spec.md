# Order Block Detection Engine Specification

## Status

Draft v1.0

---

# Purpose

The Order Block Detection Engine identifies institutional order blocks from
confirmed market structure events. It is designed as a deterministic,
non-repainting component of the market structure pipeline for both historical
backtesting and live trading.

The detector does not predict future price movement. It identifies completed
institutional price zones after sufficient structural confirmation has occurred.

---

# Objectives

The detector shall:

- Detect bullish order blocks.
- Detect bearish order blocks.
- Produce deterministic results.
- Avoid repainting.
- Operate identically in historical replay and live execution.
- Track the lifecycle of every detected order block.
- Provide structured outputs for downstream components.

The detector shall not:

- Generate trading signals.
- Execute trades.
- Predict market direction.
- Depend on future candles.

---

# Pipeline Position

Market Data
    ↓
Swing Detector
    ↓
BOS Detector
    ↓
CHOCH Detector
    ↓
Liquidity Detector
    ↓
Order Block Detector
    ↓
Fair Value Gap Detector
    ↓
Signal Generator

The Order Block Detector consumes confirmed structural information from
previous detectors and produces confirmed order block events.

---

# Dependencies

## Required Inputs

The detector consumes:

- Confirmed Swing Points
- Confirmed BOS Events
- Confirmed CHOCH Events

## Optional Inputs

The detector may consume:

- Liquidity Sweep Events

Liquidity sweeps increase confidence but are not required for a valid order
block.

---

# Order Block Definition

An Order Block is a confirmed institutional price zone created immediately
before a significant displacement that produces a confirmed structural break.

The detector shall never classify arbitrary support or resistance zones as
order blocks.

A valid order block requires:

- Confirmed market structure
- Price displacement
- Institutional origin candle
- Structural confirmation

---

# Bullish Order Block Rules

A bullish order block requires:

1. Existing bearish market structure.
2. Bullish displacement.
3. Confirmed BOS or bullish CHOCH.
4. Identification of the final bearish candle before displacement.
5. Creation of a bullish order block zone.

Optional confidence factors:

- Liquidity sweep
- Strong displacement
- Multiple structural confirmations

---

# Bearish Order Block Rules

A bearish order block requires:

1. Existing bullish market structure.
2. Bearish displacement.
3. Confirmed BOS or bearish CHOCH.
4. Identification of the final bullish candle before displacement.
5. Creation of a bearish order block zone.

Optional confidence factors:

- Liquidity sweep
- Strong displacement
- Multiple structural confirmations

---

# Confirmation Rules

The detector shall confirm an order block only after:

- Structural break is confirmed.
- Required displacement is complete.
- Source candle is finalized.

No future candles may be used.

---

# Liquidity Integration

Liquidity is treated as a confidence enhancement.

The detector shall never reject an otherwise valid order block solely because
no liquidity sweep occurred.

Liquidity contributes to the strength score.

---

# Fair Value Gap Integration

The detector does not require Fair Value Gaps.

Fair Value Gap detection occurs later in the pipeline.

Signal generation may combine:

- Order Block
- Fair Value Gap

The Order Block Detector remains independent of the Fair Value Gap Detector.

---

# Order Block Lifecycle

Each detected order block progresses through the following states:

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

Lifecycle management belongs to the detector runtime state.

---

# Detector Responsibilities

The detector is responsible for:

- Creating order blocks
- Validating order blocks
- Tracking lifecycle
- Detecting mitigation
- Detecting invalidation
- Preventing duplicate order blocks

The detector is not responsible for:

- Trade execution
- Position sizing
- Entry confirmation
- Risk management

---

# Data Model

The detector produces immutable domain models.

Primary models include:

- OrderBlock
- OrderBlockEvent

Runtime lifecycle information is stored separately inside the detector state.

---

# Runtime State

The detector maintains:

- Active order blocks
- Mitigated order blocks
- Invalidated order blocks
- Expired order blocks
- Confirmed order block events
- Last confirmed event
- Processing statistics

---

# Configuration

Configurable parameters include:

- Minimum displacement
- Minimum strength
- Maximum order block age
- Liquidity confidence bonus
- Nested order block policy
- Mitigation policy

Configuration values affect validation but never alter deterministic behavior.

---

# Non-Repainting Requirement

The detector shall never modify historical order blocks after confirmation.

Historical replay and live execution must produce identical outputs when given
identical input data.

---

# Backtesting Requirements

The detector must support:

- Historical replay
- Walk-forward analysis
- Incremental streaming execution
- Deterministic reconstruction

No future information may influence historical decisions.

---

# Output

The detector emits confirmed OrderBlockEvent objects.

Each event represents a completed lifecycle transition suitable for downstream
consumption.

---

# Error Handling

Invalid structural input shall not terminate processing.

Invalid order block candidates shall be rejected gracefully.

Duplicate events shall be ignored.

---

# Testing Requirements

Unit tests shall verify:

- Initialization
- Reset
- Bullish order block detection
- Bearish order block detection
- Duplicate prevention
- Mitigation detection
- Invalidation detection
- Lifecycle transitions
- Getter methods
- Replay determinism
- Non-repainting behavior

---

# Future Extensions

Future versions may include:

- Multi-timeframe order blocks
- Order block scoring
- Volume-based validation
- Session-aware filtering
- Machine-learning confidence models

These extensions shall remain backward compatible with Version 1.