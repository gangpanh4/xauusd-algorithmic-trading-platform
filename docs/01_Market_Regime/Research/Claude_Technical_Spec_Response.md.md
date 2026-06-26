Market Regime Detection Module — Technical Specification

Version: 1.0.0

Classification: Internal — Quantitative Infrastructure

Status: Draft for Review


1. Purpose and Scope

This document specifies the design of a production-grade Market Regime Detection (MRD) module for use within an algorithmic trading system. The MRD module is a stateful, real-time classification engine that assigns a discrete regime label to a market at each evaluation cycle, emits a confidence score, manages state transitions with hysteresis, and publishes a structured event stream consumed by downstream strategy, risk, and execution layers.

The module is agnostic to asset class but is parameterized per instrument. All thresholds, windows, and weights are externally configurable and must be validated at startup.


2. Market State Taxonomy

Regimes are organized in a two-level hierarchy: primary state and sub-state. The composite label is expressed as PRIMARY.SUBSTATE.

2.1 Primary States

IDLabelSemantic Meaning0TRENDING_UPDirectional upward price movement with elevated momentum1TRENDING_DOWNDirectional downward price movement with elevated momentum2RANGINGMean-reverting, low-directional, contained volatility3VOLATILEElevated realized volatility with no persistent direction4BREAKOUTTransitional: price escaping a prior range with surge in volume/ATR5CRISISExtreme tail volatility, correlation breakdown, liquidity stress6UNDEFINEDInsufficient data or unresolvable signal conflict

2.2 Sub-States

Each primary state carries a sub-state qualifier. Sub-states allow downstream consumers to apply fine-grained behavior without requiring a full regime transition.

Sub-StateMeaningEARLYRegime recently established; less than min_persistence bars confirmedESTABLISHEDRegime confirmed; confidence above confidence_high_thresholdLATEConfidence declining; proximity to transition zoneSTRESSEDAnomalous readings within the regime (e.g., trending but with rising VIX-equivalent)

Example composite labels: TRENDING_UP.ESTABLISHED, RANGING.STRESSED, BREAKOUT.EARLY


3. Required Indicators

All indicators are computed on a per-symbol, per-timeframe basis. All inputs must be validated for staleness before use (see §12.1).

3.1 Trend Indicators

IndicatorParametersRoleExponential Moving Average (EMA)Periods: ema_fast, ema_slowTrend direction via crossover and slopeAverage Directional Index (ADX)Period: adx_periodTrend strength (non-directional)Linear Regression Slope (LRS)Period: lrs_period; applied to closePrice velocity and accelerationRate of Change (ROC)Period: roc_periodShort-term momentum

3.2 Volatility Indicators

IndicatorParametersRoleAverage True Range (ATR)Period: atr_periodAbsolute volatility levelATR Ratioatr / atr_long_maRelative volatility (normalized, regime-portable)Realized Volatility (RV)Rolling rv_window of log returns, annualizedStatistical volatility baselineBollinger Band Width (BBW)Period: bb_period, bb_stdVolatility contraction/expansion signalHistorical Volatility Percentile (HVP)Lookback: hvp_lookbackContextual volatility positioning

3.3 Range and Structure Indicators

IndicatorParametersRoleDonchian Channel Width (DCW)Period: dc_periodRange boundary estimationPrice Position Within ChannelDerived from DCMean-reversion contextChoppiness Index (CI)Period: ci_periodTrending vs. choppy classification

3.4 Liquidity and Volume Indicators

IndicatorParametersRoleVolume Ratio (VR)volume / volume_maVolume surge detectionOn-Balance Volume Slope (OBV-S)obv_slope_periodVolume trend confirmationBid-Ask Spread (BAS)Real-time feedLiquidity stress proxy (CRISIS regime)Amihud Illiquidity RatioRolling amihud_periodMarket impact proxy

3.5 Cross-Asset and Macro Signals (Optional Layer)

These are optional inputs activated via configuration. When enabled, they participate in regime scoring with configurable weight.

