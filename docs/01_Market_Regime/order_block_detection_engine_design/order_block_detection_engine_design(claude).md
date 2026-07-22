# Order Block Detection Engine — Production Design Specification

**Module position in pipeline:**

```
Market Data → Swing Detection → BOS Detection → CHOCH Detection
→ Liquidity Detection → [ORDER BLOCK DETECTION] → FVG Detection
→ Signal Generation → Risk Management → Execution
```

This document specifies `OrderBlockDetector` as a standalone, testable, stateful
component that consumes upstream structural events (swings, BOS, CHOCH,
liquidity sweeps) and emits `OrderBlock` objects and `OrderBlockEvent`s to
downstream consumers (FVG detector, signal generator).

---

## 1. What Is an Order Block?

### 1.1 Institutional definition

An Order Block (OB) is **not** "the last opposite candle before a move." That
is the retail simplification. Institutionally, an order block represents a
**footprint of accumulated institutional orders** — a zone where large
participants (banks, funds) built a position that could not be filled by
available liquidity at one price, causing residual unfilled orders to remain
resting in that price zone. Price is expected to return to that zone to
"fill" the remaining orders before continuing in the original direction.

The defining institutional characteristics are:

- It is the **origin of a displacement** (an impulsive, structure-breaking
  move), not just any candle.
- It is **validated by a structural event** — a BOS or CHOCH — that confirms
  the move originating from that candle was significant enough to represent
  institutional participation, not noise.
- It typically follows a **liquidity sweep** (stop hunt) that filled
  institutional entries at a discount/premium before the displacement.
- It is a **zone**, not a line — defined by a candle's range (commonly
  open-to-high or open-to-low, depending on convention chosen).

### 1.2 Bullish Order Block

The last down-close (bearish) candle immediately preceding an impulsive
up-move that **breaks structure to the upside**. It represents the last zone
of institutional selling/accumulation before demand overwhelmed supply.

### 1.3 Bearish Order Block

The last up-close (bullish) candle immediately preceding an impulsive
down-move that **breaks structure to the downside**. It represents the last
zone of institutional buying/distribution before supply overwhelmed demand.

### 1.4 Real Order Blocks vs. Random Support/Resistance

| Property | Real Order Block | Random S/R |
|---|---|---|
| Origin | Last opposite candle before a **validated structural break** (BOS/CHOCH) | Any prior swing high/low or round number |
| Confirmation | Requires displacement + structure break confirmed by close | No confirmation logic — purely visual |
| Context | Frequently preceded by a liquidity sweep | No liquidity context |
| Directional bias | Encodes direction (bullish/bearish) and expected reaction | Symmetric, no directional logic |
| Lifecycle | Has defined states: created → confirmed → active → mitigated/invalidated | Static, persists indefinitely |
| Invalidation | Explicit rule: violated when price closes fully through it | Rarely formally invalidated |
| Repaint risk | Must be defined using only closed, confirmed candles | Often drawn subjectively, post-hoc |

**Design implication:** an OB detector must gate candidate zones through a
structure-confirmation filter (BOS/CHOCH) and never emit a zone based on
"this candle looks like it reversed" pattern-matching alone.

---

## 2. Detection Algorithm

### 2.1 High-level identification logic

For each newly **closed** candle, the algorithm asks:

1. Has a **BOS** or **CHOCH** just been confirmed by the upstream detectors?
2. If yes, walk backward from the breaking candle to find the **last
   opposite-colored candle** before the impulsive leg that produced the
   break (the "origin candle").
3. Validate that the leg from the origin candle to the break point was a
   genuine **displacement** (not a grind — see §2.4).
4. Optionally check whether the leg was preceded/accompanied by a
   **liquidity sweep** (raises OB quality score but is not always mandatory).
5. Construct the OB zone from the origin candle's range.
6. Emit the OB in `PENDING` state, then `CONFIRMED` once the structural
   event that created it is itself confirmed (see §5).

### 2.2 Relationship with upstream modules

