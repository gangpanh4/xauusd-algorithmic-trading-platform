# Multi-Timeframe Architecture for Institutional-Grade XAUUSD Algorithmic Trading Platform

---

## PART 1 — Timeframe Hierarchy for XAUUSD

### Architecture
Recommended canonical set: **Monthly, Weekly, Daily, H4, H1, M15, M5**.
M1 should exist **only as an execution microstructure feed**, not as a decision timeframe.

### Reasoning
The architectural principle is that each timeframe must correspond to a distinct horizon of capital commitment, order-flow regime, and participant class. If two adjacent timeframes encode the same regime, one is redundant.

- **Monthly / Weekly** correspond to sovereign / macro positioning horizons. Gold is priced as a currency-like asset against the US dollar; macro positioning by central banks, bullion banks, and large macro funds operates at this scale (BIS Quarterly Review; World Gold Council demand reports).
- **Daily** corresponds to the institutional dealing horizon. London bullion desks and COMEX market makers mark books daily at the 17:00 NY cut and the London PM fix at 10:30 NY.
- **H4** corresponds to the intraday structural horizon that bank prop desks and CTA funds use for intraday trend models (often cited in institutional execution literature; see Kissell, *The Science of Algorithmic Trading*, Ch. 6).
- **H1** corresponds to session-based regime: Asian, London, New York.
- **M15** is the lowest timeframe on which ICT "kill zones" and session ranges are structurally observable (Asian range high/low, London open displacement, NY AM session).
- **M5** is the lowest timeframe at which displacement, order blocks, and MSS can be reliably distinguished from noise for XAUUSD. Below M5, gold's spread relative to candle range destroys signal-to-noise ratio.
- **M1** is dominated by microstructure noise, dealer inventory rebalancing, and spread dynamics. It is useful for fill timing and slippage modeling, not for directional decisions.

### Evidence
- Mandelbrot (1963, 1997): price series exhibit multifractal scaling; discrete timeframe hierarchies should map onto separable scaling regimes. Empirical scaling breaks in FX/gold tend to cluster around 1m, 5m, 15m, 1h, 4h, 1d boundaries (Mantegna & Stanley, *Introduction to Econophysics*).
- Lo (1991): long-memory effects are strongest at daily and weekly scales and decay intraday; this justifies treating Monthly/Weekly/Daily as the *bias* layer.
- Hasbrouck (1991, 2007): variance decomposition of price discovery shows that for liquid instruments, the majority of informational variance is captured between the 5-minute and 1-hour scales, with sub-5-minute dominated by microstructure noise.
- Kyle (1985) informed-trader model: depth and resilience are observable only above the noise band; for XAUUSD spreads, this implies M5 as a practical floor for structural inference.
- ICT / SMC practitioner canon (unverified — hypothesis): the canonical ICT template is Monthly/Weekly/Daily/H4/H1/M15/M5/M1, but the operational layer is typically Monthly→Daily for bias and H1→M5 for entry.

### Tradeoffs
- Including Monthly adds robustness for macro regime classification but contributes weakly to intraday edge.
- Excluding M1 from decisions loses micro-precision but avoids the well-known "M1 noise trap" documented in execution literature (Almgren & Chriss, 2000; Kissell, 2013).

### Recommended Design
Use **{Monthly, Weekly, Daily, H4, H1, M15, M5}** as the decision hierarchy. Maintain **M1** as a separate *ExecutionMicrostructureFeed* consumed only by the ExecutionEngine and RiskManager (for slippage estimation and fill optimization).

### Potential Weaknesses
- Fixed timeframe ladders ignore non-linear information horizons; e.g., during NFP or FOMC, M1–M5 carry genuine information. A static hierarchy under-weights these events.
- Weekly/monthly candle closures for gold occur at variable broker times, creating inconsistency.

### Future Extensions
- Adaptive timeframe selection via wavelet decomposition or empirical mode decomposition (Huang et al., 1998 — EMD).
- Event-driven overlay that temporarily promotes LTF weight during scheduled volatility events.

---

## PART 2 — Responsibility of Each Timeframe

### Architecture
Each timeframe is assigned a *single primary responsibility*. A timeframe must not make decisions outside its responsibility.

### Monthly
**Purpose:** Define the multi-year structural regime (accumulation / distribution / markup / markdown, in Wyckoff terms).
**Decisions ONLY Monthly makes:**
- Macro directional bias (bullish/bearish/range).
- Location of multi-year liquidity pools (highs/lows not touched for ≥3 months).
- Multi-year premium/discount.
Monthly does **not** generate trade signals.

### Weekly
**Purpose:** Define the quarterly draw on liquidity.
**Decisions ONLY Weekly makes:**
- Weekly directional bias (the direction price is most likely to seek over the next 1–4 weeks).
- Weekly liquidity targets (prior week high/low, weekly equal highs/lows).
- Weekly BOS/CHOCH to confirm or invalidate Monthly regime.

### Daily
**Purpose:** Define the institutional intraday draw on liquidity.
**Decisions ONLY Daily makes:**
- Daily directional bias (the side price is likely to close toward).
- Daily premium/discount array.
- Daily BOS/CHOCH.
- Daily order blocks and FVGs that act as HTF magnets.
This is the highest timeframe that should directly gate trade permission.

### H4
**Purpose:** Bridge intraday structure to HTF bias.
**Decisions ONLY H4 makes:**
- H4 trend classification (the only trend label used by ConfluenceEngine for intraday models).
- H4 BOS/CHOCH.
- H4 liquidity pools and H4 order blocks used as intraday targets.
- Confirmation of Daily bias direction (H4 in the same direction as Daily is required for full-permission trades).

### H1
**Purpose:** Session-anchored bias and premium/discount selection.
**Decisions ONLY H1 makes:**
- Intraday premium/discount selection.
- H1 MSS as the first formal model entry trigger candidate.
- H1 kill-zone alignment (London open, NY AM).
- H1 OB/FVG pool used for entry zones.

### M15
**Purpose:** Entry-zone refinement.
**Decisions ONLY M15 makes:**
- M15 BOS/CHOCH inside the H1 OB/FVG.
- M15 displacement confirmation.
- M15 liquidity sweeps (e.g., Asian range sweeps) as final context.
M15 does not own directional bias; it inherits it from H1.

