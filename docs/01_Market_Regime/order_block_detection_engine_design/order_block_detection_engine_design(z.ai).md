As a senior quantitative developer and institutional trader, I approach the concept of "Order Blocks" (OBs) with extreme rigor. In retail trading, an OB is often reduced to "the last opposite candle before a move." Institutionally, an Order Block represents a documented footprint of aggressive institutional inventory acquisition or distribution that subsequently catalyzed a structural market shift.

For XAUUSD—a highly liquid, algorithmically driven, and central-bank-influenced market—noise is immense. A production-grade OB engine cannot simply highlight every down-candle before an up-candle. It must filter for **causality, displacement, and structural context**.

Here is the architectural and quantitative design for the `OrderBlockDetector` module.

---

### 1. What is an Order Block? (Institutional Definition)

An Order Block is the zone of consolidation (typically a single candle or a tight cluster) where a massive institutional position was accumulated or distributed, immediately preceding a **displacement** event that breaks market structure.

*   **Bullish OB:** The last bearish candle before a violent upward displacement that causes a Break of Structure (BOS) or Change of Character (CHOCH). It represents institutional demand.
*   **Bearish OB:** The last bullish candle before a violent downward displacement that causes a BOS or CHOCH. It represents institutional supply.
*   **Real OB vs. Random S/R:** Random support/resistance is an artifact of price bouncing. A real OB has **causality**—it is the *cause* of the structural break. Furthermore, a real OB must exhibit **displacement** (price leaving the zone aggressively) and **imbalance** (Fair Value Gaps) leaving the zone. Without displacement, it is just consolidation, not an Order Block.

---

### 2. Detection Algorithm

The detector operates on an **Event-Driven** paradigm, reacting to structural shifts rather than scanning blindly.

**Relationship with Upstream Modules:**
*   **CHOCH/BOS:** These are the *triggers*. The detector only looks backward to find the OB *after* a BOS or CHOCH is confirmed on the close of a candle.
*   **Swing Highs/Lows:** Used for invalidation. If a Bearish OB is bypassed by a new Swing High without being mitigated, it is invalidated.
*   **Liquidity Sweeps:** Used as a **confluence filter**. An OB that immediately follows a liquidity sweep (indicating a stop-run to fill large orders) is graded as a "Tier 1" (Institutional) OB. An OB without a sweep is "Tier 2".
*   **FVG Detector (Downstream):** Once an OB is detected, the FVG detector will later check if an FVG left the OB. If not, the OB's probability of successful mitigation drops significantly.

**Confirmation & Repainting Avoidance:**
*   **No Repainting:** An OB is strictly defined using the `close` of the trigger candle (CHOCH/BOS) and the `open/high/low/close` of historical, closed candles.
*   **Confirmation:** To prevent detecting micro-OBs in choppy XAUUSD ranges, an OB is only considered "Confirmed" if price does not return to mitigate it within $N$ candles (e.g., 3 candles), or if a subsequent pullback holds above/below the 50% level of the displacement leg.

---

### 3. Bullish Order Block Rules

1.  **Prerequisite:** A confirmed Bearish-to-Bullish CHOCH or Bullish BOS occurs at index $i$.
2.  **Lookback:** Identify the exact start of the impulsive leg that caused the break. This is typically the lowest low before the sequence of higher highs leading to the break.
3.  **Candle Condition:** The candle immediately preceding the start of the impulse (index $start - 1$) MUST be bearish (`Close < Open`).
4.  **Displacement Condition:** The move from the high of the OB candidate to the high of the CHOCH candle must exceed a minimum ATR multiplier (e.g., $> 1.5 \times ATR_{14}$). This filters out weak, ranging breaks.
5.  **Zone Definition:** `Top = OB_Candle.High`, `Bottom = OB_Candle.Low`. (Some quants use `Body`, but wicks contain stop-loss orders. We track both and use Body for strict mitigation).

---