SignalPurposeVIX-equivalent (or realized vol of vol)Fear/stress regime classifierYield curve slopeMacro regime contextCorrelation matrix shiftCrisis onset detectionCredit spread levelRisk-off signal


4. Threshold Selection Methodology

Static thresholds are fragile. The MRD module uses an adaptive threshold framework with static fallbacks.

4.1 Baseline Thresholds (Static Defaults)

Static defaults are defined per-indicator in the configuration file and serve as initialization values before adaptive estimates stabilize.

IndicatorDefault ThresholdRegime ImplicationADX≥ 25Trending (up or down)ADX< 20Non-trendingCI< 38.2Strong trendCI> 61.8Choppy / rangingATR Ratio> 1.5Elevated volatilityATR Ratio> 2.5VOLATILE primary stateHVP> 80th percentileVOLATILE or CRISISVolume Ratio> 2.0Breakout confirmationBBW< 15th percentile (of bbw_lookback)Compression; breakout precursor

4.2 Adaptive Threshold Estimation

Thresholds are recalibrated on a rolling basis using the following methodology:

Step 1 — Indicator Distribution Modeling

For each indicator, maintain a rolling empirical distribution over adaptive_lookback bars (default: 252 trading days). Compute the 20th, 50th, and 80th percentiles.

Step 2 — Regime-Conditional Quantiles

Separate distributions are maintained per confirmed regime label. A threshold that separates TRENDING from RANGING is estimated as the crossing point of their ADX conditional distributions.

Step 3 — Threshold Smoothing

Apply exponential smoothing to threshold estimates (alpha: threshold_smoothing_alpha) to prevent rapid oscillation. New thresholds are blended: T_new = alpha * T_estimated + (1 - alpha) * T_current.

Step 4 — Stability Gate

Adaptive thresholds are only applied when the estimation window has at least min_adaptive_samples observations. Prior to that, static defaults are used and a USING_STATIC_THRESHOLDS flag is set in the regime event.

Step 5 — Bounds Enforcement

Adaptive thresholds are clipped to [static_default * lower_bound_multiplier, static_default * upper_bound_multiplier] to prevent degenerate estimates.


5. Confidence Calculation

The regime confidence score C ∈ [0.0, 1.0] quantifies how strongly the current indicator state supports the emitted regime label.

5.1 Per-Indicator Signal Scores

Each indicator produces a scalar signal score s_i ∈ [-1.0, 1.0] for each candidate regime. The sign encodes direction of support (positive = supports, negative = contradicts); the magnitude encodes strength.

Signal scores are produced by a piecewise linear mapping from indicator value to score, parameterized by the threshold breakpoints:

s_i = clip(
    (x_i - threshold_neutral) / (threshold_strong - threshold_neutral),
    -1.0, 1.0
)

The neutral and strong threshold values are sourced from the adaptive threshold engine (§4).

5.2 Weighted Score Aggregation

Indicators are grouped into categories (Trend, Volatility, Structure, Liquidity). Each group has a configurable weight w_g. Within each group, indicators have relative weights w_i (sum to 1.0 within group).

The raw composite score for regime R:

Score(R) = Σ_g [ w_g * Σ_i ( w_i * s_i(R) ) ]

5.3 Softmax Normalization

Raw scores across all candidate regimes are passed through a softmax function with temperature T_softmax to produce a probability distribution:

P(R_k) = exp(Score(R_k) / T_softmax) / Σ_j exp(Score(R_j) / T_softmax)

Lower temperature sharpens discrimination; higher temperature softens it. Default T_softmax = 1.0.

5.4 Confidence Score

The confidence score for the winning regime R* is:

C = P(R*) - max(P(R_j) for j ≠ R*)

This is the margin of victory over the second-best regime. It is more informative than raw probability because it captures ambiguity between close competitors.

C is then mapped to [0.0, 1.0] via a monotonic scaling function tuned so that C = 0.5 represents a clearly dominant regime and C < 0.2 represents meaningful ambiguity.