### M5
**Purpose:** Precision entry trigger and invalidation.
**Decisions ONLY M5 makes:**
- M5 MSS as the executable entry trigger.
- M5 CHOCH as the invalidation trigger.
- M5 OB/FVG as the micro entry zone.
M5 must operate **inside** an M15/H1 zone of interest.

### M1
**Should M1 exist?**
Yes — but only as an *execution microstructure feed*. It should:
- Compute current spread, depth proxy, short-term volatility.
- Feed the ExecutionEngine for order type selection (market vs. limit, slicing).
- Feed the RiskManager for real-time stop adjustment.
M1 must **not** feed the ConfluenceEngine or SignalGenerator.

### Reasoning
The principle is *separation of concerns across scales* — a direct application of the Wyckoff cause-and-effect doctrine: the cause is built on the higher timeframe, the effect manifests on the lower. If a lower timeframe is permitted to set directional bias, the model is sampling a noise band and assigning it regime authority, which violates the scaling separation argued by Mandelbrot and confirmed empirically by Hasbrouck.

### Evidence
- Wyckoff (1908–1934): cause-effect principle — accumulation (cause) on HTF produces markup (effect) on LTF.
- ICT/SMC canon (hypothesis, not peer-reviewed): "top-down analysis" — HTF bias, LTF entry.
- Lo & MacKinlay (1988): variance-ratio tests show that returns at lower frequencies are not simple aggregates of higher-frequency returns; therefore lower-frequency signals carry distinct information and must be treated as the structural authority.
- Engle (2000): microstructure noise is mean-reverting at the highest frequencies; this is the formal basis for excluding M1 from directional inference.

### Tradeoffs
- Strict separation increases latency between regime change and execution (H4 trend change precedes M5 entry by potentially hours).
- Permitting LTF to override HTF improves responsiveness but increases false positives.

### Recommended Design
Each timeframe owns exactly one of: {regime, bias, structure, zone, trigger, execution}. No timeframe encroaches on another's domain without an explicit override protocol (Part 6).

### Potential Weaknesses
- Rigid responsibility boundaries may miss genuine fast-moving regimes (e.g., flash crash).
- Manual override protocol required for high-impact news.

### Future Extensions
- Add an H2 (or session-anchored) composite timeframe that aligns to Asian/London/NY session boundaries, which are not aligned to H1/H4 grids.

---

## PART 3 — Information Flow

### Architecture
Information flows **top-down for context and bias**, and **bottom-up only for invalidation and execution confirmation**. This is an *asymmetric, hierarchical, feedback-permitted* flow.

```
Monthly  ──────────────────────►  Macro Bias Context
   │
Weekly   ──────────────────────►  Quarterly Bias Context
   │
Daily    ──────────────────────►  Intraday Bias Gate
   │
H4       ──────────────────────►  Trend + Structure
   │
H1       ──────────────────────►  Premium/Discount + Zone
   │
M15      ──────────────────────►  Refinement
   │
M5       ──────────────────────►  Trigger
   │
M1       ──────────────────────►  Execution only

Bottom-up path (invalidation only):
M5 CHOCH → can invalidate M15 entry zone
M15 CHOCH → can invalidate H1 setup (but not H1 bias)
H1 CHOCH → can invalidate H4 trade, triggers re-evaluation
H4 CHOCH → can degrade Daily bias confidence
```

### Reasoning
The top-down flow reflects the *cause-and-effect* hierarchy. The bottom-up invalidation path reflects two empirically observed phenomena:
1. Information sometimes arrives first at finer scales (price discovery lead/lag; Hasbrouck 1991, 2007).
2. A structural failure at a lower timeframe often precedes HTF CHOCH; using LTF CHOCH as an early-warning invalidator reduces drawdown.

However, LTF signals must **not** be permitted to flip HTF bias directly, because they are contaminated by microstructure noise (Engle 2000; Bandi & Russell 2006).

### Evidence
- Hasbrouck (1991): price discovery is multi-venue and multi-horizon; smaller timeframes can carry informational lead.
- Black (1986) "Noise": high-frequency price changes are dominated by noise; treating them as authoritative creates systematic error.
- Wyckoff cause-effect: cause (HTF) precedes effect (LTF), but the effect confirms the cause is being realized.
- ICT/SMC (hypothesis): CHOCH on a lower timeframe can be used to anticipate HTF invalidation — referred to as "LTF leading HTF."

### Tradeoffs
- Pure top-down: high precision, high latency.
- Pure bottom-up: high responsiveness, low precision.
- Hybrid with asymmetric invalidation: optimal bias/precision tradeoff but architecturally complex.

### Recommended Design
Asymmetric hierarchical flow:
- Top-down: context, bias, zone inheritance.
- Bottom-up: only CHOCH-based invalidation, with a *confidence threshold* before propagation (see Part 6).

### Potential Weaknesses
- LTF CHOCH during news spikes can prematurely invalidate HTF setups.
- A feedback loop between HTF re-evaluation and LTF triggering can create cascading rejections.

### Future Extensions
- Bayesian belief network where each timeframe maintains a posterior on regime, updated by both parent and child observations with appropriate likelihood functions.

---

## PART 4 — Per-Timeframe Detection Matrix

Detection should be governed by *signal-to-noise ratio* and *economic meaning at that horizon*. The matrix below encodes whether each feature is computed at each timeframe.

| Feature | Monthly | Weekly | Daily | H4 | H1 | M15 | M5 | M1 |
|---|---|---|---|---|---|---|---|---|
| Swing | Yes | Yes | Yes | Yes | Yes | Yes | Yes | No |
| BOS | Yes | Yes | Yes | Yes | Yes | Yes | Yes | No |
| CHOCH | Yes | Yes | Yes | Yes | Yes | Yes | Yes | No |
| Liquidity | Yes | Yes | Yes | Yes | Yes | Yes | Yes | No |
| Equal Highs | Yes | Yes | Yes | Yes | Yes | Yes | Limited | No |
| Equal Lows | Yes | Yes | Yes | Yes | Yes | Yes | Limited | No |
| Displacement | No | Yes | Yes | Yes | Yes | Yes | Yes | No |
| MSS | No | Yes | Yes | Yes | Yes | Yes | Yes | No |
| Order Block | No | Yes | Yes | Yes | Yes | Yes | Yes | No |
| Fair Value Gap | No | Yes | Yes | Yes | Yes | Yes | Yes | No |
| Premium/Discount | Yes | Yes | Yes | Yes | Yes | Limited | No | No |
| Balanced Price Range | No | Yes | Yes | Yes | Yes | Limited | No | No |
| Liquidity Void | No | Yes | Yes | Yes | Yes | Yes | Yes | No |
| Volume Imbalance | No | No | Yes | Yes | Yes | Yes | Yes | No |