### 4. Bearish Order Block Rules

1.  **Prerequisite:** A confirmed Bullish-to-Bearish CHOCH or Bearish BOS occurs at index $i$.
2.  **Lookback:** Identify the highest high before the sequence of lower lows leading to the break.
3.  **Candle Condition:** The candle immediately preceding the start of the impulse (index $start - 1$) MUST be bullish (`Close > Open`).
4.  **Displacement Condition:** The move from the low of the OB candidate to the low of the CHOCH candle must exceed a minimum ATR multiplier.
5.  **Zone Definition:** `Top = OB_Candle.High`, `Bottom = OB_Candle.Low`.

---

### 5. Order Block Lifecycle

*   **Created:** Detected on the close of a BOS/CHOCH candle. State is `UNCONFIRMED`.
*   **Confirmed:** Survives the confirmation window (e.g., $N$ periods) without mitigation. State changes to `ACTIVE`. Emitted to the event bus.
*   **Mitigated:** Price action interacts with the OB body (e.g., wick into the body, or close inside the body depending on strictness settings). State changes to `MITIGATED`. Emitted to event bus for Signal Generator.
*   **Invalidated:** Market structure creates a new extreme (e.g., higher high for a bearish OB) without mitigating the OB. State changes to `INVALIDATED`. Removed from active memory.
*   **Expired:** XAUUSD is time-sensitive. If an Active OB is not mitigated within $X$ bars or $Y$ hours, it decays. State changes to `EXPIRED`.

---

### 6. Data Model Design

```python
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import pandas as pd

class OBType(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"

class OBStatus(Enum):
    UNCONFIRMED = "UNCONFIRMED"
    ACTIVE = "ACTIVE"
    MITIGATED = "MITIGATED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"

class OBEventType(Enum):
    CREATED = "CREATED"
    CONFIRMED = "CONFIRMED"
    MITIGATED = "MITIGATED"
    INVALIDATED = "INVALIDATED"

class OBTier(Enum):
    TIER_1_SWEEP = 1  # Preceded by liquidity sweep
    TIER_2_STANDARD = 2 # Standard BOS/CHOCH

@dataclass
class OrderBlock:
    ob_id: str
    ob_type: OBType
    status: OBStatus
    tier: OBTier
    
    # Candle indices
    start_index: int       # Index of the OB candle itself
    trigger_index: int     # Index of the CHOCH/BOS candle
    
    # Price Boundaries
    high_price: float
    low_price: float
    open_price: float
    close_price: float
    body_top: float
    body_bottom: float
    
    # Contextual Metrics
    displacement_atr: float # How strong the move off the OB was
    cause_event_id: str    # ID of the CHOCH/BOS that created this
    
    # Timestamps
    creation_time: datetime
    mitigation_time: datetime = None
    
    def is_mitigated_by(self, high: float, low: float, strict: bool = False) -> bool:
        """Checks if a candle mitigates the OB."""
        if strict:
            return low <= self.body_bottom and high >= self.body_top
        # Standard mitigation: price pierces the body
        return low <= self.body_top and high >= self.body_bottom

@dataclass
class OrderBlockEvent:
    event_type: OBEventType
    order_block: OrderBlock
    timestamp: datetime
    trigger_price: float # The price that caused mitigation/invalidation
```

---

### 7. State Management

```python
@dataclass
class OrderBlockDetectorState:
    """
    Maintains the exact state required by the detector. 
    Serializable for backtesting state saves.
    """
    active_obs: list[OrderBlock] = field(default_factory=list)
    unconfirmed_obs: list[OrderBlock] = field(default_factory=list)
    historical_obs: list[OrderBlock] = field(default_factory=list) # For analytics
    
    # Consumed upstream states (snapshotted or referenced)
    last_choch_id: str = None
    
    # Configuration
    min_displacement_atr: float = 1.5
    confirmation_bars: int = 3
    max_active_bars: int = 100 # Expiration limit
    strict_mitigation: bool = False
```