5.5 Confidence Decay

Between evaluation cycles, if fresh data is unavailable, confidence decays exponentially:

C_t = C_0 * exp(-lambda * delta_t)

where lambda is confidence_decay_rate and delta_t is seconds since last update. When C_t < confidence_min_floor, the regime transitions to UNDEFINED.


6. State Transition Rules with Hysteresis

Transitions are governed by a hysteresis band to prevent thrashing between regimes on noisy boundaries.

6.1 Entry Threshold

A candidate regime R_candidate becomes the active regime only if:


P(R_candidate) > entry_probability_threshold (default: 0.60)
C > confidence_entry_threshold (default: 0.25)
The candidate has held the highest probability for at least hysteresis_bars_entry consecutive evaluation cycles (default: 3)
The current active regime's confidence has fallen below exit_confidence_threshold (default: 0.40)


All four conditions must be satisfied simultaneously.

6.2 Exit Threshold

The active regime is retained unless:


Its confidence C falls below exit_confidence_threshold for hysteresis_bars_exit consecutive cycles, or
An emergency override is triggered (see §6.4)


The asymmetry between entry and exit thresholds is intentional: it is more costly to exit a correct regime than to remain in one that is fading.

6.3 Transition Cooldown

Following any state transition, a mandatory cooldown of transition_cooldown_bars evaluation cycles is enforced. During cooldown:


The new regime is held regardless of signal changes
The in_cooldown flag is set true in emitted events
No further transitions are permitted (except emergency overrides)


This prevents flip-flopping immediately after a transition.

6.4 Emergency Override (Fast Path)

Certain signals bypass hysteresis and trigger an immediate transition:

TriggerTarget RegimeHVP > 95th percentile AND Volume Ratio > 3.0CRISIS.EARLYBAS > crisis_spread_thresholdCRISIS.EARLYRealized vol > crisis_rv_multiplier × long-run RVCRISIS.EARLY

Emergency transitions are logged with transition_type = EMERGENCY and do not start a cooldown period, allowing rapid re-classification.

6.5 Transition State Machine

UNDEFINED → [any] : on confidence recovery above entry threshold
[any] → UNDEFINED : on confidence decay below floor
[any] → CRISIS    : via normal or emergency path
CRISIS → [any]    : only after min_crisis_persistence bars AND confidence recovery
RANGING → BREAKOUT: BBW compression followed by expansion AND volume surge
BREAKOUT → TRENDING_UP | TRENDING_DOWN : after breakout_confirmation_bars
BREAKOUT → RANGING : if breakout fails (price reverts within breakout_failure_bars)


7. Minimum Persistence

Each regime has a minimum number of evaluation cycles it must remain active before a voluntary transition is permitted. Emergency overrides ignore persistence constraints.

RegimeDefault min_persistence (bars)RationaleTRENDING_UP5Avoid whipsawing on noiseTRENDING_DOWN5SameRANGING8Ranges tend to be stickyVOLATILE3Volatility can resolve quicklyBREAKOUT2Breakouts are inherently short-livedCRISIS10Crisis states are costly to exit prematurelyUNDEFINED1Should resolve quickly

Persistence is tracked as bars_in_regime in module state. The sub-state EARLY is set while bars_in_regime < min_persistence. ESTABLISHED is set once persistence is satisfied and confidence remains high.


8. Handling Conflicting Signals

Signal conflicts arise when indicators from different groups point to different regimes with comparable probability. The following protocol resolves conflicts:

8.1 Conflict Detection

A conflict is flagged when:


The margin C < conflict_margin_threshold (default: 0.15), or
Two or more regimes have P(R_k) > conflict_probability_floor (default: 0.35)


When a conflict is detected, signal_conflict = true is set in the emitted event.

8.2 Conflict Resolution Hierarchy

Resolution follows a priority-ordered hierarchy:


Retain current regime. If the active regime's probability has not dropped below exit_confidence_threshold, hold the current regime. The benefit of doubt goes to the incumbent.
Apply domain-specific priority rules. The following override table is applied:

If CRISIS indicators are firing, CRISIS always wins regardless of trend/range signals.
If BREAKOUT indicators are firing against a RANGING backdrop, BREAKOUT wins.
TRENDING wins over VOLATILE if trend indicators are unambiguous (ADX > 30, CI < 38).



Blend via weighted arbitration. If no rule resolves the conflict, retain the active regime with a reduced confidence score: C_adjusted = C * conflict_confidence_penalty (default penalty: 0.70).
Escalate to UNDEFINED. If conflict persists for max_conflict_bars consecutive cycles (default: 5) without resolution, transition to UNDEFINED.STRESSED.


8.3 Indicator-Level Conflict Flags

Each emitted event includes a per-indicator conflict map identifying which indicators disagree with the emitted regime. This is used for post-trade diagnostics and threshold recalibration.


9. Logging Schema

All events are emitted as structured JSON messages to a logging/event bus. Schema is versioned.

9.1 Regime Event (Primary Output)

json{
  "schema_version": "1.0",
  "event_type": "REGIME_EVENT",
  "timestamp_utc": "2025-04-15T14:32:00.123456Z",
  "symbol": "ES",
  "timeframe": "5m",
  "evaluation_cycle": 104823,

  "regime": {
    "primary": "TRENDING_UP",
    "sub_state": "ESTABLISHED",
    "label": "TRENDING_UP.ESTABLISHED",
    "confidence": 0.71,
    "probability_distribution": {
      "TRENDING_UP": 0.58,
      "TRENDING_DOWN": 0.03,
      "RANGING": 0.15,
      "VOLATILE": 0.12,
      "BREAKOUT": 0.08,
      "CRISIS": 0.04,
      "UNDEFINED": 0.00
    }
  },

  "transition": {
    "occurred": false,
    "previous_regime": "TRENDING_UP.ESTABLISHED",
    "transition_type": null,
    "bars_in_regime": 22,
    "in_cooldown": false
  },

  "indicators": {
    "adx": 31.4,
    "ema_fast": 4521.25,
    "ema_slow": 4498.10,
    "ema_crossover": "above",
    "lrs_slope": 0.42,
    "atr_ratio": 1.08,
    "hvp_percentile": 61,
    "volume_ratio": 1.12,
    "ci": 33.7,
    "bbw_percentile": 48
  },

  "signal_scores": {
    "trend_group": 0.74,
    "volatility_group": 0.21,
    "structure_group": 0.55,
    "liquidity_group": 0.18
  },

  "flags": {
    "signal_conflict": false,
    "using_static_thresholds": false,
    "data_staleness_warning": false,
    "emergency_override": false,
    "min_persistence_met": true
  },

  "conflicting_indicators": [],

  "thresholds_applied": {
    "adx_trend_threshold": 24.8,
    "atr_ratio_volatile_threshold": 2.3,
    "source": "adaptive"
  },

  "metadata": {
    "module_version": "1.0.0",
    "config_id": "cfg_es_5m_v3",
    "compute_latency_us": 148
  }
}

9.2 Transition Event (Emitted on Any State Change)

A separate event with event_type = REGIME_TRANSITION is emitted in addition to the standard regime event whenever transition.occurred = true. It contains the full pre- and post-transition state snapshots and the trigger evidence that caused the transition.

9.3 Diagnostic Event (Periodic)

Every diagnostic_emit_interval cycles, a REGIME_DIAGNOSTIC event is emitted containing:


Current adaptive threshold values and estimation metadata
Rolling distribution statistics per indicator
Conflict resolution history over the last N cycles
Compute performance percentiles (p50, p95, p99)


9.4 Alert Event

REGIME_ALERT is emitted when:


CRISIS regime is entered (severity: HIGH)
UNDEFINED persists beyond undefined_alert_bars (severity: MEDIUM)
Compute latency exceeds latency_alert_threshold_us (severity: LOW)



10. API Interface

