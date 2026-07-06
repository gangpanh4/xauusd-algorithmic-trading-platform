"""
signals/signal_engine.py
────────────────────────
Core signal logic for XAUUSD.

Changes in this version:
  Fix #4 — Updated confidence weights (TREND 40%, MACD 25%, RSI 20%, BB 10%, VOL 5%)
  Fix #5 — HTF (H4 EMA 200) bias passed in and used as a hard gate
  Fix #6 — Dynamic TP via find_dynamic_tp() instead of fixed ATR multiple

Signal flow:
  0. News filter         → early exit if high-impact event nearby
  1. HTF trend gate      → H4 EMA 200 must agree with H1 direction  (Fix #5)
  2. H1 trend            → EMA 50/200 direction + price vs EMA 200   (Fix #4: 40%)
  3. RSI confirmation    → momentum zone check                        (Fix #4: 20%)
  4. MACD confirmation   → histogram crossover                        (Fix #4: 25%)
  5. Bollinger context   → price vs bands                             (Fix #4: 10%)
  6. Volume context      → tick volume ratio (deprioritised)          (Fix #4:  5%)
  7. Confidence gate     → must exceed MIN_CONFIDENCE
  8. ATR stop loss       → fixed ATR_SL_MULTI × ATR
  9. Dynamic TP          → swing high/low target, floored by min R:R  (Fix #6)
 10. Signal decision     → BUY / SELL / NO TRADE
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, UTC
from typing import Literal, Optional
import logging

from core.indicators import find_dynamic_tp, is_within_trading_session, get_mtf_trigger

logger = logging.getLogger(__name__)

SignalType = Literal["BUY", "SELL", "NO TRADE"]


@dataclass
class SignalResult:
    signal:         SignalType
    confidence:     float
    entry:          float
    stop_loss:      float
    take_profit:    float
    risk_reward:    float
    lot_size:       float
    pips_risk:      float
    tp_method:      str            = "atr_fallback"   # Fix #6 — how TP was chosen
    htf_aligned:    Optional[bool] = None             # Fix #5 — H4 agreement
    reasoning:      list           = field(default_factory=list)
    warnings:       list           = field(default_factory=list)
    timestamp:      str            = field(default_factory=lambda: datetime.now(UTC).isoformat())
    indicators:     dict           = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        htf_str = ("✓ aligned" if self.htf_aligned
                   else "✗ not aligned" if self.htf_aligned is False
                   else "—")
        lines = [
            f"\n{'='*62}",
            f"  XAUUSD Signal  |  {self.timestamp}",
            f"{'='*62}",
            f"  Signal     : {self.signal}",
            f"  Confidence : {self.confidence:.1%}",
            f"  HTF (H4)   : {htf_str}",
            f"  Entry      : {self.entry:.2f}",
            f"  Stop Loss  : {self.stop_loss:.2f}  (risk: {self.pips_risk:.1f} pts)",
            f"  Take Profit: {self.take_profit:.2f}  [{self.tp_method}]",
            f"  R:R Ratio  : 1:{self.risk_reward:.2f}",
            f"  Lot Size   : {self.lot_size}",
            f"{'─'*62}",
            f"  Reasoning:",
        ]
        for r in self.reasoning:
            lines.append(f"    ✓ {r}")
        if self.warnings:
            lines.append(f"  Warnings:")
            for w in self.warnings:
                lines.append(f"    ⚠ {w}")
        lines.append(f"{'='*62}")
        return "\n".join(lines)


class SignalEngine:
    """
    Generates BUY / SELL / NO TRADE signals for XAUUSD
    using a multi-layer, weighted confirmation approach.
    """

    def __init__(self, cfg):
        self.cfg = cfg

    def generate(
        self,
        snapshot: dict,
        account_balance: float,
        df,                          # full H1 DataFrame (for swing TP)
        news_blocked: bool = False,
        htf_bias: Optional[dict] = None,  # Fix #5 — H4 trend info
        mtf_trigger: Optional[dict] = None,  # Feature #8 — M15 MACD trigger
    ) -> SignalResult:
        """
        Main entry point.
        snapshot    : flat dict of latest H1 indicator values
        df          : full H1 DataFrame (needed by find_dynamic_tp)
        htf_bias    : result of get_htf_bias() on the H4 DataFrame
        mtf_trigger : result of get_mtf_trigger() on the M15 DataFrame
                      (Feature #8 — multi-timeframe entry trigger)
        """
        cfg       = self.cfg
        s         = snapshot
        reasoning = []
        warnings  = []

        # ── Feature #2: Trading session / time filter ─────────
        if not is_within_trading_session(cfg):
            return self._no_trade(
                s,
                f"Outside trading session ({cfg.TRADING_START_HOUR_UTC:02d}:00–"
                f"{cfg.TRADING_END_HOUR_UTC:02d}:00 UTC). Signal suppressed.",
                warnings,
            )

        # ── 0. News filter ────────────────────────────────────
        if news_blocked and cfg.NEWS_FILTER_ENABLED:
            return self._no_trade(s, "High-impact news event nearby — news filter active.", warnings)

        # ── 1. H1 Trend via EMA 50 / 200 ─────────────────────
        ema_slow  = s.get("ema_slow")
        ema_fast  = s.get("ema_fast")
        price     = s["close"]

        if ema_slow is None:
            return self._no_trade(s, "Insufficient data for EMA 200.", warnings)

        bullish_h1 = price > ema_slow and (ema_fast is None or ema_fast > ema_slow)
        bearish_h1 = price < ema_slow and (ema_fast is None or ema_fast < ema_slow)

        # Fix #4: WEIGHT_TREND = 0.40
        if bullish_h1:
            trend_score = cfg.WEIGHT_TREND
            reasoning.append(
                f"H1 BULLISH: price ({price:.2f}) > EMA 200 ({ema_slow:.2f})"
                + (f", EMA 50 ({ema_fast:.2f}) > EMA 200" if ema_fast else "")
            )
        elif bearish_h1:
            trend_score = cfg.WEIGHT_TREND
            reasoning.append(
                f"H1 BEARISH: price ({price:.2f}) < EMA 200 ({ema_slow:.2f})"
                + (f", EMA 50 ({ema_fast:.2f}) < EMA 200" if ema_fast else "")
            )
        else:
            trend_score = 0.0
            warnings.append(
                f"H1 mixed signals: price vs EMA 200 and EMA 50 disagree — "
                "no clear trend, signal strength reduced"
            )

        # ── Fix #5: HTF (H4 EMA 200) Hard Gate ───────────────
        htf_aligned: Optional[bool] = None

        # C5 fix: if the HTF filter is enabled but H4 data could not be
        # fetched (htf_bias is None), this is a mandatory filter that
        # cannot be evaluated — fail CLOSED (block the trade) instead of
        # silently skipping the gate and letting the signal through.
        if cfg.HTF_FILTER_ENABLED and not htf_bias:
            warnings.append(
                "H4 data unavailable — mandatory HTF filter cannot be "
                "evaluated. Failing closed: signal blocked."
            )
            return self._no_trade(
                s,
                "H4 EMA 200 filter: H4 data unavailable — failing closed.",
                warnings,
                htf_aligned=None,
            )

        if cfg.HTF_FILTER_ENABLED and htf_bias:
            htf_bullish = htf_bias.get("htf_bullish")
            htf_bearish = htf_bias.get("htf_bearish")
            htf_e200    = htf_bias.get("htf_ema200")

            if htf_bullish is None:
                warnings.append("H4 EMA 200 not available — HTF filter skipped")
            elif bullish_h1 and htf_bullish:
                htf_aligned = True
                reasoning.append(
                    f"H4 BULLISH alignment: H4 price above H4 EMA 200 ({htf_e200:.2f}) "
                    "— HTF trend confirms H1 BUY"
                )
                trend_score = min(trend_score * 1.15, cfg.WEIGHT_TREND * 1.2)
            elif bearish_h1 and htf_bearish:
                htf_aligned = True
                reasoning.append(
                    f"H4 BEARISH alignment: H4 price below H4 EMA 200 ({htf_e200:.2f}) "
                    "— HTF trend confirms H1 SELL"
                )
                trend_score = min(trend_score * 1.15, cfg.WEIGHT_TREND * 1.2)
            else:
                htf_aligned = False
                warnings.append(
                    f"H4 trend DISAGREES with H1 direction — "
                    f"H4 EMA 200 at {htf_e200:.2f}. Signal blocked by HTF filter."
                )
                return self._no_trade(
                    s,
                    f"H4 EMA 200 filter: H4 trend opposes H1 signal direction.",
                    warnings,
                    htf_aligned=False,
                )

        # ── Feature #8: M15 MACD Crossover Trigger (Multi-TF Entry) ──
        # H4 = trend (above), H1 = setup (trend_score/RSI/MACD below),
        # M15 = trigger. A directional H1 setup is only actionable once
        # the M15 MACD histogram freshly crosses in the same direction.
        if cfg.MTF_ENTRY_ENABLED and (bullish_h1 or bearish_h1):
            if mtf_trigger is None or not mtf_trigger.get("available"):
                warnings.append("M15 MTF trigger data unavailable — entry trigger skipped this cycle.")
                return self._no_trade(
                    s, "M15 trigger unavailable — cannot confirm entry timing.", warnings,
                )
            elif bullish_h1 and not mtf_trigger.get("macd_cross_up"):
                return self._no_trade(
                    s,
                    "M15 MACD has not crossed bullish yet — waiting for trigger "
                    "(H4 trend + H1 setup are bullish, M15 timing not confirmed).",
                    warnings,
                )
            elif bearish_h1 and not mtf_trigger.get("macd_cross_dn"):
                return self._no_trade(
                    s,
                    "M15 MACD has not crossed bearish yet — waiting for trigger "
                    "(H4 trend + H1 setup are bearish, M15 timing not confirmed).",
                    warnings,
                )
            else:
                reasoning.append(
                    f"M15 MACD crossover confirms entry trigger "
                    f"(hist={mtf_trigger.get('macd_hist')}) — H4 trend → H1 setup → M15 trigger aligned"
                )

        # ── 2. RSI Confirmation (Fix #4: 20%) ─────────────────
        rsi       = s["rsi"]
        rsi_score = 0.0

        if bullish_h1:
            if 40 <= rsi <= 65:
                rsi_score = cfg.WEIGHT_RSI
                reasoning.append(f"RSI ({rsi:.1f}) in bullish momentum zone (40–65)")
            elif rsi < 30:
                rsi_score = cfg.WEIGHT_RSI * 1.1
                reasoning.append(f"RSI ({rsi:.1f}) oversold on uptrend — strong bounce setup")
            elif rsi > 70:
                rsi_score = cfg.WEIGHT_RSI * 0.2
                warnings.append(f"RSI ({rsi:.1f}) overbought — BUY entry risk elevated")
            else:
                rsi_score = cfg.WEIGHT_RSI * 0.4
                warnings.append(f"RSI ({rsi:.1f}) below 40 on uptrend — momentum lagging")
        elif bearish_h1:
            if 35 <= rsi <= 60:
                rsi_score = cfg.WEIGHT_RSI
                reasoning.append(f"RSI ({rsi:.1f}) in bearish momentum zone (35–60)")
            elif rsi > 70:
                rsi_score = cfg.WEIGHT_RSI * 1.1
                reasoning.append(f"RSI ({rsi:.1f}) overbought on downtrend — strong pullback setup")
            elif rsi < 30:
                rsi_score = cfg.WEIGHT_RSI * 0.2
                warnings.append(f"RSI ({rsi:.1f}) oversold — SELL bounce risk elevated")
            else:
                rsi_score = cfg.WEIGHT_RSI * 0.4
                warnings.append(f"RSI ({rsi:.1f}) above 60 on downtrend — momentum lagging")

        # ── 3. MACD Confirmation (Fix #4: 25%) ────────────────
        macd_hist      = s["macd_hist"]
        prev_macd_hist = s["prev_macd_hist"]
        macd_score     = 0.0
        macd_cross_up  = prev_macd_hist < 0 and macd_hist > 0
        macd_cross_dn  = prev_macd_hist > 0 and macd_hist < 0

        if bullish_h1:
            if macd_cross_up:
                macd_score = cfg.WEIGHT_MACD * 1.2   # fresh cross gets bonus
                reasoning.append("MACD fresh bullish crossover ↑ — high-conviction entry")
            elif macd_hist > 0:
                macd_score = cfg.WEIGHT_MACD
                reasoning.append(f"MACD histogram positive ({macd_hist:.4f}) — bullish momentum")
            else:
                warnings.append(f"MACD histogram negative ({macd_hist:.4f}) on BUY — divergence warning")
        elif bearish_h1:
            if macd_cross_dn:
                macd_score = cfg.WEIGHT_MACD * 1.2
                reasoning.append("MACD fresh bearish crossover ↓ — high-conviction entry")
            elif macd_hist < 0:
                macd_score = cfg.WEIGHT_MACD
                reasoning.append(f"MACD histogram negative ({macd_hist:.4f}) — bearish momentum")
            else:
                warnings.append(f"MACD histogram positive ({macd_hist:.4f}) on SELL — divergence warning")

        # ── 4. Bollinger Band Context (Fix #4: 10%) ───────────
        bb_pct    = s["bb_pct"]
        bb_score  = 0.0

        if bullish_h1:
            if 0.2 <= bb_pct <= 0.75:
                bb_score = cfg.WEIGHT_BB
                reasoning.append(f"Price mid-band (BB%={bb_pct:.2f}) — room to extend upward")
            elif bb_pct > 0.85:
                warnings.append(f"Price near upper BB ({bb_pct:.2f}) — potential short-term resistance")
            elif bb_pct < 0.2:
                bb_score = cfg.WEIGHT_BB * 0.7   # near lower band on bullish = attractive entry
                reasoning.append(f"Price at lower BB ({bb_pct:.2f}) on uptrend — pullback entry zone")
        elif bearish_h1:
            if 0.25 <= bb_pct <= 0.8:
                bb_score = cfg.WEIGHT_BB
                reasoning.append(f"Price mid-band (BB%={bb_pct:.2f}) — room to extend downward")
            elif bb_pct < 0.15:
                warnings.append(f"Price near lower BB ({bb_pct:.2f}) — potential short-term support")
            elif bb_pct > 0.8:
                bb_score = cfg.WEIGHT_BB * 0.7
                reasoning.append(f"Price at upper BB ({bb_pct:.2f}) on downtrend — pullback entry zone")

        # ── 5. Volume (Fix #4: 5% — MT5 tick vol unreliable) ──
        vol_ratio  = s.get("vol_ratio", 1.0)
        vol_score  = 0.0

        if vol_ratio >= 1.5:
            vol_score = cfg.WEIGHT_VOLUME
            reasoning.append(f"Tick volume {vol_ratio:.1f}× above average (note: MT5 tick vol, indicative only)")
        elif vol_ratio >= 1.0:
            vol_score = cfg.WEIGHT_VOLUME * 0.5
        else:
            # Below average volume — no deduction but no bonus either
            pass

        # ── Final Confidence Score ─────────────────────────────
        raw_confidence = trend_score + rsi_score + macd_score + bb_score + vol_score
        confidence     = min(raw_confidence, 1.0)

        # ── ATR Stop Loss ──────────────────────────────────────
        atr         = s["atr"]
        sl_distance = atr * cfg.ATR_SL_MULTI

        if bullish_h1:
            entry     = price
            stop_loss = round(price - sl_distance, 2)
        else:
            entry     = price
            stop_loss = round(price + sl_distance, 2)

        # ── Fix #6: Dynamic Take Profit ───────────────────────
        direction = "BUY" if bullish_h1 else "SELL"
        take_profit, tp_method = find_dynamic_tp(
            df         = df,
            direction  = direction,
            entry      = entry,
            atr        = atr,
            sl_distance= sl_distance,
            cfg        = cfg,
        )

        tp_distance = abs(take_profit - entry)
        risk_reward = tp_distance / sl_distance if sl_distance > 0 else 0

        # ── Lot size ───────────────────────────────────────────
        lot_size  = self._calc_lot_size(account_balance, sl_distance, cfg)

        # ── Signal Decision ────────────────────────────────────
        passes_confidence = confidence >= cfg.MIN_CONFIDENCE
        passes_rr         = risk_reward >= cfg.MIN_RISK_REWARD

        if not passes_confidence:
            warnings.append(
                f"Confidence {confidence:.1%} below threshold {cfg.MIN_CONFIDENCE:.0%} — NO TRADE"
            )
        if not passes_rr:
            warnings.append(
                f"R:R 1:{risk_reward:.2f} below minimum 1:{cfg.MIN_RISK_REWARD} — NO TRADE"
            )

        if passes_confidence and passes_rr:
            sig = "BUY" if bullish_h1 else "SELL"
            reasoning.append(
                f"R:R 1:{risk_reward:.2f} ✓  |  TP method: {tp_method}  |  "
                f"Confidence: {confidence:.1%}"
            )
        else:
            sig = "NO TRADE"

        return SignalResult(
            signal      = sig,
            confidence  = round(confidence, 4),
            entry       = round(entry, 2),
            stop_loss   = stop_loss,
            take_profit = take_profit,
            risk_reward = round(risk_reward, 2),
            lot_size    = lot_size,
            pips_risk   = round(sl_distance, 2),
            tp_method   = tp_method,
            htf_aligned = htf_aligned,
            reasoning   = reasoning,
            warnings    = warnings,
            indicators  = {
                "rsi":          round(rsi, 2),
                "atr":          round(atr, 4),
                "macd_hist":    round(macd_hist, 4),
                "bb_pct":       round(bb_pct, 4),
                "ema_slow":     round(ema_slow, 2),
                "ema_fast":     round(ema_fast, 2) if ema_fast else None,
                "vol_ratio":    round(vol_ratio, 2),
                "tp_method":    tp_method,
                "htf_ema200":   htf_bias.get("htf_ema200") if htf_bias else None,
                "htf_bullish":  htf_bias.get("htf_bullish") if htf_bias else None,
            }
        )

    # ── Helpers ───────────────────────────────────────────────

    def _calc_lot_size(self, balance: float, sl_distance: float, cfg) -> float:
        """
        Risk-based lot sizing for XAUUSD.
        1 standard lot = 100 oz gold.
        $1 price move = $100 P&L per standard lot.
        """
        if sl_distance <= 0:
            return cfg.LOT_SIZE_MIN

        risk_amount = balance * (cfg.RISK_PER_TRADE_PCT / 100)
        lot         = risk_amount / (sl_distance * 100)
        return round(max(cfg.LOT_SIZE_MIN, min(lot, cfg.LOT_SIZE_MAX)), 2)

    def _no_trade(
        self,
        snapshot: dict,
        reason: str,
        warnings: list,
        htf_aligned: Optional[bool] = None,
    ) -> SignalResult:
        warnings.append(reason)
        return SignalResult(
            signal      = "NO TRADE",
            confidence  = 0.0,
            entry       = snapshot.get("close", 0),
            stop_loss   = 0.0,
            take_profit = 0.0,
            risk_reward = 0.0,
            lot_size    = 0.0,
            pips_risk   = 0.0,
            htf_aligned = htf_aligned,
            reasoning   = [],
            warnings    = warnings,
        )