| Upstream module | Role in OB detection |
|---|---|
| **Swing Detector** | Supplies the swing points that BOS/CHOCH reference; OB search window is bounded between two known swings, never scanned over arbitrary history. |
| **BOS Detector** | A confirmed BOS is the primary trigger to search backward for a continuation OB (trend-following OB). |
| **CHOCH Detector** | A confirmed CHOCH is the primary trigger to search backward for a reversal OB (higher quality — marks a structural regime change). |
| **Liquidity Sweep Detector** | Used as a **quality/confluence filter**: an OB whose origin candle is adjacent to a confirmed liquidity sweep is tagged `swept_liquidity=True` and given a higher `probability_score`. Not required for existence, but strongly recommended for signal weighting downstream. |
| **Market structure state** | The prevailing trend (from BOS/CHOCH history) determines whether a bullish or bearish OB is even eligible — e.g., we do not aggressively tag counter-trend OBs the same as trend-aligned ones. |

### 2.3 Confirmation requirements

An OB must **not** be emitted as tradable until:

1. The triggering BOS/CHOCH event itself is `CONFIRMED` (closed-candle
   break, not just intrabar wick pierce — this is owned by upstream
   detectors, but the OB detector must subscribe to the *confirmed* event,
   never a provisional/tentative one).
2. The displacement leg satisfies a minimum-strength filter (§2.4).
3. The origin candle has fully closed (no reliance on the forming candle).

### 2.4 Displacement / impulse validation (avoiding weak/noisy OBs)

A candidate leg qualifies as a displacement if it satisfies **at least one**
configurable criterion:

- `range(leg) >= displacement_atr_multiple * ATR(n)`
- The leg body-to-range ratio of the breaking candle(s) exceeds a threshold
  (e.g., ≥ 0.6), indicating conviction rather than indecision.
- The leg crosses the relevant swing level with a **closing** price beyond
  it by at least `min_break_buffer` (in price or ATR terms) — prevents
  "just barely poked through" false breaks from generating OBs.

This is implemented as a pure function, independently unit-testable:
`is_valid_displacement(candles, atr, config) -> bool`.

### 2.5 Avoiding repainting

Repainting is the single biggest reliability failure in retail OB
implementations. Rules enforced by this engine:

1. **Only operate on closed candles.** The detector never evaluates the
   currently-forming (incomplete) bar. It is fed candles through an
   `on_new_bar(candle: Candle, is_closed: bool)` interface, and returns
   immediately if `is_closed is False`.
2. **Never re-anchor an OB's origin candle after emission.** Once an OB is
   created and confirmed from candle index `i`, its `origin_index`,
   `top`, and `bottom` are immutable. Downstream consumers can rely on
   referential stability.
3. **State transitions are monotonic and forward-only** (see §5) —
   `PENDING → CONFIRMED → ACTIVE → MITIGATED/INVALIDATED/EXPIRED`. No
   backward transitions, no silent deletion and recreation of the same OB.
4. **Deterministic backtest/live parity**: the exact same algorithm and
   candle-closure semantics must run identically in historical replay and
   live streaming (see §9). This is a functional requirement, not a nice-to-have.
5. **Idempotent re-processing**: if the same closed candle is (re)delivered
   (e.g., reconnect/replay overlap), the detector must not create a
   duplicate OB for an already-registered origin index (see §10 duplicate
   protection tests).

---

## 3. Bullish Order Block — Exact Rules

**Candle requirements (origin candle):**
- Candle is bearish (`close < open`) — the "down candle."
- It is the **last** bearish candle immediately preceding the impulsive
  bullish leg (i.e., the candle(s) between it and the break are bullish or
  neutral-but-net-bullish).

**Structure requirements:**
- The impulsive leg following the origin candle produces a confirmed
  **BOS (bullish)** or **CHOCH (bearish→bullish)** — i.e., a prior
  swing-high is broken with a qualifying close above it.
- The break must reference a swing high supplied by the Swing Detector,
  not an arbitrary local peak.

