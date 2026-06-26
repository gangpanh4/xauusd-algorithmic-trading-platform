# Market Regime Detection Technical Specification Research Questionnaire (v1.0)

## Section 1: Objectives

1. What is the primary purpose of the Market Regime Detection module?
2. What trading decisions should depend on the detected market regime?
3. Should the module prioritize stability or responsiveness? Why?
4. What design principles should guide a production-grade market regime detector?

---

## Section 2: Regime Definitions

5. What market regimes should be supported?
6. How should each regime be formally defined?
7. Should trend direction and volatility be represented as separate dimensions or combined into a single state?
8. Are the regimes mutually exclusive?
9. Can multiple regimes exist simultaneously?
10. How should unknown or ambiguous market conditions be represented?

---

## Section 3: Input Data

11. What market data is required?
12. What minimum historical lookback is needed?
13. Which timeframes should be supported?
14. How should missing or incomplete market data be handled?
15. Should the detector support multiple symbols simultaneously?

---

## Section 4: Feature Engineering

16. Which technical indicators should be used?
17. Why was each indicator selected?
18. Which indicators measure trend?
19. Which indicators measure volatility?
20. Which indicators measure market efficiency or choppiness?
21. Which indicators should be normalized?
22. Should percentile-based features be preferred over absolute values?
23. Should features be adaptive across different assets?

---

## Section 5: Threshold Selection

24. Should thresholds be fixed or adaptive?
25. How should trend thresholds be determined?
26. How should volatility thresholds be determined?
27. Should thresholds be based on historical percentiles?
28. Which thresholds should be configurable?
29. What default threshold values are recommended?

---

## Section 6: State Transition Logic

30. Under what conditions should a regime change occur?
31. Should hysteresis be implemented? If so, how?
32. How many consecutive confirmations are required before switching regimes?
33. Should a minimum regime duration be enforced?
34. How should rapid oscillation between regimes be prevented?
35. How should conflicting indicator signals affect transitions?

---

## Section 7: Confidence Calculation

36. How should confidence be defined?
37. Which factors contribute to confidence?
38. How should indicator agreement influence confidence?
39. Should confidence increase with regime persistence?
40. How should uncertainty be represented?
41. Should confidence be normalized to a range of 0–1?

---

## Section 8: Output Specification

42. What fields should the MarketRegime object contain?
43. Which fields are mandatory?
44. Should the module include diagnostic information explaining the detected regime?
45. Should raw feature values be included in the output?

---

## Section 9: Logging and Observability

46. What events should be logged?
47. What information should every regime transition log contain?
48. Should logs use structured JSON?
49. Which metrics should be exposed for monitoring?
50. What information is useful for debugging incorrect classifications?

---

## Section 10: Module Architecture

51. What should the public interface of market_regime.py look like?
52. Should the detector be stateless or stateful?
53. Which configuration parameters should be externally configurable?
54. Should the module depend on any external services?
55. How should the detector integrate with the rest of the trading system?

---

## Section 11: Testing Strategy

56. What unit tests are required?
57. Which edge cases should be tested?
58. How should historical data be used for validation?
59. What acceptance criteria define a correct implementation?
60. What measurable performance, reliability, and maintainability requirements should the implementation satisfy before it is considered production-ready?

---

## Final Instruction

Using the answers to all of the above questions, produce a complete technical specification for a production-grade Market Regime Detection module.

The specification should:

* Define every market regime precisely.
* Justify all indicator choices.
* Recommend threshold values and explain how they should be calibrated.
* Define confidence scoring mathematically where appropriate.
* Specify state transition logic, hysteresis, and persistence rules.
* Describe the module's public API and configuration options.
* Define structured logging and diagnostic output.
* Provide a comprehensive testing and validation strategy.
* Include rationale for every major design decision.
* Avoid implementation code unless it is necessary to clarify the specification.

The final deliverable should be detailed enough that a software engineer can implement `market_regime.py` directly from the specification with minimal ambiguity.

# Market Regime Detection Module
## Technical Specification v1.0
### Research Questionnaire Answers + Full Specification

**Classification:** Internal — Quantitative Infrastructure
**Audience:** Quantitative Researchers, Software Engineers, Risk Management
**Status:** Authoritative Reference

---

# PART I — RESEARCH QUESTIONNAIRE ANSWERS

This section answers every question in the v1.0 questionnaire. Each answer provides the reasoning a quant researcher would apply. The answers collectively feed into Part II, the formal specification.

---

## Section 1: Objectives

**Q1. What is the primary purpose of the Market Regime Detection module?**

The MRD module is a real-time classification engine that assigns a discrete, human-interpretable label — such as TRENDING or RANGING — to a market at each evaluation cycle. Its purpose is to give downstream strategy, risk, and execution components a shared, consistent description of the current market environment so they can adapt their behaviour accordingly. Without a shared regime, each component would independently estimate market character from raw signals, producing inconsistent and uncoordinated decisions.

Secondary purposes: providing an audit trail of market conditions at the time of every trading decision; enabling post-trade attribution by regime; supporting research into regime-conditional strategy performance.

**Q2. What trading decisions should depend on the detected market regime?**

The following decisions should be regime-conditional:

- *Strategy selection and weighting:* Trend-following strategies are activated or upweighted in TRENDING regimes; mean-reversion strategies are activated in RANGING regimes; all discretionary strategies may be suspended in CRISIS.
- *Position sizing:* Risk per trade shrinks in VOLATILE and CRISIS regimes; it may expand modestly in high-confidence TRENDING regimes with low volatility.
- *Stop placement:* Trend-following stops widen in high-volatility regimes; tight stops are applied in low-volatility ranges.
- *Signal filtering:* Breakout signals are filtered out during RANGING; mean-reversion signals are filtered out during TRENDING.
- *Execution style:* In CRISIS, execution switches to liquidity-taking (market orders) rather than passive posting, and order size is reduced.
- *Hedging triggers:* Portfolio-level hedges are activated when CRISIS or VOLATILE regimes persist beyond a minimum duration.
- *Risk limit tightening:* Maximum drawdown thresholds and position count limits are dynamically tightened in adverse regimes.

**Q3. Should the module prioritize stability or responsiveness? Why?**

Stability, with an explicit fast path reserved for crisis events. The reasoning is asymmetric cost: a false regime transition causes a strategy to behave inappropriately for multiple bars, potentially entering or exiting trades in the wrong context. A delayed true transition causes the system to continue operating under a stale regime label, which is usually less harmful because the strategy was already adapted to that regime.

The exception is the CRISIS regime. The cost of being one bar late to classify a crisis — while the system continues normal-sized trading during a flash crash or liquidity event — is potentially catastrophic. An emergency override path bypasses hysteresis specifically for CRISIS.

**Q4. What design principles should guide a production-grade market regime detector?**

Eight principles apply:

1. *Determinism.* Given the same input sequence and configuration, the module must produce bit-identical output. Non-determinism is a bug.
2. *Fail-fast validation.* Invalid configuration is rejected at startup, not at runtime.
3. *Bounded latency.* The update path must complete within a hard latency SLA. No I/O, no heap allocation, no locks on the hot path.
4. *Observable internals.* Every classification decision must be reconstructible from the logged event. No black boxes.
5. *Separation of concerns.* Indicator computation, threshold application, confidence scoring, and transition logic are decoupled layers. Each is independently testable.
6. *Graceful degradation.* Partial indicator failure produces a degraded-quality regime, not a system failure.
7. *Configuration over code.* Thresholds, weights, and periods are parameters, not constants. Changes do not require redeployment of logic.
8. *Conservative transitions.* When in doubt, hold the current regime. The burden of proof is on the candidate, not the incumbent.

---

## Section 2: Regime Definitions

**Q5. What market regimes should be supported?**

Seven primary regimes are supported: TRENDING_UP, TRENDING_DOWN, RANGING, VOLATILE, BREAKOUT, CRISIS, and UNDEFINED. The rationale for each is described in Q6. Seven is the minimum set that covers meaningfully distinct trading behaviours. Fewer states merge categories that require different strategy responses (e.g., RANGING and VOLATILE look similar in some indicators but require opposite mean-reversion vs. risk-reduction responses).

**Q6. How should each regime be formally defined?**

- *TRENDING_UP:* Price makes consistent higher highs and higher lows over the lookback period. Directional movement explains a significantly larger fraction of total price movement than noise. ADX is elevated. Linear regression slope is positive and statistically significant. The EMA fast line is above the EMA slow line and both are rising.

- *TRENDING_DOWN:* The mirror image of TRENDING_UP. ADX is elevated. Slope is negative and significant. EMA fast is below EMA slow and both are declining.

- *RANGING:* Price oscillates within a bounded channel without persistent directional bias. The ratio of directional movement to total movement is low (Choppiness Index is high). ATR is contained relative to its long-run average. Mean-reversion is the dominant price dynamic.

- *VOLATILE:* Realized volatility is elevated relative to the instrument's long-run baseline. The regime is direction-agnostic; volatility is the defining characteristic. ATR ratio and the historical volatility percentile are both elevated. The Choppiness Index may or may not be elevated. This regime differs from RANGING because it is characterized by large moves, not containment.

- *BREAKOUT:* A transitional state in which price has escaped a prior range boundary with above-average volume confirmation. Defined by: (a) a prior period of Bollinger Band compression, (b) a subsequent expansion with price closing outside the band, (c) volume exceeding its rolling mean by a configurable multiplier. BREAKOUT is inherently short-lived; it resolves into TRENDING or reverts to RANGING.

- *CRISIS:* Extreme tail event. Realized volatility exceeds a multiple of the long-run baseline. Bid-ask spreads have widened beyond normal operating ranges. Correlation across assets has broken down or compressed abnormally. Price movements are disorderly rather than trend-driven. This regime requires immediate risk reduction and is the only one subject to emergency override.

- *UNDEFINED:* Insufficient data for classification (warmup period), unresolvable signal conflict, or confidence has decayed below the minimum floor. Downstream systems must treat this as the most conservative regime possible.

**Q7. Should trend direction and volatility be represented as separate dimensions or combined into a single state?**

Combined into a single primary state, with volatility embedded in the regime label where it is definitionally significant (e.g., VOLATILE, CRISIS). Separate dimensions would require downstream consumers to join two independent states on every decision — increasing the complexity of downstream code, the risk of inconsistency, and the number of transition events to monitor.

The practical reasoning is also empirical: the combinations that matter for trading are not the full cross-product. High-volatility trending markets (common in crisis recovery) are classified VOLATILE, not TRENDING_UP with a volatility flag, because the risk management response overrides the directional signal. Only the combinations that actually require distinct responses are given distinct state names.

**Q8. Are the regimes mutually exclusive?**

Yes, at the primary level. The module emits exactly one primary regime label per evaluation cycle. Mutual exclusivity is a prerequisite for clean downstream logic; strategies should not need to handle overlapping regime membership.

**Q9. Can multiple regimes exist simultaneously?**

Not at the primary level. However, each primary regime carries a sub-state (EARLY, ESTABLISHED, LATE, STRESSED) which partially encodes secondary information. Additionally, the emitted event includes the full probability distribution across all regimes, so downstream consumers with a specific tolerance for ambiguity can implement their own logic. A risk system might choose to activate hedges if CRISIS probability exceeds 15% regardless of whether CRISIS is the primary label.

**Q10. How should unknown or ambiguous market conditions be represented?**

Via the UNDEFINED primary state and the STRESSED sub-state. UNDEFINED is used when the system cannot make a defensible classification. STRESSED is a sub-state applied within any primary regime when internal indicators show anomalous behaviour — for example, a TRENDING_UP.STRESSED label indicates the trend is present but exhibiting unusual characteristics (e.g., trend direction and volume are diverging).

---