---

### 8. Detector Architecture

```python
class OrderBlockDetector:
    def __init__(self, state: OrderBlockDetectorState, atr_calculator):
        self.state = state
        self.atr_calculator = atr_calculator
        self._event_callbacks = []

    def subscribe(self, callback):
        self._event_callbacks.append(callback)

    def _emit(self, event: OrderBlockEvent):
        for cb in self._event_callbacks:
            cb(event)

    # --- Public Methods (Called by Orchestrator) ---

    def on_choch(self, choch_event: CHOCHEvent, current_bar_index: int):
        """Entry point when a CHOCH is detected."""
        self._evaluate_structure_break(
            event=choch_event, 
            ob_type=OBType.BULLISH if choch_event.direction == "BULLISH" else OBType.BEARISH,
            bar_index=current_bar_index
        )

    def on_bos(self, bos_event: BOSEvent, current_bar_index: int):
        """Entry point when a BOS is detected."""
        self._evaluate_structure_break(
            event=bos_event,
            ob_type=OBType.BULLISH if bos_event.direction == "BULLISH" else OBType.BEARISH,
            bar_index=current_bar_index
        )

    def on_bar_close(self, bar: 'BarData', bar_index: int):
        """
        Called on every closed bar to manage lifecycle:
        Confirmation, Expiration, Mitigation, Invalidation.
        """
        self._process_confirmations(bar_index)
        self._process_mitigations(bar, bar_index)
        self._process_expirations(bar_index)

    def reset(self):
        """Crucial for backtesting replay between different XAUUSD sessions."""
        self.state = OrderBlockDetectorState()

    # --- Private Methods ---

    def _evaluate_structure_break(self, event, ob_type: OBType, bar_index: int):
        ob_candle = self._find_ob_candidate(event, ob_type)
        if not ob_candle:
            return
            
        if not self._meets_candle_criteria(ob_candle, ob_type):
            return
            
        if not self._meets_displacement_criteria(ob_candle, event, bar_index):
            return

        tier = self._determine_tier(event)
        
        ob = OrderBlock(
            ob_id=f"OB_{bar_index}_{ob_type.value}",
            ob_type=ob_type,
            status=OBStatus.UNCONFIRMED,
            tier=tier,
            start_index=ob_candle.index,
            trigger_index=bar_index,
            high_price=ob_candle.high,
            low_price=ob_candle.low,
            open_price=ob_candle.open,
            close_price=ob_candle.close,
            body_top=max(ob_candle.open, ob_candle.close),
            body_bottom=min(ob_candle.open, ob_candle.close),
            displacement_atr=self._calc_displacement(ob_candle, event),
            cause_event_id=event.event_id,
            creation_time=event.timestamp
        )
        self.state.unconfirmed_obs.append(ob)
        self._emit(OrderBlockEvent(OBEventType.CREATED, ob, event.timestamp, ob.close_price))

    def _find_ob_candidate(self, event, ob_type) -> 'BarData':
        """Complex logic to find the exact candle prior to the impulse leg."""
        # Implementation requires access to historical OHLCV array to trace back 
        # from the event.break_price to the originating swing.
        pass

    def _meets_candle_criteria(self, candle, ob_type) -> bool:
        if ob_type == OBType.BULLISH:
            return candle.close < candle.open # Must be bearish candle
        return candle.close > candle.open # Must be bullish candle

    def _meets_displacement_criteria(self, ob_candle, event, bar_index) -> bool:
        """Ensure the move off the OB was aggressive (XAUUSD filter)."""
        atr = self.atr_calculator.get_atr(bar_index)
        if ob_type == OBType.BULLISH:
            move = event.break_price - ob_candle.high
        else:
            move = ob_candle.low - event.break_price
        return move > (self.state.min_displacement_atr * atr)

    def _process_mitigations(self, bar: 'BarData', bar_index: int):
        for ob in self.state.active_obs:
            if ob.is_mitigated_by(bar.high, bar.low, self.state.strict_mitigation):
                ob.status = OBStatus.MITIGATED
                ob.mitigation_time = bar.timestamp
                self.state.active_obs.remove(ob)
                self.state.historical_obs.append(ob)
                self._emit(OrderBlockEvent(OBEventType.MITIGATED, ob, bar.timestamp, bar.close))
```