10.1 Core Interface (Python, typed)

RegimeDetector
├── __init__(config: RegimeConfig, market_data_provider: MarketDataProvider) -> None
├── update(bar: OHLCV) -> RegimeEvent
├── update_batch(bars: List[OHLCV]) -> List[RegimeEvent]
├── get_current_regime() -> RegimeSnapshot
├── get_regime_history(n: int) -> List[RegimeSnapshot]
├── reset(symbol: str | None) -> None
├── recalibrate_thresholds() -> ThresholdUpdateReport
├── get_diagnostics() -> DiagnosticsReport
└── validate_config() -> ConfigValidationResult

10.2 Method Contracts

update(bar: OHLCV) -> RegimeEvent


Called once per completed bar.
Guaranteed non-blocking; must complete within max_compute_latency_us.
Returns a RegimeEvent on every call, including when the regime has not changed.
Raises InsufficientDataError if fewer than min_warmup_bars have been received.
Raises StaleDataError if bar timestamp gap exceeds max_bar_gap_seconds.
Thread-safe. Multiple symbols may be managed by a pool of independent instances.


recalibrate_thresholds() -> ThresholdUpdateReport


Triggers an immediate threshold recalibration pass.
Safe to call during live trading; uses a read-copy-update pattern to avoid interrupting update().
Returns a report containing old vs. new threshold values and whether any were out of bounds.


10.3 Data Types

OHLCV:
  symbol: str
  timestamp: datetime (UTC, timezone-aware)
  open: Decimal
  high: Decimal
  low: Decimal
  close: Decimal
  volume: Decimal
  bid: Decimal | None
  ask: Decimal | None

RegimeSnapshot:
  timestamp: datetime
  label: str              # e.g. "TRENDING_UP.ESTABLISHED"
  primary: RegimePrimary  # enum
  sub_state: RegimeSubState
  confidence: float
  bars_in_regime: int
  flags: RegimeFlags

RegimeEvent:
  snapshot: RegimeSnapshot
  probability_distribution: dict[str, float]
  indicators: dict[str, float]
  signal_scores: dict[str, float]
  transition: TransitionInfo
  thresholds_applied: dict[str, float]
  metadata: EventMetadata

10.4 Event Bus Interface

For systems requiring asynchronous consumption, the module implements a publisher interface:

RegimePublisher
├── subscribe(handler: Callable[[RegimeEvent], None], event_types: List[str]) -> SubscriptionHandle
├── unsubscribe(handle: SubscriptionHandle) -> None
└── publish(event: RegimeEvent) -> None

Events are dispatched synchronously within the update() call. Handlers must be non-blocking; offload to a queue if downstream processing is slow.


11. Configuration Parameters

All parameters are defined in a typed configuration object (or equivalent YAML/TOML file). Invalid configurations must fail fast at startup.

11.1 Indicator Parameters

ParameterTypeDefaultDescriptionema_fastint12Fast EMA periodema_slowint26Slow EMA periodadx_periodint14ADX calculation periodlrs_periodint20Linear regression slope periodroc_periodint10Rate of change periodatr_periodint14ATR periodatr_long_ma_periodint100Long MA for ATR ratio baselinerv_windowint21Realized volatility window (bars)bb_periodint20Bollinger Band periodbb_stdfloat2.0Bollinger Band standard deviationshvp_lookbackint252Lookback for HVP percentiledc_periodint20Donchian Channel periodci_periodint14Choppiness Index periodobv_slope_periodint10OBV slope estimation periodamihud_periodint20Amihud ratio rolling window

11.2 Threshold Parameters

ParameterTypeDefaultDescriptionadx_trending_thresholdfloat25.0ADX level indicating trendadx_non_trending_thresholdfloat20.0ADX level indicating no trendci_trending_thresholdfloat38.2CI below = trendingci_ranging_thresholdfloat61.8CI above = rangingatr_ratio_volatile_thresholdfloat2.5ATR ratio for VOLATILE statehvp_volatile_thresholdfloat80.0HVP percentile for VOLATILEhvp_crisis_thresholdfloat95.0HVP percentile for CRISISvolume_ratio_breakout_thresholdfloat2.0Volume surge for BREAKOUTcrisis_spread_thresholdfloat—BAS threshold for CRISIS (instrument-specific)crisis_rv_multiplierfloat3.0RV multiple over baseline for CRISIS

