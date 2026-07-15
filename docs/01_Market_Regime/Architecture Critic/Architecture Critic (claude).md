You haven't actually attached or described the specific architecture (no diagram, code, or spec is in this conversation) — so I can't critique your specific design decisions. What follows is a critique of the *canonical* multi-timeframe (MTF) architecture pattern that most quant shops converge on by default (resample OHLCV into multiple bar frequencies, compute indicators per timeframe, fuse signals hierarchically, backtest, deploy). If you share the actual doc/code, I'll critique that instead — this generic version is deliberately harsh so you can check which criticisms actually apply to yours.

## Hidden assumptions

- **"Higher timeframe bars are available at the moment they're needed."** This is almost never explicitly checked. A daily bar dated `2024-01-05` isn't actually known until `2024-01-05 23:59:59` (or later, depending on data vendor). If your feature join uses the date as a key without a timestamp-of-availability offset, you've assumed information exists before it does.
- **"All timeframes share a clock."** Crypto trades 24/7, equities don't. A 4H bar aggregated from continuous crypto data and a 4H bar aggregated from equities with trading halts are not the same object, but MTF pipelines usually treat them identically.
- **"Resampling is lossless and canonical."** Whether a week starts Monday or Sunday, whether a session boundary is UTC or exchange-local — these arbitrary choices materially change indicator values and are rarely justified, just defaulted.
- **"Signals from different timeframes are independent inputs to a model."** They're derived from the *same underlying price series*. Feeding 1m, 15m, 1H, and 1D RSI into one model is feeding four heavily autocorrelated transforms of one signal, not four independent features.

## Data leakage (the big one for MTF systems specifically)

1. **Repainting via improper bar closure.** The most common MTF bug: computing a higher-timeframe indicator using the *current, still-forming* higher-TF bar instead of the last *closed* one. E.g., at 10:15 on a 1H chart, if your resample includes 10:00–10:15 data in "this hour's" bar and lets the model see it, you're leaking the future relative to what would be available live.
2. **Global normalization.** If feature scaling (z-score, min-max) is fit on the full dataset before train/test split, every timeframe's features leak future distributional information — this is worse in MTF because you're doing it N times, once per timeframe.
3. **Label construction crossing timeframes.** If your label ("will price rise in next 4H") is built using the same bars used to generate lower-timeframe entry features, check the label's start timestamp isn't upstream of the feature's availability timestamp. This is easy to get subtly wrong when joining on date/hour keys instead of true event timestamps.
4. **Cross-validation without purging/embargo.** Standard k-fold CV on time series with MTF features is close to guaranteed leakage — adjacent higher-TF bars overlap across many lower-TF rows, so train/test contamination happens even if you shuffle "correctly" at the row level. You need purged, embargoed CV (López de Prado) and even that only partly helps with MTF overlap.

## Survivorship & selection bias

- If backtest universe = "current index constituents" or "symbols currently active on my data feed," you've excluded delisted/bankrupt/merged names — MTF systems that rely on years of higher-TF history are especially prone to silently pulling only symbols with long clean histories, which correlates with survival.
- **Timeframe survivorship**: if you tested 5, 15, 30, 60, 240 minute and daily, and only report/deploy the combination that backtested best, that's selection bias dressed as architecture — the "multi-timeframe" framing doesn't exempt you from multiple-testing correction. You've run dozens of implicit trials (which TFs, which combination logic, which thresholds) and reported the winner as if it were a single hypothesis test.

## Confirmation bias

- MTF designs are frequently justified post-hoc ("daily confirms trend, 1H confirms momentum, 5m times entry") — a narrative fitted to whichever combination already looked good in-sample, not a mechanism derived independently of the data. If you can't state *before* looking at backtest results which timeframe combination and confirmation logic you'd use, and why, you're likely fitting the story to the P&L curve.
- Confirmation-based signal fusion (require agreement across N timeframes) mechanically reduces trade frequency and increases apparent win rate — this looks like "robustness" but is largely a variance-reduction artifact of AND-ing correlated signals, not genuine edge validation.

## Statistical weaknesses

- **Multiple comparisons**: testing combinations of {timeframes} × {indicators} × {thresholds} × {fusion rules} generates a huge number of implicit trials. Without Deflated Sharpe Ratio, White's Reality Check, or similar correction, your reported Sharpe is almost certainly inflated.
- **Autocorrelation inflating significance**: higher-TF-derived features change slowly and are highly serially correlated; naive t-stats / p-values on strategy returns using such features overstate significance because effective sample size is much smaller than bar count.
- **Non-stationarity across timeframes not addressed**: a daily-timeframe trend filter trained on 2015–2019 data and a 5-minute entry model trained on 2023 microstructure are implicitly assuming stable relationships across regimes that don't necessarily hold together.