## Section 3: Input Data

**Q11. What market data is required?**

Mandatory fields per bar: open, high, low, close, volume, and timestamp (UTC, timezone-aware). Optional but recommended: bid price, ask price (for CRISIS spread detection), and trade count (as an alternative volume proxy for instruments where volume is unreliable).

**Q12. What minimum historical lookback is needed?**

The warmup period is determined by the longest indicator lookback: `max(all_indicator_periods) + safety_buffer`. In the default configuration, the longest window is the historical volatility percentile lookback (252 bars). A safety buffer of 20 bars is added to ensure stable estimates at the edge of the window. Default warmup: 272 bars. During warmup, the regime is UNDEFINED and no events are emitted except the initialization event.

**Q13. Which timeframes should be supported?**

The module is timeframe-agnostic by design. All periods are expressed in bars, not calendar time. A user running on 1-minute bars and a user running on daily bars both configure the same parameters. Timeframe selection is the responsibility of the caller. In practice, the module is most useful on timeframes from 1 minute to 1 day. Sub-minute timeframes require `use_tick_normalization` mode (see §14.7 of the spec).

**Q14. How should missing or incomplete market data be handled?**

Three cases:

- *Missing fields:* A bar missing any mandatory field (open, high, low, close, volume, timestamp) is rejected. A `MalformedBarError` is raised and the bar is not processed. The regime is held from the previous cycle.
- *Timestamp gaps:* A gap exceeding `max_bar_gap_seconds` raises a `StaleDataError`. The caller must decide whether to replay historical bars to fill the gap or reset the module.
- *Zero-volume bars:* Bars with zero volume (halts, auctions) are held aside, indicators are not updated, confidence decays, and a `HaltBar` flag is set. Zero-range bars are treated similarly.

**Q15. Should the detector support multiple symbols simultaneously?**