**Validation rules:**
1. Displacement check passes (§2.4) for the leg from origin candle close to
   the breakout candle close.
2. The origin candle must not itself have been already invalidated by a
   deeper subsequent low that closes below its low prior to the breakout
   (i.e., structure integrity is intact through the leg).
3. Zone definition: `top = origin_candle.open` (or `high`, per config —
   default recommendation: use `high` for a more conservative/inclusive
   zone, `open` for a tighter aggressive zone — expose as
   `OrderBlockConfig.zone_definition: Literal["open_high", "high_low"]`),
   `bottom = origin_candle.low`.
4. Optional confluence: a liquidity sweep of a nearby swing low occurring
   at or immediately before the origin candle raises `probability_score`
   and sets `swept_liquidity=True`.
5. Reject if the origin candle's range is abnormally large relative to ATR
   (`range > max_atr_multiple * ATR`) — oversized candles usually indicate
   news-spike noise rather than a clean accumulation zone.

---

## 4. Bearish Order Block — Exact Rules

**Candle requirements (origin candle):**
- Candle is bullish (`close > open`) — the "up candle."
- It is the **last** bullish candle immediately preceding the impulsive
  bearish leg.

**Structure requirements:**
- The impulsive leg produces a confirmed **BOS (bearish)** or **CHOCH
  (bullish→bearish)** — a prior swing-low is broken with a qualifying
  close below it.
- The break must reference a swing low supplied by the Swing Detector.

**Validation rules:**
1. Displacement check passes for the leg from origin candle close to the
   breakout candle close.
2. Origin candle not invalidated by a subsequent higher high closing above
   its high prior to the breakout.
3. Zone definition: `bottom = origin_candle.open` (or `low`, per config),
   `top = origin_candle.high`.
4. Optional confluence: liquidity sweep of a nearby swing high near the
   origin candle raises `probability_score`, sets `swept_liquidity=True`.
5. Reject oversized origin candles relative to ATR, same rule as bullish.

---

## 5. Order Block Lifecycle

```
                 ┌───────────┐
   candidate     │  PENDING  │  origin candle identified, awaiting
   found ───────►│           │  structural confirmation (BOS/CHOCH closed)
                 └─────┬─────┘
                       │ structural event confirmed
                       ▼
                 ┌───────────┐
                 │ CONFIRMED │  OB is valid and published to consumers,
                 │           │  not yet touched by price
                 └─────┬─────┘
                       │ becomes nearest actionable zone in its direction
                       ▼
                 ┌───────────┐
                 │  ACTIVE   │  eligible for signal generation; price has
                 │           │  not re-entered the zone yet
                 └──┬─────┬──┘
     price enters   │     │  price closes fully through opposite side
     zone (touch)   ▼     ▼  (deep violation)
            ┌────────────┐ ┌──────────────┐
            │ MITIGATED  │ │  INVALIDATED │
            │ (touched/  │ │ (structure   │
            │ partially  │ │ broken;      │
            │ used)      │ │ OB no longer │
            └─────┬──────┘ │ trustworthy) │
                  │         └──────────────┘
                  │ configurable: fully consumed after N touches
                  │ or age > max_bars
                  ▼
            ┌────────────┐
            │  EXPIRED   │
            └────────────┘
```

**State definitions:**

- **Creation (`PENDING`)**: origin candle identified; algorithm is waiting
  on the structural break to be finalized (candle close).
- **Confirmation (`CONFIRMED`)**: BOS/CHOCH is confirmed; OB zone is
  frozen (immutable `top`/`bottom`/`origin_index`) and emitted via
  `OrderBlockEvent(type=CREATED)`.
- **Active (`ACTIVE`)**: OB is live and untouched; it is a valid candidate
  for downstream signal generation.
- **Mitigation (`MITIGATED`)**: price has traded back into the zone at
  least once. Configurable policy:
  - `mitigation_mode="first_touch"` → OB becomes `MITIGATED` (weakened but
    optionally still usable once) on first touch.
  - `mitigation_mode="full_close_through"` → OB is only mitigated when a
    candle **closes** through the zone entirely.
  A `mitigated_count` field tracks number of touches for scoring/decay.