### Reasoning / Evidence

**Swing** is structural and fractal; detect at all decision TFs (Wyckoff).
- Mandelbrot fractal market hypothesis: swings are self-similar across scales.

**BOS / CHOCH** are defined by swing breaks. They are meaningful wherever swings are meaningful. Excluded from M1 because swing noise dominates (Engle 2000).

**Liquidity** (untouched swing highs/lows, equal highs/lows, session ranges). Liquidity is a magnet concept (ICT, hypothesis): the more significant the HTF level, the stronger the magnet. Liquidity should be detected on all decision TFs and aggregated cross-timeframe.

**Equal Highs / Equal Lows** at M5 are "limited" because the majority of M5 EQH/EQL inside the spread are noise; only EQH/EQL formed across ≥3 separate M5 pivots should be retained.

**Displacement** requires a candle body large relative to recent ATR. At Monthly, displacement is rare and statistically dominated by macro gaps; better captured on Weekly and below. Empirically, ICT-style displacement is operationally defined at H4 and lower (hypothesis).

**MSS** is CHOCH + displacement. Same logic as displacement.

**Order Block** requires the last opposing candle before a displacement move. Below M5, OBs are dominated by inventory-driven candles, not institutional positioning. Excluded at M1.

**Fair Value Gap** is a three-candle imbalance pattern. Below M5, FVGs are too numerous and statistical edge degrades (Hypothesis — supported by informal practitioner backtests; no peer-reviewed study exists).

**Premium/Discount** is meaningful only when the range is itself meaningful. At M5, the range is too noisy to define a meaningful 50% equilibrium. Limited at M15 (only when a clean M15 range exists).

**Balanced Price Range** (BPR / consolidated range) requires sustained two-sided equilibrium; meaningful only on H1 and higher. Limited at M15.

**Liquidity Void** is a fast-move gap that price tends to revisit. Detectable on Weekly and below. At Monthly, voids are macro gaps and rarely revisited in a tradeable horizon.

**Volume Imbalance** (two-candle body gap, as defined in SMC) requires reliable body geometry. Below M5 the spread distorts body geometry. Not meaningful on Monthly (candle count too sparse for body continuity).

### Tradeoffs
- Computing all features on all TFs maximizes information but wastes compute and increases false positives.
- The matrix above balances edge density and noise.

### Recommended Design
Adopt the matrix above as the canonical detection specification. Features excluded at a TF must not be approximated or inferred at that TF.

### Potential Weaknesses
- Hard exclusion thresholds ignore regime-dependent edge; e.g., FVGs may be valid on M1 during NFP.
- Detection parameters (swing length, displacement multiplier) must be TF-specific.

### Future Extensions
- Per-feature, per-TF edge attribution study (information coefficient vs. forward return) to validate the matrix empirically.

---

## PART 5 — Engine Ownership and Reuse

### Architecture
Each timeframe **owns a complete MarketStructureEngine and PriceActionEngine instance** configured with TF-specific parameters. Higher-timeframe *results* (not raw data) are exposed as immutable context to lower-timeframe engines via a `TimeframeContextRegistry`.

```
┌─────────────────────────────────────────────────────────────────┐
│                    TimeframeContextRegistry                       │
│  { Monthly: MonthlyContext, Weekly: WeeklyContext, ... M5: ... } │
└─────────────────────────────────────────────────────────────────┘
                              ▲ read-only access
                              │
┌────────────┬────────────┬────────────┬────────────┬────────────┐
│  Monthly   │  Weekly    │   Daily    │    H4      │    H1      │
│  MSE       │  MSE       │   MSE      │    MSE     │    MSE     │
│  PAE       │  PAE       │   PAE      │    PAE     │    PAE     │
└────────────┴────────────┴────────────┴────────────┴────────────┘
┌────────────┬────────────┐
│   M15      │    M5      │
│   MSE/PAE  │   MSE/PAE  │
└────────────┴────────────┘
┌────────────┐
│     M1     │
│  Execution │
│  MicroFeed │
└────────────┘
```

### Reasoning
- **Ownership:** Each timeframe's structural detection requires TF-specific parameters (swing depth, displacement ATR multiple, OB decay). Sharing one engine across TFs forces parameter leakage and creates coupling.
- **Reuse of results, not data:** Lower TFs need HTF *conclusions* (e.g., "Daily bias = bullish, daily OB at 2032.50"), not HTF raw candles. This is both efficient and semantically correct — the LTF engine should treat HTF output as exogenous context.

### Evidence
- Software engineering: Law of Demeter / interface segregation — a TF engine should not reach into another TF's internals.
- Information theory: lower TFs benefit from HTF as a *prior*, not as raw observations (Bayesian framework; Berger 1985).
- Microstructure: HTF outputs are slower-moving state variables; treating them as constants during LTF evaluation is a valid approximation (Hypothesis).

### Tradeoffs
- Full per-TF engines consume more memory and CPU than shared engines.
- Result-based reuse introduces a small lag (HTF context updates only on HTF candle events).

### Recommended Design
- Each TF owns its own MSE and PAE.
- A `TimeframeContextRegistry` exposes immutable snapshots of each TF's current structural state.
- LTF engines declare dependencies (e.g., `M5Engine.dependsOn(Daily, H4, H1, M15)`); the registry injects immutable context objects.
- HTF updates propagate via an event bus (push), not polling.

### Potential Weaknesses
- Snapshot staleness during fast HTF candle closes.
- Parameter drift between TF engines if not centrally configured.

### Future Extensions
- Versioned context objects with monotonic timestamps to enable deterministic backtesting.