Each `RegimeDetector` instance manages a single symbol-timeframe pair. Multi-symbol deployment is achieved by running a pool of independent instances, one per symbol. This avoids shared mutable state between symbols and allows independent configuration per instrument. A supervisor layer (outside the module's scope) manages the pool.

---

## Section 4: Feature Engineering

**Q16. Which technical indicators should be used?**

Trend: EMA crossover (fast/slow), ADX, Linear Regression Slope, Rate of Change.
Volatility: ATR ratio (ATR normalized by its long-run moving average), Realized Volatility, Bollinger Band Width, Historical Volatility Percentile.
Structure/Choppiness: Choppiness Index, Donchian Channel Width, price position within channel.
Volume/Liquidity: Volume Ratio (current volume vs. rolling average), OBV slope, Bid-Ask Spread, Amihud Illiquidity Ratio.

**Q17. Why was each indicator selected?**

Each indicator was selected to satisfy two criteria: (a) it measures a distinct aspect of market character not captured by other indicators in the set, and (b) it has a well-understood relationship with regime type supported by decades of practitioner and academic literature. The full justification is in the indicator rationale table in Part II §3. Key points: ADX is the most widely validated trend strength measure and is direction-agnostic; the Choppiness Index is mathematically derived from the ratio of ATR sum to the range, making it a clean measure of directional efficiency; ATR ratio normalizes volatility for cross-asset comparability; HVP percentile contextualizes current volatility within the instrument's own history.

**Q18. Which indicators measure trend?**

EMA crossover (direction), ADX (strength), Linear Regression Slope (velocity and direction), Rate of Change (momentum). These four measure different aspects of trending: EMA gives cross-sectional position, ADX gives strength without direction, LRS gives statistical best-fit velocity, and ROC gives recent price acceleration.

**Q19. Which indicators measure volatility?**

ATR ratio (relative volatility level), Realized Volatility (statistical volatility from log returns), Bollinger Band Width (volatility expansion/compression), Historical Volatility Percentile (contextual positioning within own history).

**Q20. Which indicators measure market efficiency or choppiness?**

Choppiness Index (primary: ratio of sum of ATR to total range over the period), Donchian Channel Width (range boundary estimation), price position within channel (mean-reversion context). These three form the structure group.

**Q21. Which indicators should be normalized?**

ATR must be normalized (as ATR ratio = ATR / long-run ATR moving average) because absolute ATR values are not comparable across instruments or across time for a single instrument as price level changes. Volume must be normalized (as volume ratio = volume / rolling volume mean) for the same reason. BBW is normalized as a percentile of its own history. All indicators that are compared against thresholds that are intended to be instrument-agnostic must be normalized.

**Q22. Should percentile-based features be preferred over absolute values?**

Yes, wherever the goal is cross-asset portability or temporal comparability. HVP and BBW percentile are expressed as percentiles of their own history. However, some indicators such as the Choppiness Index have mathematically bounded ranges (0–100, with specific theoretical values at 38.2 and 61.8) that are inherently comparable without percentile normalization.

**Q23. Should features be adaptive across different assets?**

Yes. The adaptive threshold engine (see §4 of the spec) maintains rolling empirical distributions per indicator per symbol. What constitutes "high ADX" for a futures contract with persistent structural trends differs from what constitutes "high ADX" for a low-volatility fixed income instrument. Adaptive thresholds correct for this. Static thresholds serve as initialization values and bounds.

---

## Section 5: Threshold Selection

**Q24. Should thresholds be fixed or adaptive?**

Both, in a layered architecture. Static thresholds are the baseline and are used during warmup. Adaptive thresholds are estimated from rolling empirical distributions and gradually replace static defaults once sufficient data is available. Adaptive thresholds are bounded within multiples of static defaults to prevent degenerate estimates. This design prevents the cold-start problem (adaptive thresholds are unavailable at launch) and the staleness problem (static thresholds fail in changing markets).

**Q25. How should trend thresholds be determined?**

For ADX, the threshold separating trending from non-trending markets is the value that best discriminates between bars subsequently observed to be in persistent directional moves vs. those that revert. In practice, the J. Welles Wilder original calibration of 25 (trending) and 20 (non-trending) is a well-validated starting point for equities and futures. For cross-asset or adaptive use, these thresholds are estimated as the ADX levels at the 60th and 40th percentile of the instrument's own ADX distribution respectively. For Choppiness Index, the theoretical boundaries of 38.2 (equivalent to a perfect geometric trend) and 61.8 (equivalent to maximum choppiness) are mathematically derived and hold universally.

**Q26. How should volatility thresholds be determined?**

The ATR ratio threshold for VOLATILE onset is calibrated to the 75th percentile of the instrument's own ATR ratio distribution. The CRISIS threshold is the 95th percentile. These percentile anchors are instrument-adaptive and empirically grounded — they fire roughly as often as the market truly exhibits those conditions for that instrument. Fixed multiples (ATR ratio > 1.5 for elevated, > 2.5 for VOLATILE) serve as static defaults.

**Q27. Should thresholds be based on historical percentiles?**

Yes, as the adaptive layer. Percentile-based thresholds have the advantage of maintaining approximately constant signal frequency across time and across assets — a threshold at the 75th percentile fires 25% of the time by definition, making the system self-calibrating to changing distributional regimes. However, this comes with the risk that in a persistently abnormal market (e.g., a prolonged crisis), what appears to be the 75th percentile is objectively dangerous. For this reason, crisis thresholds have an absolute floor below which the static default always applies regardless of the percentile estimate.

**Q28. Which thresholds should be configurable?**

All thresholds should be configurable, with recommended defaults provided. The most operationally significant are: ADX trending and non-trending thresholds, CI trending and ranging thresholds, ATR ratio volatile and crisis thresholds, HVP volatile and crisis percentiles, volume ratio breakout threshold, BAS crisis threshold, and confidence entry/exit thresholds. See the full configuration table in Part II §11.

**Q29. What default threshold values are recommended?**

The full table of recommended defaults is in Part II §11. The most critical values: ADX ≥ 25 = trending, ADX < 20 = non-trending; CI < 38.2 = strong trend, CI > 61.8 = ranging; ATR ratio > 1.5 = elevated volatility, > 2.5 = VOLATILE state; HVP > 80th percentile = VOLATILE, > 95th percentile = CRISIS; Volume Ratio > 2.0 = breakout confirmation.

---

## Section 6: State Transition Logic

**Q30. Under what conditions should a regime change occur?**

A regime change occurs when: (a) the candidate regime's probability exceeds the entry threshold, (b) the confidence margin exceeds the confidence entry threshold, (c) the candidate has been the leading regime for at least `hysteresis_bars_entry` consecutive cycles, and (d) the current regime's confidence has fallen below the exit threshold. All four conditions are necessary. Emergency transitions require only condition (a) and a specific crisis trigger.

**Q31. Should hysteresis be implemented? If so, how?**

Yes. Hysteresis is implemented via two mechanisms: (a) a bar-count gate on entry (the candidate must lead for N consecutive bars before the transition fires) and (b) an asymmetric probability/confidence threshold (entering requires higher probability than exiting requires to retain). This two-layer hysteresis prevents both rapid oscillation (bar count gate) and premature entry (probability asymmetry). The exit condition is intentionally easier to trigger than the entry condition to respect the conservative-transitions principle.

**Q32. How many consecutive confirmations are required before switching regimes?**

Default: 3 bars for entry, 2 bars for exit. These are configurable (`hysteresis_bars_entry`, `hysteresis_bars_exit`). The lower exit bar count reflects the asymmetry: once a regime's confidence is falling, requiring fewer bars to acknowledge this is appropriate. However, the mandatory transition cooldown prevents the module from immediately re-entering the old regime after exiting.

**Q33. Should a minimum regime duration be enforced?**

Yes. Each regime has a minimum persistence in bars before a voluntary transition is permitted. Defaults: TRENDING 5 bars, RANGING 8 bars, VOLATILE 3 bars, BREAKOUT 2 bars, CRISIS 10 bars, UNDEFINED 1 bar. These values reflect the expected natural duration of each regime type — ranges tend to be stickier than breakouts.

**Q34. How should rapid oscillation between regimes be prevented?**

Three mechanisms in combination: (a) the bar-count hysteresis gate on entry; (b) the mandatory transition cooldown (`transition_cooldown_bars` = 5 bars by default) after any transition, during which no further voluntary transitions are permitted; (c) minimum persistence enforcement. The combination means that the module cannot transition into a regime, immediately back out, and immediately re-enter within a window shorter than `min_persistence + cooldown` bars.

**Q35. How should conflicting indicator signals affect transitions?**

See Section 8 of the questionnaire answers and the full conflict resolution protocol in Part II §8. The short answer: conflicts are resolved by a priority hierarchy (CRISIS always wins; BREAKOUT wins over RANGING; incumbent wins on tie), reduced to lower confidence if unresolvable, and escalated to UNDEFINED if unresolvable beyond a maximum duration.

---

## Section 7: Confidence Calculation

**Q36. How should confidence be defined?**

Confidence is defined as the margin of victory of the winning regime over its nearest competitor in the softmax-normalized probability distribution. Formally: `C = P(R*) - max(P(Rj) for j ≠ R*)`. This measures how clearly dominant the winning regime is, not merely how probable it is. A regime with 40% probability when the runner-up has 38% has low confidence; the same 40% when the runner-up has 5% has high confidence.

**Q37. Which factors contribute to confidence?**

Three factors: (a) the degree of indicator agreement within each group (trend indicators pointing the same way raises the trend group score), (b) the margin between the top and second regime in the probability distribution, and (c) regime persistence (a regime that has been held for many bars without degradation has more evidence behind it, encoded via the sub-state and optionally as a persistence bonus on confidence). A fourth factor applies in the conflict path: the conflict confidence penalty reduces confidence when signals disagree.

**Q38. How should indicator agreement influence confidence?**

Indicator agreement is captured in the group signal score. The group score is the weighted average of individual indicator scores within the group. When all indicators agree (all positive scores, or all negative), the group score is high in magnitude. When they disagree, the absolute value of the group score is lower, which flows through to a lower aggregate regime score and a lower confidence margin.

**Q39. Should confidence increase with regime persistence?**

Optionally. A persistence bonus on confidence is supported via configuration (`persistence_confidence_bonus_enabled`). When enabled, confidence receives a small additive bonus proportional to `log(bars_in_regime)`, capped at `max_persistence_bonus`. This bonus is small by design — it should reinforce a clear regime, not rescue an ambiguous one. The bonus is zeroed on any transition.

**Q40. How should uncertainty be represented?**

Through three complementary mechanisms: (a) the UNDEFINED primary state for unresolvable ambiguity; (b) the confidence score (low confidence signals uncertainty regardless of the label); (c) the full probability distribution in the emitted event, allowing downstream consumers to see how uncertain the classification is even when a primary label is emitted. Downstream consumers should treat any regime with `confidence < confidence_low_threshold` as unreliable.

**Q41. Should confidence be normalized to a range of 0–1?**

Yes. Confidence is always expressed in `[0.0, 1.0]` after a monotonic scaling transform applied to the raw margin. The scaling is designed so that 0.5 represents a clearly dominant regime (margin of ~0.3 in probability terms) and values below 0.2 represent meaningful ambiguity. This provides an interpretable scale for downstream consumers.

---

## Section 8: Output Specification

**Q42. What fields should the MarketRegime object contain?**

Core: `timestamp`, `symbol`, `timeframe`, `primary_regime`, `sub_state`, `label` (composite), `confidence`, `probability_distribution`. Transition info: `transition_occurred`, `previous_regime`, `transition_type`, `bars_in_regime`, `in_cooldown`. Indicators: `indicator_values` (dict), `signal_scores` (per group). Flags: `signal_conflict`, `using_static_thresholds`, `data_staleness_warning`, `emergency_override`, `min_persistence_met`, `externally_locked`. Thresholds applied and their source (static vs. adaptive). Metadata: `evaluation_cycle`, `module_version`, `config_id`, `compute_latency_us`. See Part II §9 for the full JSON schema.

**Q43. Which fields are mandatory?**

Mandatory fields (must always be populated): `timestamp`, `symbol`, `timeframe`, `primary_regime`, `sub_state`, `label`, `confidence`, `probability_distribution`, `bars_in_regime`, `evaluation_cycle`, `module_version`, `config_id`. All other fields may be null in degraded modes (e.g., `indicator_values` may be partially populated if an indicator failed computation).

**Q44. Should the module include diagnostic information explaining the detected regime?**

Yes. The `signal_scores` dict, the `conflicting_indicators` list, and the `thresholds_applied` dict together constitute a machine-readable explanation of why the regime was classified as it was. In addition, a periodic `REGIME_DIAGNOSTIC` event (emitted every N cycles) provides a deeper snapshot including the adaptive threshold history and signal score distributions.

**Q45. Should raw feature values be included in the output?**

Yes, as the `indicator_values` dict. This serves two critical purposes: (a) it allows post-trade debugging of incorrect classifications by replaying the signal values at the time of each decision; (b) it provides inputs for any downstream consumers that want to compute their own derived features on top of the regime signal.

---

## Section 9: Logging and Observability

**Q46. What events should be logged?**

Six event types: `REGIME_INITIALIZED` (startup), `REGIME_EVENT` (every evaluation cycle), `REGIME_TRANSITION` (on any state change), `REGIME_DIAGNOSTIC` (periodic), `REGIME_ALERT` (crisis, undefined persistence, latency breach), `REGIME_ERROR` (malformed bar, stale data, indicator failure).

**Q47. What information should every regime transition log contain?**

Pre-transition state snapshot (full RegimeEvent), post-transition state snapshot, the specific trigger evidence (which indicators changed, which thresholds were crossed), the transition type (NORMAL, EMERGENCY, LOCK_RELEASE), bars_in_prior_regime, and the wall-clock time of the transition event. This enables complete reconstruction of every transition from logs alone.

**Q48. Should logs use structured JSON?**

Yes, mandatory. Structured JSON enables downstream aggregation, alerting, and analysis without custom parsers. Every log line is a self-contained JSON object with a `schema_version` field to support forward compatibility. Human-readable formatting is not a requirement; log consumers are machines.

**Q49. Which metrics should be exposed for monitoring?**

Prometheus-compatible metrics: current regime label (as integer enum), current confidence, compute latency percentiles (p50, p95, p99), total transition count since startup, total conflict event count, CRISIS active flag (0/1), total emergency overrides, adaptive threshold values (for each key indicator). These are defined in Part II §15.4.

**Q50. What information is useful for debugging incorrect classifications?**

The full `indicator_values` dict at the time of the incorrect classification, the `signal_scores` dict showing each group's contribution, the `thresholds_applied` dict showing whether static or adaptive thresholds were in use, the `probability_distribution` showing how close the second-best regime was, the `conflicting_indicators` list, the `bars_in_regime` count (to check if persistence constraints were binding), and the `flags` dict (to check for staleness, warmup, or lock conditions). All of this is present in every `REGIME_EVENT` log entry.

---

## Section 10: Module Architecture

**Q51. What should the public interface of market_regime.py look like?**

The public interface is defined in Part II §10. Primary class is `RegimeDetector`. Public methods: `__init__`, `update`, `update_batch`, `get_current_regime`, `get_regime_history`, `reset`, `recalibrate_thresholds`, `get_diagnostics`, `validate_config`. Secondary classes: `RegimeConfig` (typed configuration), `RegimeEvent` (output data class), `RegimePublisher` (async event bus), `SyntheticMarketGenerator` (test utility).

**Q52. Should the detector be stateless or stateful?**

Stateful. The module maintains rolling indicator buffers, the adaptive threshold engine's distribution estimates, the current regime label and bars-in-regime counter, the hysteresis counter, the conflict counter, the cooldown counter, and the confidence history. Statefulness is required because regime detection is fundamentally a sequential classification problem — the current classification depends on the history of bar observations, not just the current bar. The state is encapsulated within the instance and is not shared across instances.

**Q53. Which configuration parameters should be externally configurable?**

All parameters. No hardcoded constants should exist in the implementation. The full parameter table is in Part II §11, organized into six groups: indicator periods, threshold values, transition and hysteresis settings, persistence settings, adaptive threshold settings, and system settings. Parameters are validated at initialization; the module refuses to start with invalid configuration.

**Q54. Should the module depend on any external services?**

No. The module is a self-contained computation engine. It accepts OHLCV bars as input and produces RegimeEvents as output. It has no network dependencies, no database dependencies, and no filesystem dependencies during normal operation. Configuration is loaded by the caller and passed in at construction. Log events are emitted via a callback or publisher interface; the transport is the caller's responsibility. This design allows the module to run in backtesting, paper trading, and live trading environments without modification.

**Q55. How should the detector integrate with the rest of the trading system?**

Via two integration points: (a) the synchronous `update(bar)` call, invoked by the strategy event loop on each completed bar; (b) the event publisher interface, via which downstream systems (risk, execution, monitoring) subscribe to regime events asynchronously. The module should sit between the market data feed and the strategy layer in the processing pipeline. Strategies query `get_current_regime()` to gate their signal generation; the risk system subscribes to `REGIME_ALERT` events to adjust limits; the monitoring system consumes all events for dashboarding.

---

## Section 11: Testing Strategy

**Q56. What unit tests are required?**

Ten test categories covering: indicator correctness, signal score mapping, confidence calculation, hysteresis and transition logic, emergency override, conflict resolution, adaptive thresholds, data quality handling, scenario integration tests, and performance benchmarks. Each is detailed in Part II §12.

**Q57. Which edge cases should be tested?**

Critical edge cases: exactly `min_warmup_bars` bars, gap bars triggering StaleDataError, zero-volume bars, NaN and inf inputs, all-constant price series (zero ATR), a perfectly linear series (maximum ADX), transition immediately followed by a reversal signal (cooldown enforcement), simultaneous CRISIS trigger during cooldown of a prior transition, regime lock during an emergency override attempt, `max_conflict_bars` being reached exactly, adaptive thresholds being bounded by multiplier constraints.

**Q58. How should historical data be used for validation?**

Historical data should be used in two ways: (a) in regime labelling exercises where a human expert labels regimes for a set of historical periods, and the module's classifications are compared against those labels to measure precision and recall per regime type; (b) in strategy performance attribution, where the module's historical regime labels are applied to a strategy's trade history to verify that strategy P&L is regime-conditional in the expected direction. Neither validation method should use data from the period used to calibrate static thresholds.

**Q59. What acceptance criteria define a correct implementation?**

A correct implementation satisfies: determinism (same input = same output, always), latency SLA (p99 < `max_compute_latency_us`), memory stability (no growth beyond initial buffer allocation over 100,000 cycles), all unit tests passing, regime label plausibility on synthetic data with known regimes (each synthetic regime type produces the correct primary label in > 80% of bars during the steady-state period of that regime), config validation rejection of all invalid parameters, and zero exceptions raised on any valid OHLCV input sequence.

**Q60. What measurable performance, reliability, and maintainability requirements should the implementation satisfy before it is considered production-ready?**

*Performance:* p99 update latency < 1,000 µs on target hardware; memory footprint stable and bounded; no GC pauses in the hot path (Python: avoid object allocation on hot path; consider Cython or Rust extension for inner loops if latency is critical).
*Reliability:* 100% of test categories passing; zero known exceptions on valid input; graceful degradation on partial indicator failure; complete state recovery from a checkpoint (if checkpointing is implemented).
*Maintainability:* All configuration in one typed config class; all thresholds named constants in config, not magic numbers; each logical layer (indicators, scoring, transition) in a separate module; public API stable across minor versions; every public method has a docstring with contract, raises, and return type.

---

# PART II — FORMAL TECHNICAL SPECIFICATION

This specification is the authoritative implementation reference. It is derived from the questionnaire answers above. An engineer should be able to implement `market_regime.py` directly from this document.

---

## 1. Purpose and Scope

The Market Regime Detection (MRD) module is a stateful, real-time classification engine that assigns a discrete regime label to a financial instrument at each evaluation cycle. It emits a structured `RegimeEvent` on every bar, which downstream strategy, risk, and execution components use to adapt their behaviour.

**Scope includes:** regime classification, confidence scoring, state transition management, hysteresis, persistence enforcement, conflict resolution, adaptive thresholds, structured logging, and the public API.

**Scope excludes:** market data transport, bar construction, strategy logic, order management, and portfolio-level regime aggregation.

---

## 2. Market State Taxonomy

### 2.1 Primary States

| ID | Enum Name | Semantic Definition |
|----|-----------|---------------------|
| 0 | `TRENDING_UP` | Persistent directional upward movement. ADX elevated, EMA fast > slow, LRS slope positive and significant, CI below trend threshold. |
| 1 | `TRENDING_DOWN` | Persistent directional downward movement. ADX elevated, EMA fast < slow, LRS slope negative and significant, CI below trend threshold. |
| 2 | `RANGING` | Price oscillating within bounded horizontal channel. CI above ranging threshold, ATR ratio contained, no persistent directional bias. |
| 3 | `VOLATILE` | Realized volatility elevated relative to long-run baseline, direction-agnostic. ATR ratio and HVP both above their respective thresholds. |
| 4 | `BREAKOUT` | Transitional: price has escaped a prior compression zone with volume confirmation. BBW expanded after compression, volume ratio elevated, price outside Bollinger Bands. |
| 5 | `CRISIS` | Extreme tail volatility, potential liquidity stress, disorderly price action. HVP above 95th percentile, or BAS above crisis threshold, or RV above crisis multiple of baseline. |
| 6 | `UNDEFINED` | Insufficient data (warmup), unresolvable conflict, or confidence below minimum floor. |

### 2.2 Sub-States

Sub-states qualify the primary label with information about regime quality and maturity.

| Sub-State | Condition |
|-----------|-----------|
| `EARLY` | `bars_in_regime < min_persistence[primary]` |
| `ESTABLISHED` | `bars_in_regime >= min_persistence[primary]` AND `confidence >= confidence_high_threshold` |
| `LATE` | `confidence < confidence_late_threshold` AND `bars_in_regime >= min_persistence[primary]` |
| `STRESSED` | Any stress indicator fires within the current regime (e.g., volume diverging from trend direction, spread widening in a non-crisis regime) |

The composite label is expressed as `PRIMARY.SUBSTATE`, e.g., `TRENDING_UP.ESTABLISHED`.

Sub-states are determined after the primary regime is confirmed. Only one sub-state applies per cycle, resolved in priority order: STRESSED > LATE > EARLY > ESTABLISHED.

---

## 3. Required Indicators

### 3.1 Indicator Reference Table

All indicators are computed incrementally (no full-history recalculation on each bar). Rolling buffers of fixed capacity are pre-allocated at initialization.

#### Trend Group

| Indicator | Symbol | Config Parameters | Rationale |
|-----------|--------|------------------|-----------|
| EMA Crossover | EMA | `ema_fast`, `ema_slow` | Canonical directional trend signal. Crossover gives direction; the gap between lines gives magnitude. Included because it is widely used and forms a clean prior for trend direction before ADX confirms strength. |
| Average Directional Index | ADX | `adx_period` | Welles Wilder's directional movement index measures trend strength without regard to direction. ADX rising above 25 has been empirically validated across decades and asset classes as a reliable trending signal. Selected over pure momentum because it explicitly separates direction (+DI, -DI) from strength (ADX). |
| Linear Regression Slope | LRS | `lrs_period` | The best-fit slope of prices over a rolling window provides a statistically clean measure of price velocity. Unlike EMA crossover, it is not subject to lag artifacts from two independent smoothing operations. Provides a continuous signal where EMA crossover is binary. |
| Rate of Change | ROC | `roc_period` | Short-term momentum. Confirms the trend is still accelerating vs. decelerating. Included because ADX and EMA can remain in trending territory during a slowdown that precedes reversal; ROC provides early warning. |

#### Volatility Group

| Indicator | Symbol | Config Parameters | Rationale |
|-----------|--------|------------------|-----------|
| ATR Ratio | ATRR | `atr_period`, `atr_long_ma_period` | ATR normalized by its own long-run moving average. Normalization makes the indicator cross-asset comparable and temporally stable as price levels change. Chosen over raw ATR for this reason. |
| Realized Volatility | RV | `rv_window` | Standard deviation of log returns, annualized. The statistically cleanest measure of volatility. Serves as the ground-truth volatility signal; other volatility indicators are validated against it. |
| Bollinger Band Width | BBW | `bb_period`, `bb_std` | Measures the width of the Bollinger Bands normalized by the middle band. Sensitive to volatility compression (low BBW) which precedes breakouts. Included specifically for BREAKOUT detection. |
| Historical Volatility Percentile | HVP | `hvp_lookback` | Contextualizes current RV against the instrument's own history. A 90th percentile HVP means current volatility is higher than 90% of historical readings for this instrument. Critical for regime-relative threshold setting. |

#### Structure Group

| Indicator | Symbol | Config Parameters | Rationale |
|-----------|--------|------------------|-----------|
| Choppiness Index | CI | `ci_period` | Mathematically derived as `100 * log10(sum(ATR) / (highest_high - lowest_low))` normalized to [0, 100]. Pure measure of directional efficiency. A perfect geometric trend produces CI = 38.2 (Fibonacci level, which is the theoretical minimum of the CI formula); maximum choppiness produces CI = 61.8. These theoretical boundaries make CI thresholds instrument-agnostic without percentile normalization. |
| Donchian Channel Width | DCW | `dc_period` | The width of the N-bar high-low channel. Measures range size. Confirms ranging conditions alongside CI. |
| Price-in-Channel Position | PCP | derived from DC | Where price sits within the Donchian Channel. Values near 0 or 1 indicate price is at the extremes of the range; 0.5 is the midpoint. Used to confirm mean-reversion context within RANGING. |

#### Volume / Liquidity Group

| Indicator | Symbol | Config Parameters | Rationale |
|-----------|--------|------------------|-----------|
| Volume Ratio | VR | `volume_ma_period` | Current bar volume divided by its rolling mean. Values above threshold indicate unusual volume surges required for BREAKOUT confirmation. Volume is a necessary (not sufficient) condition for a valid breakout. |
| OBV Slope | OBVS | `obv_slope_period` | Slope of On-Balance Volume. Confirms whether volume flow is aligned with price direction in TRENDING regimes. Divergence between OBVS and price slope is a STRESSED sub-state trigger. |
| Bid-Ask Spread | BAS | real-time | Direct liquidity stress measure. Widens significantly in CRISIS and flash crashes. Optional input; activates crisis fast path when available. |
| Amihud Illiquidity Ratio | AIR | `amihud_period` | `|return| / volume`, normalized. Measures price impact per unit of volume. Elevated AIR indicates thinning order books. Useful CRISIS precursor. |

### 3.2 Indicator Computation Notes

- All periods in bars, not calendar time.
- For indicators requiring a minimum number of bars (e.g., ADX requires `2 * adx_period - 1`), those indicators return `NaN` until their minimum is met and are excluded from scoring with proportional weight redistribution.
- EMA is initialized with SMA for the first `ema_fast` bars to avoid cold-start distortion.
- ATR uses the standard Wilder smoothed method: `ATR_t = (ATR_{t-1} * (n-1) + TR_t) / n`.
- ADX uses the full Wilder DI system: compute +DI and -DI, then DX, then smooth DX to ADX.
- CI formula: `100 * log10(sum(ATR, n) / (max(high, n) - min(low, n))) / log10(n)`.
- LRS uses ordinary least squares on a rolling price vector. Slope is expressed in price units per bar; normalize by dividing by the mean price over the window to produce a dimensionless percentage slope.

---

## 4. Threshold Selection Methodology

### 4.1 Architecture

Thresholds are managed by a two-layer system:

**Layer 1 — Static Defaults:** Fixed values defined in configuration. Used during warmup and as bounds for adaptive estimates. See §11 for default values.

**Layer 2 — Adaptive Engine:** Recalibrates thresholds from rolling empirical data. Activated once `min_adaptive_samples` bars have been observed. Operates on a read-copy-update pattern so that `update()` is never blocked during recalibration.

### 4.2 Adaptive Threshold Estimation Algorithm

**Step 1 — Maintain rolling empirical CDF per indicator.**
For each indicator, maintain a rolling sorted buffer of the last `adaptive_lookback` values. Implement using an order-statistic data structure (e.g., a sorted deque or Fenwick tree) to support O(log n) percentile queries.

**Step 2 — Estimate regime-discriminating percentile.**
For each (indicator, regime_pair) combination that the threshold is intended to separate, query the percentile corresponding to the configured separation target. Example: the ADX threshold separating TRENDING from non-TRENDING is estimated as the `adx_trend_percentile` percentile of the ADX distribution.

**Step 3 — Apply exponential smoothing.**
```
T_new = alpha * T_estimated + (1 - alpha) * T_current
```
where `alpha = threshold_smoothing_alpha` (default: 0.05). This prevents abrupt threshold shifts.

**Step 4 — Enforce bounds.**
```
T_bounded = clip(T_new,
    static_default * lower_bound_multiplier,
    static_default * upper_bound_multiplier)
```
Default multipliers: lower 0.5, upper 2.0.

**Step 5 — Stability gate.**
If `adaptive_sample_count < min_adaptive_samples`, set `using_static_thresholds = true` and use Layer 1 values unchanged.

**Step 6 — Atomic swap.**
Compute the full new threshold set in a shadow copy. Atomically replace the active threshold reference at the end of the recalibration cycle. The `update()` method reads the threshold pointer once per cycle under a lightweight reader lock.

### 4.3 Threshold Recalibration Schedule

Recalibration runs: (a) on explicit call to `recalibrate_thresholds()`, (b) automatically every `auto_recalibrate_interval` bars (default: 50). Recalibration is not performed on the `update()` hot path; it is dispatched to a background task.

---

## 5. Confidence Calculation

### 5.1 Per-Indicator Signal Score

Each indicator `i` produces a scalar signal score `s_i(R) ∈ [-1.0, 1.0]` expressing its support for regime `R`.

Signal scores are produced by a **piecewise linear mapping** from indicator value to score:

```
s_i = clip(
    (x_i - T_neutral) / (T_strong - T_neutral),
    -1.0,
    1.0
)
```

Where:
- `x_i` is the current indicator value
- `T_neutral` is the threshold below which the indicator is neutral with respect to regime R
- `T_strong` is the threshold above which the indicator fully supports regime R
- Values below `T_neutral` produce negative scores (contradiction)

Threshold values `T_neutral` and `T_strong` are sourced from the active threshold set (adaptive or static).

**Example — ADX score for TRENDING:**
- T_neutral = 20 (adx_non_trending_threshold)
- T_strong = 30 (adx_strong_trend_threshold)
- ADX = 27 → s = (27 - 20) / (30 - 20) = 0.70
- ADX = 15 → s = (15 - 20) / (30 - 20) = -0.50 → clipped to -0.50

### 5.2 Group Score Aggregation

Indicators are organized into four groups. Each indicator has a relative weight within its group (weights sum to 1.0 within group). Each group has an absolute weight (weights sum to 1.0 across groups).

```
GroupScore(g, R) = sum_i( w_i * s_i(R) )   for i in group g

CompositeScore(R) = sum_g( W_g * GroupScore(g, R) )
```

Where `w_i` = indicator relative weight within group, `W_g` = group absolute weight.

**Default group weights:**

| Group | Default Weight `W_g` |
|-------|---------------------|
| Trend | 0.35 |
| Volatility | 0.30 |
| Structure | 0.20 |
| Liquidity | 0.15 |

Within-group indicator weights are equal by default (configurable).

### 5.3 Regime Probability via Softmax

Raw composite scores across all regimes are transformed to a probability distribution:

```
P(R_k) = exp(Score(R_k) / T_softmax) / sum_j( exp(Score(R_j) / T_softmax) )
```

`T_softmax` (default: 1.0) controls sharpness. Lower values sharpen discrimination; higher values soften it. In practice, T_softmax is tuned so that a clear trending market (ADX = 35, CI = 30, aligned EMA) produces `P(TRENDING_UP) > 0.70`.

### 5.4 Confidence as Margin of Victory

```
C_raw = P(R*) - max( P(R_j) for j ≠ R* )
```

Where `R*` is the regime with the highest probability.

`C_raw ∈ [-1/6, 1.0]` (minimum occurs when all regimes have equal probability; maximum is 1.0 when P(R*) = 1.0).

Apply a monotonic scaling transform to map to `[0.0, 1.0]`:

```
C = (C_raw - C_min) / (C_max - C_min)
```

Where `C_min = -1/(n_regimes - 1)` and `C_max = 1.0`. For 7 regimes: `C_min ≈ -0.167`.

This guarantees `C = 0.0` when all regimes are tied and `C = 1.0` when one regime is certain.

**Interpretive reference:**

| Confidence Range | Interpretation |
|-----------------|----------------|
| 0.0 – 0.2 | Ambiguous; treat with caution |
| 0.2 – 0.4 | Weak regime signal |
| 0.4 – 0.6 | Moderate confidence |
| 0.6 – 0.8 | High confidence |
| 0.8 – 1.0 | Very high confidence; regime is dominant |

### 5.5 Confidence Decay

If no new bar is received (stale data scenario), confidence decays:

```
C_t = C_0 * exp(-lambda * delta_t_seconds)
```

Where `lambda = confidence_decay_rate` (default: 0.005 per second). When `C_t < confidence_min_floor` (default: 0.05), the regime transitions to `UNDEFINED`.

### 5.6 Optional Persistence Bonus

When `persistence_confidence_bonus_enabled = true`:

```
C_adjusted = min(C + bonus_weight * log(1 + bars_in_regime) / log(1 + bonus_saturation_bars), 1.0)
```

Default `bonus_weight = 0.03`, `bonus_saturation_bars = 20`. The bonus is small by design and is zeroed on any transition.

---

## 6. State Transition Rules

### 6.1 Transition State Machine

```
Any State → UNDEFINED    : confidence decays below confidence_min_floor
Any State → CRISIS       : emergency trigger (fast path, bypasses normal rules)
UNDEFINED → Any State    : confidence recovers above entry threshold

RANGING   → BREAKOUT     : BBW expansion after compression + volume surge + price outside BB
BREAKOUT  → TRENDING_*   : breakout_confirmation_bars elapsed + direction confirmed
BREAKOUT  → RANGING      : price reverts within breakout_failure_bars

CRISIS    → Any State    : only after min_persistence[CRISIS] bars AND confidence recovery
```

### 6.2 Normal Transition Conditions

All of the following must be simultaneously true to trigger a voluntary transition:

1. `P(R_candidate) >= entry_probability_threshold` (default: 0.60)
2. `C >= confidence_entry_threshold` (default: 0.25) for the candidate
3. `R_candidate` has been the highest-probability regime for `hysteresis_bars_entry` (default: 3) consecutive evaluation cycles
4. Active regime confidence `C_active < exit_confidence_threshold` (default: 0.40)

### 6.3 Hysteresis Counter

A per-candidate counter `hysteresis_count[R_candidate]` increments by 1 each cycle that `R_candidate` holds the highest probability and conditions 1 and 2 are met. It resets to 0 when a different regime leads. The transition fires when `hysteresis_count[R_candidate] >= hysteresis_bars_entry`.

The exit-side hysteresis: a separate `low_confidence_count` counter increments when active regime confidence falls below `exit_confidence_threshold`. The active regime is eligible for replacement only after `low_confidence_count >= hysteresis_bars_exit` (default: 2).

### 6.4 Transition Cooldown

After any transition, set `cooldown_remaining = transition_cooldown_bars` (default: 5). Decrement by 1 each evaluation cycle. While `cooldown_remaining > 0`, no voluntary transition is permitted. Set `in_cooldown = true` in emitted events. Emergency transitions are not subject to cooldown enforcement.

### 6.5 Minimum Persistence Gate

A voluntary transition from the active regime is blocked if `bars_in_regime < min_persistence[active_regime]`. Emergency transitions bypass this gate.

Default minimum persistence values:

| Regime | `min_persistence` (bars) |
|--------|--------------------------|
| TRENDING_UP | 5 |
| TRENDING_DOWN | 5 |
| RANGING | 8 |
| VOLATILE | 3 |
| BREAKOUT | 2 |
| CRISIS | 10 |
| UNDEFINED | 1 |

### 6.6 Emergency Override (Fast Path)

An emergency transition to CRISIS bypasses: hysteresis gate, cooldown, minimum persistence, conflict resolution. It triggers when any of the following conditions is met:

| Trigger | Condition |
|---------|-----------|
| Extreme volatility | `HVP > crisis_hvp_threshold` (default: 95th percentile) AND `ATRR > crisis_atrr_threshold` (default: 3.0) |
| Spread crisis | `BAS > crisis_spread_threshold` (instrument-specific; required config if BAS is provided) |
| Volatility explosion | `RV > crisis_rv_baseline_multiplier * RV_long_run_mean` (default multiplier: 3.0) |

Emergency transitions set `transition_type = EMERGENCY` and `emergency_override = true` in the emitted event. A circuit breaker prevents degenerate cascading: if more than `max_crisis_overrides_per_hour` emergency overrides occur in a rolling 60-minute window, `circuit_breaker_active = true` is set, emergency overrides are suspended, and `CRISIS.STRESSED` is held until the circuit breaker clears.

Circuit breaker clears after `crisis_storm_clear_bars` (default: 30) bars of non-crisis conditions or on explicit `reset()` call.

---

## 7. Minimum Persistence

Minimum persistence values are defined in §6.5. Implementation notes:

- `bars_in_regime` increments by 1 on every evaluation cycle while the primary regime label is unchanged.
- `bars_in_regime` resets to 0 on any transition (including emergency overrides).
- The `EARLY` sub-state is active while `bars_in_regime < min_persistence[primary]`.
- `ESTABLISHED` sub-state requires `bars_in_regime >= min_persistence[primary]` AND `C >= confidence_high_threshold` (default: 0.50).
- The minimum persistence gate in §6.5 checks `bars_in_regime < min_persistence[active]` at the point a transition would otherwise fire.

---

## 8. Handling Conflicting Signals

### 8.1 Conflict Detection

A conflict is flagged when any of:
- `C < conflict_margin_threshold` (default: 0.15), OR
- Two or more regimes have `P(R_k) >= conflict_probability_floor` (default: 0.30)

When flagged: set `signal_conflict = true` in the emitted event. Populate `conflicting_indicators` with the list of indicators whose signal scores contradict the winning regime's direction.

### 8.2 Conflict Resolution Hierarchy

Apply in order; stop at the first resolution:

**Rule 1 — Crisis Override.**
If any CRISIS emergency trigger condition is met, assign CRISIS regardless of other signals. `conflict_resolution = CRISIS_OVERRIDE`.

**Rule 2 — Incumbent Retention.**
If the active regime's probability has not fallen below `exit_confidence_threshold`, retain the active regime with `C_adjusted = C * conflict_confidence_penalty` (default: 0.70). `conflict_resolution = INCUMBENT_RETAINED`.

**Rule 3 — Domain Priority Rules.**

Apply the following ordered rule table:

| Condition | Winner | Rationale |
|-----------|--------|-----------|
| BREAKOUT triggers fire AND active is RANGING | BREAKOUT | Breakout evidence supersedes range continuation |
| ADX > adx_trending_threshold AND CI < ci_trending_threshold | TRENDING (direction from +DI/-DI) | Unambiguous trend indicators override volatility classification |
| ATRR > atr_ratio_volatile_threshold AND HVP > hvp_volatile_threshold | VOLATILE over RANGING | Elevated volatility changes the trading response even if range is present |

`conflict_resolution = DOMAIN_RULE`.

**Rule 4 — Blended Confidence Penalty.**
If Rules 1–3 do not resolve: retain the highest-probability regime. Set `C_adjusted = C * conflict_confidence_penalty`. `conflict_resolution = PENALTY_APPLIED`.

**Rule 5 — UNDEFINED Escalation.**
If the conflict has persisted for `max_conflict_bars` (default: 5) consecutive cycles without resolution under Rules 1–3: transition to `UNDEFINED.STRESSED`. `conflict_resolution = ESCALATED_UNDEFINED`.

### 8.3 Conflict Tracking

Maintain `conflict_streak_count`: a counter that increments each cycle a conflict is active and resets to 0 when the conflict resolves. Used for Rule 5 escalation.

---

## 9. Logging Schema

All log entries are JSON objects emitted to the system's log sink. Schema version is `"1.0"`. The `schema_version` field is mandatory on every event.

### 9.1 REGIME_EVENT (Every Cycle)

```json
{
  "schema_version": "1.0",
  "event_type": "REGIME_EVENT",
  "timestamp_utc": "<ISO 8601 with microseconds>",
  "symbol": "<string>",
  "timeframe": "<string, e.g. '5m'>",
  "evaluation_cycle": "<int, monotonically increasing>",

  "regime": {
    "primary": "<enum string>",
    "sub_state": "<enum string>",
    "label": "<PRIMARY.SUBSTATE>",
    "confidence": "<float [0,1]>",
    "probability_distribution": {
      "TRENDING_UP": "<float>",
      "TRENDING_DOWN": "<float>",
      "RANGING": "<float>",
      "VOLATILE": "<float>",
      "BREAKOUT": "<float>",
      "CRISIS": "<float>",
      "UNDEFINED": "<float>"
    }
  },

  "transition": {
    "occurred": "<bool>",
    "previous_regime": "<label string or null>",
    "transition_type": "<NORMAL | EMERGENCY | LOCK_RELEASE | null>",
    "conflict_resolution": "<string or null>",
    "bars_in_regime": "<int>",
    "in_cooldown": "<bool>",
    "cooldown_remaining": "<int>"
  },

  "indicators": {
    "ema_fast": "<float>",
    "ema_slow": "<float>",
    "ema_crossover": "<above | below>",
    "adx": "<float>",
    "plus_di": "<float>",
    "minus_di": "<float>",
    "lrs_slope_pct": "<float>",
    "roc": "<float>",
    "atr": "<float>",
    "atr_ratio": "<float>",
    "rv_annualized": "<float>",
    "bbw": "<float>",
    "bbw_percentile": "<float>",
    "hvp_percentile": "<float>",
    "ci": "<float>",
    "dcw": "<float>",
    "price_in_channel": "<float>",
    "volume_ratio": "<float>",
    "obv_slope": "<float>",
    "bas": "<float or null>",
    "amihud_ratio": "<float or null>"
  },

  "signal_scores": {
    "trend_group": "<float>",
    "volatility_group": "<float>",
    "structure_group": "<float>",
    "liquidity_group": "<float>"
  },

  "flags": {
    "signal_conflict": "<bool>",
    "conflict_streak_count": "<int>",
    "using_static_thresholds": "<bool>",
    "data_staleness_warning": "<bool>",
    "emergency_override": "<bool>",
    "circuit_breaker_active": "<bool>",
    "min_persistence_met": "<bool>",
    "externally_locked": "<bool>",
    "is_warmup": "<bool>",
    "halt_bar_skipped": "<bool>"
  },

  "conflicting_indicators": ["<list of indicator names that contradict winning regime>"],

  "thresholds_applied": {
    "adx_trend_threshold": "<float>",
    "adx_non_trend_threshold": "<float>",
    "ci_trend_threshold": "<float>",
    "ci_range_threshold": "<float>",
    "atr_ratio_volatile_threshold": "<float>",
    "hvp_volatile_threshold": "<float>",
    "hvp_crisis_threshold": "<float>",
    "volume_ratio_breakout_threshold": "<float>",
    "source": "<static | adaptive>"
  },

  "metadata": {
    "module_version": "<semver string>",
    "config_id": "<sha256 hash of config>",
    "compute_latency_us": "<int>"
  }
}
```

### 9.2 REGIME_TRANSITION

Emitted in addition to `REGIME_EVENT` when `transition.occurred = true`. Contains:
- Full pre-transition `RegimeEvent` snapshot under `"before"` key
- Full post-transition `RegimeEvent` snapshot under `"after"` key
- `"trigger_evidence"`: dict of indicator values and threshold comparisons that triggered the transition

### 9.3 REGIME_DIAGNOSTIC (Periodic)

Emitted every `diagnostic_emit_interval` cycles (default: 100). Contains:
- Current adaptive threshold values with their estimation metadata
- Rolling distribution statistics (mean, p25, p50, p75, p95) per indicator
- Conflict resolution history over the last `diagnostic_history_bars` cycles
- Compute performance statistics (mean, p50, p95, p99 latency in µs)
- `adaptive_sample_count` per indicator

### 9.4 REGIME_ALERT

Emitted on notable conditions:

| Condition | Severity | `alert_type` |
|-----------|----------|-------------|
| CRISIS entered | HIGH | `CRISIS_ONSET` |
| UNDEFINED persists > `undefined_alert_bars` | MEDIUM | `EXTENDED_UNDEFINED` |
| Compute latency p99 > `latency_alert_threshold_us` | LOW | `LATENCY_BREACH` |
| Circuit breaker activated | HIGH | `CIRCUIT_BREAKER_ACTIVE` |
| Conflict persists > `max_conflict_bars` | MEDIUM | `EXTENDED_CONFLICT` |

### 9.5 REGIME_ERROR

Emitted on input or computation errors:

| Condition | `error_type` |
|-----------|-------------|
| Missing mandatory OHLCV field | `MALFORMED_BAR` |
| Timestamp gap > max_bar_gap_seconds | `STALE_DATA` |
| Indicator numerical failure (overflow, div-by-zero) | `INDICATOR_FAILURE` |
| Configuration validation failure | `CONFIG_INVALID` |

`REGIME_ERROR` events do not interrupt the module's operation unless the error is a configuration error (which occurs at startup).

---

## 10. API Interface

### 10.1 Class: RegimeDetector

The primary public class. One instance per symbol-timeframe pair.

#### Constructor

```
RegimeDetector(
    config: RegimeConfig,
    market_data_provider: MarketDataProvider | None = None
) -> None
```

- Validates `config` on construction. Raises `ConfigValidationError` on failure.
- Pre-allocates all rolling buffers.
- Sets internal state to warmup mode.
- If `market_data_provider` is provided, immediately requests historical bars to fill the warmup period.

#### update

```
update(bar: OHLCV) -> RegimeEvent
```

**Contract:** Called once per completed bar. Returns a `RegimeEvent` on every call.

**Preconditions:**
- `bar.timestamp` must be strictly greater than the previous bar's timestamp.
- All mandatory OHLCV fields must be non-null, non-NaN, non-inf, and positive (except open=0 is rejected).

**Raises:**
- `MalformedBarError`: bar fails validation.
- `StaleDataError`: timestamp gap exceeds `max_bar_gap_seconds`.
- `InsufficientDataError`: called before `min_warmup_bars` received and no historical data provided. (Note: during warmup, `update()` processes the bar for indicator accumulation and returns a `RegimeEvent` with `primary = UNDEFINED` and `is_warmup = true`.)

**Guarantees:**
- Completes within `max_compute_latency_us`.
- No heap allocation after initialization.
- Thread-safe for read (multiple readers of `get_current_regime()` are safe). Writes are single-threaded per instance; do not call `update()` from multiple threads on the same instance.

#### update_batch

```
update_batch(bars: List[OHLCV]) -> List[RegimeEvent]
```

Equivalent to calling `update()` for each bar in sequence. Returns a list of events in the same order. Used for backtesting and warmup replay.

#### get_current_regime

```
get_current_regime() -> RegimeSnapshot
```

Returns the regime snapshot from the most recent `update()` call. Thread-safe (returns a copy). Raises `InsufficientDataError` if no bar has been processed yet.

#### get_regime_history

```
get_regime_history(n: int) -> List[RegimeSnapshot]
```

Returns the last `n` regime snapshots in reverse chronological order (index 0 = most recent). If fewer than `n` snapshots are available, returns all available. `n` must be <= `max_history_depth` (configurable, default: 500).

#### reset

```
reset(preserve_adaptive_history: bool = True) -> None
```

Resets internal state: clears current regime, resets bars_in_regime, resets all counters, restores warmup mode. If `preserve_adaptive_history = True`, the adaptive threshold engine's distribution estimates are retained (useful for instrument rolls). If `False`, all state is cleared to the post-initialization condition.

#### recalibrate_thresholds

```
recalibrate_thresholds() -> ThresholdUpdateReport
```

Triggers an immediate synchronous threshold recalibration pass. Uses read-copy-update to avoid blocking `update()`. Returns a `ThresholdUpdateReport` containing old vs. new threshold values, whether any were bounded, and the current adaptive sample count per indicator.

#### get_diagnostics

```
get_diagnostics() -> DiagnosticsReport
```

Returns the same content as `REGIME_DIAGNOSTIC` event as a typed object rather than a log event. Does not trigger emission.

#### validate_config

```
validate_config() -> ConfigValidationResult
```

Re-validates the current configuration and returns a typed result with a list of any validation errors. Can be called at any time without side effects.

#### lock_regime

```
lock_regime(regime: str, duration_bars: int) -> None
```

Externally forces the emitted regime label for `duration_bars` evaluation cycles. Internal signals continue to be computed and logged. Transitions are suppressed while locked. Sets `externally_locked = true` in emitted events. Intended for use during scheduled macro events (e.g., FOMC announcements). Calling `lock_regime` with `duration_bars = 0` clears any active lock.

### 10.2 Class: RegimeConfig

All configuration parameters in a single typed class (dataclass or Pydantic model). Validated at instantiation. Fields are described in §11. Configuration can be serialized to/from JSON or TOML. The `config_id` field is a SHA-256 hash of the serialized configuration, computed at construction.

### 10.3 Class: RegimePublisher

```
RegimePublisher
├── subscribe(handler: Callable[[RegimeEvent], None],
             event_types: List[str] = ["REGIME_EVENT"]) -> SubscriptionHandle
├── unsubscribe(handle: SubscriptionHandle) -> None
└── publish(event: RegimeEvent) -> None
```

`RegimeDetector` holds an optional `RegimePublisher` reference. When provided, events are dispatched synchronously within `update()` immediately after the event is constructed. Handlers must be non-blocking; any slow downstream processing must be offloaded to a queue within the handler. Handler exceptions are caught, logged as `REGIME_ERROR`, and do not propagate to the caller.

### 10.4 Data Types

```
OHLCV:
  symbol: str
  timestamp: datetime (UTC, timezone-aware)
  open: Decimal
  high: Decimal
  low: Decimal
  close: Decimal
  volume: Decimal
  bid: Decimal | None = None
  ask: Decimal | None = None

RegimeSnapshot:
  timestamp: datetime
  label: str
  primary: RegimePrimary    # Enum: TRENDING_UP, TRENDING_DOWN, RANGING, VOLATILE, BREAKOUT, CRISIS, UNDEFINED
  sub_state: RegimeSubState # Enum: EARLY, ESTABLISHED, LATE, STRESSED
  confidence: float
  bars_in_regime: int
  flags: RegimeFlags

RegimeEvent:
  snapshot: RegimeSnapshot
  probability_distribution: dict[str, float]
  indicator_values: dict[str, float | None]
  signal_scores: dict[str, float]
  transition: TransitionInfo
  thresholds_applied: dict[str, float]
  conflicting_indicators: list[str]
  metadata: EventMetadata

ThresholdUpdateReport:
  timestamp: datetime
  updates: list[ThresholdChange]  # {name, old_value, new_value, bounded, source}
  adaptive_sample_counts: dict[str, int]

DiagnosticsReport:
  timestamp: datetime
  thresholds: dict[str, float]
  indicator_distributions: dict[str, DistributionStats]
  conflict_history: list[ConflictRecord]
  latency_stats: LatencyStats
  adaptive_sample_counts: dict[str, int]

ConfigValidationResult:
  valid: bool
  errors: list[str]
  warnings: list[str]
```

---

## 11. Configuration Parameters

All parameters belong to `RegimeConfig`. Organized into six groups. The `config_id` is auto-computed and not user-settable.

### 11.1 Indicator Periods

| Parameter | Type | Default | Validation | Description |
|-----------|------|---------|------------|-------------|
| `ema_fast` | int | 12 | 1 ≤ x < ema_slow | Fast EMA period |
| `ema_slow` | int | 26 | x > ema_fast | Slow EMA period |
| `adx_period` | int | 14 | 2 ≤ x ≤ 100 | ADX and DI period |
| `lrs_period` | int | 20 | 5 ≤ x ≤ 200 | Linear regression slope period |
| `roc_period` | int | 10 | 1 ≤ x ≤ 100 | Rate of change period |
| `atr_period` | int | 14 | 2 ≤ x ≤ 100 | ATR period |
| `atr_long_ma_period` | int | 100 | x > atr_period | Long-run ATR MA period for ratio |
| `rv_window` | int | 21 | 5 ≤ x ≤ 252 | Realized volatility window |
| `bb_period` | int | 20 | 5 ≤ x ≤ 200 | Bollinger Band period |
| `bb_std` | float | 2.0 | 0.5 ≤ x ≤ 4.0 | Bollinger Band standard deviations |
| `hvp_lookback` | int | 252 | 60 ≤ x ≤ 1260 | HVP percentile lookback |
| `dc_period` | int | 20 | 5 ≤ x ≤ 200 | Donchian Channel period |
| `ci_period` | int | 14 | 5 ≤ x ≤ 100 | Choppiness Index period |
| `volume_ma_period` | int | 20 | 5 ≤ x ≤ 200 | Volume moving average period |
| `obv_slope_period` | int | 10 | 3 ≤ x ≤ 100 | OBV slope estimation period |
| `amihud_period` | int | 20 | 5 ≤ x ≤ 200 | Amihud ratio period |

### 11.2 Threshold Values (Static Defaults)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `adx_trending_threshold` | float | 25.0 | ADX ≥ this → trending |
| `adx_non_trending_threshold` | float | 20.0 | ADX < this → non-trending |
| `adx_strong_trend_threshold` | float | 30.0 | ADX ≥ this → strong trend (for signal score) |
| `ci_trending_threshold` | float | 38.2 | CI < this → trending |
| `ci_ranging_threshold` | float | 61.8 | CI > this → ranging |
| `atr_ratio_elevated_threshold` | float | 1.5 | ATR ratio ≥ this → elevated volatility |
| `atr_ratio_volatile_threshold` | float | 2.5 | ATR ratio ≥ this → VOLATILE state |
| `atr_ratio_crisis_threshold` | float | 3.0 | ATR ratio ≥ this → CRISIS (in combination) |
| `hvp_volatile_threshold` | float | 80.0 | HVP percentile ≥ this → VOLATILE |
| `hvp_crisis_threshold` | float | 95.0 | HVP percentile ≥ this → CRISIS (in combination) |
| `volume_ratio_breakout_threshold` | float | 2.0 | VR ≥ this → breakout volume confirmation |
| `bbw_compression_threshold` | float | 15.0 | BBW percentile ≤ this → compression (breakout precursor) |
| `crisis_spread_threshold` | float | None | BAS ≥ this → crisis (instrument-specific; required if BAS provided) |
| `crisis_rv_baseline_multiplier` | float | 3.0 | RV > this × baseline → crisis |

### 11.3 Transition and Hysteresis Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `entry_probability_threshold` | float | 0.60 | P(R) ≥ this required for entry |
| `confidence_entry_threshold` | float | 0.25 | C ≥ this required for entry |
| `exit_confidence_threshold` | float | 0.40 | C < this allows exit |
| `confidence_high_threshold` | float | 0.50 | C ≥ this → ESTABLISHED sub-state |
| `confidence_late_threshold` | float | 0.35 | C < this → LATE sub-state |
| `hysteresis_bars_entry` | int | 3 | Bars candidate must lead before entry |
| `hysteresis_bars_exit` | int | 2 | Bars confidence must be low before exit |
| `transition_cooldown_bars` | int | 5 | Mandatory hold bars after transition |
| `conflict_margin_threshold` | float | 0.15 | C < this → conflict flagged |
| `conflict_probability_floor` | float | 0.30 | P(R) ≥ this for two regimes → conflict |
| `conflict_confidence_penalty` | float | 0.70 | Confidence multiplier during conflict |
| `max_conflict_bars` | int | 5 | Bars before UNDEFINED escalation |
| `breakout_confirmation_bars` | int | 3 | Bars to confirm BREAKOUT → TRENDING |
| `breakout_failure_bars` | int | 5 | Bars for BREAKOUT to revert to RANGING |
| `max_crisis_overrides_per_hour` | int | 10 | Emergency overrides before circuit breaker |
| `crisis_storm_clear_bars` | int | 30 | Bars of calm before circuit breaker clears |

### 11.4 Persistence Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `min_persistence_trending` | int | 5 | Min bars in TRENDING states |
| `min_persistence_ranging` | int | 8 | Min bars in RANGING |
| `min_persistence_volatile` | int | 3 | Min bars in VOLATILE |
| `min_persistence_breakout` | int | 2 | Min bars in BREAKOUT |
| `min_persistence_crisis` | int | 10 | Min bars in CRISIS |
| `min_persistence_undefined` | int | 1 | Min bars in UNDEFINED |

### 11.5 Adaptive Threshold Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `adaptive_thresholds_enabled` | bool | true | Enable adaptive threshold engine |
| `adaptive_lookback` | int | 252 | Rolling distribution window (bars) |
| `min_adaptive_samples` | int | 60 | Minimum samples before adaptive activates |
| `threshold_smoothing_alpha` | float | 0.05 | EMA alpha for threshold updates |
| `threshold_lower_bound_multiplier` | float | 0.5 | Floor as multiple of static default |
| `threshold_upper_bound_multiplier` | float | 2.0 | Cap as multiple of static default |
| `auto_recalibrate_interval` | int | 50 | Bars between automatic recalibration |

### 11.6 Confidence and Scoring Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `t_softmax` | float | 1.0 | Softmax temperature |
| `group_weight_trend` | float | 0.35 | Trend group absolute weight |
| `group_weight_volatility` | float | 0.30 | Volatility group absolute weight |
| `group_weight_structure` | float | 0.20 | Structure group absolute weight |
| `group_weight_liquidity` | float | 0.15 | Liquidity group absolute weight |
| `persistence_confidence_bonus_enabled` | bool | false | Enable persistence confidence bonus |
| `persistence_bonus_weight` | float | 0.03 | Bonus weight coefficient |
| `persistence_bonus_saturation_bars` | int | 20 | Saturation point for bonus |
| `confidence_decay_rate` | float | 0.005 | Lambda for stale-data confidence decay |
| `confidence_min_floor` | float | 0.05 | C below this → UNDEFINED |

### 11.7 System Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `min_warmup_bars` | int | 272 | Bars before regime emitted as non-UNDEFINED |
| `max_bar_gap_seconds` | int | 300 | Max timestamp gap before StaleDataError |
| `max_compute_latency_us` | int | 1000 | Compute SLA in microseconds |
| `max_history_depth` | int | 500 | Maximum regime history to retain |
| `max_missing_indicator_fraction` | float | 0.40 | Max missing weighted mass before UNDEFINED |
| `diagnostic_emit_interval` | int | 100 | Cycles between REGIME_DIAGNOSTIC events |
| `undefined_alert_bars` | int | 10 | UNDEFINED bars before REGIME_ALERT |
| `latency_alert_threshold_us` | int | 500 | Latency p99 threshold for alert |
| `use_tick_normalization` | bool | false | Enable tick-count volume normalization |
| `gap_multiplier` | float | 2.0 | Gap bar detection ATR multiple |
| `discontinuity_threshold` | float | 0.20 | Price discontinuity warning threshold |
| `preserve_adaptive_history_on_roll` | bool | true | Retain adaptive history on reset |

### 11.8 Configuration Validation Rules

The following validation failures are hard errors (startup abort):

- `ema_fast >= ema_slow`
- Any period < 1
- Group weights do not sum to 1.0 (within 1e-6 tolerance)
- `crisis_spread_threshold` not set when BAS data is expected (determined by whether the MarketDataProvider reports BAS available)
- `confidence_entry_threshold < 0` or `> 1`
- `entry_probability_threshold < 0` or `> 1`
- `exit_confidence_threshold > entry_probability_threshold`
- `hysteresis_bars_entry < 1`
- `min_warmup_bars < max(all indicator minimum bar requirements)`

---

## 12. Unit Testing Strategy

### 12.1 Test Organization

Tests are organized into ten categories. Each category is implemented in a separate test module. All tests use synthetically generated OHLCV data; no real market data is included in the test suite.

### 12.2 Synthetic Data Generator

A `SyntheticMarketGenerator` class must be implemented as a test utility. It generates OHLCV series with the following controllable properties:

| Mode | Description | Key Parameters |
|------|-------------|----------------|
| `TRENDING` | Linear price drift with Gaussian noise | `drift_per_bar`, `noise_std`, `n_bars` |
| `RANGING` | Sinusoidal oscillation within a bounded channel | `amplitude`, `period`, `noise_std` |
| `VOLATILE` | GARCH(1,1) process with elevated variance | `omega`, `alpha`, `beta` |
| `CRISIS` | Extreme GARCH with fat tails | `crisis_multiplier` applied to GARCH |
| `BREAKOUT` | RANGING followed by step change with volume surge | `compression_bars`, `breakout_magnitude` |
| `MIXED` | Sequence of segments from the above modes | `segment_list: List[(mode, n_bars, params)]` |

All generator methods accept a `random_seed` parameter for reproducibility. Volume is generated proportional to absolute price change, with configurable noise.

### 12.3 Test Category Specifications

#### Category 1: Indicator Correctness

For each indicator, supply a synthetic OHLCV series with a known analytical solution. Assert values match within `1e-6` tolerance.

Required test cases:
- All-constant price series (EMA = constant, ATR = 0, ADX = 0, CI = 100, LRS slope = 0)
- Linear ramp (LRS slope = exact drift value, EMA trails by known lag)
- Sinusoidal series (RV = exact analytical volatility, CI approaches 61.8)
- Step function (ATR spike at step bar)
- Exactly `n_bars` of data at each indicator's minimum requirement (boundary condition)
- `n_bars - 1` (indicator should return NaN and be excluded from scoring)

#### Category 2: Signal Score Mapping

For each indicator, provide a grid of known input values. Assert:
- Signal score is a monotone function of indicator value within each linear segment
- Score is in [-1.0, 1.0] for all inputs
- Score has the correct sign for values clearly above/below neutral threshold
- Score is 0.0 at exactly `T_neutral` and ±1.0 at `T_strong` and below `T_low`

#### Category 3: Confidence Calculation

- Supply a signal score vector where all indicators agree unanimously on TRENDING_UP. Assert `C > 0.7`.
- Supply a vector split evenly between TRENDING_UP and RANGING. Assert `C < 0.2` and `signal_conflict = true`.
- Supply a vector where one regime has a clear but not overwhelming lead. Assert confidence in the expected range.
- Test margin-of-victory formula: construct known P distributions and assert exact C values.
- Test softmax normalization: assert all P(R_k) sum to 1.0 within 1e-10.
- Test confidence decay: from known C_0, assert C_t at t = {1, 10, 100, 1000} seconds matches analytic decay formula within 1e-6.

#### Category 4: Hysteresis and Transition Logic

- Simulate a regime where P(TRENDING) crosses entry threshold on bar N. Assert no transition before bar `N + hysteresis_bars_entry - 1`. Assert transition fires on bar `N + hysteresis_bars_entry`.
- Test exit hysteresis: simulate a transition, then immediately drop active regime confidence. Assert exit does not occur until `hysteresis_bars_exit` consecutive bars.
- Test cooldown: immediately after a transition, supply signals favouring a return to the old regime. Assert no transition for `transition_cooldown_bars` cycles.
- Test minimum persistence gate: supply exit-favourable signals before `min_persistence` is met. Assert exit is blocked.
- Test persistence gate release: supply the same signals after `min_persistence` is met. Assert exit is now permitted (given other conditions).

#### Category 5: Emergency Override

- Supply CRISIS emergency trigger conditions (HVP > 95th, ATRR > 3.0). Assert immediate transition to CRISIS regardless of: active cooldown, minimum persistence unsatisfied, active hysteresis count for another regime.
- Assert `transition_type = EMERGENCY` and `emergency_override = true` in emitted event.
- Assert `bars_in_regime` resets to 0 after emergency transition.
- Test circuit breaker: supply `max_crisis_overrides_per_hour + 1` emergency triggers within one hour. Assert `circuit_breaker_active = true` after the threshold is breached. Assert CRISIS.STRESSED is held. Assert subsequent emergency triggers are suppressed.

#### Category 6: Conflict Resolution

- Supply two regimes with nearly equal probability (both above `conflict_probability_floor`). Assert `signal_conflict = true`.
- Assert Rule 1 (CRISIS override): when CRISIS trigger fires during a conflict, assert CRISIS wins regardless.
- Assert Rule 2 (incumbent retention): when active regime's confidence is above exit threshold during a conflict, assert incumbent is retained with penalized confidence.
- Assert Rule 5 (escalation): maintain conflict for `max_conflict_bars` cycles. Assert transition to `UNDEFINED.STRESSED`.
- Assert `conflict_streak_count` increments correctly and resets on resolution.

#### Category 7: Adaptive Thresholds

- Supply fewer than `min_adaptive_samples` bars. Assert `using_static_thresholds = true` in all emitted events.
- Supply exactly `min_adaptive_samples` bars. Assert `using_static_thresholds` flips to `false` on the next recalibration.
- Supply a long series with known distributional properties. Assert that adaptive thresholds converge toward the expected percentile values within `adaptive_lookback` bars.
- Assert smoothing: supply a single extreme bar. Assert threshold does not jump by more than `threshold_smoothing_alpha * max_change`.
- Assert bounds: supply extreme distribution that would push threshold outside bounds. Assert threshold is clipped to `[static * lower_multiplier, static * upper_multiplier]`.

#### Category 8: Data Quality

- Missing mandatory field (e.g., `volume = None`). Assert `MalformedBarError` raised.
- `high < low` in a bar. Assert `MalformedBarError` raised.
- `close <= 0`. Assert `MalformedBarError` raised.
- `volume < 0`. Assert `MalformedBarError` raised.
- Timestamp gap > `max_bar_gap_seconds`. Assert `StaleDataError` raised.
- `volume = 0` (halt bar). Assert bar is skipped, `halt_bar_skipped = true` in emitted event, regime is held.
- NaN and inf in OHLCV fields. Assert `MalformedBarError` raised.
- First call before `min_warmup_bars` with no historical data provider. Assert `is_warmup = true` in emitted event and `primary = UNDEFINED`.

#### Category 9: Scenario Integration Tests

For each of the following synthetic scenarios, run the full module and assert that the majority of bars in the steady-state portion of each segment produce the expected primary regime label (target: ≥ 80% of bars):

| Scenario | Expected Sequence |
|----------|-------------------|
| 100 RANGING bars → 5 BREAKOUT bars → 100 TRENDING_UP bars | RANGING → BREAKOUT → TRENDING_UP |
| 100 TRENDING_DOWN bars → 50 VOLATILE bars → 100 RANGING bars | TRENDING_DOWN → VOLATILE → RANGING |
| 200 RANGING bars → 1 crisis bar (extreme vol + spread spike) | RANGING → CRISIS (emergency) |
| 50 RANGING bars → 5 breakout bars → price reverts within 5 bars | RANGING → BREAKOUT → RANGING |

For each scenario, assert:
- `REGIME_TRANSITION` event is emitted at the correct bar (within ±`hysteresis_bars_entry` tolerance)
- `bars_in_regime` resets to 0 on each transition
- No transitions occur during `transition_cooldown_bars` after each transition
- Sub-states progress correctly: EARLY → ESTABLISHED within the steady-state segment

#### Category 10: Performance and Memory Tests

- Run `update()` on a pre-generated sequence of 100,000 valid bars.
- Record wall-clock time per call.
- Assert: mean latency < `max_compute_latency_us / 2`, p99 latency < `max_compute_latency_us`.
- Profile memory usage at bar 0 (post-initialization) and bar 100,000. Assert the delta is zero (or within a small epsilon for Python runtime overhead). Specifically assert that the rolling buffers are not growing.
- Assert no Python `gc.collect()` is triggered during the hot path by checking GC statistics before and after the run.

### 12.4 Acceptance Criteria

The implementation is considered production-ready when all of the following pass:

| Criterion | Requirement |
|-----------|-------------|
| All unit test categories | 100% pass |
| Integration scenario tests | ≥ 80% correct classification in steady-state portions |
| Determinism test | Identical output for identical input in 1,000 independent runs |
| p99 update latency | < `max_compute_latency_us` on target hardware |
| Memory stability | Zero growth over 100,000 cycles |
| Config validation | All invalid configs rejected at startup; all valid configs accepted |
| Error handling | Zero unhandled exceptions on any valid or invalid OHLCV input sequence |

---

## 13. Performance Considerations

### 13.1 Compute Budget and Latency SLA

The `update()` method must complete within `max_compute_latency_us` (default: 1,000 µs). This SLA applies on the p99 latency observed on the target production hardware. The method is called synchronously in the strategy event loop; any blocking is unacceptable.

### 13.2 Memory Allocation

Pre-allocate at initialization:
- One circular buffer per indicator, of capacity `max(all_indicator_periods) + 20`.
- One probability array of length 7 (number of regimes), reused each cycle.
- One signal score array per group, reused each cycle.
- One `RegimeEvent` object, overwritten each cycle. Downstream handlers that need to retain the event must copy it.

No heap allocation is permitted within `update()` after initialization.

### 13.3 Arithmetic Precision

All arithmetic uses `float64` (Python `float` or NumPy `float64`). Decimal types are used only for raw OHLCV input and converted to `float64` at bar ingestion. Using `Decimal` throughout the computation path would violate the latency SLA.

### 13.4 Indicator Computation Optimization

All indicators are computed incrementally using O(1) update formulas:
- EMA: `EMA_t = alpha * close_t + (1 - alpha) * EMA_{t-1}`
- ATR: Wilder smoothed method (O(1))
- ADX: Wilder DI method (O(1))
- Bollinger Bands: maintain a running sum and sum-of-squares for O(1) mean and std
- Choppiness Index: maintain a rolling sum of ATR values and update the Donchian high/low incrementally
- HVP: maintain a sorted insertion buffer; use bisect for O(log n) insertion and O(1) percentile lookup

The LRS (Linear Regression Slope) is the most expensive indicator. Compute incrementally using the Welford/online least-squares update. The slope update is O(1) after precomputing `sum(x)`, `sum(x^2)`, `sum(xy)`, `sum(y)` where x is the bar index and y is the close price.

### 13.5 Parallelism

Each `RegimeDetector` instance is single-threaded (its `update()` must not be called concurrently). Parallel processing of multiple symbols uses a thread pool where each thread owns one or more detector instances. No state is shared between instances. The `recalibrate_thresholds()` method uses a read-copy-update pattern to avoid blocking the `update()` thread.

### 13.6 Language and Extension Notes

The module is specified for Python. Given the latency SLA, inner loops for indicator computation (especially the sorted HVP buffer and the LRS update) should be implemented using NumPy vectorized operations where batch updates are needed, or as Cython extensions if profiling reveals that Python overhead exceeds the latency budget. The interface contract does not change; only the internal implementation of the computation layer differs.

---

## 14. Edge Cases

### 14.1 Market Open Gap Bars

The first bar of a session may have an outsized overnight gap. Detection: `|open - prev_close| > gap_multiplier * ATR`. On gap bars: set `halt_bar_skipped = false` (the bar is processed), but exclude the gap component from ATR computation for that bar (use the true range as `max(high - low, |high - open|, |open - low|)` rather than the standard definition that incorporates `prev_close`). Set a `gap_bar = true` flag in the event for downstream awareness.

### 14.2 Zero-Volume and Halt Bars

Bars with `volume = 0` or `high == low == open == close` are treated as halt bars:
- Not processed into indicator buffers.
- Confidence decay is applied.
- `halt_bar_skipped = true` is set in the emitted event.
- The regime label is held from the last non-halt cycle.

### 14.3 Extreme Price Discontinuity

If `|close_t - close_{t-1}| / close_{t-1} > discontinuity_threshold` and volume is not elevated (volume ratio < 1.5), emit a `PriceDiscontinuityWarning` in the event metadata. This is likely a corporate action or data error. The bar is processed normally but the flag alerts operators to investigate the data feed.

### 14.4 Insufficient Indicator Coverage

If the fraction of missing indicator weight exceeds `max_missing_indicator_fraction`, the regime is set to UNDEFINED regardless of available signals. "Missing weight" means the sum of group weights (`W_g`) for groups where all indicators are unavailable (below their minimum bar requirement).

### 14.5 Regime Lock During Emergency Override

If `lock_regime()` is active and an emergency CRISIS trigger fires: the emergency override takes precedence. The CRISIS regime is emitted with `emergency_override = true` and `externally_locked = false`. The prior lock is cancelled. Operators are alerted via `REGIME_ALERT` with type `LOCK_OVERRIDDEN_BY_EMERGENCY`.

### 14.6 Instrument Roll (Continuous Futures)

When a continuous futures instrument rolls, call `reset(preserve_adaptive_history = True)`. The adaptive threshold engine's empirical distributions are retained under the assumption that the new front-month contract shares the same distributional properties. Set `preserve_adaptive_history_on_roll = false` if the roll is to a fundamentally different maturity or if the price level change is large enough to invalidate the prior distribution.

### 14.7 Sub-Minute and Tick Data

Enable `use_tick_normalization = true`. In this mode:
- Volume normalization uses tick count per bar rather than traded volume.
- ATR for high-frequency bars uses mid-price range (`(bid + ask) / 2`) rather than `high - low` to reduce microstructure noise.
- The minimum bar gap check (`max_bar_gap_seconds`) is not applied for bars with expected gaps under 60 seconds (set `max_bar_gap_seconds = 60` in this context).

### 14.8 First Bar After Reset

The first bar after `reset()` is treated as if it is the first bar ever received. `bars_in_regime = 0`, `regime = UNDEFINED`, `is_warmup = true` if the adaptive history was cleared, or `is_warmup = false` with the prior regime carried forward if adaptive history was preserved and `min_warmup_bars` is already satisfied. In the preserved-history case, the first post-reset bar emits the regime estimated from the prior distribution, with `transition.occurred = false` and a note in the metadata that the state was reset.

---

## 15. Operational Considerations

### 15.1 Startup Sequence

The following sequence must be executed in order at startup:

1. Load configuration from source (file, environment, or programmatic construction).
2. Call `validate_config()`. Abort if `valid = false`.
3. Initialize `RegimeDetector` (buffer allocation, adaptive engine initialization).
4. If a `MarketDataProvider` is available, request the last `min_warmup_bars` historical bars and call `update_batch()`. Events during this batch have `is_warmup = true`.
5. Emit `REGIME_INITIALIZED` event with the first non-warmup regime or `UNDEFINED` if warmup is incomplete.
6. Begin live bar processing via `update()`.

### 15.2 Graceful Degradation Modes

| Condition | Behaviour |
|-----------|-----------|
| Non-critical indicator failure | Exclude indicator, redistribute weight, set warning flag |
| Critical indicator failure (ADX or ATR) | Regime → UNDEFINED for that cycle, log REGIME_ERROR |
| All indicators failed | Regime → UNDEFINED, `signal_conflict = true` |
| Event publisher handler exception | Log error, continue processing |
| Recalibration thread exception | Log error, retain prior thresholds |

### 15.3 Checkpointing (Optional)

If the system supports warm restarts, the module's state can be serialized to a checkpoint:

**State to checkpoint:** All indicator buffer values, current regime label, `bars_in_regime`, all counters (hysteresis, conflict, cooldown, crisis override), adaptive threshold engine state (distribution buffers and current threshold values), `evaluation_cycle`.

**Restore:** Load checkpoint, validate against current configuration (reject if `config_id` differs), resume from `evaluation_cycle + 1`.

### 15.4 Metrics Endpoint

Expose the following Prometheus-compatible gauge and counter metrics:

| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `mrd_regime_label` | Gauge | symbol, timeframe | Current regime as integer (0–6) |
| `mrd_confidence` | Gauge | symbol, timeframe | Current confidence score |
| `mrd_bars_in_regime` | Gauge | symbol, timeframe | Bars in current regime |
| `mrd_compute_latency_us` | Summary | symbol, timeframe | Latency percentiles |
| `mrd_transition_total` | Counter | symbol, timeframe, type | Total transitions by type |
| `mrd_conflict_total` | Counter | symbol, timeframe | Total conflict events |
| `mrd_emergency_override_total` | Counter | symbol, timeframe | Total emergency overrides |
| `mrd_crisis_active` | Gauge | symbol, timeframe | 1 if CRISIS, 0 otherwise |
| `mrd_circuit_breaker_active` | Gauge | symbol, timeframe | 1 if circuit breaker active |
| `mrd_using_static_thresholds` | Gauge | symbol, timeframe | 1 if static, 0 if adaptive |
| `mrd_adx_threshold` | Gauge | symbol, timeframe | Current adaptive ADX threshold |

### 15.5 Versioning Policy

- **Module version** follows semantic versioning (MAJOR.MINOR.PATCH).
- Changes to the classification logic or confidence formula increment MAJOR.
- Changes to configuration parameters (additions, removals, renamed fields) increment MINOR.
- Bug fixes with no observable behaviour change increment PATCH.
- The `schema_version` in log events follows the same major version as the module.
- Downstream consumers should filter log events by `schema_version` to handle version coexistence.

---

## Appendix A: Design Decision Rationale Summary

| Decision | Rationale |
|----------|-----------|
| Seven primary regimes | Minimum set covering meaningfully distinct strategy responses. Fewer merges categories requiring different responses. More introduces transitions not warranted by distinct trading behaviours. |
| Mutual exclusivity of primary states | Clean downstream logic. Strategies should not handle overlapping membership. The full probability distribution is available for consumers needing ambiguity. |
| Stability over responsiveness | Asymmetric cost: wrong entry is typically worse than delayed entry. Emergency override handles the one case (CRISIS) where this trade-off reverses. |
| Adaptive thresholds | Static thresholds fail across changing market regimes and across instruments. Percentile-based adaptation maintains consistent signal frequency. Bounds prevent degenerate estimates. |
| Confidence as margin of victory | Raw softmax probability conflates certainty of one regime with ambiguity between two. Margin of victory is the relevant measure for downstream confidence in the classification. |
| Cooldown after transition | Prevents the module from oscillating immediately after a transition when indicator signals are noisy near the boundary. |
| Asymmetric hysteresis (entry harder than exit) | Conservative-transition principle. Burden of proof is on the candidate. Exiting is easier than entering because a declining regime is less dangerous than entering a wrong one. |
| No external dependencies in update() | Guarantees latency SLA. Module must be deployable in backtest, paper, and live environments identically. |
| Structured JSON logging | Enables machine-readable audit trail. Every classification decision is reconstructible from logs without rerunning the model. |
| Group-weighted scoring | Separates trend, volatility, structure, and liquidity contributions. Allows regime-specific weighting without indicator-level combinatorial explosion. |

---

*End of Document — Market Regime Detection Module Technical Specification v1.0*
*Prepared for implementation of `market_regime.py`*