- **Invalidity (`INVALIDATED`)**: a candle **closes** beyond the far side
  of the OB in the adverse direction (e.g., for a bullish OB, a close
  below `bottom`), meaning the underlying structural premise failed. This
  is terminal — invalidated OBs are never reused.
- **Expiration (`EXPIRED`)**: OB exceeds a configurable maximum age
  (`max_age_bars`) or maximum mitigation touches without invalidation;
  moved to historical archive, no longer considered `ACTIVE`.

State transitions are enforced by a single method
(`_transition(ob, new_state)`) with an explicit allowed-transition table,
rejecting any illegal transition (defensive programming — this is exactly
the kind of invariant that should have a dedicated unit test).

---

## 6. Data Model Design

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional, Literal


class OrderBlockDirection(Enum):
    BULLISH = auto()
    BEARISH = auto()


class OrderBlockState(Enum):
    PENDING = auto()
    CONFIRMED = auto()
    ACTIVE = auto()
    MITIGATED = auto()
    INVALIDATED = auto()
    EXPIRED = auto()


class OrderBlockTriggerType(Enum):
    BOS = auto()
    CHOCH = auto()


class OrderBlockEventType(Enum):
    CREATED = auto()
    CONFIRMED = auto()
    ACTIVATED = auto()
    MITIGATED = auto()
    INVALIDATED = auto()
    EXPIRED = auto()


@dataclass(frozen=True)
class OrderBlock:
    """
    Immutable core identity + zone. Fields that change over time (state,
    mitigation count) are intentionally NOT here if you want full
    immutability — see OrderBlockRecord below for the mutable wrapper
    pattern, which is the recommended production approach.
    """
    id: str                                   # stable uuid, generated at creation
    direction: OrderBlockDirection
    origin_index: int                         # bar index of origin candle
    origin_timestamp: datetime
    top: float
    bottom: float
    trigger_type: OrderBlockTriggerType
    trigger_index: int                        # bar index of confirming BOS/CHOCH
    swept_liquidity: bool = False
    displacement_strength: float = 0.0        # e.g., ATR multiple of the leg
    probability_score: float = 0.0            # composite quality score 0-1
    symbol: str = "XAUUSD"
    timeframe: str = "M15"


@dataclass
class OrderBlockRecord:
    """
    Mutable state wrapper the engine actually manages internally.
    The immutable `OrderBlock` is the identity/zone; this wrapper tracks
    lifecycle state, which is expected to change over time.
    """
    ob: OrderBlock
    state: OrderBlockState = OrderBlockState.PENDING
    mitigated_count: int = 0
    last_state_change_index: int = 0
    created_at_index: int = 0
    invalidated_reason: Optional[str] = None


@dataclass(frozen=True)
class OrderBlockEvent:
    """
    Emitted to downstream consumers (FVG detector, signal generator,
    event bus / logging). Immutable, timestamped, fully self-describing —
    downstream should never need to reach back into detector internals.
    """
    event_type: OrderBlockEventType
    order_block_id: str
    order_block: OrderBlock
    bar_index: int
    timestamp: datetime
    previous_state: Optional[OrderBlockState]
    new_state: OrderBlockState
    metadata: dict = field(default_factory=dict)
