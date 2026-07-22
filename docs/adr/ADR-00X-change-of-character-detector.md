# ADR-00X — Change of Character (CHoCH) Detector

## Status

Accepted

---

## Context

The Market Structure Engine currently detects confirmed Swing Points and Breaks of Structure (BOS).

A Break of Structure confirms continuation of the current market trend and establishes the protected swing that defines the active market structure.

The trading platform also requires the ability to detect potential trend reversals. In Smart Money Concepts (SMC) and Inner Circle Trader (ICT) methodology, this event is known as a Change of Character (CHoCH).

CHoCH serves as an early indication that market control may be shifting from buyers to sellers or from sellers to buyers by detecting violations of the protected swing established by BOS.

This detector will become the foundation for:

* Liquidity Sweep Detection
* Order Block Detection
* Fair Value Gap Detection
* Market Regime Analysis
* Trade Entry Confirmation

---

## Decision

A dedicated `CHOCHDetector` will be implemented as an independent component inside the Market Structure Engine.

The detector shall:

* consume confirmed `SwingPoint` objects
* consume confirmed `BOSEvent` objects
* read the current trend from the BOS detector
* read the protected swing from the BOS detector
* operate sequentially on confirmed market structure events
* emit immutable `CHOCHEvent` objects
* maintain only detector-specific runtime state (such as duplicate protection)
* contain no execution or trading logic

The BOS detector is the single source of truth for market structure state.

The BOS detector owns:

* `current_trend`
* `protected_swing`

The CHOCH detector reads BOS state and never owns or modifies market structure state.

The detector will never place trades.

---

## Detection Rules

A Change of Character is confirmed only after price violates the protected swing established by the current market trend.

Examples include:

### Bullish CHoCH

* A bearish trend is active.
* A Lower Low and Lower High have been confirmed.
* Price breaks above the protected Lower High.
* A Bullish CHOCH is emitted.

### Bearish CHoCH

* A bullish trend is active.
* A Higher High and Higher Low have been confirmed.
* Price breaks below the protected Higher Low.
* A Bearish CHOCH is emitted.

The detector evaluates only confirmed market structure.

No prediction or forecasting is performed.

---

## Trend Management

The BOS detector owns the market trend and protected swing.

Possible trend states are:

* UNKNOWN
* BULLISH
* BEARISH

The trend is established and updated exclusively by confirmed BOS events.

The CHOCH detector reads the BOS state to determine whether the protected swing has been violated.

A confirmed CHOCH emits a `CHOCHEvent` indicating a potential change in market character. Responsibility for updating the market trend remains with the BOS detector.

---

## Consequences

### Advantages

* Single source of truth for market structure
* Clear ownership of trend and protected swing
* No duplicated state between BOS and CHOCH
* Deterministic behaviour
* Easier unit testing
* Simpler maintenance
* Better extensibility for downstream detectors
* Consistent architecture across the Market Structure Engine

### Trade-offs

* Requires confirmed Swing Points
* Requires confirmed BOS events
* CHOCH depends on BOS state being available
* May detect reversals later than predictive models

---

## Version 1 Scope

### Included

* Bullish CHOCH detection
* Bearish CHOCH detection
* Immutable `CHOCHEvent`
* Detector runtime state
* Duplicate protection
* Unit tests

### Excluded

* Liquidity confirmation
* Volume confirmation
* Multi-timeframe confirmation
* Order Block validation
* Fair Value Gap validation
* AI-assisted confirmation

These features belong to future versions.