---

## PART 6 — Conflict Resolution

### Architecture
Conflicts are resolved by a **hierarchical probabilistic gating protocol**, not by majority vote.

**Rule 1 — HTF Bias Gate (hard).**
A trade is permitted only if Monthly, Weekly, and Daily biases are aligned OR neutral. A direct conflict (one bullish, one bearish) on Monthly/Weekly/Daily = **No Trade**.

**Rule 2 — Trend Alignment Gate (soft).**
Daily ↔ H4 must agree. If they conflict, trade permission is reduced to "counter-trend only" and RiskManager caps risk to ≤0.25R.

**Rule 3 — Zone Gate (hard).**
H1 must be in premium for shorts, discount for longs, *or* a clear H1 MSS must have occurred against the H4 trend (counter-trend setup with reduced size).

**Rule 4 — Trigger Gate (hard).**
M5 MSS must fire inside an M15 zone inside an H1 zone. No M5 trigger without M15 confirmation.

**Rule 5 — Invalidation Propagation (conditional).**
An LTF CHOCH can invalidate an HTF setup only if:
- The LTF CHOCH is accompanied by displacement ≥ 1.5 × ATR(14, LTF).
- The LTF CHOCH occurs after a sweep of the HTF liquidity the setup was predicated on.

Without both conditions, the LTF CHOCH is logged but does not propagate.

### Example Resolution
```
Daily  : Bullish
H4     : Bullish
H1     : Bearish
M15    : Bullish
M5     : Bullish
```
- Rule 1: pass.
- Rule 2: pass.
- Rule 3: H1 bearish conflicts with H4 bullish. Reduce to counter-trend-tier risk.
- Rule 4: M5 bullish trigger acceptable only inside an M15 bullish zone that aligns with H4 bullish (i.e., H1 bearish is a pullback into H4 discount).
- **Verdict: Trade permitted at reduced risk (0.25–0.5R), but only if H1 is in discount relative to H4 bullish structure AND the M5 trigger fires from an H4-aligned OB.**

### Reasoning
Majority voting on timeframes is statistically invalid because the timeframes are not independent samples — they are highly correlated, non-stationary, and have unequal information content (Lo & MacKinlay 1988; Hasbrouck 1991). The correct treatment is hierarchical Bayesian gating, where HTF carries the prior and LTF carries the likelihood.

### Evidence
- Berger (1985) *Statistical Decision Theory*: hierarchical priors dominate flat voting under correlated observations.
- Kelly (1956): position sizing must scale with edge; reduced-risk tiers under conflict are a Kelly-conservative response.
- ICT/SMC practitioner rule (hypothesis): "trade with the higher timeframe, never against" — implemented here as Rule 1.

### Tradeoffs
- Strict gating reduces trade frequency; statistically desirable but commercially painful.
- Allowing reduced-risk counter-trend trades adds edge in range regimes but degrades in trending regimes.

### Recommended Design
Implement a five-tier trade-permission enum:
```
FULL_PERMISSION   — all gates pass.
REDUCED_PERMISSION — minor conflict (H1 vs H4), risk capped at 0.5R.
COUNTER_TREND_ONLY — major conflict (H4 vs Daily), risk capped at 0.25R, requires MSS.
WATCH_ONLY         — conflict unresolved; no new entries, manage open positions.
REJECT             — Monthly/Weekly/Daily conflict; no trade.
```

### Potential Weaknesses
- Hard rules can miss valid setups during regime transitions.
- The displacement threshold (1.5 × ATR) is a hypothesis and requires empirical calibration per session.

### Future Extensions
- Replace static tiers with a continuous Bayesian posterior probability and a Kelly-fraction position size derived from it.

---

## PART 7 — Confluence Scoring

### Architecture
Use an **exponential weighting scheme** favoring HTF, with weights calibrated to information content rather than arbitrary percentages.

Recommended weights:
```
Monthly : 5%
Weekly  : 10%
Daily   : 25%
H4      : 25%
H1      : 20%
M15     : 10%
M5      : 5%
```
Total: 100%.

### Reasoning
The proposed weights are not arbitrary; they encode three principles:
1. **Information horizon dominance**: Monthly and Weekly should not dominate intraday confluence because their signal-to-noise for intraday edge is low; they function as *gates*, not weights. This is why Monthly+Weekly = only 15%.
2. **Decision authority**: Daily and H4 jointly set the intraday trend. They receive the largest combined weight (50%) because that is where intraday directional edge lives (Hasbrouck 1991; for FX/gold, intraday trend persistence peaks at the 4h–daily horizon — hypothesis, requires empirical validation).
3. **Trigger contribution**: M5 contributes little *directional* information but is essential as the trigger. A low weight (5%) reflects that it confirms rather than biases.

The naive scheme (Weekly 40% / Daily 30% / H4 15% / H1 10% / M15 5%) over-weights Weekly for an intraday strategy. Weekly regime shifts are slow; a Weekly bias change is a quarterly event, not a per-trade edge source. Over-weighting it causes the model to hold stale bias through intraday reversals.

### Evidence
- Information coefficient studies in FX (Dacorogna et al., *An Introduction to High-Frequency Finance*) show IC peaks at the 1h–4h horizon for intraday strategies.
- Bayesian model averaging (Hoeting et al., 1999): weights should reflect predictive likelihood, not hierarchy depth.
- Kelly (1956): position sizing scales with edge, and edge is empirically concentrated at the H4–H1 scale for XAUUSD intraday strategies (hypothesis).

### Tradeoffs
- Static weights are simple but non-adaptive.
- Equal weights violate information-hierarchy dominance.

### Recommended Design
- Static exponential-style weights as above as the default.
- Add a `WeightCalibrator` that runs a rolling 90-day IC-weighted recalibration, capping any single-TF weight shift to ±5 percentage points per cycle to avoid regime overfitting.

### Potential Weaknesses
- Static weights may misallocate edge across sessions (Asia vs. London vs. NY).
- The 90-day recalibration window may itself be regime-sensitive.

### Future Extensions
- Session-conditional weight matrices (different weights for Asian, London, NY sessions).
- Regime-conditional weights (trending vs. ranging) using a Hidden Markov Model overlay.