11.3 Transition and Hysteresis Parameters

ParameterTypeDefaultDescriptionentry_probability_thresholdfloat0.60Minimum P(R) to enter regimeconfidence_entry_thresholdfloat0.25Minimum C to enter regimeexit_confidence_thresholdfloat0.40C below this allows exithysteresis_bars_entryint3Bars candidate must lead before entryhysteresis_bars_exitint2Bars confidence must be low before exittransition_cooldown_barsint5Mandatory hold after transitionconflict_margin_thresholdfloat0.15C below this flags conflictconflict_probability_floorfloat0.35P(R) above this in 2+ regimes = conflictconflict_confidence_penaltyfloat0.70Confidence multiplier during conflictmax_conflict_barsint5Bars before escalation to UNDEFINED

11.4 Persistence Parameters

ParameterTypeDefaultDescriptionmin_persistence_trendingint5Minimum bars in TRENDINGmin_persistence_rangingint8Minimum bars in RANGINGmin_persistence_volatileint3Minimum bars in VOLATILEmin_persistence_breakoutint2Minimum bars in BREAKOUTmin_persistence_crisisint10Minimum bars in CRISISmin_persistence_undefinedint1Minimum bars in UNDEFINEDbreakout_confirmation_barsint3Bars to confirm BREAKOUT as TRENDINGbreakout_failure_barsint5Bars for BREAKOUT to revert to RANGING

11.5 Adaptive Threshold Parameters

ParameterTypeDefaultDescriptionadaptive_thresholds_enabledbooltrueEnable adaptive threshold engineadaptive_lookbackint252Lookback for distribution estimation (bars)min_adaptive_samplesint60Minimum samples before adaptive activatesthreshold_smoothing_alphafloat0.05EMA alpha for threshold smoothingthreshold_lower_bound_multiplierfloat0.5Floor as multiple of static defaultthreshold_upper_bound_multiplierfloat2.0Cap as multiple of static default

11.6 System Parameters

ParameterTypeDefaultDescriptionmin_warmup_barsint50Minimum bars before any regime emittedmax_bar_gap_secondsint300Max gap before StaleDataErrormax_compute_latency_usint1000Compute SLA in microsecondsconfidence_decay_ratefloat0.01Lambda for confidence decayconfidence_min_floorfloat0.05C below this triggers UNDEFINEDt_softmaxfloat1.0Softmax temperaturediagnostic_emit_intervalint100Cycles between diagnostic eventsundefined_alert_barsint10UNDEFINED bars before alertlatency_alert_threshold_usint500Latency threshold for alert


12. Unit Testing Strategy

12.1 Test Categories

Category 1: Indicator Correctness


For each indicator, supply synthetic OHLCV series with known analytical solutions. Assert indicator values match to within 1e-6.
Cover: all-constant series, linear ramp, sinusoidal, step function, spike.
Include edge cases: single bar, two bars, exactly n bars (boundary), gap in timestamps.


Category 2: Signal Score Mapping


For each indicator, supply a set of known indicator values and assert that signal_score falls within expected range and has correct sign.
Assert scores are monotone functions of indicator value within each segment.


Category 3: Confidence Calculation


Construct synthetic signal score vectors with known properties (unanimous, split, one dominant). Assert that resulting confidence scores satisfy expected inequalities.
Assert softmax outputs sum to 1.0 within floating-point tolerance.
Test confidence decay: given a fixed C_0, assert C_t at various delta_t matches analytic decay formula.


Category 4: Hysteresis and Transition Logic