```

**Design notes:**
- `OrderBlock` is frozen (immutable) — its zone and origin can never
  silently change post-confirmation, which is the direct implementation of
  the "no repainting" requirement.
- `OrderBlockRecord` is the internal, mutable lifecycle tracker; only
  `OrderBlockEvent`s (immutable snapshots) leave the detector boundary.
- `id` should be deterministically derivable (e.g., hash of
  `symbol+timeframe+origin_index+direction`) rather than a random UUID, so
  that re-running the same historical data produces identical IDs — this
  is important for reproducible backtests and event deduplication.

---

## 7. State Management

```python
@dataclass
class OrderBlockDetectorState:
    """
    Owns all data required to resume detection at any point without
    recomputation — this is what allows clean checkpoint/restore for
    live trading restarts and deterministic backtest replay.
    """
    symbol: str
    timeframe: str

    # Owned: full lifecycle registry
    order_blocks: dict[str, OrderBlockRecord] = field(default_factory=dict)

    # Owned: fast lookup indices
    active_bullish_ids: list[str] = field(default_factory=list)
    active_bearish_ids: list[str] = field(default_factory=list)

    # Owned: dedup guard — origin indices already used to create an OB
    used_origin_indices: set[int] = field(default_factory=set)

    # Owned: bookkeeping
    last_processed_bar_index: int = -1
    last_processed_timestamp: Optional[datetime] = None

    # Consumed (references only, not owned) — passed in per update, not
    # persisted as detector-owned mutable state:
    #   - latest confirmed Swing points (from SwingDetectorState)
    #   - latest confirmed BOS events (from BOSDetectorState)
    #   - latest confirmed CHOCH events (from CHOCHDetectorState)
    #   - latest confirmed LiquiditySweep events (from LiquidityDetectorState)
```

**What it owns:** the full set of `OrderBlockRecord`s and their lifecycle
state, dedup guards, and its own processing cursor (`last_processed_bar_index`).

**What it consumes (read-only, per bar):** confirmed swing points, BOS
events, CHOCH events, liquidity sweep events. The OB detector must **never**
own or mutate upstream state — it subscribes to already-confirmed,
immutable events from those detectors. This keeps a strict one-way data
flow and avoids circular coupling between structural detectors.

---

## 8. Detector Architecture

```python
from typing import Callable, Iterable

class OrderBlockDetector:
    """
    Stateful, incremental detector. Designed to run identically in
    historical replay and live streaming contexts.

    Inputs (per bar, via update()):
        - candle: Candle (OHLCV, closed or forming)
        - confirmed_swings: list[SwingPoint]      (from SwingDetector)
        - confirmed_bos_events: list[BOSEvent]     (from BOSDetector)
        - confirmed_choch_events: list[CHOCHEvent] (from CHOCHDetector)
        - confirmed_sweep_events: list[LiquiditySweepEvent] (from LiquidityDetector)

    Outputs:
        - list[OrderBlockEvent]  (emitted this update — created/confirmed/
                                   activated/mitigated/invalidated/expired)
        - queryable snapshot via get_active_order_blocks()
    """

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        config: "OrderBlockConfig",
    ) -> None:
        self._config = config
        self._state = OrderBlockDetectorState(symbol=symbol, timeframe=timeframe)
        self._candle_buffer: list["Candle"] = []   # bounded rolling window

    # ---------------- Public API ----------------

    def update(
        self,
        candle: "Candle",
        is_closed: bool,
        confirmed_swings: Iterable["SwingPoint"],
        confirmed_bos_events: Iterable["BOSEvent"],
        confirmed_choch_events: Iterable["CHOCHEvent"],
        confirmed_sweep_events: Iterable["LiquiditySweepEvent"],
    ) -> list[OrderBlockEvent]:
        """
        Main entry point. Called once per bar (and optionally once per
        tick for forming-bar mitigation checks, if intrabar mitigation
        tracking is enabled in config).
        Returns all OrderBlockEvents emitted as a result of this update.
        """
        ...

    def get_active_order_blocks(
        self, direction: Optional[OrderBlockDirection] = None
    ) -> list[OrderBlock]:
        """Read-only snapshot for downstream consumers (FVG, signal gen)."""
        ...

    def get_order_block(self, ob_id: str) -> Optional[OrderBlockRecord]:
        ...

    def reset(self) -> None:
        """Full state reset — required for clean backtest re-runs and unit tests."""
        ...

    def get_state_snapshot(self) -> OrderBlockDetectorState:
        """For checkpointing / persistence between live-trading restarts."""
        ...

    def load_state_snapshot(self, state: OrderBlockDetectorState) -> None:
        ...

    # ---------------- Private methods ----------------

    def _try_create_from_bos(self, bos_event: "BOSEvent") -> Optional[OrderBlockRecord]:
        """Search backward from bos_event.break_index for a valid origin candle."""
        ...

    def _try_create_from_choch(self, choch_event: "CHOCHEvent") -> Optional[OrderBlockRecord]:
        ...

    def _find_origin_candle(
        self, break_index: int, direction: OrderBlockDirection
    ) -> Optional[int]:
        """Locate last opposite-colored candle before the impulsive leg."""
        ...

    def _validate_displacement(
        self, origin_index: int, break_index: int
    ) -> tuple[bool, float]:
        """Returns (is_valid, displacement_strength)."""
        ...

    def _check_liquidity_confluence(
        self, origin_index: int, sweep_events: Iterable["LiquiditySweepEvent"]
    ) -> bool:
        ...

    def _register_order_block(self, record: OrderBlockRecord) -> OrderBlockEvent:
        """Dedup-guarded insertion into state.order_blocks."""
        ...

    def _update_mitigation_and_invalidation(
        self, candle: "Candle"
    ) -> list[OrderBlockEvent]:
        """Runs every closed bar against all ACTIVE order blocks."""
        ...

    def _expire_stale_blocks(self, current_index: int) -> list[OrderBlockEvent]:
        ...

    def _transition(
        self, record: OrderBlockRecord, new_state: OrderBlockState, reason: str = ""
    ) -> OrderBlockEvent:
        """Single choke point for all state changes; enforces legal-transition table."""
        ...