---

## PART 8 — Historical Data Storage

### Architecture
Per-timeframe circular buffer of candle objects. Each TF retains a window sized to its analytical need.

| TF | Candles retained | Lookback | Memory (per candle ~120 bytes) |
|---|---|---|---|
| Monthly | 240 | 20 years | ~29 KB |
| Weekly | 520 | 10 years | ~63 KB |
| Daily | 780 | ~3 years | ~94 KB |
| H4 | 1,080 | 180 days | ~130 KB |
| H1 | 1,440 | 60 days | ~173 KB |
| M15 | 1,920 | 20 days | ~230 KB |
| M5 | 2,880 | 10 days | ~346 KB |
| M1 (exec only) | 14,400 | 10 days | ~1.7 MB |

Total decision-TF memory ≈ **1.07 MB**. Adding M1 execution buffer ≈ **2.8 MB**. Negligible on modern hardware.

### Reasoning
- HTF needs long history for regime classification (Wyckoff accumulation/distribution can span months).
- LTF needs short history: M5 signals decay within hours; storing years of M5 is wasteful and statistically meaningless because XAUUSD microstructure regimes drift (Hasbrouck 2007).
- Circular buffers provide O(1) append and eviction, ideal for streaming market data.

### Storage Design
- Candle schema: `{tf, openTime, open, high, low, close, volume, tickCount, vwap, sourceFlag}`.
- Structural objects (swings, BOS, OBs, FVGs, liquidity levels): persisted in a separate immutable append-only event log keyed by `(tf, timestamp, object_id)`.
- Snapshotting: every HTF candle close serializes the full TimeframeContextRegistry to disk for fast recovery.

### Evidence
- Database engineering: circular buffers / ring buffers are the canonical streaming-data structure (Knuth, TAOCP Vol. 1).
- Quantitative finance: tick-data retention is bounded by regime half-life (Lo 1991, long-memory studies); beyond the half-life, additional history contributes negligible predictive power.

### Tradeoffs
- Long HTF history is memory-cheap but computationally expensive to reprocess for parameter recalibration.
- Short LTF history is cheap both ways.

### Recommended Design
Adopt the table above. Use ring buffers for candles and an append-only event log for structural objects. Maintain a `BacktestHistoricalStore` (e.g., Parquet files) with deeper history for offline research, decoupled from the live engine.

### Potential Weaknesses
- Broker candle timestamps differ across providers, complicating HTF/LTF alignment.
- Volume data for OTC gold is broker-specific and not exchange-aggregated; volume-based features are noisy.

### Future Extensions
- Migrate to a columnar time-series database (kdb+, ClickHouse, or QuestDB) for cross-TF analytical queries.
- Aggregate multi-source tick data into a synthetic consolidated tape (hypothesis: improves LTF signal quality).

---

## PART 9 — Complete Software Architecture

### High-Level Topology

```
                    ┌───────────────────────────┐
                    │     MarketDataGateway      │
                    │  (M1 tick + bar aggregation│
                    │   to all decision TFs)     │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │     BarDispatcher          │
                    │ (routes closed bars to TFs)│
                    └─────────────┬─────────────┘
                                  │
        ┌─────────────────────────┼──────────────────────────┐
        │                         │                          │
┌───────▼────────┐  ┌─────────────▼──────────┐  ┌─────────────▼─────────┐
│ TFEngineLayer  │  │ TFEngineLayer           │  │ TFEngineLayer          │
│ Monthly        │  │ Weekly                  │  │ Daily                  │
│  └─ MSE        │  │  └─ MSE                 │  │  └─ MSE                │
│  └─ PAE        │  │  └─ PAE                 │  │  └─ PAE                │
│  └─ TFReporter │  │  └─ TFReporter          │  │  └─ TFReporter         │
└───────┬────────┘  └─────────────┬──────────┘  └─────────────┬──────────┘
        │                         │                          │
        └──────────────┬──────────┴──────────────────────────┘
                       │
            ┌──────────▼──────────┐
            │ TimeframeContext     │
            │   Registry           │
            │  (immutable snapshots│
            │   per TF)            │
            └──────────┬──────────┘
                       │
        ┌──────────────▼───────────────┐
        │   ConfluenceEngine            │
        │   - reads TFContext snapshots │
        │   - applies weighting matrix  │
        │   - applies gating rules      │
        │   - emits ConfluenceReport    │
        └──────────────┬───────────────┘
                       │
            ┌──────────▼──────────┐
            │   SignalGenerator    │
            │  (entry/invalidation)│
            └──────────┬──────────┘
                       │
            ┌──────────▼──────────┐
            │   RiskManager        │
            │ (Kelly sizing, gates)│
            └──────────┬──────────┘
                       │
            ┌──────────▼──────────┐
            │   ExecutionEngine     │
            │   (+ M1 micro feed)   │
            └──────────────────────┘
```

### Core Classes