Simulate regime-crossing sequences where the candidate's probability crosses entry threshold on bar N. Assert transition does not occur before hysteresis_bars_entry. Assert it occurs on bar N + hysteresis_bars_entry.
Test cooldown: simulate a transition, then immediately supply signals favoring a second transition. Assert the second transition is blocked for transition_cooldown_bars.
Test minimum persistence: supply a signal that would trigger exit before min persistence is met. Assert no exit occurs.


Category 5: Emergency Override


Construct CRISIS-triggering signals. Assert immediate transition regardless of cooldown, hysteresis, and persistence state.
Assert transition_type = EMERGENCY in emitted event.


Category 6: Conflict Resolution


Construct signal vectors producing two near-equal regime probabilities. Assert signal_conflict = true is emitted. Assert the resolution hierarchy is followed in correct order. Assert escalation to UNDEFINED after max_conflict_bars.


Category 7: Adaptive Thresholds


Supply fewer than min_adaptive_samples bars. Assert using_static_thresholds = true.
Supply sufficient bars. Assert threshold values shift from static defaults. Assert shifted thresholds are within bounds.
Assert threshold smoothing: large single-step shift is attenuated.


Category 8: Data Quality


Supply a bar with a timestamp gap exceeding max_bar_gap_seconds. Assert StaleDataError is raised.
Supply negative volume. Assert InvalidBarError is raised.
Supply fewer than min_warmup_bars. Assert InsufficientDataError is raised.
Supply NaN/inf OHLCV values. Assert graceful failure.


Category 9: Regime Sequence Scenarios (Integration Tests)


Construct multi-bar synthetic series designed to produce a known regime sequence (e.g., RANGING → BREAKOUT → TRENDING_UP). Run the full module. Assert emitted labels match expected sequence, with correct sub-states and transition events.


Category 10: Performance Tests


Supply 10,000 bars and measure mean and p99 compute latency per update() call.
Assert p99 latency < max_compute_latency_us.
Memory profile: assert no unbounded growth in memory usage over 100,000 cycles.


12.2 Test Data Requirements


All test OHLCV data must be synthetically generated (no real market data in test suite).
A SyntheticMarketGenerator utility must be provided, capable of generating the following regimes on demand: trending, mean-reverting, GARCH-volatile, and crisis.
Random seed must be fixed per test for determinism.



13. Performance Considerations

13.1 Compute Budget

The update() method must complete within max_compute_latency_us (default: 1,000 µs) for all normal paths. Emergency override paths are exempt from this SLA due to their rarity. The method runs synchronously in the strategy event loop — any blocking I/O is strictly prohibited.

13.2 Indicator Computation


All indicators are computed incrementally. No indicator recalculates from full history on each bar. This requires maintaining rolling state buffers for each indicator.
Circular buffers of fixed capacity (max(all indicator periods) + buffer_headroom) are pre-allocated at initialization. No heap allocation occurs during update().
Arithmetic is performed in float64. Decimal types are used only for raw OHLCV input and converted at ingestion.


13.3 Memory Layout


Indicator state is stored in a flat struct layout (struct-of-arrays pattern) to maximize cache locality.
A pre-allocated event object is reused per cycle with fields overwritten (zero-copy emit via publisher). Downstream consumers must copy the event if they require persistence beyond the callback scope.


13.4 Parallelism


Each symbol-timeframe pair is managed by an independent RegimeDetector instance. Parallelism is achieved via a thread pool of detector instances.
No locks are held within update(). State mutation is single-threaded per instance.
recalibrate_thresholds() uses a read-copy-update pattern: computes new thresholds in a shadow copy, then atomically swaps the reference. update() reads the threshold pointer once per cycle.


13.5 Benchmarking Requirements


Benchmark suite must report: mean, p50, p95, p99, max latency for update() across 100,000 bars.
Benchmarks must be run on the target production hardware profile. Results must be stored in the CI artifact store with each release.
Any commit that causes p99 latency regression > 20% must be flagged for review.



14. Edge Cases

14.1 Market Open / Close Gaps