---

### 9. Backtesting Considerations

1.  **Strict Event Sequencing:** The orchestrator must process the OHLCV `Bar[i]`, then call `SwingDetector`, then `BOS/CHOCH`, then `OrderBlockDetector.on_choch()`, and finally `OrderBlockDetector.on_bar_close()`. If `on_bar_close` runs before `on_choch`, the OB will be missed or delayed by 1 bar.
2.  **No Intra-bar Assumptions:** We assume entry/mitigation happens on the close of the bar, or strictly using the High/Low of the closed bar. We *never* assume we knew price hit the OB body at 14:03:22 if the bar closes at 14:05:00.
3.  **Historical Replay Compatibility:** The `reset()` method and pure state injection (`OrderBlockDetectorState`) allow the engine to be rewound to any tick or bar index without carrying forward ghost data.
4.  **ATR Lookahead:** The ATR calculator used for displacement must be strictly rolling (e.g., `ta.lib.ATR(high, low, close, timeperiod=14)` evaluated *at the trigger bar*), not a statically calculated ATR over the whole dataset.

---

### 10. Testing Strategy

Using `pytest`. We construct synthetic OHLCV arrays and mock upstream events.

*   `test_standard_bullish_ob_creation`: 3-bar downtrend, strong bullish breakout. Assert `UNCONFIRMED` OB created at the correct high/low.
*   `test_rejection_weak_displacement`: Breakout is only 0.5 ATR. Assert NO OB created.
*   `test_rejection_wrong_candle_color`: Breakout is strong, but the candle before impulse is also bullish. Assert NO OB created (fails institutional logic of accumulation).
*   `test_lifecycle_confirmation`: Create OB. Forward 3 bars where price stays away. Assert status changes to `ACTIVE` and `CONFIRMED` event emitted.
*   `test_lifecycle_mitigation_strict`: Create Bearish OB. Forward bar where low wicks into body but closes above body. Assert NOT mitigated under strict rules.
*   `test_lifecycle_mitigation_standard`: Same bar. Assert IS mitigated under standard rules.
*   `test_duplicate_protection`: CHOCH occurs, OB created. A second CHOCH occurs in the same impulse leg pointing to the exact same OB candle. Assert only ONE OB exists in `active_obs`.
*   `test_expiration`: Create OB. Forward 101 bars (if limit is 100) without mitigation. Assert status is `EXPIRED`.

---

### 11. Architectural Recommendations

**Should OrderBlockDetector consume BOS state?**
**Yes.** While CHOCH marks reversals (highest probability OBs), BOS marks continuations. An OB left behind during a BOS is a "continuation OB" and is highly tradable in XAUUSD trends.

**Should it consume CHOCH events?**
**Absolutely.** This is the primary trigger. The detector should be largely dormant until a CHOCH event arrives.

**Should it consume LiquiditySweep events?**
**As metadata, yes.** The detector should query the `LiquiditySweepDetector` state: *"Did a sweep occur at the extreme just before this CHOCH?"* If yes, it upgrades the OB to `TIER_1`. It should not, however, *wait* for a sweep to create an OB. Not all OBs are preceded by visible sweeps (some are hidden).

**What should it own?**
It must own the **ATR calculation** (or at least the logic interface to it) to enforce displacement. It owns the **lifecycle state machine** of the Order Blocks. It must NOT own the raw OHLCV data; it should receive a reference to the historical array or an interface to fetch a bar by index, maintaining loose coupling with the data pipeline.