```
// === Data Layer ===
class Candle {
    timeframe, openTime, open, high, low, close,
    volume, tickCount, vwap, sourceFlag
}

class RingBuffer<T> {
    capacity, head, tail, push(T), snapshot(): List<T>
}

class MarketDataGateway {
    subscribeSymbol(symbol)
    onTick(tick): aggregate
    onBarClose(timeframe, candle): dispatch
}

class BarDispatcher {
    register(timeframe, handler)
    dispatch(timeframe, candle)
}

// === Timeframe Engine Layer ===
interface TimeframeEngine {
    val timeframe: Timeframe
    val marketStructure: MarketStructureEngine
    val priceAction: PriceActionEngine
    val context: TimeframeContext
    fun onBar(candle: Candle)
    fun snapshot(): TimeframeContext
}

class MonthlyEngine  : TimeframeEngine
class WeeklyEngine   : TimeframeEngine
class DailyEngine    : TimeframeEngine
class H4Engine       : TimeframeEngine
class H1Engine       : TimeframeEngine
class M15Engine      : TimeframeEngine
class M5Engine       : TimeframeEngine

class M1ExecutionFeed {
    spread, depth_proxy, micro_volatility
    fun onTick(tick)
}

// === Market Structure / Price Action ===
class MarketStructureEngine {
    swingDetector: SwingDetector
    bosDetector: BosDetector
    chochDetector: ChochDetector
    liquidityMapper: LiquidityMapper
    eqhqlDetector: EqualHighLowDetector
    displacementDetector: DisplacementDetector
    mssDetector: MssDetector
    pdArrayBuilder: PremiumDiscountBuilder
    fun update(candle: Candle): MarketStructureEvent
}

class PriceActionEngine {
    orderBlockDetector: OrderBlockDetector
    fvgDetector: FvgDetector
    liquidityVoidDetector: LiquidityVoidDetector
    volumeImbalanceDetector: VolumeImbalanceDetector
    bprDetector: BalancedPriceRangeDetector
    fun update(candle: Candle, mseState): PriceActionEvent
}

// === Context / Result Objects ===
data class TimeframeContext {
    timeframe: Timeframe
    timestamp: long
    bias: BiasDirection          // BULLISH / BEARISH / NEUTRAL
    trend: TrendState            // UP / DOWN / RANGE
    lastBOS: BosEvent?
    lastCHOCH: ChochEvent?
    swingHighs: List<Swing>
    swingLows: List<Swing>
    liquidityPools: List<LiquidityPool>
    orderBlocks: List<OrderBlock>
    fvgs: List<Fvg>
    premiumDiscount: PremiumDiscountArray
    displacementEvents: List<DisplacementEvent>
    mssEvents: List<MssEvent>
    version: long                // monotonic
}

data class ConfluenceReport {
    timestamp: long
    permission: TradePermission  // FULL / REDUCED / COUNTER_TREND / WATCH / REJECT
    directionalScore: Double     // -1.0 .. +1.0
    confidenceScore: Double      // 0.0 .. 1.0
    weightedContributions: Map<Timeframe, Double>
    primaryLiquidityTarget: Price?
    invalidationLevel: Price?
    contributingContexts: Map<Timeframe, TimeframeContext>
}

// === Confluence / Signal / Risk ===
class TimeframeContextRegistry {
    register(tf, context)
    get(tf): TimeframeContext
    snapshotAll(): Map<Timeframe, TimeframeContext>
}

class ConfluenceEngine {
    weightMatrix: Map<Timeframe, Double>
    gatingRules: List<GatingRule>
    fun evaluate(registry: TimeframeContextRegistry): ConfluenceReport
}

interface GatingRule {
    fun evaluate(contexts, report): GatingResult
}

class HTFBiasGateRule        : GatingRule   // Rule 1
class TrendAlignmentRule     : GatingRule   // Rule 2
class ZoneGateRule           : GatingRule   // Rule 3
class TriggerGateRule        : GatingRule   // Rule 4
class InvalidationPropRule   : GatingRule   // Rule 5

class SignalGenerator {
    fun generate(report: ConfluenceReport): Signal?
}

class RiskManager {
    kellyFraction: Double
    tierCaps: Map<TradePermission, Double>
    fun size(signal: Signal, accountState): OrderRequest?
}

class ExecutionEngine {
    m1Feed: M1ExecutionFeed
    fun submit(orderRequest: OrderRequest)
}
```

### Data Flow (event-driven)
1. `MarketDataGateway` receives M1 ticks.
2. Aggregator forms higher-TF bars as their boundaries close.
3. `BarDispatcher` routes each closed bar to its TF engine.
4. Each `TimeframeEngine` updates its `MarketStructureEngine` then `PriceActionEngine`.
5. On update, engine publishes a new immutable `TimeframeContext` version to `TimeframeContextRegistry`.
6. `ConfluenceEngine` is triggered on any TF context update (debounced to M5 bar close for intraday decisions; immediate on H4/Daily close for bias updates).
7. `ConfluenceEngine` evaluates all gating rules, produces a `ConfluenceReport`.
8. `SignalGenerator` consumes the report; if a valid entry zone + trigger exists, emits a `Signal`.
9. `RiskManager` sizes the signal according to permission tier.
10. `ExecutionEngine` consumes `M1ExecutionFeed` for fill timing and submits orders.

### Reasoning
- **Immutability** of `TimeframeContext` ensures deterministic backtests and thread-safe reads from downstream engines (software engineering; Clojure/STM literature).
- **Event-driven** design avoids polling and matches the discrete nature of candle events.
- **Decoupled registry** permits adding timeframes without modifying consumers (Open/Closed Principle).

### Evidence
- Software architecture: SOLID principles (Martin 2000); immutability for concurrency (Goetz et al., *Java Concurrency in Practice*).
- Quantitative systems: event-driven backtesting is the institutional standard (Leshik & Cralle, *An Introduction to Algorithmic Trading*).

### Tradeoffs
- Event-driven systems require careful ordering and idempotency.
- Immutable snapshots consume more memory than mutable shared state.

### Recommended Design
Implement exactly as above. Use a single-threaded event loop per symbol to eliminate ordering complexity; parallelize across symbols only.

### Potential Weaknesses
- Single-threaded per-symbol loop becomes a bottleneck at high symbol counts; not a concern for XAUUSD-only deployment.
- M1 tick throughput can overwhelm the loop during volatility spikes; require backpressure handling.

### Future Extensions
- Actor-model implementation (Akka / Proto.Actor) for horizontal scalability.
- Causal-ordering broadcast for multi-symbol MTF arbitrage.

---

## PART 10 — Common Retail Multi-Timeframe Bot Mistakes

### 1. **Treating timeframes as independent voters**
**Mistake:** Compute signal on each TF independently, then average. This ignores the strong cross-TF correlation and information hierarchy.
**Fix:** Hierarchical gating (Part 6). HTF sets prior; LTF updates likelihood.

**Evidence:** Lo & MacKinlay (1988) variance-ratio tests demonstrate returns are not independent across timeframes; treating them as independent violates basic assumptions of voting/aggregation.

### 2. **Using M1 / tick data for directional decisions**
**Mistake:** Building signals on M1 because it "feels precise."
**Fix:** M1 is execution-only. Directional decisions begin at M5 minimum.

**Evidence:** Bandi & Russell (2006), Hansen & Lunde (2006): microstructure noise dominates below 5 minutes for liquid instruments.