## Market microstructure mistakes

- **Using close prices for signals that can't be executed at close.** If your daily-timeframe filter uses the daily close as an input but the actual trade executes intraday on a lower timeframe, you have a look-ahead-adjacent execution mismatch — the daily close isn't tradeable until the next session opens.
- **Ignoring spread/latency asymmetry across timeframes.** Slippage and spread cost matter enormously at 1m/5m granularity and are often modeled (if at all) using one blanket assumption applied uniformly across all timeframes, when in reality the lower-TF component is far more cost-sensitive.
- **Assuming synchronized fills across timeframes.** If your architecture treats "signal generated on 1H bar" and "order filled on next available price" as the same timestamp, you've ignored the latency and slippage window that's often the difference between a profitable and unprofitable strategy at higher frequencies.

## Trading / risk-management mistakes

- **No signal conflict resolution defined.** What happens when the daily trend says long and the 5-minute momentum says short? Most MTF designs I've seen either don't specify this or bolt on an ad hoc priority rule after the fact — this is a critical piece of the architecture, not an implementation detail.
- **No portfolio-level risk aggregation.** Multiple timeframe signals on the same instrument (or correlated instruments) can silently stack correlated exposure — you may think you have three independent alpha sources when you actually have one source triple counted.
- **No explicit position sizing / capital allocation logic across timeframes** — different timeframes imply different holding periods and different volatility profiles; treating them with uniform sizing is a common, quietly costly mistake.

## Computational / software design flaws

- **Redundant recomputation.** Naively recomputing higher-TF indicators from raw ticks on every lower-TF update is O(bars × timeframes) with heavy redundancy — should be incrementally updated (streaming aggregation), not recomputed from scratch.
- **Tight coupling between data ingestion and strategy logic.** If the resampling logic lives inside the strategy class rather than a separate, testable, reusable bar-aggregation service, you can't unit test for the repainting bug above, and every strategy re-implements (and re-breaks) timeframe alignment independently.
- **No single source of truth for "current time."** In an event-driven backtester with multiple timeframes running as separate async streams, without a strict global event clock that enforces causal ordering across streams, you can get non-deterministic replay — same backtest, different results, run to run.
- **No backtest/live parity layer.** If the backtest resampling code and the live resampling code are different implementations (common when backtest is vectorized/pandas and live is event-driven), timeframe boundary bugs will differ between the two environments and you won't discover it until live divergence shows up as unexplained P&L.
- **No feature/schema versioning.** MTF feature sets tend to grow indicator-by-indicator over time; without versioning, you can't reproduce a specific backtest result or know which feature set a live model is actually consuming.

## What I'd do instead

1. **Single canonical event-driven bar engine** that ingests raw ticks/trades once, maintains all timeframes as incrementally-updated aggregations, and stamps every emitted bar with both its *nominal* period and its *availability timestamp* (when it was actually knowable). All downstream consumers key off availability timestamp, never nominal period.
2. **Point-in-time joins only** — every feature lookup is an as-of join against availability timestamp, enforced by the data layer, not left to strategy authors to get right by convention.
3. **Shared library between research and live execution** for resampling/feature computation — not separate pandas vs streaming implementations — to guarantee parity.
4. **Purged, embargoed, combinatorial walk-forward validation** (López de Prado-style), sized to account for the overlap induced by higher-timeframe features, not standard k-fold.
5. **Explicit multiple-testing correction** (Deflated Sharpe Ratio at minimum) applied to the entire search space you actually explored — timeframes, thresholds, and fusion rules included — not just the final chosen configuration.
6. **Explicit signal-conflict and capital-allocation rules** specified and tested *before* backtesting, with a portfolio-level risk aggregator that treats correlated multi-timeframe signals as one risk factor, not several.
7. **Survivorship-bias-free universe** including delisted/failed instruments, sourced from a point-in-time constituent database, not a live symbol list.
8. **Transaction cost and slippage models calibrated per timeframe**, weighted toward realism at the highest-frequency component, since that's where cost erodes edge fastest.

If you paste the actual architecture (diagram, doc, or code), I'll go through it point by point against this list rather than the generic version.