The first bar after a market close gap may show an outsized ATR due to the overnight move. A gap adjustment flag is set on bars where |open - prev_close| > atr * gap_multiplier (default gap_multiplier = 2.0). Gap-adjusted bars have their ATR contribution normalized to prevent spurious VOLATILE or CRISIS classification.


14.2 Halts and Auction Periods


Bars emitted during trading halts (zero volume, zero range) are rejected and not passed to indicators. HaltSkipped is incremented in diagnostics. Regime is held during halt periods with confidence decay applied.


14.3 Corporate Actions and Price Adjustments


Module does not adjust for splits or dividends internally. Upstream data feed must deliver adjusted prices. A discontinuity detection check raises a PriceDiscontinuityWarning if |close_t - close_{t-1}| / close_{t-1} > discontinuity_threshold (default: 0.20) and volume is not elevated.


14.4 Extreme Volatility Cascades


A rapid sequence of CRISIS emergency overrides (more than max_crisis_overrides_per_hour in a rolling hour) triggers a CrisisStormWarning event and sets a circuit_breaker_active flag. While active, regime transitions are suspended and the regime is held at CRISIS.STRESSED. The flag is cleared manually or after crisis_storm_clear_minutes of normalized conditions.


14.5 Regime Lock During Risk Events


Downstream risk systems may call lock_regime(regime: str, duration_bars: int) to externally force a regime label for a fixed number of bars (e.g., during a scheduled macro event). Locked regimes are held with externally_locked = true in the emitted event. All internal signals are still computed and logged; locking only suppresses transitions.


14.6 Insufficient History for Specific Indicators


If an indicator has not yet accumulated enough bars (e.g., ADX requires 2 * adx_period - 1 bars), it is excluded from scoring and its group weight is redistributed proportionally among available indicators. If more than max_missing_indicator_fraction (default: 0.40) of weighted indicator mass is unavailable, the regime is set to UNDEFINED regardless of other signals.


14.7 Tick Data and Sub-Bar Timeframes


For tick or sub-minute bars, volume normalization references a rolling tick-count baseline rather than a volume baseline. The use_tick_normalization flag enables this mode. Sub-bar ATR uses mid-price range rather than high-low to reduce microstructure noise.


14.8 Symbol Universe Changes


If the underlying instrument changes (e.g., continuous futures roll), the module state must be reset via reset(symbol). The threshold adaptive history is preserved by default (preserve_adaptive_history_on_roll = true) on the assumption that the new contract shares the same distributional properties. This behavior is configurable.



15. Operational Considerations

15.1 Startup Sequence


Load and validate configuration. Fail fast on any invalid parameter.
Pre-allocate all buffers.
Replay min_warmup_bars of historical bars silently (no events emitted, is_warmup = true).
After warmup, emit a single REGIME_INITIALIZED event with the first regime assignment.
Begin normal operation.


15.2 Graceful Degradation

If a non-critical indicator computation fails (e.g., numerical instability), the indicator is excluded for that cycle with a warning logged. Critical indicator failures (ADX, ATR) cause the regime to be set to UNDEFINED for that cycle.

15.3 Versioning and Reproducibility


Every emitted event carries module_version, config_id, and evaluation_cycle.
config_id is a deterministic hash of the full configuration object. Two instances with identical configurations will have identical config_id.
Given the same sequence of OHLCV bars and the same configuration, the module must produce identical events (deterministic). Non-determinism is a bug.


15.4 Monitoring and Alerting

The module exposes a metrics endpoint (Prometheus-compatible) publishing:


mrd_regime_label{symbol, timeframe} — current regime as an integer label
mrd_confidence{symbol, timeframe} — current confidence score
mrd_compute_latency_us{symbol, timeframe, quantile} — latency percentiles
mrd_transition_count{symbol, timeframe} — total transitions since startup
mrd_conflict_count{symbol, timeframe} — total conflict events
mrd_crisis_active{symbol, timeframe} — 1 if CRISIS, 0 otherwise



End of Specification — v1.0.0
Share