### 3. **Repainting structural detectors**
**Mistake:** Detecting swings/BOS in real-time without waiting for candle confirmation. Backtest looks profitable; live trading loses.
**Fix:** All structural detectors must wait for the candle to close before emitting events. Use only confirmed bars in backtest.

**Evidence:** Look-ahead bias is the most common backtesting error (Bailey, Borwein, López de Prado, Zhu — *The Probability of Backtest Overfitting*, 2016).

### 4. **Polling HTF state on every LTF tick**
**Mistake:** Reading Daily bias inside the M5 evaluation loop on every M5 close, even when Daily hasn't changed. Wastes CPU and creates race conditions.
**Fix:** HTF context is event-pushed; LTF engine consumes immutable snapshots.

### 5. **Parameter sharing across timeframes**
**Mistake:** Same swing depth, same displacement multiplier for M5 and Daily. Daily swings are noise-filtered; M5 swings need different thresholds.
**Fix:** Per-TF parameter sets, validated empirically.

### 6. **Symmetric weighting**
**Mistake:** Equal weights to all timeframes.
**Fix:** Exponential weighting favoring H4/Daily (Part 7).

### 7. **Ignoring session structure**
**Mistake:** Treating all H1 bars as equivalent. XAUUSD's London and NY sessions have materially different microstructure.
**Fix:** Session-conditional weight overlays; session-tagged context.

**Evidence:** Dacorogna et al. document intraday seasonality in FX/gold; Andersen & Bollerslev (1997, 1998) on intraday volatility patterns.

### 8. **Hard-coding bias without invalidation protocol**
**Mistake:** "Daily bias is bullish" held all day regardless of price action.
**Fix:** Bias is a *state* with confidence and invalidation criteria. Bias degrades after CHOCH on H1/H4.

### 9. **Looking at HTF only at HTF candle close**
**Mistake:** Daily bias updates once per day at 17:00 NY. Intraday regime shifts are missed.
**Fix:** HTF context updates on HTF candle close, but HTF *bias confidence* updates continuously based on LTF CHOCH propagation (Part 3, Part 6).

### 10. **No trade-permission tiers**
**Mistake:** Binary trade/no-trade. Misses reduced-edge opportunities, or takes full risk on weak setups.
**Fix:** Five-tier permission system (Part 6) with Kelly-scaled position sizes.

### 11. **Overfitting to a single session or regime**
**Mistake:** Backtested on six months of NY-only data; deployed 24/5.
**Fix:** Walk-forward across full session and macro-regime coverage.

**Evidence:** Bailey et al. (2014) — *Deflated Sharpe Ratio*: cross-regime validation is mandatory.

### 12. **Ignoring broker candle alignment**
**Mistake:** Daily candle closes at different times across brokers; MTF alignment is inconsistent.
**Fix:** Standardize on a canonical session definition (e.g., NY 17:00 close for Daily) and document all TF boundaries.

---

## PART 11 — Hedge-Fund-Grade MTF Subsystem (From Scratch)

### Design Philosophy
A hedge-fund-grade XAUUSD MTF subsystem must satisfy five institutional requirements:

1. **Determinism**: identical inputs produce identical outputs across live and backtest.
2. **Auditability**: every signal decision must be reconstructable from immutable context snapshots.
3. **Adaptivity**: weights, parameters, and even TF inclusion must recalibrate from data.
4. **Microstructure awareness**: the system must understand that XAUUSD is traded across OTC spot, futures (COMEX), and ETFs (GLD), each with different price discovery.
5. **Risk-first**: every architectural decision must be defensible from a risk standpoint, not just an edge standpoint.

### Layer 0 — Multi-Source Consolidated Tape
Before any MTF logic, aggregate ticks from:
- Primary broker feed (spot XAUUSD).
- COMEX GC futures (lead-month).
- GLD ETF (as a slow-correlated proxy).

Construct a *consolidated best-bid/offer* and a *synthetic mid* with source attribution. This is the canonical input to the bar aggregator.

**Reasoning:** Hasbrouck (1991, 2007) price discovery literature shows that for gold, COMEX often leads OTC spot by 100–500ms during volatility events. A single-broker feed is structurally disadvantaged.

**Hypothesis:** Multi-source consolidation improves LTF edge by 5–15% in IC terms; requires empirical validation.

### Layer 1 — Bar Aggregation with Canonical Boundary Definition
- M1, M5, M15, H1, H4 aligned to UTC.
- Daily closes at NY 17:00 (5 PM ET) — the bullion market standard.
- Weekly closes Friday NY 17:00.
- Monthly closes last business day NY 17:00.
- **Session tags** attached to every bar: ASIA / LONDON / NY / OVERLAP.

### Layer 2 — Per-TF Engine Fleet (Part 5, Part 9)
Seven engines (Monthly → M5), each with own MSE + PAE and TF-specific parameter sets. M1 is an execution-only microstructure feed.

### Layer 3 — Timeframe Context Registry with Versioning
- Each context object carries a monotonic `version` and `asOf` timestamp.
- Snapshots are persisted to an append-only event log for audit and backtest replay.
- Recovery from crash = replay event log from last snapshot.

### Layer 4 — Confluence Engine
- Static weight matrix (Part 7) as the prior.
- Rolling 90-day IC-weighted recalibration, capped at ±5pp per cycle.
- Session-conditional weight overlay: separate weight matrices for Asian, London, NY.
- Regime-conditional overlay via a 2-state HMM (trending / ranging) trained on H4 returns.

### Layer 5 — Gating Layer
Five-tier permission (Part 6) implemented as a pipeline of `GatingRule` instances. Each rule produces a structured `GatingResult` with reason codes, enabling post-hoc attribution.

### Layer 6 — Signal Generator
Consumes `ConfluenceReport` plus LTF trigger events (M5 MSS). Produces `Signal` objects containing:
- Direction.
- Entry zone (from H1 OB / FVG).
- Precise trigger (M5 MSS within zone).
- Stop loss (beyond the M5 OB).
- Target (next HTF liquidity pool).
- Permission tier (from gating).
- Risk fraction (Kelly-derived).

