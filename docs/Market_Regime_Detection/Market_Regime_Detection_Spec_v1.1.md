# Market Regime Detection Specification v1.1

---
Section 1: Objectives
What is the primary purpose of the Market Regime Detection module?
What trading decisions should depend on the detected market regime?
Should the module prioritize stability or responsiveness? Why?
What design principles should guide a production-grade market regime detector?

Section 2: Regime Definitions
What market regimes should be supported?
How should each regime be formally defined?
Should trend direction and volatility be represented as separate dimensions or combined into a single state?
Are the regimes mutually exclusive?
Can multiple regimes exist simultaneously?
How should unknown or ambiguous market conditions be represented?

Section 3: Indicators (Input Data)
What market data is required?
What minimum historical lookback is needed?
Which timeframes should be supported?
How should missing or incomplete market data be handled?
Should the detector support multiple symbols simultaneously?

Section 4: Feature Engineering (Indicator Selection and Rationale)
Which technical indicators should be used?
Why was each indicator selected?
Which indicators measure trend?
Which indicators measure volatility?
Which indicators measure market efficiency or choppiness?
Which indicators should be normalized?
Should percentile-based features be preferred over absolute values?
Should features be adaptive across different assets?

Section 5: Threshold Selection and Adaptive Calibration
Should thresholds be fixed or adaptive?
How should trend thresholds be determined?
How should volatility thresholds be determined?
Should thresholds be based on historical percentiles?
Which thresholds should be configurable?
What default threshold values are recommended?

Section 6: State Transition Logic
Under what conditions should a regime change occur?
Should hysteresis be implemented? If so, how?
How many consecutive confirmations are required before switching regimes?
Should a minimum regime duration be enforced?
How should rapid oscillation between regimes be prevented?
How should conflicting indicator signals affect transitions?

Section 7: Confidence Calculation
How should confidence be defined?
Which factors contribute to confidence?
How should indicator agreement influence confidence?
Should confidence increase with regime persistence?
How should uncertainty be represented?
Should confidence be normalized to a range of 0–1?

Section 8: Output Specification
What fields should the MarketRegime object contain?
Which fields are mandatory?
Should the module include diagnostic information explaining the detected regime?
Should raw feature values be included in the output?

Section 9: Logging and Observability
What events should be logged?
What information should every regime transition log contain?
Should logs use structured JSON?
Which metrics should be exposed for monitoring?
What information is useful for debugging incorrect classifications?

Section 10: Module Architecture
What should the public interface of market_regime.py look like?
Should the detector be stateless or stateful?
Which configuration parameters should be externally configurable?
Should the module depend on any external services?
How should the detector integrate with the rest of the trading system?

Section 11: Testing Strategy
What unit tests are required?
Which edge cases should be tested?
How should historical data be used for validation?
What acceptance criteria define a correct implementation?
What measurable performance, reliability, and maintainability requirements should the implementation satisfy before it is considered production-ready?

# 1. Objectives

...
What is the primary purpose of the Market Regime Detection module?
What trading decisions should depend on the detected market regime?
Should the module prioritize stability or responsiveness? Why?
What design principles should guide a production-grade market regime detector?


Here is a thorough answer to each of the four questions.

Q1 — What is the primary purpose of the Market Regime Detection module?
The module's job is to classify the current market environment into a discrete (or probabilistic) state so that every downstream component of the trading system can adapt its behavior accordingly. Without it, a strategy built on one set of distributional assumptions operates blindly through periods where those assumptions are violated — often catastrophically.
A regime is not just "volatility is high." It is a characterization of the joint distribution of returns, autocorrelation structure, cross-asset correlation, and liquidity conditions that are likely to persist over a forward horizon meaningful to the strategy. Concretely, the module must answer: Is the market trending directionally? Is it oscillating in a range? Is it in stress or dislocation? That answer then becomes a routing key.
The secondary purpose is to provide a confidence signal, not just a hard classification. Downstream consumers need to know whether the module is 90% confident in a risk-off call versus 55% uncertain between trending and mean-reverting. That confidence governs how aggressively positions and strategies adapt.

Q2 — What trading decisions should depend on the detected market regime?
Every risk-sensitive decision in the system should at minimum be aware of the current regime, and several should change materially:
Signal routing is the most direct dependency. A momentum factor performs well in trending regimes and destroys value in mean-reverting ones. A pairs-trading or stat-arb signal behaves oppositely. The regime label determines which alpha signals are live, scaled, or suppressed entirely.
Position sizing changes because the regime shifts the return distribution. In a trending regime with low realized volatility, a volatility-targeted position is relatively large. In a high-volatility stress regime, the same target shrinks the position automatically, but you may also want a regime-specific overlay that cuts size further or faster than the volatility estimate alone would suggest.
Execution style adapts because market microstructure changes with regime. In trending, aggressive fills may be justified to avoid adverse selection. In mean-reverting, passive limit orders at better prices make sense. In stress regimes, liquidity vanishes and slippage assumptions break down — execution should become more conservative and spread-aware.
Risk limits and stop logic need regime-conditioned parameters. A fixed 2% stop that is appropriate in normal conditions may trigger a whipsaw exit in a high-volatility regime while still being too loose in a tail event. Regime-aware multipliers on drawdown ceilings and VaR limits allow risk controls to breathe correctly.
Universe and instrument selection — certain assets are structurally unsuitable in certain regimes. Flight-to-safety regimes favor sovereign bonds and volatility products; trending regimes may reward high-beta equities. The regime label can gate which instruments are eligible each day.
Rebalancing frequency shifts. In quiet, range-bound conditions, a daily rebalance is efficient. In rapidly evolving stress, the regime module may trigger intraday re-evaluation of the entire book.

Q3 — Should the module prioritize stability or responsiveness? Why?
In production, stability must be the default bias, but responsiveness must be configurable per regime tier. This is not a philosophical position — it is an economic one.
The case for stability rests on transaction costs and whipsaw risk. If the module flips from trending to mean-reverting and back within a few bars, every strategy attached to it pays the bid-ask spread and market impact of repositioning twice. On liquid markets, that cost is real. On illiquid markets, it can eliminate a significant portion of annual alpha. Furthermore, spurious regime transitions caused by noise in the detection signal are asymmetrically costly: the module generates turnover with no corresponding information advantage.
The case for responsiveness exists specifically for tail risk and stress regimes. A module that is slow to classify a correlated drawdown event as a risk-off regime can leave the book over-exposed during the most dangerous periods. A missed transition into a stress state is an asymmetric loss event.
The production solution is therefore a two-speed architecture:

For transitions into or out of normal-market regimes (trending ↔ mean-reverting), require strong evidence over a confirmation window (e.g., several bars of persistent signal) before committing. Use a hysteresis band around the decision boundary so the system does not toggle on marginal signals.
For transitions into high-volatility, risk-off, or dislocation regimes, use a more sensitive, faster-confirming trigger. The cost of a false positive (cutting risk when you didn't need to) is much lower than the cost of a false negative (staying in when you should have cut).


Q4 — What design principles should guide a production-grade market regime detector?
Probabilistic output over hard labels. The module should emit a posterior probability distribution over regimes — P(trending) = 0.71, P(mean-reverting) = 0.22, P(stress) = 0.07 — not a single label. Hard labels create discrete jumps that propagate into position discontinuities. Probabilities allow downstream systems to blend smoothly and express uncertainty in their own weighting logic.
Multi-signal ensemble. No single feature — volatility, trend strength, autocorrelation, cross-asset correlation, breadth — is reliably diagnostic across all market environments. The module should fuse heterogeneous features from multiple signal families (statistical, structural, macro, microstructure) using an ensemble method. This reduces the chance that a single failed feature drives a false classification.
Regime hysteresis. A minimum dwell time or a Bayesian prior that favors the current state prevents rapid toggling. Once in a regime, the posterior should require meaningful evidence to escape it. This is not stubbornness — it is the correct Bayesian update for a world where regimes are genuinely persistent.
Stationarity and lookback awareness. Detection features computed over rolling windows are implicitly sensitive to the choice of lookback. A short window is responsive but noisy; a long window is stable but slow. The module should use explicitly calibrated lookbacks for each feature and be aware that the features themselves may be non-stationary over very long windows (regimes a decade ago may differ structurally from today's).
Observable confidence and auditability. Every regime call must be explainable after the fact. The module should log the feature values and their contributions to the classification at the time of each decision. This enables post-trade attribution, regime-specific P&L decomposition, and model auditing — all essential for a production system subject to risk management review.
Graceful degradation under data failure. In live trading, data feeds go stale, exchanges halt, and features become uncomputable. The module needs a fallback policy: when too many inputs are missing, it should either hold the last known regime (with a staleness flag) or step down to a default conservative regime rather than crashing or emitting a spurious call.

---

# 2. Regime Definitions

...
## Q1 — What market regimes should be supported?

A production-grade module should support a minimum viable taxonomy of six named regimes, organized in two tiers by how they affect strategy behavior:

The first tier covers the three normal-market regimes that govern everyday alpha routing: a bull trending regime (sustained upward momentum with low-to-moderate volatility), a bear trending regime (sustained downward momentum, often with elevated volatility), and a mean-reverting or range-bound regime (no directional bias, oscillating within a band, autocorrelation is negative at short lags).

The second tier covers three stress or structural regimes: a high-volatility expansion regime (volatility spike without a clear directional trend — common during event risk or macro shocks), a risk-off / flight-to-safety regime (correlated drawdown across risk assets, spread widening, vol compression in safe havens), and a low-volatility compression regime (suppressed realized volatility, often preceding a breakout, where options are cheap and carry trades dominate).

Beyond these six, an `unknown` or `unclassified` state is mandatory — covered in Q6.---

## Q2 — How should each regime be formally defined?

Formal definitions need to be measurable, parameterized, and asset-class-aware. The goal is not a verbal description but a set of testable conditions on observable features. Here is the formal specification for each:

**Bull trend**: The N-day exponential moving average slope is significantly positive (e.g., > +k σ of the slope distribution), the Hurst exponent H > 0.55 over a rolling window, and realized volatility is below its 67th percentile (Low/Normal boundary per Section 5.4). Momentum factor (12-1 month return) is in the top quartile of its rolling distribution.

**Bear trend**: Same criteria as bull trend but slope significantly negative, and realized volatility is elevated (above its 67th percentile, per the Elevated band in Section 5.4). Correlation of returns across assets may be rising. Put/call ratio and credit spreads may be included as corroborating signals.

**Mean-reverting**: The first-order return autocorrelation is significantly negative (ρ₁ < −threshold), the Hurst exponent H < 0.45, and the N-day price range is contracting relative to its rolling median. ADX (average directional index) is low (typically < 20–25).

**High-volatility expansion**: Realized volatility is above its 85th percentile *and* the change in volatility (vol-of-vol) is high, but the trend signal is weak or conflicted. VIX term structure may be inverted. No persistent autocorrelation in either direction.

**Risk-off / flight-to-safety**: Cross-asset correlation rises sharply (equities and credit both falling), spread widening in IG and HY credit is detected, gold and short-duration bonds are outperforming. May overlap with bear trend or high-vol expansion — the distinguishing feature is *correlation structure* across assets, not just direction in one market.

**Low-volatility compression**: Realized volatility is below its 20th percentile, the Bollinger Band width is at multi-month lows, and implied volatility (where available) is below realized — options pricing a quiet future. Historical analog: pre-breakout coil periods.

**Unknown**: None of the above regimes satisfies its minimum posterior probability threshold (e.g., max regime probability < 0.40), or key features are missing or stale.

---

## Q3 — Should trend direction and volatility be separate dimensions or combined into a single state?

They should be modeled as separate dimensions and combined deliberately, not collapsed into a single label from the start.

The reason is that the two dimensions have different dynamics and different downstream dependencies. Trend direction is captured by momentum signals and autocorrelation structure, and it governs which alpha factors are active. Volatility level governs position sizing, execution behavior, and risk limits. A strategy may need to *change its alpha signal* based on direction while *keeping position sizes the same* — or vice versa. If you fuse both into a single state label upfront, you can't decompose the effect.

The practical architecture is a **compositional two-axis space**: one axis is direction (bull, neutral/mean-reverting, bear) and the other is volatility level (low, normal, high). The regime taxonomy above is essentially a structured subset of the cells in this 3×3 grid — the cells that have coherent and distinct strategy implications. The `risk-off` regime occupies the (bear, high-vol) cell with an additional cross-asset correlation condition. `Low-vol compression` occupies the (neutral, low-vol) cell.

The module should internally track both dimensions as separate latent variables and expose them both — so that downstream consumers can condition on direction alone, volatility alone, or the joint state.

This two-axis structure becomes the reference for the next diagram.The six named regimes populate the cells with the clearest strategy implications. Three cells (dashed borders) represent valid but lower-priority states worth monitoring without dedicated strategy switching logic at first.

---

## Q4 — Are the regimes mutually exclusive?

At the level of the *final hard label*, yes — by convention, a system that outputs a single regime at time t must pick one. But this is an architectural simplification, not a claim about market reality.

The underlying regime *probabilities* are not mutually exclusive, and should not be forced to be zero-or-one. A market can be simultaneously 60% consistent with a bear trend and 40% consistent with risk-off. Forcing a hard classification loses that information. The correct answer is: emit a full probability vector, let the hard label be the argmax (when needed), and let downstream consumers weight their decisions by the full distribution.

The *dimensions* are also not mutually exclusive. Volatility level and trend direction are orthogonal axes — a bear trend can have low, normal, or high volatility. The six named regimes are six specific (direction × volatility) cells, but the module should track both axes independently.

---

## Q5 — Can multiple regimes exist simultaneously?

In a single-instrument, single-timeframe context, the answer is no at the level of an integrated state: there is one current market environment. But across three practical dimensions, "simultaneous regimes" is a meaningful and important concept:

**Across timeframes.** A market can be in a long-term bull trend (weekly regime) while experiencing a short-term high-volatility regime (intraday or daily). The module should support multi-horizon regime tracking, with each horizon feeding different strategy components — a trend-following strategy might care about the monthly regime while a vol-targeting overlay cares about the daily.

**Across instruments or asset classes.** Equities can be in a risk-off regime while credit is in high-vol expansion and rates are in a bull trend. If the module is designed to serve a multi-asset book, it must produce per-asset or per-asset-class regime readings in addition to any aggregate cross-asset regime.

**Across regime dimensions.** As noted above, the direction dimension and the volatility dimension are always simultaneously defined. A position sizing component may need the volatility dimension only; a signal routing component needs the direction dimension. Both are "active" at once.

The design implication is that the module's output contract should be a structured object — not a single string — carrying the full probability vector, the inferred direction state, the inferred volatility state, the confidence level, and per-horizon signals where configured.

---

## Q6 — How should unknown or ambiguous market conditions be represented?

The `unknown` state must be a first-class output, not an afterthought or an error code. Several situations produce it:

**Low maximum posterior probability.** If the highest probability across all regimes is below a calibrated threshold (e.g., 0.40), the module is too uncertain to commit. It should output `unknown` with the full raw probability vector attached, so the caller can see *which* regimes the uncertainty is spread across.

**Transitional periods.** When the regime is actively switching, probabilities are in flux and the classification is unstable. A separate `transitioning` flag (or a dedicated `transitional` regime state) can be emitted alongside the best-guess label, signaling to downstream systems that hysteresis is active and confidence is low.

**Feature unavailability.** When input features are stale, missing, or anomalous (e.g., a market halt, a data feed gap), the module cannot compute a reliable posterior. It should emit `unknown` with a `data_quality` annotation, not attempt to extrapolate from incomplete inputs.

**Structurally novel conditions.** If all features fall outside their historical training distribution (e.g., negative oil prices in April 2020), the model is operating out-of-sample. A distributional novelty detector can flag this and force the output to `unknown` until the situation stabilizes.

The `unknown` state should trigger a specific default behavior in all downstream consumers: fall back to the most conservative parameter set for each decision (smallest position sizes, most passive execution, tightest risk limits, no alpha signal routing). Unknown is not neutral — it is an asymmetric risk signal.

# 3. Indicators

...
Q1 — What market data is required?
The input data stack has four distinct layers, each serving a different aspect of regime characterization.
  ::view-transition-group(*),
  ::view-transition-old(*),
  ::view-transition-new(*) {
    animation-duration: 0.25s;
    animation-timing-function: cubic-bezier(0.19, 1, 0.22, 1);
  }
VvisualizeVvisualize show_widgetLayer 1 — Raw price and volume is the non-negotiable foundation. OHLCV data is the minimum; adjusted close prices (split and dividend adjusted) are required for any computation involving historical comparison. Bid/ask spread and order book depth are required at the microstructure layer for execution-sensitive consumers. Open interest in futures and options markets provides a sentiment and positioning proxy.
Layer 2 — Derived statistical features are computed on the fly from Layer 1. These are the features that most directly signal regime: realized volatility (rolling standard deviation of log-returns at multiple windows), the Hurst exponent (distinguishing trending H > 0.5 from mean-reverting H < 0.5), lag-1 return autocorrelation, trend strength proxies (ADX, EMA slope z-scored against its own distribution), volume regime (current volume relative to its rolling average), and rolling drawdown depth.
Layer 3 — Cross-asset signals lift the module beyond single-instrument myopia. A risk-off regime cannot be reliably detected from one equity series alone — you need equity-bond correlation rising, credit spreads widening, and safe-haven demand confirming simultaneously. This layer requires: cross-asset rolling correlation matrices (equity, fixed income, credit, FX), IG and HY option-adjusted spreads, and the implied volatility surface — particularly VIX level and the slope of the VIX term structure (contango = calm, backwardation = fear).
Layer 4 — Macro and microstructure provides the slowest-moving but most persistent signals. Macro indicators (PMI, yield curve slope, credit conditions surveys) update monthly or weekly but carry strong regime-persistence information. Market breadth (advance-decline line, percentage of stocks above their 200-day MA, new highs vs. new lows) provides a distributional view that single-instrument price data cannot. Microstructure data (bid-ask spread levels, price impact coefficients, portfolio turnover rates) signals liquidity stress early — often before price dislocations are visible.

Q2 — What minimum historical lookback is needed?
Lookback requirements vary by feature family and should be specified explicitly for each. The architecture must maintain a ring buffer deep enough to satisfy the longest lookback without recomputation.
FeatureMinimum lookbackRationaleRealized volatility (short)21 daysOne trading month — fast vol signalRealized volatility (slow)63 daysOne quarter — regime-level vol baselineHurst exponent100–252 barsRequires sufficient observations for reliable R/S analysisLag-1 autocorrelation63 barsShort window is noisy; needs ~60+ observationsEMA slope z-score252 barsNeed a year to z-score the slope meaningfullyADX14–28 barsStandard ADX period; can extend to 50 for smoother signalCross-asset correlation63 barsRolling 3-month correlation matrixCredit spread regime252 barsSpreads are slow-moving; need a year for percentile contextVIX term structure30 daysShort lookback; VIX structure changes rapidlyMacro indicators12–24 monthsEconomic cycles require multi-year contextDrawdown depth252 barsNeed full-year high-water mark for drawdown percentile
The practical implication is that the module requires a minimum of 252 trading days (~1 year) of clean history before any regime output can be trusted. For robust percentile-based features, 3–5 years is preferable, with a regime-conditional recalibration that excludes the most structurally different historical periods. On initial deployment, the module should output unknown until the warm-up lookback is satisfied.

Q3 — Which timeframes should be supported?
The module should support three timeframe tiers, each with a different purpose and update cadence.
  ::view-transition-group(*),
  ::view-transition-old(*),
  ::view-transition-new(*) {
    animation-duration: 0.25s;
    animation-timing-function: cubic-bezier(0.19, 1, 0.22, 1);
  }
VvisualizeVvisualize show_widgetThe daily tier is the primary regime. It is the timeframe at which most features are most reliable and at which strategy logic should consume the regime label. The intraday tier informs the execution layer and intraday risk management, not the primary regime. The weekly/monthly tier provides a slow-moving structural bias that conditions the daily tier — think of it as a prior over which daily regime is plausible. A system in a monthly bear structural regime should require stronger evidence to classify a daily regime as bull.
The multi-tier architecture avoids two common failure modes: a module that fires on intraday noise and causes excessive strategy churn; and one that updates so slowly it misses the first days of a stress event.

Q4 — How should missing or incomplete market data be handled?
Missing data is not a rare edge case in production — it is a daily operational reality. The module must have an explicit, documented policy for every failure mode.
Stale prices (last-value carry-forward) are the most common form of missing data: a tick does not arrive for N bars. The module should carry the last known price forward for a configurable maximum number of bars (e.g., 3 bars intraday, 2 days on the daily tier) before marking the feature as stale. Any feature computed from a stale input must be flagged with a staleness indicator and given reduced weight in the ensemble. Beyond the maximum staleness threshold, the instrument is moved to the unknown regime with a data_stale annotation.
Sparse or irregular data (e.g., thinly traded instruments, pre-market bars, early close days) should be detected by comparing the number of valid observations within a rolling window to a minimum observation count. If fewer than 80% of expected observations are present in the lookback window, the feature is marked unreliable (default; configurable via min_observation_completeness_pct in Section 10.3).
Feature computation failure (e.g., Hurst exponent fails to converge, correlation matrix is singular) must be caught at the feature layer, not propagated as NaN into the model. Each feature should have a fallback value or a not_computed sentinel. The ensemble should degrade gracefully when a subset of features is unavailable, re-weighting the remaining features rather than crashing.
Cross-asset data gaps (e.g., credit spread data has a weekend or holiday gap) require an asset-class-specific staleness tolerance. Credit spreads can be safely carried 3–5 business days. VIX data should not be carried more than 1 day without flagging. Macro data gaps of up to 30 days are acceptable given the feature's slow update cadence.
Data anomalies and outliers — prices that are statistically implausible (e.g., a log-return more than 8–10 standard deviations from the rolling mean) should be flagged as suspect rather than used. The module should have a configurable spike filter that replaces outlier observations with the previous value and logs the event for human review.
The overriding principle: the module must never silently produce a confident regime label when the input data is materially compromised. Uncertainty in inputs must propagate forward as uncertainty in the output.

Q5 — Should the detector support multiple symbols simultaneously?
Yes, and this is architecturally non-negotiable for a production system serving a multi-instrument book. But "support" means three distinct capabilities that must each be designed explicitly:

> **OPEN ISSUE (pending scope decision):** This requirement assumes the module serves a multi-instrument book. An earlier draft of this spec contained a conflicting note scoping an initial release to a single instrument (XAUUSD) only. That note has been removed as obsolete, but the underlying scope question — whether v1.1/v2.3 targets single-symbol or multi-symbol operation — has not been formally decided. The multi-symbol requirements below remain the specified design until a scope decision is made and documented; this note exists so that decision is made explicitly rather than by default.
Per-symbol regime tracking. Each instrument or asset should have its own regime state, computed from its own price history and features. This is a straightforward parallelization of the single-symbol case. The output is a symbol-keyed dictionary of regime probability vectors.
Cross-symbol aggregate regime. For a multi-asset portfolio, a single aggregate regime label is useful for top-level risk decisions (cut all book-level leverage, shift execution style globally). This aggregate regime is not computed by averaging per-symbol regime labels — that loses structural information. It is computed from a separate feature set that explicitly represents cross-asset relationships: the pairwise correlation matrix across symbols, dispersion of per-symbol returns, aggregate breadth. The aggregate regime often diverges from individual symbol regimes, and both are needed.
Symbol-to-symbol influence. Some instruments are leading indicators for others. The VIX leads realized equity volatility. The HY spread is a leading indicator for equity risk-off. The 2s10s yield curve slope leads recession regimes with a long lag. The multi-symbol architecture should support a configurable influence graph where a designated set of "sentinel" instruments can trigger regime flags for dependent instruments even before those instruments' own price series reflect the change.
The implementation implication is that the module's core compute unit is a symbol registry with a shared feature computation graph, not N independent single-symbol instances. Shared features (cross-asset correlations, breadth indices) are computed once at the graph level and referenced by all symbol-level computations. This avoids redundant computation and ensures consistency — the cross-asset correlation seen by the equity regime module is identical to the one seen by the fixed income module.


# 4. Thresholds

...
Q1 & Q2 — Which technical indicators should be used, and why was each selected?
The indicator set should be chosen on three criteria: each indicator must measure something structurally distinct from the others, it must be computable from the input data stack defined in Section 3, and it must have a theoretically grounded relationship to regime state rather than being a heuristic retrofit.
  ::view-transition-group(*),
  ::view-transition-old(*),
  ::view-transition-new(*) {
    animation-duration: 0.25s;
    animation-timing-function: cubic-bezier(0.19, 1, 0.22, 1);
  }
VvisualizeVvisualize show_widgetThe selection rationale for each family:
Trend indicators are chosen because they each measure a different aspect of directional persistence. EMA slope gives direction and speed. ADX gives strength without direction — a rising ADX with falling price is as informative as one with rising price. The EMA crossover ratio gives a normalized view of how far apart fast and slow trends have diverged. TSMOM captures the 12-month-minus-1-month momentum that is the backbone of the academic cross-sectional and time-series literature. Linear regression slope with R² gives both the rate of directional change and how cleanly prices fit that direction. Breadth thrust confirms trend at the index level via participation — a rally with 80% of stocks above their 200d MA is structurally different from one with 40%.
Volatility indicators span the realized/implied and point/path dimensions. Multi-window realized vol (5d, 21d, 63d) captures the term structure of realized volatility — a short-window spike that is not yet visible in 63d vol is an early warning. Parkinson's estimator uses the high-low range, which captures intraday extremes that close-to-close returns miss. Vol-of-vol (the standard deviation of realized volatility) distinguishes a persistently high-vol environment from an episodic spike. BB width is a compressed, intuitive version of realized vol. VIX term structure slope is the market's forward-looking risk signal and distinguishes normal backwardation (fear) from contango (calm). The IV minus RV spread (variance risk premium) signals whether the market is over- or under-pricing future volatility.
Efficiency and choppiness indicators form the most theoretically grounded family for distinguishing trending from mean-reverting regimes. The Hurst exponent directly tests the long-memory property of the price series. The Choppiness Index is a normalized ratio of the sum of N individual ATRs to the ATR of the full N-period range — bounded between 0 and 100, with high values (>61.8) indicating choppiness and low values (<38.2) indicating trend. Return autocorrelation at lag 1 directly tests whether today's return predicts tomorrow's. Kaufman's Efficiency Ratio measures how much of the total path traveled during a period was used in net directional movement — a ratio near 1 means nearly pure trend, near 0 means random walk or mean-reversion.
Cross-asset and macro indicators are the features that no single-instrument price series can provide. Change in the cross-asset correlation matrix is the most reliable early signal of risk-off — correlations spike toward 1 before prices fully adjust. Credit spread OAS percentile is the credit market's view on systemic risk. The yield curve slope carries cycle regime information at a multi-month horizon. Put/call ratio captures hedging demand and positioning extremes.

Q3 — Which indicators measure trend?
IndicatorWhat it measuresTrending signalMean-reverting signalEMA slope (z-scored)Rate of price change per unit timeStrongly positive or negative z-scoreNear-zero z-scoreADX (14-period)Trend strength regardless of directionADX > 25, risingADX < 20, fallingEMA crossover ratioFast-slow MA divergenceLarge positive or negative spreadSpread near zero, oscillatingTSMOM (12-1)Long-horizon return continuationTop or bottom quartile of rolling distributionMiddle two quartilesLR slope with R²Linear fit quality over N barsHigh R², non-zero slopeLow R², slope near zeroBreadth thrustParticipation across index membersHigh breadth (>70%) in direction of trendLow breadth, divergent
The critical design point: ADX is directionally agnostic. It tells you how much of a trend exists without telling you which way it is going. The directional signal must come from EMA slope, TSMOM, or the crossover ratio. This separation matters — a system that uses only ADX will misclassify a violent bear trend as equivalent to a calm bull trend in terms of trend strength, even though their strategy implications are opposite.

Q4 — Which indicators measure volatility?
IndicatorWindowWhat it capturesRealized vol (close-to-close)5d, 21d, 63dPoint-in-time volatility at multiple horizonsParkinson estimator21dIntraday range volatility; more efficient than close-to-closeVol-of-vol21d of daily realized volStability of the volatility regime itselfBollinger Band width20d, 2σCompressed band = compression regime; wide band = expansionVIX level (percentile)Spot vs. 252d historyForward-looking fear; absolute level percentileVIX term slope (M1 minus M3)SpotBackwardation = acute stress; contango = complacencyIV minus RV spreadRollingVariance risk premium; high = options expensive relative to realized
The multi-window realized vol is especially important. Rather than using a single window, the module should compute the ratio of short-window to long-window realized vol — a ratio significantly above 1 (e.g., 5d vol / 63d vol > 1.5) is a reliable early-warning signal of a volatility regime change that has not yet been reflected in the slow-moving estimate.

Q5 — Which indicators measure market efficiency or choppiness?
These are the most important and most underused family in commercial implementations. They directly address whether prices are trending (auto-correlated, persistent) or mean-reverting (anti-correlated, antipersistent), which is the foundational question of regime detection.
  ::view-transition-group(*),
  ::view-transition-old(*),
  ::view-transition-new(*) {
    animation-duration: 0.25s;
    animation-timing-function: cubic-bezier(0.19, 1, 0.22, 1);
  }
VvisualizeVvisualize show_widgetThe Hurst exponent H is the theoretical anchor. It measures the long-memory property of the time series — H > 0.5 means past returns positively predict future returns (persistence, trending); H < 0.5 means past returns negatively predict future returns (antipersistence, mean-reversion); H = 0.5 is the random walk null hypothesis. It is estimated via rescaled range (R/S) analysis or via a detrended fluctuation analysis (DFA), with DFA preferred in practice for its better finite-sample behavior.
The Choppiness Index is a more practically robust and computationally cheap proxy. It is bounded between 0 and 100 by construction, making it directly interpretable without distributional assumptions. Thresholds at the Fibonacci levels 38.2 and 61.8 are conventional but should be calibrated per asset class.
Lag-1 autocorrelation is the simplest and most direct test. Its weakness is sensitivity to the rolling window length — a 21-day rolling ρ₁ is noisy; 63 days is more stable. Combining multiple window estimates is preferable.
Kaufman's Efficiency Ratio is defined as |net_change_over_N_bars| / sum(|individual_bar_changes|). It is directionally agnostic and naturally bounded between 0 (maximal choppiness) and 1 (perfect directional efficiency). An ER consistently above 0.65–0.70 is a strong trending signal.
These four indicators are partially redundant by design — that redundancy is a feature, not a bug. When all four agree on trending, the signal is far more reliable than any single one.

Q6 — Which indicators should be normalized?
Every indicator used as a model feature should be normalized. The question is how, because different indicators have different distributional properties that call for different normalization strategies.
Z-score normalization is appropriate for indicators with approximately Gaussian distributions and where the absolute level is informative only relative to recent history: EMA slope, realized volatility, TSMOM, yield curve slope, credit spread OAS, and the IV-RV spread. Z-score each over a rolling window of 252 bars.
Percentile ranking is appropriate for indicators that are heavy-tailed, skewed, or where the cross-time distribution is non-stationary: VIX level, BB width, ADX, vol-of-vol, and drawdown depth. A 252-bar rolling percentile rank maps the indicator to [0, 1] and is robust to distributional shifts.
No normalization needed for indicators that are already naturally bounded and interpretable: the Hurst exponent (0–1), Choppiness Index (0–100), Efficiency Ratio (0–1), and lag-1 autocorrelation (−1 to +1). These should still be fed into the model as-is but may benefit from mild clipping to remove extreme outliers.
Min-max scaling is generally not recommended for production because the min and max will shift over time, creating inconsistent scaling across the training and inference periods.

Q7 — Should percentile-based features be preferred over absolute values?
Yes, and the reasoning is both statistical and practical.
Statistically, absolute feature values conflate the level of an indicator with its regime-informativeness. A realized volatility of 20% is a high-stress regime for a low-vol asset and a calm regime for a historically high-vol one. Percentile rank removes this ambiguity — the 85th percentile of realized volatility means the same thing ("unusually elevated") regardless of the asset's baseline vol level.
Practically, percentile-based features are far more robust to structural breaks in the time series. If a regime shift permanently elevates the baseline level of some indicator (e.g., persistently higher credit spreads post-2008), absolute features trained in one period will be miscalibrated in another. Percentile features adapt because they are always measured relative to the most recent rolling history.
The implementation requires choosing a percentile lookback window. A 252-bar (one-year) rolling window balances responsiveness and stability adequately for most features. For very slow-moving macro features (yield curve, credit cycle), a longer window of 504–756 bars (2–3 years) is appropriate. The window length should be a named configuration parameter, not a hardcoded constant.
One important nuance: percentile features compress the extremes. An indicator at the 97th percentile and one at the 99th percentile will appear close together, even though the latter may be a historically unprecedented reading. For features where extreme tail readings carry outsized information (e.g., VIX above its 99th percentile, credit spreads at 30-year highs), retain the raw absolute value as a separate feature alongside the percentile rank.

Q8 — Should features be adaptive across different assets?
Yes, and this is one of the most consequential design decisions in the module. The same indicator with the same threshold will mean structurally different things across asset classes, and even across individual securities within the same asset class.
  ::view-transition-group(*),
  ::view-transition-old(*),
  ::view-transition-new(*) {
    animation-duration: 0.25s;
    animation-timing-function: cubic-bezier(0.19, 1, 0.22, 1);
  }
VvisualizeVvisualize show_widgetThree forms of adaptation are required:
Threshold adaptation. A 20% annualized realized volatility threshold for "high vol" is appropriate for large-cap equities but would classify almost every day in energy commodities as high-vol and almost no day in government bonds. Each asset class needs its own threshold table, calibrated from the asset's own historical distribution. The production implementation should store per-asset-class threshold configurations as named parameter sets, versioned and auditable.
Lookback adaptation. Mean-reversion dynamics operate on different timescales across asset classes. Currency pairs and index futures tend to have shorter-lived regimes than credit or macro factors. The Hurst estimation window, autocorrelation lookback, and percentile ranking window should all be configured per asset class. A rough guide: faster-moving, higher-liquidity markets warrant shorter lookbacks; slower-moving, institutionally-dominated markets warrant longer ones.
Feature relevance adaptation. Not all features are equally relevant across all asset classes. Open interest and term structure slope are critical for futures; meaningless for spot equities. The put/call ratio is deeply informative for single-name equities with active options markets; unavailable for most fixed income instruments. The module should support a per-asset-class feature mask that activates or deactivates specific features and reweights the ensemble accordingly, rather than forcing every asset through the same feature vector.
The implementation architecture that supports all three forms of adaptation is a FeatureConfig object that travels with each symbol's computation context, is loaded from a configuration store at initialization, and is periodically re-calibrated (e.g., quarterly) as the asset's return distribution evolves. This config is distinct from the model weights and can be updated without retraining.


# 5. Adaptive Calibration

...
5.1 Fixed vs. Adaptive Thresholds
Thresholds should be dual-layered: a fixed structural baseline overlaid with adaptive calibration. Neither approach alone is sufficient in production.
Fixed thresholds provide reproducibility, auditability, and protection against overfitting to recent history. They are necessary for regime labels to remain comparable across time and across model versions — if thresholds shift continuously, regime labels become non-stationary by construction, which breaks any downstream strategy or risk model that trains on labeled regimes.
Adaptive thresholds are necessary because market microstructure changes over time. A volatility threshold calibrated on 2010–2015 equities will misclassify regimes during COVID-era volatility spikes or the low-volatility suppression of 2017. Ignoring this leads to chronic misclassification in structurally different regimes.
The recommended architecture:

Hard-coded floor/ceiling guards: Absolute bounds that can never be crossed regardless of adaptive recalibration. These prevent degenerate outputs (e.g., every day classified as "trending," or a volatility threshold of zero).
Rolling calibration window: Thresholds are recomputed on a trailing window (e.g., 252 or 504 trading days) using percentile-based rules described in 5.4. The calibration itself is scheduled, not continuous — update frequency should be weekly or monthly, not intraday, to avoid threshold chasing.
Regime-aware dampening: Threshold updates are suppressed or down-weighted during confirmed crisis/high-volatility regimes. Recalibrating thresholds using data from a crash embeds the crash into the definition of "normal," which distorts subsequent labeling.
Change detection gate: Adaptive updates only apply when a statistical test (e.g., Kolmogorov-Smirnov or CUSUM on the underlying signal distribution) confirms structural drift. Without this gate, adaptive thresholds introduce unnecessary noise.

Thresholds should never be updated in real-time within a trading session. All recalibrations apply at the open of the next calibration cycle.

5.2 Trend Threshold Determination
Trend thresholds govern classification of directional signals — typically the output of ADX, a moving-average crossover spread, or a normalized momentum score. Determination involves three steps:
Step 1 — Signal normalization. Raw trend indicators have scale artifacts (ADX is bounded 0–100; MA spreads are price-denominated). All trend signals must be normalized before threshold application, either by z-scoring against a rolling window or by expressing as a percentile rank within the calibration window. This ensures thresholds have consistent semantic meaning across instruments and time periods.
Step 2 — Regime-labeled historical segmentation. Using an independent reference labeling (e.g., analyst-annotated regimes, or a Hidden Markov Model trained on a held-out period), identify the empirical distribution of the normalized trend signal within confirmed trending vs. non-trending periods. The threshold is set at the intersection of these distributions — the point that minimizes combined classification error (false trending + false ranging). In practice this approximates the point where the two Gaussian distributions cross, weighted by their base rates.
Step 3 — Hysteresis band construction. Do not use a single threshold value. Set a lower entry threshold (signal must exceed this to enter a trending regime) and a higher exit threshold (signal must fall below this to exit a trending regime). The band width should be calibrated so that false regime flips are suppressed across typical mean-reversion noise in the trend indicator. A reasonable starting band is ±0.5 standard deviations around the optimal threshold, tightened or widened based on false-flip frequency observed in backtest.
For ADX specifically: trending regimes historically begin to exhibit meaningful persistence above ADX ≈ 20–25. The hysteresis band is typically set at 20 (entry) / 17 (exit), though these require instrument-specific calibration.

5.3 Volatility Threshold Determination
Volatility thresholds are structurally more complex than trend thresholds because volatility is highly autocorrelated, non-Gaussian (fat-tailed), and exhibits strong regime dependence — the very thing being measured.
Preferred approach — realized volatility percentile anchoring:
Compute rolling realized volatility (e.g., 21-day annualized) over the calibration window. Map the realized volatility time series to its empirical percentile distribution. Define volatility regime boundaries at fixed percentile cuts (e.g., <33rd percentile = low, 33rd–67th = normal, >67th = elevated, >90th = crisis). This is superior to fixed annualized volatility levels because it automatically adjusts to the volatility-of-volatility of each instrument class.
Regime-specific multipliers: Volatility thresholds interact with trend thresholds. A trend signal during a high-volatility period carries different confidence than the same signal in a low-volatility period. The module should maintain a volatility scaling factor that modulates trend threshold sensitivity based on the current volatility regime. In high-volatility periods, trend thresholds should be raised (require stronger directional evidence) to avoid noise-driven mislabeling.
GARCH-informed dynamic baseline: For production systems, a GARCH(1,1) or EGARCH model should provide a conditional volatility estimate alongside the realized volatility input. The threshold determination logic should compare both: when GARCH conditional volatility and realized volatility disagree significantly (e.g., realized has spiked but conditional has not yet caught up), flag the regime label as uncertain rather than committing to a volatility regime transition.
Handling volatility clustering: Implement a minimum dwell time for volatility regime changes — e.g., require that realized volatility exceeds the threshold for at least 3 consecutive periods before a volatility regime transition is confirmed. This prevents whipsawing during intraday or day-to-day volatility oscillations.

5.4 Historical Percentile-Based Thresholds
Yes — percentile anchoring should be the primary method for all continuous-signal thresholds, with the following design constraints:
Calibration window: The rolling window for percentile computation must be long enough to capture at least one full market cycle (bull, bear, ranging, crisis). A minimum of 504 trading days (~2 years) is recommended; 756 days (~3 years) is preferable. Windows shorter than 252 days introduce substantial look-ahead sensitivity.
Percentile definitions per signal type:
SignalLow RegimeNormal RegimeHigh/Trending RegimeRealized Volatility< P33P33 – P67> P67 (crisis > P90)ADX (normalized)< P30P30 – P60> P60Trend momentum z-score< –P60–P60 to +P60outside ±P60Volume ratio< P25P25 – P75> P75
Non-stationarity caveat: Percentile-based thresholds assume the calibration window is representative of the current market structure. When a structural break is detected (see Section 5.1 CUSUM gate), the calibration window should be reset or expanded to include pre- and post-break data, and thresholds should be flagged as provisional until sufficient post-break history accumulates (minimum 63 trading days).
Extreme tail handling: The top and bottom 5th percentiles should be treated as separate regime flags ("crisis" and "dormant") rather than absorbed into the high/low regime bins. These tails often correspond to qualitatively different market conditions requiring distinct downstream treatment.

5.5 Configurable Thresholds
All thresholds should be externally configurable via a validated configuration schema (e.g., YAML or JSON with Pydantic validation at load time). The following are the minimum required configurable parameters:
Trend thresholds:

trend_entry_threshold — normalized signal level to enter a trending regime
trend_exit_threshold — normalized signal level to exit a trending regime
trend_calibration_window_days — rolling window for trend signal percentile computation
trend_min_dwell_periods — minimum consecutive periods before regime transition is confirmed

Volatility thresholds:

vol_low_percentile — upper bound of low-volatility regime (default: P33)
vol_high_percentile — lower bound of high-volatility regime (default: P67)
vol_crisis_percentile — lower bound of crisis regime (default: P90)
vol_calibration_window_days
vol_min_dwell_periods
vol_garch_disagreement_tolerance — fractional divergence between GARCH and realized vol before uncertainty flag is raised

Adaptive recalibration controls:

adaptive_recalibration_enabled — bool; disables all adaptive updates when false
recalibration_frequency — e.g., "weekly", "monthly"
recalibration_min_history_days — minimum history required before adaptive thresholds activate
structural_break_sensitivity — KS-test or CUSUM sensitivity parameter

Global guards:

absolute_vol_floor — minimum realized vol threshold regardless of percentile (prevents near-zero thresholds in suppressed vol environments)
absolute_vol_ceiling — maximum vol threshold (prevents extreme tail events from setting an absurdly high "normal")
max_adaptive_threshold_drift — maximum fractional change allowed per recalibration cycle (prevents jump discontinuities)

All configurable thresholds must pass validation at module initialization. Invalid configurations (e.g., trend_exit_threshold > trend_entry_threshold) should raise a ThresholdConfigurationError with an explicit message before any computation begins.

5.6 Recommended Default Values
The following defaults are calibrated for liquid, large-cap equity indices (e.g., SPX, NDX). They require instrument-specific recalibration for FX, fixed income, commodities, or individual equities.
Trend defaults:
ParameterDefaultRationaletrend_entry_thresholdP60 of normalized ADXHistorically, ADX above this level shows meaningful trend persistence (cross-reference: this percentile rank is calibrated to correspond approximately to raw ADX ≈ 20–25 per Section 2, Q2 and Section 5.2; the two are not guaranteed to coincide outside the reference calibration window and must be re-derived per instrument)trend_exit_thresholdP45 of normalized ADXCreates a hysteresis band; avoids flip-flopping near boundarytrend_calibration_window_days504Two full years; captures at least one cycletrend_min_dwell_periods3 daysSuppresses single-day signal spikes
Volatility defaults:
ParameterDefaultRationalevol_low_percentile33Tertile split; symmetric baselinevol_high_percentile67Tertile split upper boundvol_crisis_percentile90Top decile; consistent with VIX spike thresholds in literaturevol_calibration_window_days504Symmetric with trend windowvol_min_dwell_periods3 daysConsistent with trend; prevents vol-spike whipsawingabsolute_vol_floor5% annualizedBelow this, vol regime labels become numerically unstableabsolute_vol_ceiling150% annualizedAbove this, crisis regime is forced regardless of percentilevol_garch_disagreement_tolerance0.40 (40% divergence)Empirically, larger divergence signals structural event in progress
Adaptive recalibration defaults:
ParameterDefaultadaptive_recalibration_enabledtruerecalibration_frequency"weekly"recalibration_min_history_days126 (half-year)max_adaptive_threshold_drift0.15 (15% per cycle)
These defaults should be treated as a validated starting point, not a production guarantee. Any deployment targeting a specific instrument class, time horizon, or strategy type should conduct a calibration study over at least 5 years of in-sample history before treating them as final. All defaults must be documented in the module's configuration schema with units, valid ranges, and the rationale for the default value.


# 6. Transition Logic

...
6.1 Conditions for Regime Change
A regime change should never be triggered by a single indicator crossing a threshold in a single period. Production-grade transition logic requires simultaneous satisfaction of multiple independent conditions, forming a conjunctive gate. A regime change is authorized only when all of the following conditions are met:
Condition 1 — Primary signal confirmation. The primary regime indicator (e.g., normalized ADX for trend, realized volatility percentile for volatility) must cross the designated entry threshold and remain beyond it for the minimum dwell period defined in configuration. A single-period exceedance is treated as a candidate event, not a confirmed transition.
Condition 2 — Secondary signal corroboration. At least one secondary indicator must independently agree with the proposed transition. For a trend regime entry, this could be a moving-average slope sign change, a momentum z-score exceeding its threshold, or a volume confirmation. For a volatility regime transition, this could be GARCH conditional volatility directionally agreeing with realized volatility movement. The secondary indicator does not need to cross its own threshold — directional agreement is sufficient at this stage.
Condition 3 — Confidence score threshold. The module's internal regime probability estimate (see Section 7 on confidence scoring) must exceed a minimum confidence floor for the proposed new regime. A low-confidence reading during threshold exceedance indicates the system is near a boundary, not clearly in a new state. The proposed transition is deferred until confidence rises above the floor or the signal retreats.
Condition 4 — Macro context compatibility. If the module maintains a macro overlay (e.g., VIX level, credit spread regime, risk-on/risk-off flag), the proposed transition must not directly contradict the macro state. A micro-level signal suggesting a strong trending regime while macro signals indicate crisis conditions should trigger a conflict resolution path (see 6.6) rather than an unconditional transition.
Condition 5 — No active suppression flag. Certain system states suppress transitions outright: a structural break flag raised by the CUSUM monitor, an active data quality warning on the input feed, or, optionally, a calendar event lock — if implemented, defined via a configurable calendar_event_lock_windows parameter (Section 10.3) listing instrument-specific event types (e.g., scheduled earnings releases, central bank rate decisions) and the number of sessions before/after each event during which transitions are suppressed. This sub-condition is optional and may be deferred for an initial (e.g., v2.3) release scoped to simpler operation; if deferred, Condition 5 is satisfied by the structural-break and data-quality checks alone. During suppression, the current regime label is frozen and the candidate transition is queued for re-evaluation once suppression lifts.
These five conditions are evaluated in order. Failure at any gate stops evaluation for that period; the system re-evaluates from Condition 1 at the next observation.

6.2 Hysteresis Implementation
Hysteresis is mandatory. A module without hysteresis will produce regime labels that oscillate at boundaries, generating excessive transaction costs and strategy instability in any downstream consumer.
The implementation uses a dual-threshold state machine per signal dimension, not a single crossing threshold. The entry and exit thresholds for each regime are set at different levels, creating a band of ambiguity within which the current regime is maintained regardless of signal value.
Structural design:
Each regime dimension (trend, volatility) maintains a current state variable. Transitions operate as follows:

From ranging to trending: signal must exceed trend_entry_threshold. Until it does, the ranging label persists even if the signal is above the exit threshold.
From trending to ranging: signal must fall below trend_exit_threshold, which is set strictly below the entry threshold. A signal hovering between exit and entry thresholds remains classified in its current state.

The hysteresis band width — the gap between entry and exit thresholds — should be calibrated to be at least 1.5× the typical short-term standard deviation of the signal in question. This ensures normal noise oscillation does not produce transitions. As a practical rule, if backtesting the regime labels reveals more than one transition per 10-day window on average during range-bound markets, the hysteresis band is too narrow.
Asymmetric hysteresis for crisis regimes: Crisis/high-volatility regimes should implement asymmetric bands — easy to enter (lower entry bar), hard to exit (high exit bar requiring significant and sustained volatility compression). This reflects the empirical asymmetry of volatility: spikes are fast and must be captured quickly; recoveries are gradual and should not be prematurely labeled as regime exits. The crisis exit threshold should require realized volatility to fall below the P67 level (not merely the P90 entry level) and sustain for a minimum of 5 periods.
State machine persistence: The hysteresis logic must be implemented as a stateful object, not a stateless function applied to each observation independently. The current regime label must be an explicit state variable carried forward across observations. Stateless re-labeling of history on each call is not a hysteresis implementation — it is threshold crossing detection, which produces the very oscillation problem hysteresis is designed to solve.

6.3 Consecutive Confirmation Requirements
The minimum number of consecutive confirmation periods required before a regime transition is committed should vary by regime type and transition direction. A single recommended value applied uniformly is inadequate.
Recommended confirmation counts by transition type:
TransitionMinimum ConfirmationsRationaleRanging → Weakly Trending3 periodsModerate evidence bar; false trends are common near range boundariesWeakly Trending → Strongly Trending2 periodsAlready in trend; incremental confirmation is sufficientTrending → Ranging4 periodsTrend exhaustion signals are noisy; require sustained evidence of decayLow Vol → Normal Vol2 periodsVol expansion confirms quickly in real dataNormal Vol → High Vol2 periodsErr toward fast capture of volatility expansionHigh Vol → Normal Vol5 periodsVolatility compression must be sustained; premature recovery labeling is costlyAny → Crisis1 periodCrisis onset must be captured immediately; confirmation delay is unacceptableCrisis → Any7 periodsCrisis exits are the highest-stakes transitions; require strong sustained evidence
Confirmation counting rules:
The consecutive counter must reset to zero on any period where the signal retreats back across the relevant threshold, even by a small amount. Partial credit (e.g., counting a near-miss as 0.5) is not recommended — it introduces a hidden continuous parameter that is difficult to audit and calibrate. The counter is binary: each period either extends the confirmation streak or resets it.
The confirmation counter for a candidate transition runs in parallel with the current regime label, which does not change until the confirmation count is satisfied. The candidate transition and its running count should be exposed as observable outputs of the module, not hidden internal state — downstream consumers need to know when the system is approaching a transition boundary.

6.4 Minimum Regime Duration
A minimum regime duration must be enforced as a hard constraint, independent of and in addition to the consecutive confirmation requirement. Confirmation prevents premature entry into a new regime; minimum duration prevents premature exit.
Minimum duration by regime:
RegimeMinimum DurationNotesStrongly Trending5 trading daysStrong trends are persistent; allow time to developWeakly Trending3 trading daysShorter persistence expected; exit bar is lowerRanging5 trading daysRange regimes are stable by nature; short-duration ranging is usually transition noiseHigh Volatility3 trading daysVol events can resolve quickly; somewhat shorter floorCrisis10 trading daysLongest minimum; crisis regimes have real-world consequences for downstream modelsLow Volatility5 trading daysSuppressed vol periods are structurally stable; short durations indicate noise
Implementation: The module tracks current_regime_entry_time. On each observation, before evaluating any transition, it checks whether current_time - current_regime_entry_time >= minimum_duration[current_regime]. If the minimum duration has not elapsed, all transition logic is bypassed and the current label is maintained unconditionally. The bypass itself is logged with a DURATION_LOCK flag in the output metadata so downstream consumers can distinguish a confident regime label from a duration-locked one.
Override provision: The minimum duration enforcement must be bypassable for crisis entry. If crisis conditions are met while a non-crisis regime is duration-locked, the crisis entry proceeds immediately. Duration locking must never delay the capture of a crisis regime onset.

6.5 Prevention of Rapid Regime Oscillation
Rapid oscillation — where the module flips between two regimes on consecutive or near-consecutive observations — is a signal of threshold miscalibration, insufficient hysteresis, or genuine market ambiguity. The system should detect and respond to it explicitly rather than allowing it silently.
Primary prevention mechanisms (structural — built into the transition logic):
The combination of dual-threshold hysteresis (6.2), minimum confirmation counts (6.3), and minimum regime duration (6.4) eliminates the majority of oscillation. These three mechanisms must all be active simultaneously; removing any one significantly increases oscillation frequency.
Secondary prevention — flip frequency monitoring:
Maintain a rolling counter of regime transitions over a configurable lookback window (default: 21 trading days). If the transition count exceeds a configurable threshold (default: 3 transitions per 21-day window for any single regime dimension), activate an oscillation suppression mode:

The current regime label is locked.
Threshold entry requirements are temporarily raised by one confirmation period.
An OSCILLATION_WARNING flag is set in the module output.
The condition persists until the rolling transition count falls back below the threshold.

This suppression is not silent — it must be logged and observable. An oscillation warning is itself a signal: it indicates the market is genuinely at a regime boundary, which is useful information for downstream consumers.
Tertiary prevention — regime probability smoothing:
Apply a short exponential moving average to the raw regime probability scores before threshold evaluation (not to the regime labels themselves, which must remain discrete). A smoothing factor of α = 0.3 over 3 periods removes high-frequency noise from the probability estimates without introducing meaningful lag. Smoothing must be applied to the input signal, not the output label — label smoothing post-hoc is not a valid substitution.
What not to do: Do not implement oscillation prevention by simply increasing minimum duration or confirmation counts uniformly to large values. Doing so trades oscillation risk for catastrophic lag in crisis detection. The targeted mechanisms above are preferred because they activate conditionally based on observed oscillation, preserving responsiveness under normal conditions.

6.6 Handling Conflicting Indicator Signals
Conflicting signals are not edge cases — they are the norm near regime boundaries and during transitions. The module must have an explicit, deterministic conflict resolution policy rather than leaving conflicts undefined.
Step 1 — Signal independence audit. Before classifying a signal set as conflicting, verify that the signals are genuinely independent. ADX and a moving-average slope are not independent — both derive from price. True conflict resolution is only meaningful when signals from independent sources disagree (e.g., price-based trend signal vs. volume-based confirmation vs. volatility-implied direction). Correlated signals that disagree are more likely a calibration artifact than a true conflict.
Step 2 — Conflict taxonomy. Classify the conflict type before applying resolution logic:

Magnitude conflict: The direction of all signals agrees but their intensity disagrees (e.g., trend confirmed but volatility elevated). Resolution: proceed with transition, add a REDUCED_CONFIDENCE flag, raise the confidence floor requirement.
Directional conflict — minority dissent: One signal disagrees with a majority of others. Resolution: proceed with the majority signal, log the dissenting indicator, apply a confidence penalty proportional to the weight of the dissenting signal.
Directional conflict — even split: Signals are evenly divided in direction. This is the only true conflict. Resolution: do not transition. Maintain current regime. Set an AMBIGUOUS_REGIME flag in output metadata. Re-evaluate next period.
Scale conflict: Signals agree on regime type but disagree on severity (e.g., one suggests weakly trending, another strongly trending). Resolution: assign the more conservative (lower intensity) of the proposed regimes.

Step 3 — Signal weighting. Not all signals carry equal weight in conflict resolution. The module should maintain a configurable signal weight vector, with weights representing each indicator's historical accuracy in regime classification on the calibration dataset. In a conflict, the weighted vote determines the majority. Default weights should be uniform at initialization and updated during periodic recalibration based on each indicator's confusion matrix performance.
Step 4 — Conflict persistence handling. If an even-split conflict persists for more than conflict_max_duration periods (default: 3), escalate: assign the regime that has the lowest expected cost of misclassification given the current context. In practice, during an unresolved conflict between trending and ranging, defaulting to ranging is lower cost for most strategies — it produces underperformance on a genuine trend rather than the larger risk of full trend-following exposure in a ranging market. This asymmetric default must be documented and configurable.
Conflict metadata output: Every observation should carry a conflict_state field in the output — not just observations where a conflict is active. Values: NONE, MINORITY_DISSENT, EVEN_SPLIT, MAGNITUDE_CONFLICT, SCALE_CONFLICT. This field enables downstream consumers to distinguish a clean, high-confidence regime label from one produced under ambiguity, and to adjust position sizing or strategy allocation accordingly.


# 7. Confidence

...
7.1 Defining Confidence
Confidence must be defined precisely and operationally — an informal notion of "how sure the system is" is insufficient for a production module whose output is consumed by risk engines, position sizers, and allocation models that require a calibrated, interpretable score.
Formal definition: Confidence is the module's estimate of the posterior probability that the current regime label is correct, conditioned on all available evidence at the time of labeling. It is not a measure of signal strength, trend intensity, or volatility magnitude — those are raw signal values. Confidence specifically quantifies label reliability: a high-confidence ranging label means the system assigns high probability that the market is genuinely ranging, not that the range is wide or stable.
This distinction has practical consequences. A very strong ADX reading produces a high-confidence trending label. But a moderate ADX reading that is corroborated by volume, momentum, and macro context may produce an equally high or higher confidence label than a strong but uncorroborated ADX alone. Confidence aggregates evidence quality, not signal intensity.
Two distinct confidence quantities must be maintained:

Instantaneous confidence — the confidence assigned to the current regime label at the current observation, based on current signal values. This is what most downstream consumers use for position sizing and risk scaling.
Regime confidence — the confidence that the current regime epoch (the uninterrupted run of the current label) is correctly classified, updated as a running estimate since the last confirmed regime entry. This grows with persistence (see 7.4) and resets on each transition.

Both quantities must be computed and exposed separately. Conflating them produces a confidence estimate that is neither a reliable instantaneous signal nor a reliable persistence-adjusted one.
Calibration requirement: Confidence scores must be empirically calibrated against historical labeling accuracy. A score of 0.80 should correspond to approximately 80% historical accuracy on similarly-scored observations. Uncalibrated scores — raw probability estimates from a model that has never been checked against realized accuracy — are not production-ready. Calibration curves should be generated and stored as part of the module's initialization artifacts, and rechecked during each adaptive recalibration cycle.

7.2 Contributing Factors
Confidence is a composite score assembled from multiple independent evidence dimensions. Each dimension contributes a sub-score; the composite is computed as a weighted combination. The weights are configurable and should be recalibrated periodically against historical accuracy.
Factor 1 — Primary signal margin. How far the primary signal is from the nearest threshold boundary, expressed as a normalized distance. A signal deep inside a regime's territory contributes high confidence; a signal near the boundary contributes low confidence regardless of which side it is on. Computed as the ratio of (signal value − nearest threshold) to (threshold range width). Capped at 1.0 to prevent extreme signal values from dominating the composite.
Factor 2 — Indicator agreement rate. The fraction of independent indicators that agree with the current regime label, weighted by each indicator's historical precision on this regime class. Described in detail in 7.3.
Factor 3 — Regime persistence. Time elapsed in the current regime relative to its historical median duration. Described in detail in 7.4.
Factor 4 — Historical base rate alignment. Whether the current regime is consistent with the expected base rate distribution. A regime that is rare in historical data (e.g., sustained strong trending in a normally mean-reverting instrument) should carry a confidence penalty reflecting its low prior probability. This is a Bayesian prior term: the likelihood-based evidence from Factors 1–2 must overcome a low prior to produce high composite confidence.
Factor 5 — Signal stability. The variance of the primary signal over the confirmation window. A signal that crossed the threshold cleanly and has remained stable since contributes higher confidence than one that crossed erratically and has been oscillating near the threshold. Measured as 1 − (normalized rolling standard deviation of the signal over the dwell window).
Factor 6 — Macro context alignment. A binary or graded agreement term reflecting whether the macro overlay state is consistent with the current micro regime label. Full consistency contributes a positive adjustment; contradiction applies a penalty; absence of macro data applies no adjustment (neutral). This factor should have a lower default weight than Factors 1–3, as macro overlays may not be available in all deployment contexts.
Factor 7 — Recency of calibration. A time-decay term reflecting how recently the adaptive thresholds were last recalibrated. Confidence in threshold-based decisions degrades as the calibration ages, because structural drift may have moved the true regime boundaries away from the current thresholds. This factor decays linearly from 1.0 at recalibration to a configurable floor (default: 0.85) at the maximum allowable recalibration age.
Composite assembly:
confidence = w1·F1 + w2·F2 + w3·F3 + w4·F4 + w5·F5 + w6·F6 + w7·F7
where weights sum to 1.0. Default weights must be documented in configuration. Any factor for which input data is unavailable is excluded from the sum and the remaining weights are renormalized rather than treated as zero — zero-imputation would penalize deployments with fewer indicators, producing artificially low confidence scores that are not comparable across configurations.

7.3 Indicator Agreement and Confidence
Indicator agreement is the most operationally tractable confidence component and deserves its own design specification.
Agreement is not a simple vote count. Three indicators agreeing out of four is not automatically better than two out of two. What matters is the weighted precision of agreeing indicators on this specific regime class, and the independence of those indicators from one another.
Independence-adjusted agreement score:
Before computing the agreement score, cluster all indicators by their underlying data source. Price-derived indicators (ADX, MA slope, momentum) form one cluster; volume-derived indicators form another; volatility-derived indicators a third; macro/cross-asset indicators a fourth. Within each cluster, agreement is aggregated to a single cluster vote weighted by the precision of the best indicator in that cluster. Cross-cluster agreement is then computed as the fraction of clusters voting for the current regime, weighted by each cluster's historical reliability.
This prevents a situation where five price-derived indicators agreeing — all correlated with each other by construction — produces spuriously high confidence simply because many indicators were defined.
Precision weighting: Each indicator maintains a per-regime precision score from the calibration dataset: the fraction of times this indicator voted for this regime class and the label was subsequently confirmed correct. These precision scores are stored in the module's calibration artifact and updated during recalibration cycles. An indicator with 0.90 precision on trending regimes but 0.55 precision on ranging regimes contributes its vote with weight 0.90 when evaluating a trending label, and 0.55 when evaluating a ranging label.
Dissent penalty structure: The agreement factor is not merely the weighted sum of agreeing indicators. Dissenting indicators apply a multiplicative penalty to the agreement score, scaled by their historical precision on the proposed regime class. A high-precision dissenter (an indicator that is usually right about this regime) applies a larger penalty than a low-precision dissenter. This asymmetry is intentional: if your most reliable trend indicator dissents from a trending label, confidence should drop substantially even if four lower-quality indicators agree.
Agreement factor formula:
agreement_score = (Σ precision_i for agreeing indicators) 
                  × (1 − Σ α·precision_j for dissenting indicators)
normalized to [0, 1]
where α is a configurable dissent amplification factor (default: 0.6). The dissent term is additive across dissenters, capped at 0.5 to prevent a single dissenter from collapsing the agreement score to zero regardless of how many high-quality indicators agree.

7.4 Confidence and Regime Persistence
Confidence should increase with regime persistence, but the relationship must be carefully specified to avoid two failure modes: overconfident stale labels and under-responsive crisis detection.
The empirical basis: Regime persistence is informative because regimes are autocorrelated. A trending regime that has been correctly labeled for 15 consecutive days is more likely to remain trending tomorrow than a trending regime that was just entered. This is not circular reasoning — it reflects genuine autocorrelation in the underlying market structure, and it is the correct Bayesian update to make.
Persistence contribution design:
Define a persistence factor P(t) as a function of the time elapsed since confirmed regime entry:
P(t) = P_max · (1 − exp(−t / τ))
where t is periods elapsed since regime entry, τ is a regime-specific time constant (the number of periods at which persistence has contributed half its maximum value), and P_max is the maximum persistence contribution to confidence (a configurable ceiling, default: 0.20, meaning persistence can contribute at most 20 percentage points to the composite confidence score).
Regime-specific time constants:
Regimeτ (periods)P_maxStrongly Trending100.20Weakly Trending70.15Ranging120.20High Volatility50.15Crisis30.10Low Volatility150.20
The shorter time constants for crisis and high-volatility regimes reflect that these regimes can terminate quickly — persistence should accrue more cautiously. The lower P_max for crisis reflects deliberate conservatism: the module should not become highly confident a crisis is ongoing to the point that it suppresses detection of recovery signals.
Hard cap on persistence contribution: Persistence can never be the sole driver of high confidence. If the instantaneous confidence from Factors 1–2 (primary signal margin and indicator agreement) falls below a minimum floor (default: 0.40), the persistence bonus is zeroed out regardless of how long the regime has been running. A stale, weakly-supported regime label should not achieve high confidence simply because nothing has explicitly contradicted it for a long time.
Persistence reset: On regime transition, the persistence factor resets to zero immediately. During the confirmation window (before a transition is committed), persistence is not applied to the candidate new regime — it continues to apply to the outgoing regime until the transition is committed.

7.5 Representing Uncertainty
Confidence is a point estimate; it does not fully represent the epistemic state of the module. A confidence score of 0.65 could reflect a clear second-best regime at 0.30 (a bimodal near-split) or a diffuse uncertainty across four regimes. These situations have very different implications for downstream consumers and must be distinguished.
Full regime probability distribution: The module must output a probability vector over all defined regime classes at every observation, not just a scalar confidence for the winning label. The winning label's probability is the instantaneous confidence; the full vector contains the information about how probability mass is distributed across alternatives. Downstream consumers who apply their own decision logic (e.g., blend strategy weights proportional to regime probabilities rather than hard-switching) require the full distribution.
Uncertainty decomposition: Distinguish between two types of uncertainty in the output metadata:

Aleatoric uncertainty — irreducible uncertainty arising from the market genuinely being near a regime boundary or in transition. Indicated when the top two regime probabilities are within a configurable tolerance of each other (default: 0.15). This is real ambiguity; no amount of additional data would resolve it cleanly.
Epistemic uncertainty — uncertainty arising from insufficient data, stale calibration, or conflicting signals of known provenance. Indicated by active flags: OSCILLATION_WARNING, CALIBRATION_STALE, STRUCTURAL_BREAK_DETECTED, DATA_QUALITY_WARNING. This uncertainty is reducible — it would decrease with better data or fresher calibration.

Both types must be explicitly flagged in output metadata. Downstream consumers have different appropriate responses: aleatoric uncertainty warrants conservative position sizing; epistemic uncertainty may warrant delaying a decision until the source is resolved.
Confidence interval output: For the instantaneous confidence score, output a 90% empirical confidence interval derived from the calibration dataset's bootstrap distribution at similar signal configurations. This interval communicates the historical reliability of confidence estimates at this level — a confidence score of 0.72 with interval [0.68, 0.76] is more trustworthy than one with interval [0.55, 0.88], even though the point estimate is the same.
Entropy as a summary uncertainty metric: Compute the Shannon entropy of the full regime probability distribution at each observation. High entropy indicates diffuse uncertainty across regimes; low entropy indicates confident concentration on one label. Expose this as a scalar regime_entropy output field. It provides a single-number uncertainty summary for consumers who do not process the full probability vector.

7.6 Normalization to [0, 1]
Yes — the final confidence score must be normalized to a closed [0, 1] interval, but the normalization requires deliberate design. Naive normalization produces a score whose endpoints are never reached in practice, which compresses the useful range and makes the score harder to act on.
Hard boundary semantics: The endpoints must carry explicit meaning:

0.0 — the module has no basis to assert the current label. This should only be reachable under specific defined conditions: active structural break with all signals conflicting, data quality failure causing total signal loss, or system initialization before minimum history has accumulated. It is not simply a "very low confidence" value — it is a sentinel indicating the label should not be consumed.
1.0 — this value should be unreachable in live operation. Perfect confidence is not epistemically justified. The composite score formula should be designed so that the maximum achievable score under ideal conditions is approximately 0.95, leaving a structural gap at the top that communicates humility about model completeness.

Calibration-based normalization: The composite weighted sum from 7.2 will not naturally produce uniform coverage of [0, 1]. After computing the raw composite, apply a calibration mapping — a monotone transformation fit during calibration that maps the empirical distribution of raw composite scores to the [0, 1] range such that the resulting scores are probability-calibrated (i.e., a score of 0.70 corresponds to 70% historical accuracy). Use isotonic regression on the calibration dataset's (raw score, label correctness) pairs to fit this mapping. Store the fitted isotonic regression as part of the module's calibration artifact and refit it during each recalibration cycle.
Operational thresholds on the normalized score:
Define named tiers on the normalized scale and expose them as a categorical confidence_tier field alongside the scalar score. These tiers provide a human-readable and rule-based-friendly version of the score:
TierScore RangeInterpretationRecommended Downstream BehaviorVERY_LOW[0.0, 0.40)Label unreliable; near boundary or conflicting signalsDo not act; treat as regime unknownLOW[0.40, 0.55)Weak evidence; transition may be in progressReduce exposure; monitor closelyMODERATE[0.55, 0.70)Reasonable evidence; some uncertainty remainsNormal operation with reduced sizingHIGH[0.70, 0.85)Strong multi-factor agreementFull strategy allocation appropriateVERY_HIGH[0.85, 1.0)Deep in regime, strong corroboration, stableMaximum conviction allocation
These tier boundaries are configurable. They are deliberately asymmetric — the HIGH and VERY_HIGH tiers together cover only 30% of the scale, reflecting that high-confidence regime labels should be relatively rare. If backtesting reveals that more than 60% of observations are classified as HIGH or VERY_HIGH, the tier boundaries or the composite weighting should be reviewed for overconfidence.
Score continuity requirement: The normalized confidence score must be a continuous value within each tier, not discretized to tier midpoints. Downstream consumers who use the scalar score for continuous position sizing must receive a smooth signal. The tier label is a categorical convenience; the scalar is the ground truth output.



# 8. Output Specification

...
8.1 MarketRegime Object Fields
The MarketRegime object is the canonical output contract of the module. Every field must earn its place — the object should contain everything a downstream consumer could reasonably need without requiring them to re-derive it, and nothing that belongs in internal module state. The full field specification is organized into five logical groups.

Group A — Identity and Timing
regime_id: UUID

A globally unique identifier for this specific output record. Enables exact record lookup, deduplication in message queues, and idempotency checking in downstream persistence layers. Generated fresh on each emission, not reused across recalculations of the same timestamp.
instrument_id: str

The canonical identifier of the instrument for which the regime is computed. Must match the instrument registry identifier used across the platform — not a ticker alias or display name.
timestamp: datetime (UTC, timezone-aware)

The observation timestamp to which this regime label applies. Always the close of the observation period, not the computation time. Timezone-aware and explicitly UTC. Naive datetime objects are not permitted in the schema.
computation_timestamp: datetime (UTC, timezone-aware)

The wall-clock time at which this output was produced. Distinct from timestamp to support latency monitoring and to distinguish same-period recalculations (e.g., after recalibration) from original emissions.
bar_type: Enum[DAILY, HOURLY, WEEKLY, CUSTOM]

The resolution of the input data underlying this label. Required because the same module may be deployed at multiple resolutions and outputs must not be ambiguously compared across them.
regime_epoch_id: UUID

Identifies the contiguous run of the current regime label. Shared across all observations within the same uninterrupted regime period; changes only on confirmed regime transition. Enables downstream consumers to group all records belonging to the same regime episode without time-range logic.

Group B — Regime Classification
primary_regime: Enum

The top-level regime label. Enumeration values must be defined exhaustively in the module schema with no open string values permitted. Recommended values: STRONGLY_TRENDING_UP, STRONGLY_TRENDING_DOWN, WEAKLY_TRENDING_UP, WEAKLY_TRENDING_DOWN, RANGING, HIGH_VOLATILITY, LOW_VOLATILITY, CRISIS, TRANSITIONING, UNKNOWN. UNKNOWN is reserved for initialization and total signal failure states; TRANSITIONING for periods where a candidate regime change has accumulated sufficient consecutive confirmations (Section 6.3) but the candidate's confidence score has not yet crossed the minimum confidence floor required to commit the transition (Section 6.1, Condition 3); the transition is not yet "confirmed" in the Section 6 sense until both conditions are met.
primary_regime_direction: Enum[BULLISH, BEARISH, NEUTRAL, UNDEFINED]

Directional bias of the current regime, decoupled from intensity classification. Provides a clean separation between "what kind of regime" and "which direction" that simplifies downstream strategy selection logic. UNDEFINED for non-directional regimes such as RANGING or LOW_VOLATILITY.
volatility_regime: Enum[LOW, NORMAL, ELEVATED, HIGH, CRISIS]

Volatility classification as a separate orthogonal dimension from the trend/momentum classification in primary_regime. Must always be populated independently, even when primary_regime itself encodes a volatility state, to ensure consumers who only care about volatility regime can read a single field without parsing trend labels.
trend_regime: Enum[STRONG_TREND, WEAK_TREND, RANGING, UNDEFINED]

Trend classification as a separate orthogonal dimension. Same rationale as volatility_regime — orthogonal decomposition enables cleaner downstream consumption than a single combined label.
regime_probability_distribution: Dict[str, float]

Full probability vector over all defined regime classes. Keys are regime label strings; values are probabilities summing to 1.0. Must include all defined regimes, not only those with non-trivial probability. This is the foundational output for any downstream consumer performing soft allocation or blended strategy weighting.
candidate_transition: Optional[CandidateTransition]

Structured sub-object populated when a regime transition is in progress but not yet confirmed. Contains: candidate_regime (the proposed new label), confirmation_count (periods of consecutive confirmation so far), confirmation_required (total periods required), candidate_probability (current probability estimate for the candidate regime), and entry_timestamp (when the candidate transition was first detected). Null when no transition is in progress.

Group C — Confidence and Uncertainty
confidence: float

The normalized instantaneous confidence score for primary_regime, in [0.0, 1.0]. Defined, calibrated, and bounded as specified in Section 7.
confidence_tier: Enum[VERY_LOW, LOW, MODERATE, HIGH, VERY_HIGH]

Categorical tier derived from confidence per the tier boundaries in Section 7.6. Provided as a convenience field for rule-based downstream consumers; the scalar confidence remains the authoritative value.
regime_confidence: float

Confidence in the current regime epoch as a whole, incorporating the persistence factor. Distinct from confidence as described in Section 7.1. Will typically be higher than confidence in well-established regimes and equal to confidence immediately after a transition.
confidence_interval_low: float

Lower bound of the 90% empirical confidence interval for the confidence score. Derived from the calibration bootstrap distribution. See Section 7.5.
confidence_interval_high: float

Upper bound of the 90% empirical confidence interval. See Section 7.5.
regime_entropy: float

Shannon entropy of regime_probability_distribution, in nats. Higher values indicate greater uncertainty across regime classes. See Section 7.5.
uncertainty_type: Enum[NONE, ALEATORIC, EPISTEMIC, BOTH]

Classification of active uncertainty as defined in Section 7.5. NONE when confidence is high and no flags are active; ALEATORIC when the market is genuinely near a boundary; EPISTEMIC when uncertainty is traceable to data or calibration issues; BOTH when both sources are simultaneously active.

Group D — Transition Metadata
regime_entry_timestamp: datetime (UTC)

Timestamp at which the current regime epoch began — i.e., when the transition into the current primary_regime was confirmed. Used by downstream consumers to compute regime age without access to historical records.
regime_duration_periods: int

Number of observation periods elapsed since regime_entry_timestamp, inclusive of the current period. Provided as a convenience to avoid downstream time arithmetic across varying bar types and calendar effects.
previous_regime: Optional[str]

The primary_regime value of the immediately preceding regime epoch. Null only at module initialization. Enables downstream consumers to implement regime-transition-aware logic (e.g., different strategy response to ranging→trending vs. crisis→trending transitions) without maintaining their own state.
previous_regime_duration_periods: int

Duration of the preceding regime in observation periods. Provides context for interpreting the current regime — a transition out of a very short-lived prior regime carries different implications than a transition out of a long-established one.
transition_trigger: Optional[str]

Human-readable summary of the primary factor that triggered the most recent confirmed regime transition. Not a free-form string — drawn from a controlled vocabulary of trigger codes (e.g., ADX_THRESHOLD_BREACH, VOL_PERCENTILE_EXCEEDANCE, MACRO_CONFLICT_RESOLVED, CONFIRMATION_COUNT_MET). Null during stable regime periods between transitions.

Group E — System and Audit
module_version: str

Semantic version string of the regime detection module that produced this output. Required for reproducibility, debugging, and detecting when outputs were produced by different module versions in a historical dataset.
calibration_version: str

Version identifier of the calibration artifact (threshold set, indicator weights, isotonic calibration mapping) active at computation time. Distinct from module_version because calibration updates more frequently than code. Enables exact reproduction of any historical output by pairing code version with calibration version.
status_flags: List[Enum]

List of active system status flags at computation time. Drawn from the controlled set defined in Sections 5–7: OSCILLATION_WARNING, CALIBRATION_STALE, STRUCTURAL_BREAK_DETECTED, DATA_QUALITY_WARNING, DURATION_LOCK, REDUCED_CONFIDENCE, AMBIGUOUS_REGIME, TRANSITION_IN_PROGRESS, INITIALIZATION_PERIOD. Empty list when system is operating nominally with no active conditions. Downstream consumers must check this field before acting on the label; a non-empty flag list is an explicit signal to adjust downstream behavior.
data_quality_score: float

Composite score in [0.0, 1.0] reflecting the quality of the input data underlying this output. Derived from: staleness of each input feed, fraction of indicators with complete vs. imputed data, and any detected anomalies in raw signal values. A score below a configurable floor (default: 0.70) should automatically add DATA_QUALITY_WARNING to status_flags.

8.2 Mandatory Fields
Mandatory fields are those without which the output is either non-actionable or non-auditable. Any record missing a mandatory field must be rejected at the schema validation layer before emission — partial records must never reach downstream consumers.
The following fields are unconditionally mandatory:
regime_id, instrument_id, timestamp, computation_timestamp, bar_type, regime_epoch_id, primary_regime, volatility_regime, trend_regime, confidence, confidence_tier, regime_entropy, uncertainty_type, regime_entry_timestamp, regime_duration_periods, status_flags, data_quality_score, module_version, calibration_version
The following fields are conditionally mandatory — required when their preconditions are met, and must be explicitly null otherwise (absent fields and null fields are not equivalent in the schema):
primary_regime_direction — mandatory when primary_regime is any trending variant; null for RANGING, LOW_VOLATILITY, UNKNOWN.
candidate_transition — mandatory (as a structured null or populated object) whenever TRANSITION_IN_PROGRESS is in status_flags; explicitly null otherwise.
previous_regime and previous_regime_duration_periods — mandatory after the first confirmed regime transition; null only during the initialization period before the first transition has occurred.
regime_probability_distribution — mandatory in all cases. An empty or partial distribution is not permitted; all defined regime classes must appear as keys with valid float values.
confidence_interval_low and confidence_interval_high — mandatory when calibration artifacts are available; may be null only during the initialization period before minimum calibration history has accumulated, with INITIALIZATION_PERIOD flag active.
Soft mandatory fields — these are technically optional but their absence must be justified and logged: transition_trigger (null is valid between transitions but must not be null immediately following a confirmed transition), previous_regime (null only during initialization).

8.3 Diagnostic Information
Yes — diagnostic information must be included, but it must be structured, not narrative. Free-text explanations are not auditable, not machine-readable, and not testable. The module should produce a diagnostics sub-object with the following design:
diagnostics sub-object structure:
regime_drivers: List[IndicatorContribution]

Ordered list of indicators contributing to the current regime label, sorted descending by contribution magnitude. Each IndicatorContribution contains: indicator_name, indicator_value (normalized), threshold_used, margin_to_threshold (signed distance, positive = inside regime, negative = outside), vote (the regime this indicator voted for), weight (this indicator's weight in the composite), contribution_to_confidence (scalar contribution to the final confidence score). This is the primary diagnostic tool — it answers "why is the regime labeled X" with quantitative specificity.
confidence_factor_breakdown: Dict[str, float]

Decomposition of the confidence score by contributing factor as defined in Section 7.2 (signal margin, indicator agreement, persistence, base rate, signal stability, macro alignment, calibration recency). Each key is a factor name; each value is that factor's contribution to the final score before weighting. Enables rapid identification of which factor is depressing or elevating confidence.
threshold_distances: Dict[str, float]

For each active threshold in the current regime evaluation, the signed distance of the relevant signal from that threshold, normalized by the threshold range width. Positive values indicate the signal is within the current regime's territory; negative values indicate it is outside. This field is the primary tool for detecting when a regime is near its boundary without the consumer needing to know the raw threshold values.
transition_history: List[TransitionRecord]

A bounded history of confirmed regime transitions, capped at a configurable depth (default: last 5 transitions). Each TransitionRecord contains: from_regime, to_regime, transition_timestamp, trigger_code, confidence_at_transition, prior_candidate_abort_count, status_flags_at_transition. Provides transition context without requiring consumers to query a separate historical store for routine diagnostic purposes.
suppression_log: List[SuppressionEvent]

Record of any transitions suppressed during the current regime epoch due to duration lock, oscillation suppression, or structural break gating. Each event records the suppressed candidate regime and the suppression reason. Exposes what the module almost did — critical for diagnosing cases where a consumer suspects the module is failing to capture a genuine regime change.
Diagnostic availability tiers: The diagnostics sub-object should support two verbosity levels controlled by a configuration flag: STANDARD (includes regime_drivers and confidence_factor_breakdown only) and FULL (all fields). Production real-time consumers should use STANDARD to minimize serialization overhead; backtesting, monitoring, and debugging pipelines should use FULL. The verbosity level should be logged in the output metadata so that the absence of certain diagnostic fields in archived records is explicitly traceable to a configuration choice rather than a data loss event.

8.4 Raw Feature Values
Raw feature values should be included in the output, but as a conditionally emitted sub-object, not as top-level fields, and with strict controls on what "raw" means in this context.
The case for inclusion: Raw features are essential for reproducibility — without them, it is impossible to audit a historical regime label without reconstructing the exact input data and feature engineering pipeline as it existed at that moment. They are necessary for model monitoring (detecting input distribution drift before it manifests as regime label drift), for debugging disagreements between the module's output and a consumer's intuition, and for training any downstream model that takes regime features as inputs rather than regime labels.
The case for controlled inclusion: Emitting all raw features in every record doubles or triples the output payload size. Real-time consumers on hot paths do not need raw features; they need the label and confidence. Storing raw features at every observation in a production time series database is expensive and operationally complex. The solution is conditional emission, not omission.
features sub-object design:
features is emitted only when a configuration flag include_raw_features is true. When false, the field is absent from the serialized output entirely — not null, not empty — to avoid consumer-side null checks on a deliberately omitted field.
The sub-object contains two categories:
normalized_features: Dict[str, float]

The normalized (post-transformation, pre-threshold) value of each indicator used in regime classification. These are the values that actually drove the regime decision — normalized to the same scale used in threshold comparison. Mandatory within the sub-object if include_raw_features is true.
raw_features: Dict[str, float]

The pre-normalization values of each indicator in their native units (e.g., ADX on its 0–100 scale, realized volatility as an annualized percentage). These are useful for external validation and cross-system comparison but should not be used to reproduce threshold decisions — normalized_features is the correct field for that. Conditionally mandatory within the sub-object, controlled by a secondary flag include_unnormalized_features (default: false in production, true in backtesting mode).
feature_snapshot_timestamp: datetime (UTC)

The timestamp of the most recent input data point used to compute these feature values. Should equal timestamp in normal operation; any divergence indicates staleness in one or more input feeds and must trigger a DATA_QUALITY_WARNING.
imputed_features: List[str]

List of feature names for which the value was imputed (e.g., due to missing data) rather than computed from live input. An empty list when all features are fully observed. Downstream consumers using raw features for model training must filter out records with non-empty imputed_features lists or apply appropriate imputation-aware handling.
Schema versioning for features: The set of features and their names must be versioned alongside the module. A feature_schema_version field within the features sub-object records the schema version active at computation time. This is separate from calibration_version because feature definitions change on code deployments, not calibration cycles. Without this versioning, a historical dataset containing raw features from multiple module versions is uninterpretable without external documentation.

---

# 9. Logging

...
9.1 Events to Log
Logging must be event-driven, not purely time-driven. Emitting a log record on every observation tick conflates monitoring with data storage and produces volumes that are operationally unmanageable at scale. The correct design separates three distinct logging concerns — state change events, periodic health telemetry, and diagnostic traces — each with different retention, verbosity, and routing requirements.
Category 1 — Regime State Change Events

These are the highest-priority log records and must be emitted synchronously before the output object is released to downstream consumers. Any failure to write a state change log must block output emission and trigger an alerting path; a regime transition that occurred without a log record is an audit failure.
Events in this category:

Confirmed regime transition (from any regime to any regime)
Candidate transition opened (a potential transition has begun accumulating confirmations)
Candidate transition aborted (a candidate that was in progress was invalidated before confirmation)
Regime epoch closed (the prior regime's closing record, complementary to the transition open record)
Duration lock engaged (a transition was suppressed due to minimum duration enforcement)
Duration lock released (minimum duration elapsed; transition evaluation resumed)
Oscillation suppression activated
Oscillation suppression deactivated
Crisis regime entered (always logged as a distinct event type regardless of the general transition log, for routing to high-priority alert channels)
Crisis regime exited

Category 2 — System State Change Events

These track changes to the module's operational configuration and calibration state, not its market assessment. Mandatory for audit and reproducibility.
Events in this category:

Module initialization completed (records initial configuration, calibration artifact versions, and first regime label)
Adaptive recalibration completed (records old and new threshold values, calibration window dates, and any indicators whose weights changed materially)
Structural break detected
Structural break cleared
Data quality degradation (score crosses below the configured warning floor)
Data quality restored
Input feed staleness detected (any input feed has not updated within its expected interval)
Input feed restored
Configuration change applied (records the before and after values of any modified parameter)

Category 3 — Periodic Health Telemetry

Emitted on a fixed schedule regardless of state changes. Provides a heartbeat and baseline against which anomaly detection can operate. Frequency: configurable per environment (default: every observation period in development, every 15 minutes in production real-time, every computed bar in backtesting mode).
Records in this category:

Confidence score and tier at current observation
All status_flags active at emission time
Transition candidate status (none, or candidate regime with confirmation count)
Data quality score
Feature computation latency (wall-clock time to compute all indicators)
Input feed freshness (age of most recent data point per feed)

Category 4 — Diagnostic Traces

High-verbosity records emitted only in debug mode or when explicitly triggered by a diagnostic request. Never enabled by default in production to avoid I/O overhead. These records include full feature values, all indicator votes, the complete confidence factor breakdown, and the threshold evaluation trace for a single observation. They are the equivalent of a step-through debugger for a single bar.

9.2 Regime Transition Log Content
Every confirmed regime transition event must produce a self-contained log record — complete enough to reconstruct the circumstances of the transition without querying any other system. A transition log that requires joining against a feature store, a configuration database, or a prior log record to be interpretable is incomplete.
Mandatory fields for every transition log record:
Identity and timing:

event_type: "REGIME_TRANSITION_CONFIRMED", event_id: UUID, instrument_id, timestamp (observation time of the transition), computation_timestamp (wall-clock), bar_type, module_version, calibration_version
Transition description:

from_regime, from_regime_epoch_id, from_regime_entry_timestamp, from_regime_duration_periods, to_regime, to_regime_epoch_id (newly generated UUID for the new epoch), transition_trigger (controlled vocabulary code from Section 8.1), transition_direction: Enum[ESCALATION, DE-ESCALATION, LATERAL] — whether the new regime represents greater market stress, lesser, or a lateral shift (e.g., trending-up to trending-down)
Confirmation record:

confirmation_periods_required, confirmation_periods_elapsed, confirmation_period_timestamps: List[datetime] — the timestamps of each confirmation period that contributed to meeting the confirmation requirement. This allows post-hoc verification that the confirmation window was clean and not contaminated by a suppressed dissent.
Signal state at transition:

primary_signal_value_at_transition (normalized), primary_signal_threshold_used, primary_signal_margin, secondary_signal_agreement_count, secondary_signal_total_count, confidence_at_transition, regime_entropy_at_transition, probability_of_new_regime_at_transition, probability_of_prior_regime_at_transition
Hysteresis record:

entry_threshold_used, exit_threshold_applicable_to_new_regime (the threshold that would trigger exit from the regime just entered), hysteresis_band_width
Context:

volatility_regime_at_transition, macro_context_flag_at_transition, active_status_flags_at_transition: List[str], data_quality_score_at_transition
Suppression history during this transition:

prior_candidate_abort_count: int — how many times a transition to this regime was attempted and aborted before this confirmation succeeded. A value greater than zero is a signal of borderline conditions and should increase scrutiny of the transition in monitoring.

9.3 Structured JSON Logging
Yes — all log records must use structured JSON. Unstructured or semi-structured log formats (formatted strings, mixed key-value pairs, ad hoc text) are not acceptable in a production-grade module whose logs feed monitoring pipelines, alerting systems, and audit queries.
Schema enforcement: Every log record must validate against a versioned JSON Schema before emission. Schema violations must fail loudly — a log record that does not conform to its schema must not be silently emitted as a best-effort record. The schema version must appear as a top-level field in every record: "log_schema_version": "2.1.0". This allows log consumers to handle schema migrations correctly when the logging schema evolves.
Required top-level fields present in every record regardless of event type:
json{
  "log_schema_version": "2.1.0",
  "event_type": "REGIME_TRANSITION_CONFIRMED",
  "event_id": "uuid-v4",
  "service_name": "market_regime_detector",
  "module_version": "1.4.2",
  "calibration_version": "cal-2026-01-15",
  "instrument_id": "SPX",
  "timestamp": "2026-01-20T21:00:00Z",
  "computation_timestamp": "2026-01-20T21:00:00.123Z",
  "bar_type": "DAILY",
  "environment": "production",
  "hostname": "regime-svc-prod-03",
  "severity": "INFO"
}
Severity levels: Use a strict severity taxonomy. DEBUG for diagnostic traces. INFO for normal state changes (regime transitions, calibration updates, health telemetry). WARNING for degraded but operational conditions (OSCILLATION_WARNING, CALIBRATION_STALE, data quality below floor). ERROR for conditions that impair output reliability (input feed failure, schema validation failure, threshold configuration error). CRITICAL for conditions that halt output emission (total signal loss, initialization failure, unrecoverable calibration error). Severity must be a controlled enum, not a free string.
No PII or sensitive market data in logs: Log records are routed to observability infrastructure that may have broader access than the primary data pipeline. Raw price data, order flow, or position information must never appear in log records even when included in raw feature values. Normalized and percentile-mapped feature values are acceptable; absolute price levels are not.
Log routing by event category: The four event categories from 9.1 should be routed to separate log streams or topics in the observability infrastructure. State change events route to the primary audit log (long retention, immutable). Periodic health telemetry routes to a metrics sink with shorter retention. Diagnostic traces route to a debug sink with minimal retention and access-controlled read permissions. This separation prevents diagnostic verbosity from polluting the audit record.

9.4 Metrics for Monitoring
Metrics are distinct from logs. Logs record events; metrics track the ongoing health of the system as quantitative time series. The module must expose metrics via a standard interface (Prometheus exposition format recommended for compatibility) with sensible default scrape intervals and alert thresholds.
Category A — Regime State Metrics
regime_current{instrument, regime} — gauge, value 1 for the active regime label, 0 for all others. Enables regime-conditional alerting and dashboarding across instruments.
regime_confidence{instrument} — gauge, current confidence score. Alert threshold: below 0.45 sustained for more than 3 periods.
regime_entropy{instrument} — gauge, current Shannon entropy. Useful for detecting persistent boundary ambiguity.
regime_duration_periods{instrument} — gauge, periods elapsed in current regime. Unusually long or short durations signal potential classification problems.
regime_transition_total{instrument, from_regime, to_regime} — counter, incremented on each confirmed transition. Transition rate over a rolling window is the primary oscillation detection metric.
candidate_transition_active{instrument} — gauge, 1 when a candidate transition is in progress, 0 otherwise.
candidate_transition_confirmation_progress{instrument} — gauge, fraction of required confirmations met for the active candidate (0.0 if none active).
Category B — Signal Quality Metrics
data_quality_score{instrument} — gauge, current composite data quality score. Alert threshold: below 0.70.
input_feed_staleness_seconds{instrument, feed_name} — gauge, age of the most recent data point per input feed. Alert threshold: exceeds 2× expected update interval.
indicator_imputation_rate{instrument, indicator_name} — gauge, rolling fraction of recent observations where this indicator was imputed rather than computed. Alert threshold: above 0.05 (5%) sustained over 10 periods.
primary_signal_margin{instrument} — gauge, normalized distance of the primary signal from the nearest threshold. Values near zero indicate the system is operating close to a regime boundary; sustained near-zero values are a diagnostic signal even without a transition.
Category C — Calibration Health Metrics
calibration_age_days{instrument} — gauge, days since last successful recalibration. Alert threshold: exceeds recalibration_frequency + 2 business days.
threshold_drift_magnitude{instrument, threshold_name} — gauge, fractional change applied to each threshold at the most recent recalibration. Large values indicate structural drift between calibration cycles.
structural_break_active{instrument} — gauge, 1 when a structural break flag is active, 0 otherwise.
calibration_accuracy{instrument, regime} — gauge, per-regime accuracy from the most recent calibration evaluation, reflecting how well the current thresholds classify historical labeled periods.
Category D — Operational Performance Metrics
computation_latency_seconds{instrument} — histogram, wall-clock time to compute a complete output record. Alert threshold: p99 exceeds 500ms for daily-bar deployments; lower thresholds required for intraday.
output_emission_total{instrument, status} — counter, total output records emitted, labeled by whether emission was clean (status=ok), flagged (status=warned), or blocked (status=failed).
log_write_failure_total{instrument} — counter, number of log write failures. Any non-zero value requires immediate investigation; a failed log write on a transition record is an audit integrity event.
schema_validation_failure_total{instrument} — counter, number of records that failed schema validation before emission. Should always be zero in production; non-zero values indicate a code or configuration error.
Dashboard design: Expose two dashboard tiers. An operational dashboard (primary audience: on-call engineers) showing regime state heatmap across instruments, confidence and entropy trends, active flag counts, input feed health, and computation latency. An analytical dashboard (primary audience: quant researchers) showing regime transition frequency over time, confidence distribution by regime class, calibration drift history, and indicator agreement rates. The two dashboards pull from the same metrics but are filtered and arranged for their distinct audiences.

9.5 Debugging Incorrect Classifications
Incorrect classifications — where the module labels a regime that a reasonable analyst or a realized-outcome check would dispute — are the most operationally consequential failure mode. The debugging process must be systematic and the module must emit everything needed to conduct it without reconstructing computation from scratch.
The five-layer debugging framework:
Layer 1 — Reproduce the label. Verify that the label can be reproduced exactly from the logged inputs. Check module_version, calibration_version, and feature_schema_version in the output record. Retrieve the normalized_features sub-object from the output. Rerun the threshold evaluation logic against those features using the versioned module and calibration. If the label does not reproduce exactly, the problem is non-determinism or a logging gap — investigate the computation pipeline before analyzing the market.
Layer 2 — Audit the signal state. Examine regime_drivers from the diagnostics sub-object. Identify which indicators voted for the incorrect label and which dissented. Check margin_to_threshold for each driver: was the primary signal deeply in the incorrectly labeled regime, or barely over the threshold? A thin margin combined with a wrong label suggests the threshold itself is miscalibrated. A deep margin combined with a wrong label suggests the indicator is systematically wrong on this instrument or time period.
Layer 3 — Audit the confidence state. Examine confidence_factor_breakdown. Identify which factors contributed to high confidence in the incorrect label. If persistence was the dominant factor, the module was anchored to a prior regime that had become stale — check suppression_log for suppressed transitions that should have been allowed through. If indicator_agreement was dominant, examine which indicators were agreeing and whether they share a common data source or computational lineage that could have introduced correlated error.
Layer 4 — Audit the transition history. Retrieve the transition_history from diagnostics. Check prior_candidate_abort_count on the transition that established the incorrect regime: were there multiple aborted candidates before this one confirmed? If so, the confirmation logic may have been overfitted to a signal that was systematically misleading during this period. Check whether the transition into the incorrect regime occurred at a time when any status_flags were active — a transition that committed under OSCILLATION_WARNING or CALIBRATION_STALE is a known-risk decision that should have been treated more cautiously downstream.
Layer 5 — Audit the calibration artifact. Retrieve the calibration artifact identified by calibration_version. Check the calibration accuracy metric for the incorrectly assigned regime class: was this regime consistently misclassified during calibration evaluation, suggesting the threshold has been wrong for this class throughout? Check the calibration window dates: did the calibration window happen to exclude a prior historical period that was structurally similar to the period being misclassified? If so, the calibration window is too short or poorly positioned relative to the market cycle.
Tooling requirement: The module must expose a debug_replay interface that accepts a historical timestamp and instrument_id and returns the full diagnostic trace for that observation — equivalent to enabling FULL diagnostic mode retroactively for any historical record. This requires that the module store sufficient state to replay the computation at any historical point: specifically, the normalized feature values, the threshold set, the indicator weights, and the confidence factor values at that timestamp. These replay inputs should be stored in a dedicated debug artifact store with a configurable retention period (default: 90 days). Without this interface, debugging a misclassification reported after the fact requires manual reconstruction of historical state, which is slow, error-prone, and often impossible when adaptive thresholds have since been recalibrated.
Systematic misclassification detection: Beyond debugging individual cases, the observability system should run a continuous retrospective accuracy check: compare regime labels emitted at time T against a realized-outcome signal computed at time T+N (e.g., subsequent realized volatility, subsequent trend persistence). Persistent divergence between emitted labels and realized outcomes for a specific regime class is the earliest warning that systematic miscalibration is accumulating. This check should emit its own metric realized_accuracy_rolling{instrument, regime} and alert when it drops below the calibration-time accuracy baseline by more than a configurable tolerance (default: 0.08, i.e., 8 percentage points).

---

# 10. Module Architecture

...
10.1 Public Interface
The public interface is the contract between the regime detection module and every consumer in the trading system. It must be minimal, stable, and expressive — minimal so that consumers are not coupled to internal implementation details, stable so that internal refactors do not break callers, and expressive so that the full richness of the module's output is accessible without requiring consumers to call multiple methods or reconstruct derived values.
The interface is organized into three layers: the primary detector class, supporting data classes that form the type contract, and a factory function for standard construction.
Primary class: MarketRegimeDetector
pythonclass MarketRegimeDetector:
    """
    Stateful, single-instrument market regime detector.

    One instance per instrument. Thread-safe for concurrent reads;
    write operations (update) acquire an internal lock.
    Not safe for concurrent calls to update() from multiple threads.
    """

    def __init__(
        self,
        instrument_id: str,
        config: RegimeDetectorConfig,
        calibration: CalibrationArtifact,
        clock: Clock | None = None,  # resolved to SystemClock() inside __init__ if None
        logger: StructuredLogger | None = None,
    ) -> None: ...

    def update(
        self,
        bar: MarketBar,
    ) -> MarketRegime:
        """
        Consume one observation and return the current regime assessment.

        The primary entry point for live and backtesting use. Advances
        internal state, evaluates all transition logic, emits log events,
        and returns a fully-populated MarketRegime object.

        Args:
            bar: A validated MarketBar containing OHLCV and any
                 auxiliary fields required by configured indicators.

        Returns:
            MarketRegime: The current regime assessment after
                          incorporating this observation. Never None.

        Raises:
            DataQualityError: If bar fails validation and
                              config.strict_data_validation is True.
            StaleInputError:  If bar.timestamp is not strictly after
                              the last processed timestamp.
        """
        ...

    def update_batch(
        self,
        bars: Sequence[MarketBar],
        *,
        progress: bool = False,
    ) -> list[MarketRegime]:
        """
        Process a sequence of bars in chronological order.

        Preserves all state transitions across the sequence exactly
        as sequential update() calls would. Intended for backtesting
        and historical initialization. Returns one MarketRegime per
        bar in input order.

        Args:
            bars:     Sequence of MarketBar, must be strictly
                      chronologically ordered.
            progress: If True, emit a progress indicator for
                      long sequences.

        Raises:
            ChronologyError: If bars are not strictly ascending
                             in timestamp.
        """
        ...

    def current_regime(self) -> MarketRegime | None:
        """
        Return the most recently computed regime without advancing state.

        Returns None if update() has never been called. Safe to call
        from a read thread concurrently with another thread calling
        current_regime(). Not safe to call concurrently with update().
        """
        ...

    def regime_history(
        self,
        n: int | None = None,
    ) -> list[MarketRegime]:
        """
        Return recent regime records in reverse chronological order.

        Args:
            n: Maximum records to return. None returns all retained
               history up to config.history_retention_periods.

        Returns an empty list if no updates have been processed.
        """
        ...

    def recalibrate(
        self,
        calibration: CalibrationArtifact,
        *,
        effective_from: datetime | None = None,
    ) -> RecalibrationResult:
        """
        Apply a new calibration artifact to the running detector.

        Does not reset regime state or history. Thresholds and weights
        take effect from the next update() call after effective_from
        (defaults to immediately). Logs a CALIBRATION_UPDATED event.

        Args:
            calibration:    A fully validated CalibrationArtifact.
            effective_from: Optional future timestamp at which the
                            new calibration becomes active. If provided,
                            the detector buffers the incoming artifact
                            and swaps atomically at the specified time.

        Returns:
            RecalibrationResult: Summary of what changed — old vs new
                                 threshold values, weight deltas,
                                 and drift magnitudes per parameter.

        Raises:
            CalibrationValidationError: If the artifact fails
                                        internal consistency checks.
        """
        ...

    def reset(
        self,
        *,
        preserve_calibration: bool = True,
    ) -> None:
        """
        Reset all internal state to initialization values.

        Intended for use between backtesting runs or when reinitializing
        after a critical error. Logs a MODULE_RESET event.

        Args:
            preserve_calibration: If True, the current CalibrationArtifact
                                  is retained. If False, the detector
                                  reverts to the calibration supplied at
                                  construction.
        """
        ...

    def snapshot(self) -> DetectorSnapshot:
        """
        Capture a complete, serializable snapshot of internal state.

        The snapshot can be used to restore the detector to this exact
        state via MarketRegimeDetector.from_snapshot(). Intended for
        checkpointing in long-running processes and for state transfer
        between processes in distributed deployments.
        """
        ...

    @classmethod
    def from_snapshot(
        cls,
        snapshot: DetectorSnapshot,
        *,
        clock: Clock | None = None,
        logger: StructuredLogger | None = None,
    ) -> "MarketRegimeDetector":
        """
        Restore a detector from a previously captured snapshot.

        Produces a detector in exactly the state represented by the
        snapshot, including regime history, current epoch, and
        calibration artifact.
        """
        ...

    @property
    def instrument_id(self) -> str: ...

    @property
    def config(self) -> RegimeDetectorConfig: ...

    @property
    def calibration_version(self) -> str: ...

    @property
    def is_initialized(self) -> bool:
        """
        True once the minimum history required for reliable labeling
        has been accumulated (config.initialization_periods).
        """
        ...

    @property
    def status_flags(self) -> frozenset[StatusFlag]: ...
Factory function:
pythondef create_detector(
    instrument_id: str,
    config_path: Path | str,
    calibration_path: Path | str,
    *,
    warm_up_bars: Sequence[MarketBar] | None = None,
    clock: Clock | None = None,
    logger: StructuredLogger | None = None,
) -> MarketRegimeDetector:
    """
    Standard factory for production and backtesting use.

    Loads and validates config and calibration from disk, constructs
    the detector, and optionally warms it up with historical bars so
    that the first call to update() returns a fully initialized regime
    rather than an INITIALIZATION_PERIOD result.

    Raises:
        ConfigValidationError:       If config file fails schema
                                     validation.
        CalibrationValidationError:  If calibration artifact is
                                     malformed or expired.
        ChronologyError:             If warm_up_bars are not strictly
                                     ascending.
    """
    ...
Key interface design decisions worth making explicit:
The interface is deliberately instrument-scoped. One MarketRegimeDetector instance manages one instrument. Multi-instrument orchestration is the caller's responsibility — a RegimeDetectorRegistry or similar container lives outside this module. This keeps the core class simple, testable, and free of cross-instrument coupling.

> **OPEN ISSUE (pending scope decision):** Section 3, Q5 describes the module's core compute unit as "a symbol registry with a shared feature computation graph, not N independent single-symbol instances," with cross-asset features computed once and shared across instruments. The fully independent, per-instrument `MarketRegimeDetector` design above does not implement that shared computation graph. Resolving this requires a project-scope decision (see also the open issue on Section 3, Q5 and Section 10.5) and is intentionally left unresolved in this revision rather than redesigned unilaterally.
update() returns a MarketRegime synchronously. Async variants should be thin wrappers (async_update() calling update() in an executor) rather than reimplementing the core logic asynchronously. The regime computation itself is CPU-bound and should not be awaited within an async event loop.
The Clock dependency injection enables deterministic testing: pass a MockClock in tests to control wall time without monkeypatching. SystemClock is the default for production. This pattern must be established at construction rather than accessed via datetime.now() inside methods, which is untestable.

10.2 Stateful vs. Stateless Design
The detector must be stateful. This is not a preference — it is an architectural requirement imposed by the logic specified in preceding sections.
Hysteresis (Section 6.2) requires knowing the current regime to evaluate whether an exit threshold has been crossed. Consecutive confirmation counting (Section 6.3) requires a counter that persists across observations. Minimum duration enforcement (Section 6.4) requires the regime entry timestamp. Oscillation suppression (Section 6.5) requires a rolling transition counter. Persistence-adjusted confidence (Section 7.4) requires the elapsed time in the current epoch. None of these can be computed from a single observation in isolation; all require carrying forward state from prior observations.
The practical consequence is that the MarketRegimeDetector is not a pure function and must not be treated as one. Callers who serialize the detector state, restart processes, or transfer computation between machines must use snapshot() and from_snapshot() to preserve continuity. Failing to do so produces incorrect regime labels from the first post-restart observation, because the new instance begins in the initialization state with no regime history.
Internal state managed by the detector:
python@dataclass
class _DetectorState:
    # Current regime epoch
    current_regime: RegimeLabel
    current_regime_epoch_id: UUID
    current_regime_entry_timestamp: datetime
    current_regime_duration_periods: int

    # Transition logic state
    candidate_transition: CandidateTransition | None
    confirmation_counter: int
    oscillation_transition_timestamps: deque[datetime]
    oscillation_suppression_active: bool

    # Confidence and persistence state
    persistence_periods_elapsed: int
    previous_regime: RegimeLabel | None
    previous_regime_duration_periods: int

    # Signal history for stability factor computation
    primary_signal_history: deque[float]

    # Calibration and system state
    active_status_flags: set[StatusFlag]
    last_processed_timestamp: datetime | None
    initialization_periods_remaining: int

    # Retained output history
    regime_history: deque[MarketRegime]
    transition_history: deque[TransitionRecord]
State mutation discipline: All state mutations must occur within a single method (_commit_state_update()) called once per update() invocation, after all evaluation logic has completed. No indicator computation, threshold comparison, or confidence calculation method should mutate state as a side effect. This discipline is essential for testability — it means evaluation logic can be exercised against any arbitrary state without risk of unintended state modification — and for correctness in the presence of evaluation errors (an exception mid-evaluation must not leave state partially updated).
State immutability of outputs: The MarketRegime objects returned by update() and stored in history are immutable after construction. They must be frozen dataclasses or NamedTuple instances. Mutable output objects that could be modified by a caller post-return would corrupt the module's internal history record.

10.3 Externally Configurable Parameters
Configuration must be fully externalizable and validated at load time through a typed schema. No parameter that affects regime classification behavior should be hardcoded. The complete configuration schema, organized by subsystem:
yaml# regime_detector_config.yaml

instrument:
  instrument_id: "SPX"
  bar_type: "DAILY"                     # DAILY | HOURLY | WEEKLY | CUSTOM
  asset_class: "EQUITY_INDEX"           # Informs default calibration choices

initialization:
  initialization_periods: 63            # Bars required before exiting UNKNOWN
  warm_up_strict_mode: true             # Raise on insufficient warm-up data

trend:
  indicator: "ADX"                      # ADX | MA_SLOPE | MOMENTUM_ZSCORE
  calibration_window_days: 504
  entry_percentile: 60
  exit_percentile: 45
  min_dwell_periods: 3
  confirmation_periods_ranging_to_weak: 3
  confirmation_periods_weak_to_strong: 2
  confirmation_periods_trending_to_ranging: 4
  hysteresis_band_multiplier: 1.5       # Band = multiplier × signal stddev

volatility:
  calibration_window_days: 504
  low_percentile: 33
  high_percentile: 67
  crisis_percentile: 90
  min_dwell_periods: 3
  confirmation_periods_low_to_normal: 2
  confirmation_periods_normal_to_high: 2
  confirmation_periods_high_to_normal: 5
  confirmation_periods_any_to_crisis: 1
  confirmation_periods_crisis_to_any: 7
  absolute_vol_floor: 0.05              # 5% annualized
  absolute_vol_ceiling: 1.50            # 150% annualized
  garch_disagreement_tolerance: 0.40
  crisis_exit_requires_percentile: 67   # Must fall to P67 to exit crisis

confidence:
  weights:
    signal_margin: 0.25
    indicator_agreement: 0.25
    persistence: 0.15
    base_rate: 0.10
    signal_stability: 0.10
    macro_alignment: 0.10
    calibration_recency: 0.05
  persistence_p_max_default: 0.20
  calibration_recency_floor: 0.85
  dissent_amplification_factor: 0.60
  dissent_penalty_cap: 0.50
  minimum_signal_confidence_for_persistence: 0.40

thresholds:
  max_adaptive_drift_per_cycle: 0.15
  structural_break_sensitivity: 0.05    # KS-test p-value threshold
  conflict_max_duration_periods: 3
  conflict_default_regime: "RANGING"    # Regime assigned on unresolved even-split

oscillation:
  detection_window_periods: 21
  max_transitions_before_suppression: 3
  suppression_additional_confirmations: 1

adaptive_recalibration:
  enabled: true
  frequency: "weekly"                   # daily | weekly | monthly
  min_history_days: 126
  suppress_during_crisis: true
  suppress_during_structural_break: true

output:
  include_raw_features: false
  include_unnormalized_features: false
  diagnostics_verbosity: "STANDARD"     # STANDARD | FULL | NONE
  history_retention_periods: 252

data_quality:
  strict_data_validation: true
  quality_warning_floor: 0.70
  max_input_staleness_seconds: 7200
  imputation_allowed: true
  max_imputation_fraction: 0.05

logging:
  log_level: "INFO"
  emit_health_telemetry: true
  telemetry_frequency_periods: 1
  diagnostic_trace_enabled: false
  transition_log_synchronous: true      # Block output until log written
Configuration validation rules enforced at load time:

exit_percentile must be strictly less than entry_percentile for all threshold pairs
All confidence weights must sum to 1.0 (±0.001 tolerance for float precision)
confirmation_periods_any_to_crisis must equal 1 and is not overridable to a higher value
crisis_exit_requires_percentile must be less than or equal to high_percentile
max_adaptive_drift_per_cycle must be in (0.0, 0.50]
absolute_vol_floor must be strictly positive
absolute_vol_ceiling must be greater than absolute_vol_floor
All min_dwell_periods values must be positive integers

Any configuration that fails validation raises ConfigValidationError with a structured error message enumerating all failing rules, not just the first one encountered.

10.4 External Service Dependencies
The module should be designed for maximum operational independence. Every external dependency introduces a failure mode: a service that is unavailable, slow, or returning corrupt data can degrade or halt regime detection, which is a core risk management function that must operate even under adverse conditions. Dependencies must be justified individually and each must have a defined degradation path.
Tier 1 — Required dependencies (module cannot function without them):
Market data feed. The module requires OHLCV bar data. This is provided via the MarketBar input to update() — it is injected by the caller rather than fetched internally. The module has no direct network dependency on the market data provider; it is the caller's responsibility to source and validate data before passing it in. If a bar is unavailable, the caller decides whether to skip the period, impute, or raise before calling update(). Once a bar is passed to update(), the module applies its own internal staleness/imputation policy (Section 3, Q4) to the features derived from that bar, independent of how the caller sourced the bar itself.
Tier 2 — Optional dependencies (module degrades gracefully without them):
Calibration artifact store. At initialization the module loads a CalibrationArtifact from disk or an object store. If this is unavailable, the module falls back to hardcoded default thresholds (see Section 5.6) and sets CALIBRATION_STALE immediately. It can still emit regime labels at reduced confidence. The calibration store is not polled continuously; it is accessed only at initialization and during scheduled recalibration cycles.
GARCH model service. If a GARCH conditional volatility estimate is configured as a secondary volatility signal, it may come from an external model service. The module must tolerate the absence of this signal by excluding the GARCH term from confidence calculation and flagging REDUCED_CONFIDENCE. The GARCH service is never on the critical path for primary regime labeling.
Macro context service. The macro overlay (risk-on/risk-off flag, VIX level, credit spread regime) is an optional confidence modifier. If the service is unavailable, the macro alignment factor is treated as neutral (contributes zero to confidence adjustment). Regime labels continue without interruption.
Metrics sink. Prometheus or equivalent metrics exposition. Failure to write metrics must never affect regime computation or output emission. Metrics writes are fire-and-forget with a local buffer; failures are counted locally and emitted when the sink recovers.
Log sink. As established in Section 9.3, transition log writes are synchronous and must succeed before output is emitted. All other log writes (health telemetry, diagnostic traces) are asynchronous with a configurable local buffer. If the log sink is unreachable for transition events, the module holds output emission and retries with a configurable timeout (default: 2 seconds, 3 attempts). If all retries fail, the module writes to a local fallback log file, sets LOG_SINK_DEGRADED in status flags, and proceeds with output emission. It must not silently drop transition log records.
Tier 3 — No internal network calls. The module must make no HTTP requests, database queries, or message queue reads within update(). All external data must be injected at construction or via recalibrate(). This constraint ensures that update() latency is bounded by local computation only, and that the module can be tested in complete isolation without network mocking.
Dependency injection pattern: All Tier 2 services are provided to the constructor as optional protocol-typed interfaces, defaulting to None (which activates the graceful degradation path) or to local no-op implementations:
pythonclass MarketRegimeDetector:
    def __init__(
        self,
        instrument_id: str,
        config: RegimeDetectorConfig,
        calibration: CalibrationArtifact,
        clock: Clock | None = None,  # resolved to SystemClock() inside __init__ if None
        logger: StructuredLogger | None = None,
        garch_provider: GarchProvider | None = None,
        macro_provider: MacroContextProvider | None = None,
        metrics_sink: MetricsSink | None = None,
    ) -> None: ...
This pattern ensures that unit tests, backtests, and paper trading deployments can run the full module logic without any external services, while production deployments inject live implementations through their dependency injection framework of choice.

10.5 Integration with the Trading System
The module is a producer of regime state. It does not consume strategy signals, positions, or orders. Its integration surface is deliberately narrow: it receives market data and emits MarketRegime objects. Everything else — routing those objects to consumers, persisting them, alerting on them — is the trading system's responsibility, not the module's.
Integration pattern: push-based event emission
In a live trading system, the primary integration mechanism is an event bus or message broker (Kafka, Redis Streams, or an internal pub/sub system). The regime detector publishes MarketRegime events to a dedicated topic per instrument on each update() call. Downstream consumers (strategy engines, risk engines, position sizers, monitoring dashboards) subscribe independently. This decoupling ensures that a slow consumer cannot block regime computation and that new consumers can be added without modifying the detector.
MarketDataFeed
      │
      ▼
 [Ingestion Layer]
      │  MarketBar
      ▼
MarketRegimeDetector
      │  MarketRegime
      ├──────────────────► Regime Event Bus (per instrument topic)
      │                          │
      │                          ├──► Strategy Engine
      │                          ├──► Risk Engine
      │                          ├──► Position Sizer
      │                          └──► Monitoring / Dashboard
      │
      └──────────────────► Audit Log Sink (synchronous, transition events)
Integration pattern: pull-based registry for synchronous consumers
Strategies or risk checks that need the current regime synchronously within their own computation cycle should not consume from the event bus — that introduces latency uncertainty and ordering complexity. Instead, a RegimeDetectorRegistry provides a synchronous, in-process read interface:
pythonclass RegimeDetectorRegistry:
    """
    In-process registry of MarketRegimeDetector instances.
    Provides synchronous regime reads for strategy and risk consumers.
    """

    def register(
        self,
        detector: MarketRegimeDetector,
    ) -> None: ...

    def current_regime(
        self,
        instrument_id: str,
    ) -> MarketRegime | None: ...

    def current_confidence(
        self,
        instrument_id: str,
    ) -> float | None: ...

    def all_regimes(self) -> dict[str, MarketRegime]: ...

    def update_all(
        self,
        bars: dict[str, MarketBar],
    ) -> dict[str, MarketRegime]:
        """
        Advance all registered detectors with one bar each.
        Intended for synchronized multi-instrument updates at bar close.
        """
        ...
The registry holds references to live MarketRegimeDetector instances. It does not copy or cache regime state — current_regime() delegates directly to the detector's current_regime() property, ensuring that reads always reflect the most recently committed state.
Integration with the backtesting engine:
The backtesting integration uses update_batch() on a pre-loaded bar sequence. The regime detector must produce bit-for-bit identical labels in backtesting and live operation given the same input sequence and calibration artifact. Any divergence between live and backtest regime labels for the same bar is a critical reproducibility failure. To enforce this:

The backtesting engine must pass the same CalibrationArtifact that was active at the historical time being replicated, not the current artifact.
The Clock injected into the backtesting instance must be a ReplayClock that advances according to bar timestamps, not wall time, so that any time-dependent logic (e.g., recalibration scheduling) behaves as it would have historically.
The backtesting engine must call reset() between independent simulation runs to prevent state leakage.

Integration with the risk engine:
The risk engine is a high-priority consumer that uses regime state to set position limits, margin requirements, and drawdown thresholds. Its integration requirements are stricter than strategy consumers:

The risk engine must consume regime updates synchronously before any order validation for the same bar period. The event ordering guarantee must be enforced by the integration layer.
The risk engine must act on confidence_tier — during VERY_LOW or LOW confidence, risk limits should fall back to conservative defaults rather than regime-specific values. The regime module makes this easy by providing the tier explicitly; the risk engine must consume it.
The risk engine must subscribe to status_flags changes independently of regime label changes. A transition from empty flags to STRUCTURAL_BREAK_DETECTED is a risk event even if the regime label itself has not changed.

Integration with strategy selection:
Strategies that switch behavior by regime should consume regime_probability_distribution rather than primary_regime alone wherever their logic permits. Hard regime-conditional switching (full allocation to one strategy when trending, zero otherwise) amplifies the impact of misclassification at boundaries. Strategies that blend allocations proportional to regime probabilities produce smoother transitions and are less sensitive to the precise location of threshold boundaries — which are inherently uncertain. The module provides the full distribution to enable this; strategy authors should be guided to use it.
Deployment topology:
In production, each instrument's detector runs in a dedicated thread or lightweight process within a regime service. The service is horizontally scalable by instrument shard. It exposes the RegimeDetectorRegistry interface internally and the event bus topic externally. It does not share state between instrument detectors — cross-instrument correlation logic, if required, is a separate higher-order service that consumes from multiple instrument topics and maintains its own state.

> **OPEN ISSUE (pending scope decision):** As noted in Section 10.1, this topology does not implement the shared feature computation graph described in Section 3, Q5. Whether cross-instrument features (correlation matrices, breadth, aggregate regime) are computed by a separate higher-order service (as stated here) or by a shared component referenced directly by each detector (as Section 3, Q5 implies) is an open architectural question pending a project-scope decision, not resolved in this revision.

---

# 11. Testing Strategy

...
11.1 Required Unit Tests
Unit tests must cover every computational layer of the module in isolation. Each test class targets a single component with all dependencies either injected as fakes or driven from controlled fixture data. No unit test may perform network I/O, file I/O outside of fixture loading, or sleep. The full unit suite must complete in under 60 seconds on a standard development machine.
The test suite is organized into six component groups.

Group 1 — Configuration and Validation
TestRegimeDetectorConfig
├── test_valid_config_loads_without_error
├── test_exit_percentile_exceeds_entry_percentile_raises
├── test_confidence_weights_not_summing_to_one_raises
├── test_crisis_confirmation_overridden_above_one_raises
├── test_vol_floor_exceeds_ceiling_raises
├── test_all_validation_errors_reported_simultaneously
├── test_missing_required_field_raises_with_field_name
├── test_optional_fields_default_correctly
└── test_config_is_immutable_after_construction
Configuration validation is the cheapest and most frequently triggered failure mode in production. Every validation rule enumerated in Section 10.3 must have a corresponding negative test that confirms the exact exception type and that the error message identifies the offending field by name.

Group 2 — Feature Computation
One test class per indicator. Shown here for ADX; the same structure applies to all configured indicators.
TestAdxIndicator
├── test_output_range_bounded_zero_to_hundred
├── test_known_value_against_reference_implementation
├── test_insufficient_history_returns_none
├── test_exactly_sufficient_history_returns_value
├── test_all_same_prices_returns_zero_adx
├── test_monotone_increasing_prices_returns_high_adx
├── test_normalization_maps_to_unit_interval
├── test_normalization_stable_across_calibration_window_sizes
├── test_imputed_bar_flagged_in_output
└── test_nan_input_raises_data_quality_error

TestVolatilityIndicator
├── test_realized_vol_annualization_correct
├── test_garch_unavailable_falls_back_to_realized
├── test_garch_disagreement_above_tolerance_sets_flag
├── test_percentile_mapping_monotone
├── test_percentile_mapping_stable_at_boundary_values
├── test_crisis_percentile_threshold_correctly_applied
└── test_vol_floor_and_ceiling_guards_applied

TestIndicatorRegistry
├── test_all_configured_indicators_instantiated
├── test_unavailable_indicator_excluded_from_vote
├── test_indicator_weight_renormalization_on_exclusion
└── test_cluster_independence_grouping_correct
Reference values for test_known_value_against_reference_implementation must be computed using a trusted external library (e.g., TA-Lib or pandas-ta) on a fixed synthetic price series defined in a fixture file. The fixture and the expected output must both be committed to version control so that the reference is stable and reviewable.

Group 3 — Threshold Evaluation
TestThresholdEvaluator
├── test_signal_above_entry_threshold_votes_trending
├── test_signal_below_exit_threshold_votes_ranging
├── test_signal_between_exit_and_entry_preserves_current_regime
├── test_signal_at_exactly_entry_threshold_votes_trending
├── test_signal_at_exactly_exit_threshold_preserves_current
├── test_hysteresis_band_width_computed_correctly
├── test_adaptive_threshold_applied_after_recalibration
├── test_adaptive_threshold_not_applied_during_suppression
├── test_drift_cap_enforced_on_large_calibration_update
├── test_absolute_floor_prevents_zero_threshold
├── test_absolute_ceiling_prevents_extreme_threshold
├── test_percentile_computed_correctly_on_known_distribution
└── test_percentile_stable_at_window_boundary
The between-threshold test (test_signal_between_exit_and_entry_preserves_current_regime) must be run twice: once with the detector in a trending regime (expecting preservation of trending) and once in a ranging regime (expecting preservation of ranging). This is the canonical hysteresis correctness test.

Group 4 — State Transition Logic
This is the largest and most critical group. Every transition path in the state machine must have a dedicated test.
TestConfirmationCounter
├── test_counter_increments_on_consecutive_signal
├── test_counter_resets_on_single_period_retreat
├── test_transition_commits_at_exactly_required_count
├── test_transition_does_not_commit_one_period_early
├── test_different_required_counts_per_transition_type
└── test_candidate_exposed_in_output_during_confirmation

TestDurationLock
├── test_transition_suppressed_before_minimum_duration
├── test_transition_permitted_at_exactly_minimum_duration
├── test_crisis_entry_bypasses_duration_lock
├── test_duration_lock_flag_set_in_status_flags
├── test_duration_periods_counted_correctly_across_bar_types
└── test_duration_lock_log_event_emitted

TestOscillationSuppression
├── test_suppression_activates_at_threshold_transition_count
├── test_suppression_raises_confirmation_requirement
├── test_suppression_deactivates_when_rate_drops
├── test_oscillation_warning_flag_set
└── test_suppression_window_is_rolling_not_cumulative

TestHysteresis
├── test_entry_from_ranging_requires_entry_threshold
├── test_exit_from_trending_requires_exit_threshold
├── test_signal_in_band_preserves_ranging
├── test_signal_in_band_preserves_trending
├── test_asymmetric_crisis_band_harder_to_exit
└── test_hysteresis_state_preserved_across_serialization

TestConflictResolution
├── test_minority_dissent_applies_confidence_penalty
├── test_even_split_defers_transition
├── test_even_split_assigns_default_regime_after_timeout
├── test_magnitude_conflict_sets_reduced_confidence_flag
├── test_scale_conflict_assigns_conservative_regime
├── test_conflict_state_exposed_in_output
└── test_high_precision_dissenter_applies_larger_penalty
Each state transition test must construct the detector with an explicit initial state (using from_snapshot() with a crafted DetectorSnapshot) rather than driving it to the target state through a long sequence of bars. Building up state through a sequence couples the test to the sequence's intermediate behavior; direct state injection isolates the behavior under test.

Group 5 — Confidence Calculation
TestConfidenceComposite
├── test_deep_in_regime_produces_high_confidence
├── test_near_threshold_produces_low_confidence
├── test_all_factors_weighted_correctly
├── test_weights_renormalized_when_factor_unavailable
├── test_unavailable_macro_provider_neutral_contribution
├── test_calibration_recency_decays_linearly
├── test_composite_bounded_in_zero_one
├── test_composite_never_reaches_one
└── test_calibrated_score_matches_isotonic_mapping

TestPersistenceFactor
├── test_zero_at_regime_entry
├── test_grows_toward_p_max_asymptotically
├── test_regime_specific_time_constants_applied
├── test_zeroed_when_signal_confidence_below_floor
├── test_resets_immediately_on_regime_transition
└── test_crisis_p_max_lower_than_other_regimes

TestIndicatorAgreement
├── test_all_agree_produces_maximum_agreement_score
├── test_all_dissent_produces_minimum_agreement_score
├── test_high_precision_dissenter_penalizes_more_than_low
├── test_correlated_indicators_clustered_not_double_counted
├── test_dissent_penalty_capped
└── test_precision_weights_loaded_from_calibration_artifact

TestUncertaintyRepresentation
├── test_full_distribution_sums_to_one
├── test_all_regime_classes_present_in_distribution
├── test_entropy_zero_for_certain_label
├── test_entropy_maximum_for_uniform_distribution
├── test_aleatoric_flag_when_top_two_within_tolerance
├── test_epistemic_flag_when_status_flags_active
├── test_confidence_interval_contains_point_estimate
└── test_confidence_tier_boundary_values_correct

Group 6 — Output Schema and Serialization
TestMarketRegimeSchema
├── test_all_mandatory_fields_present_in_output
├── test_conditional_mandatory_fields_present_when_required
├── test_conditional_mandatory_fields_null_when_not_required
├── test_output_validates_against_json_schema
├── test_serialization_roundtrip_produces_identical_object
├── test_regime_epoch_id_stable_within_epoch
├── test_regime_epoch_id_changes_on_transition
├── test_computation_timestamp_after_observation_timestamp
└── test_unknown_regime_during_initialization_period

TestDetectorSnapshot
├── test_snapshot_restores_identical_state
├── test_restored_detector_produces_same_next_output
├── test_snapshot_version_recorded
├── test_snapshot_from_future_version_raises
└── test_snapshot_roundtrip_through_json

11.2 Edge Cases
Edge cases represent conditions where the module's behavior is deterministic but non-obvious. Every edge case must have a named test that documents the expected behavior as clearly as it tests it.
Data boundary conditions:

First bar ever processed: output must have primary_regime = UNKNOWN, is_initialized = False, all history fields null, INITIALIZATION_PERIOD in status flags.
Bar at exactly the initialization boundary: the bar that completes the minimum history must produce the first non-UNKNOWN label.
Two bars with identical timestamps: must raise StaleInputError — equal timestamps are not strictly ascending.
Bar with timestamp before the last processed timestamp: must raise StaleInputError regardless of how small the regression.
Bar with all zero volume: must set DATA_QUALITY_WARNING; computation must not divide by zero.
Bar with OHLC inconsistency (low > high, close outside high/low): must raise DataQualityError when strict_data_validation = True, set flag and proceed when False.
Bar with NaN in any OHLCV field: must raise DataQualityError; NaN must not propagate into indicator computation.
Extremely large price values (e.g., BTC at 10^9): normalization must not overflow float64.
Extremely small price values (e.g., a penny stock): realized volatility computation must not produce infinity.

Threshold and calibration boundary conditions:

Signal at exactly the entry threshold: must trigger a transition candidate, not be rounded either way by floating-point comparison. Threshold comparisons must use >= for entry consistently.
Signal at exactly the exit threshold: must be treated as still inside the regime (exit requires strictly below).
Calibration window contains fewer distinct observations than the percentile computation requires: must use available data and flag CALIBRATION_STALE.
Recalibration produces a threshold change that exactly equals max_adaptive_drift_per_cycle: must be accepted.
Recalibration produces a threshold change exceeding the cap: must be clamped to the cap, not rejected.
CalibrationArtifact with an expiry timestamp in the past: must set CALIBRATION_STALE immediately on load.

State machine boundary conditions:

Regime transition attempted during duration lock: must be suppressed, must log a DURATION_LOCK event, must not advance the confirmation counter.
Confirmation counter reaches required count on the same bar that the duration lock expires: transition must commit — the two conditions are independent and must not block each other.
Crisis entry while oscillation suppression is active: crisis entry must proceed immediately; oscillation suppression must not delay crisis capture under any circumstances.
recalibrate() called while a candidate transition is in progress: the candidate must be re-evaluated against the new thresholds before the next update(). If the candidate no longer qualifies under new thresholds, it must be aborted and logged.
reset() called while a candidate transition is in progress: the candidate must be discarded cleanly with no partial state retained.
update_batch() with a sequence that crosses a calibration recalibration boundary: the recalibration must apply at the correct bar, not at the start or end of the batch.

Concurrent access conditions:

current_regime() called from a read thread while update() is executing in the write thread: must return either the pre-update or post-update regime, never a partially updated intermediate state.
recalibrate() called while update() is executing: must not corrupt either operation; the calibration swap must be atomic with respect to the update cycle.
Multiple calls to snapshot() in rapid succession: must produce identical snapshots if no update() has occurred between them.

Confidence and uncertainty edge cases:

All indicators unavailable (total signal loss): confidence must be 0.0 exactly, primary_regime must be set to UNKNOWN, UNKNOWN regime logged.
Single indicator available (all others missing): weight renormalization must produce a well-defined confidence; must not divide by zero.
Regime probability distribution where the top two probabilities are exactly equal: must select deterministically (by enum ordinal or configured tiebreak rule, not by dict iteration order).
Persistence factor at exactly minimum_signal_confidence_for_persistence floor: persistence must be zeroed; at one epsilon above the floor, persistence must be applied.


11.3 Historical Data Validation
Historical validation answers a question unit tests cannot: does the module produce regime labels that are meaningful against real market behavior? This layer uses actual market data and requires separate infrastructure from the unit test suite — it is not run on every commit, but is run before every production release and after any material change to threshold logic or confidence calculation.
Dataset requirements:
The validation dataset must span a minimum of 20 years of daily bars for at least three instruments representing distinct asset classes and microstructures. Recommended: SPX (large-cap equity index), a 10-year Treasury futures series (fixed income), and a major FX pair (EURUSD). The dataset must include at minimum one example of each of the following market episodes, with analyst-annotated ground truth labels for those episodes:

A sustained strong uptrend (e.g., 2017 equity bull run)
A sustained ranging period with well-defined support and resistance
A volatility crisis with rapid onset (e.g., March 2020, August 2015)
A volatility crisis with gradual onset (e.g., 2008 financial crisis)
A false trend signal that resolved back to ranging within 10 bars
A low-volatility suppression period (e.g., 2017)
A regime transition involving all three regime dimensions changing simultaneously

Ground truth labels are not a mechanical computation — they require human annotation by a qualified analyst who reviews price charts, realized volatility time series, and contemporaneous market commentary. Annotation disagreements between multiple annotators must be recorded; observations with annotator disagreement are excluded from accuracy metrics but retained for boundary analysis.
Validation tests run against the historical dataset:
Accuracy validation:

Compute the module's regime label for every bar in the annotated dataset using the calibration artifact that would have been active at that historical date (simulating live operation, not hindsight). Compare against ground truth labels. Required outcomes are enumerated in Section 11.4.
Transition timing validation:

For each annotated regime transition, measure the lag between the annotator-identified transition date and the module's confirmed transition date. Compute the distribution of lags. Acceptable outcomes are enumerated in Section 11.4.
False positive rate by episode type:

Compute the rate at which the module labels a trending regime during annotated ranging episodes, and vice versa. Compute separately for each episode type to identify systematic biases.
Confidence calibration validation:

Group all historical observations by confidence decile. Within each decile, compute the empirical accuracy of the label (fraction of observations where the module's label matches ground truth). Plot the calibration curve. A well-calibrated module produces a curve close to the diagonal. Measure the Expected Calibration Error (ECE) — required to be below 0.05.
Stability validation:

Run the module twice on the same historical dataset with identical configuration and calibration. Confirm that every output record is bit-for-bit identical. Any non-determinism is a defect.
Regime duration distribution validation:

Compare the distribution of regime durations produced by the module against the distribution of annotated regime durations. The module's distribution must not be systematically shorter (indicating excessive oscillation) or longer (indicating failure to capture transitions). A KS test between the two distributions must not reject at p < 0.05.
Recalibration stability validation:

Run the module in adaptive recalibration mode across the full dataset. At each recalibration point, check that the threshold values changed by less than max_adaptive_drift_per_cycle. Confirm that no recalibration event caused a retroactive relabeling of prior observations.

11.4 Acceptance Criteria
These are binary pass/fail criteria. A module that fails any one of them is not production-ready regardless of how well it satisfies the others.
Correctness criteria:

Overall regime classification accuracy against annotated ground truth is ≥ 0.75 on the full validation dataset, measured as the fraction of bars where the module's primary regime label matches the annotated label.
Per-regime accuracy for the crisis regime class is ≥ 0.85. Crisis misclassification carries asymmetric cost and requires a higher accuracy floor.
Per-regime accuracy for the ranging regime class is ≥ 0.70. Ranging is the most ambiguous class and has a lower required floor, but the floor must still be met.
False positive trending rate during annotated ranging periods is ≤ 0.15 (at most 15% of ranging bars are incorrectly labeled as trending of any kind).
False negative crisis rate during annotated crisis periods is ≤ 0.10 (the module must not miss more than 10% of crisis bars).

Transition timing criteria:

Median transition detection lag is ≤ 3 bars for crisis onset (the module must capture the start of a crisis episode within 3 daily bars in the median case).
90th percentile transition detection lag is ≤ 5 bars for crisis onset.
Median transition detection lag is ≤ 5 bars for trend onset.
The module must not produce a confirmed transition earlier than 1 bar after the annotated transition date in more than 5% of cases (early transitions indicate the confirmation logic is being bypassed or the annotated date is being leaked).

Calibration criteria:

Expected Calibration Error (ECE) across all confidence deciles is ≤ 0.05.
No single confidence decile has an empirical accuracy more than 0.12 below its nominal confidence level.
The confidence score for crisis regime labels averages ≥ 0.65 during confirmed crisis episodes.
The confidence score during the initialization period is exactly 0.0 for all UNKNOWN labels.

Stability and reproducibility criteria:

Identical inputs produce bit-for-bit identical outputs across all platforms and Python versions in the support matrix.
The module produces identical labels in backtesting and live replay modes for the same input sequence and calibration artifact.
No regime label changes when update() is called twice with the same bar (idempotency when fed duplicates under strict_data_validation = False with deduplication enabled).
Snapshot and restore produces a detector whose next 100 outputs are identical to those of the original.

Schema and contract criteria:

Every output record passes JSON Schema validation with zero errors.
Every mandatory field is populated in every output record.
Every conditional mandatory field is populated when its precondition is met and explicitly null otherwise.
The full output suite across the 20-year validation dataset contains zero schema validation failures.

Degradation criteria:

When the macro context provider is unavailable, regime labels match the full-provider output on ≥ 0.90 of bars.
When the GARCH provider is unavailable, regime labels match the full-provider output on ≥ 0.85 of bars.
When data_quality_score falls below 0.70, the output correctly sets DATA_QUALITY_WARNING on 100% of affected records.
A total input feed failure (all bars unavailable) causes the module to halt output emission, not to emit stale labels silently.


11.5 Production Readiness Requirements
These are measurable, auditable requirements that must be satisfied before the module is approved for production deployment. They are distinct from acceptance criteria in that they govern operational characteristics rather than functional correctness.
Performance requirements:
P1 — Computation latency. The wall-clock time from update() invocation to return of the MarketRegime object, excluding log write time, must satisfy: p50 ≤ 5ms, p95 ≤ 20ms, p99 ≤ 50ms, measured on the target production hardware with all optional providers (GARCH, macro) connected. These bounds apply per instrument. Multi-instrument throughput scales linearly with the number of registered detectors up to the core count of the deployment host.
P2 — Batch processing throughput. update_batch() must process ≥ 10,000 daily bars per second per instrument on the target hardware. This supports full-history backtests completing in under 1 second for a 40-year dataset.
P3 — Memory footprint. The steady-state memory footprint of a single initialized detector, including retained history at history_retention_periods = 252, must not exceed 50MB. Memory must not grow unboundedly over time; all internal deques must be bounded.
P4 — Startup time. create_detector() including config loading, calibration loading, and a 252-bar warm-up sequence must complete in under 2 seconds. Cold start in a container environment must not exceed 10 seconds including Python interpreter startup.
Reliability requirements:
R1 — No unhandled exceptions. Every exception path that can be triggered by external inputs (malformed bars, missing calibration data, unavailable providers) must be caught, wrapped in a typed exception from the module's exception hierarchy, and either raised with a structured message or handled gracefully per the degradation policy. Python's base Exception must never propagate uncaught out of any public method.
R2 — No silent data corruption. State mutations must be atomic with respect to update(). If any exception occurs during state evaluation, internal state must remain identical to its pre-update() value. This must be verified by a test that injects an exception mid-evaluation and confirms state is unchanged.
R3 — Log write failure handling. A failure to write a transition log record must not result in a silent success. The module must either retry successfully, write to the fallback log, or raise a LogWriteError that the caller can handle. Under no circumstances may a regime transition occur without a durable log record.
R4 — Calibration expiry handling. A module running with an expired CalibrationArtifact beyond the maximum configured staleness must not silently continue — it must set CALIBRATION_STALE and reduce confidence scores by the recency decay factor. After a configurable maximum staleness (default: 30 days beyond scheduled recalibration), the module must halt output emission and require explicit operator intervention to resume.
Test coverage requirements:
T1 — Line coverage. Minimum 90% line coverage across all non-test source files, measured by the CI pipeline on every merge to the main branch. Coverage must be reported per file; no source file may fall below 80% even if the aggregate meets 90%.
T2 — Branch coverage. Minimum 85% branch coverage. Every if/elif/else path in state transition logic must be exercised by at least one test.
T3 — Mutation testing score. Run a mutation testing framework (e.g., mutmut or cosmic-ray) against the state transition and confidence calculation modules. The mutation score — fraction of injected mutations that cause at least one test to fail — must be ≥ 0.80. A mutation score below this indicates tests are passing without actually asserting on the behavior they exercise.
T4 — Historical validation must pass in CI. The full historical validation suite (Section 11.3) must run and pass in the CI pipeline before any release is tagged. It may run on a dedicated validation runner rather than the standard build agent, but it must complete and produce a pass/fail signal that gates the release.
Code quality requirements:
Q1 — Type completeness. All public interfaces and all internal methods with non-trivial signatures must have complete type annotations. Running mypy --strict on the module source must produce zero errors.
Q2 — No mutable default arguments. No function or method in the module may use a mutable default argument. This is a Python-specific correctness requirement; mutable defaults produce state shared across calls.
Q3 — Cyclomatic complexity. No single method may have a cyclomatic complexity above 10, measured by a linter in CI. Methods approaching this limit are candidates for decomposition into helper methods with their own targeted tests.
Q4 — Dependency surface. The module's required dependencies (those without which it cannot function) must be limited to the Python standard library and a small set of approved scientific computing packages (numpy, pandas, scipy). Optional dependencies (for GARCH, logging adapters, metrics sinks) must be truly optional — the module must import and run correctly if they are not installed, raising ImportError only when the optional feature is actually invoked. This must be verified by a CI job that installs only required dependencies and runs the full unit suite.
Q5 — Changelog and version discipline. Every change to the public interface, configuration schema, output schema, or default threshold values must increment the semantic version and include a changelog entry. Breaking changes to the output schema require a major version increment and a documented migration path. The version embedded in module_version output fields must match the installed package version exactly.

---