```

**`OrderBlockConfig`** (companion dataclass, not expanded fully here, but
should include at minimum): `zone_definition`, `displacement_atr_multiple`,
`max_atr_multiple`, `min_break_buffer`, `mitigation_mode`,
`max_age_bars`, `require_liquidity_confluence: bool`,
`min_probability_score`.

---

## 9. Backtesting Considerations

- **No future data leakage**: `update()` only ever receives data up to and
  including the current bar. The origin-candle search
  (`_find_origin_candle`) walks *backward* only. No function in this
  detector may accept or reference `future_candles`. This should be
  enforced structurally (no such parameter exists anywhere in the API),
  not just by convention.
- **No repainting**: guaranteed by immutability of `OrderBlock` post
  confirmation (§2.5, §6) and by only acting on `is_closed=True` bars for
  zone creation. Mitigation/invalidation checks may optionally run
  intrabar (for live responsiveness), but zone geometry itself never
  changes.
- **Historical replay compatibility**: the detector must be fully
  deterministic — same input sequence → same output sequence, every time.
  This means: no wall-clock (`datetime.now()`) calls inside detection
  logic, no reliance on external random state, no hidden global state.
  All "now" concepts come from the candle's own timestamp.
  A backtest engine should be able to feed candles one at a time from an
  array and get bit-identical results to a live run over the same data.
- **Live trading compatibility**: same `update()` interface used in both
  contexts — the detector must be agnostic to *where* candles come from
  (historical array vs. live feed adapter). This is why `update()` takes
  plain data objects (`Candle`, event lists) rather than reaching into a
  broker/data connection itself.
- **Checkpoint/restore**: `get_state_snapshot()` / `load_state_snapshot()`
  allow a live process to restart mid-session without re-processing full
  history, while producing state identical to what continuous processing
  would have produced (assuming the snapshot itself was taken correctly
  at a bar boundary).
- **Warm-up handling**: detector should clearly report whether it has
  sufficient buffered candles/ATR history to begin emitting OBs
  (`is_warmed_up` property), so a backtest doesn't score false negatives
  during the warm-up window.

---

## 10. Testing Strategy

Suggested unit test suite (pytest-style naming), organized by concern:

**Initialization & reset**
- `test_initializes_with_empty_state`
- `test_reset_clears_all_order_blocks_and_indices`
- `test_state_snapshot_roundtrip_restores_identical_state`

**Bullish OB detection**
- `test_bullish_ob_created_on_confirmed_bos_with_valid_displacement`
- `test_bullish_ob_created_on_confirmed_choch`
- `test_bullish_ob_zone_matches_origin_candle_open_high_low_per_config`
- `test_bullish_ob_flags_liquidity_confluence_when_sweep_present`

**Bearish OB detection**
- `test_bearish_ob_created_on_confirmed_bos_with_valid_displacement`
- `test_bearish_ob_created_on_confirmed_choch`
- `test_bearish_ob_zone_matches_origin_candle_definition`

**Invalid OB rejection**
- `test_rejects_ob_when_displacement_below_atr_threshold`
- `test_rejects_ob_when_origin_candle_exceeds_max_atr_multiple`
- `test_rejects_ob_when_break_close_does_not_clear_min_buffer`
- `test_rejects_ob_when_no_confirmed_structural_event_present`
- `test_ignores_unclosed_forming_candle_for_ob_creation`

**Mitigation**
- `test_ob_transitions_to_mitigated_on_first_touch_mode`
- `test_ob_transitions_to_mitigated_only_on_full_close_through_mode`
- `test_mitigated_count_increments_on_repeated_touches`
- `test_ob_invalidated_on_adverse_close_through_far_side`
- `test_ob_expires_after_max_age_bars`

**Duplicate protection**
- `test_does_not_create_second_ob_for_same_origin_index`
- `test_replaying_same_candle_twice_does_not_duplicate_ob`
- `test_ob_ids_are_deterministic_given_same_inputs`

**State machine integrity**
- `test_illegal_state_transition_raises_or_is_rejected`
- `test_state_transitions_are_monotonic_never_revert`

**Determinism / backtest-live parity**
- `test_batch_replay_produces_identical_events_to_incremental_replay`
- `test_no_lookahead_origin_search_never_reads_beyond_current_index`

---

## 11. Architectural Recommendations

**Should `OrderBlockDetector` consume BOS state?**
Yes — but only **confirmed BOS events**, not raw BOS detector internal
state. It should depend on the *event stream/interface* (`BOSEvent`), not
on `BOSDetector`'s internal data structures. This is the primary trigger
for continuation-style order blocks.

**Should it consume CHOCH events?**
Yes, for the same reason — CHOCH-triggered OBs are typically the
higher-quality, reversal-marking blocks and should be tagged distinctly
(`trigger_type=CHOCH`) so downstream signal generation can weight them
differently from BOS-triggered continuation OBs.

**Should it consume Liquidity Sweep events?**
Yes, but as an **optional confluence input**, not a hard dependency. The
detector should function (with lower `probability_score`) even if no
sweep event is available near the origin candle. Treat it as a
scoring/quality signal, not a gating requirement, unless the platform's
strategy explicitly wants to restrict to swept OBs only
(`require_liquidity_confluence=True` in config — expose the choice, don't
hardcode it).

**What should it own?**
- The full `OrderBlockRecord` registry and lifecycle state machine.
- Its own dedup guard (`used_origin_indices`).
- Its own processing cursor and warm-up status.
- Its own configuration (`OrderBlockConfig`).

**What it must NOT own:**
- Swing points, BOS/CHOCH logic, or liquidity sweep logic — those remain
  the exclusive responsibility of their own detectors. `OrderBlockDetector`
  only ever reads their **confirmed, immutable outputs**.
- Any knowledge of Fair Value Gaps, signal generation, or risk management
  — those are downstream consumers of `OrderBlockEvent`s, not concerns of
  this module.

**Coupling principle:** each detector in the pipeline should depend only
on the *event/output types* of the module directly upstream of it, never
on that module's internal state or implementation. This keeps the chain
```
Swing → BOS → CHOCH → Liquidity → OrderBlock → FVG
```
composable, independently testable, and safely replaceable — you should
be able to swap out the BOS detector implementation entirely as long as it
still emits `BOSEvent`, without touching `OrderBlockDetector` at all.