### Layer 7 — Risk Manager
- Kelly-fractional sizing with cap.
- Tier-based caps: FULL=1.0R, REDUCED=0.5R, COUNTER_TREND=0.25R.
- Daily loss limit (e.g., 3R) triggers session shutdown.
- Volatility-targeted notional scaling using ATR(D1, 20).
- Correlation monitor against DXY, US10Y real yield (gold is statistically driven by these; World Gold Council quant research).

### Layer 8 — Execution Engine
- M1 micro-feed drives order-type selection: market in fast markets, limit in calm.
- Smart order routing across broker liquidity pools.
- Slippage model trained on historical fills.
- Anti-gaming logic: avoid placing obvious stop-loss levels at round numbers (gold stop runs cluster at psychological levels — hypothesis, supported by practitioner observation).

### Layer 9 — Research / Backtest Plane
- Deterministic replay from event log.
- Walk-forward framework with regime-stratified folds.
- Deflated Sharpe Ratio and PBO (Probability of Backtest Overfitting) reported for every strategy variant (Bailey et al. 2014, 2016).
- Per-TF, per-feature attribution: which feature on which TF contributed the edge?

### Layer 10 — Monitoring and Observability
- Every context update, every gating decision, every signal logged with full provenance.
- Real-time dashboards: bias per TF, permission tier, open risk, slippage distribution.
- Alerting on drift: if 90-day IC of any TF drops below threshold, flag for recalibration.

### Layer 11 — Governance
- Strategy changes require sign-off and shadow-mode validation.
- Production deployment: canary → 10% risk → full.
- Kill switch: daily loss limit, drawdown limit, microstructure anomaly detector (e.g., spread > 5× median).

### Why This Is Hedge-Fund-Grade
- **Determinism + auditability** = institutional compliance.
- **Multi-source tape** = price discovery edge.
- **Session- and regime-conditional weighting** = adaptive, not static.
- **Kelly-tiered risk** = capital efficiency with drawdown control.
- **Deflated Sharpe / PBO** = honest performance attribution.
- **Governance** = operational sustainability.

### Reasoning
This design treats MTF not as "looking at multiple charts" but as a *hierarchical Bayesian inference system over a multi-source consolidated tape, gated by deterministic rules, sized by Kelly-conservative tiers, and validated by walk-forward regime-stratified backtesting with deflation*.

### Evidence
- Hasbrouck (2007) — multi-venue price discovery.
- Kelly (1956), Thorp (1969) — Kelly sizing.
- Bailey, López de Prado (2014, 2016) — deflated Sharpe, PBO.
- Hamilton (1989) — regime switching via HMM.
- Andersen, Bollerslev, Diebold (2007) — realized volatility and intraday seasonality.
- ICT/SMC practitioner canon (hypothesis-level evidence): top-down + LTF trigger.

### Tradeoffs
- Complexity is high; requires a small team to maintain.
- Multi-source tape licensing is costly.
- Adaptive weights can overfit without strict governance.

### Recommended Design
Adopt the eleven-layer model. Phase implementation: Layer 0 → 2 → 3 → 5 → 7 → 11 first (a working single-strategy system), then add Layer 4 adaptive weighting, Layer 8 advanced execution, Layer 9 research plane, Layer 10 observability.

### Potential Weaknesses
- Single-symbol focus (XAUUSD) underutilizes cross-asset edge (DXY, real yields).
- Static TF boundaries ignore event-driven regime changes.
- HMM regime classification is itself a noisy signal and can flip-flop.

### Future Extensions
- Cross-asset MTF: DXY and US10Y real yield feed forward their MTF context as priors into the XAUUSD confluence engine (gold's beta to these is well documented; World Gold Council, BIS).
- Cointegration-based overlay: when XAUUSD deviates from its DXY/yield-implied fair value, generate mean-reversion signals with reduced-risk tier.
- Machine-learned gating: train a gradient-boosted model on gated reports → realized R to learn gating thresholds directly, with strict out-of-sample validation.
- Real-time liquidity-graph construction across TFs as a directed acyclic graph of liquidity pools, enabling "which liquidity must be swept before the target is reached" reasoning.
- Quantum-resistant cryptographic provenance for context snapshots (institutional compliance forward-looking).

---

## Summary Table — Canonical MTF Configuration for XAUUSD

| Layer | Decision | Specification |
|---|---|---|
| Timeframes | Decision TFs | Monthly, Weekly, Daily, H4, H1, M15, M5 |
| Timeframes | Execution TF | M1 only |
| Flow | Top-down | Bias, zone, context |
| Flow | Bottom-up | CHOCH invalidation only, displacement-gated |
| Engines | Per-TF | Own MSE + PAE; results shared via registry |
| Confluence | Weighting | M5/W5/D5/H4-25/H1-20/M15-10/M5-5 |
| Gating | Tiers | FULL / REDUCED / COUNTER_TREND / WATCH / REJECT |
| Storage | Candles | Per-TF ring buffers; total ~2.8 MB |
| Storage | Events | Append-only log; immutable TimeframeContext |
| Architecture | Pattern | Event-driven, single-thread per symbol |
| Risk | Sizing | Kelly-capped, tier-scaled |
| Validation | Method | Walk-forward, regime-stratified, Deflated Sharpe |

---

### Final Note on Hypotheses vs. Established Results

**Established (peer-reviewed / microstructure literature):**
- Microstructure noise dominates sub-5-minute returns (Engle, Bandi-Russell, Hansen-Lunde).
- Markets exhibit fractal scaling with discrete regime breaks (Mandelbrot, Lo).
- Price discovery is multi-venue (Hasbrouck).
- Kelly sizing is optimal under known edge (Kelly, Thorp).
- Backtest overfitting is widespread; deflation required (Bailey-López de Prado).

**Hypotheses (practitioner canon, not peer-reviewed):**
- ICT/SMC concept definitions (OB, FVG, MSS, liquidity voids, EQH/EQL) are operationally useful but lack peer-reviewed validation. Their inclusion is justified by practitioner adoption and internal backtesting — not academic proof.
- The specific displacement threshold (1.5× ATR) for invalidation propagation is a hypothesis requiring empirical calibration.
- The specific weight matrix is a hypothesis grounded in information-horizon reasoning but should be validated via per-TF IC studies.

Every numeric threshold stated above must be treated as a **starting prior**, to be replaced by empirical estimates from walk-forward analysis on the production data feed.