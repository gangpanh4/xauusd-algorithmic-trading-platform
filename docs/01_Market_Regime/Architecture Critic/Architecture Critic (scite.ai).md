Reference	Response
1	
Deep Hawkes process for high-frequency market making
Pankaj Kumar 2024
J BANK FINANC TECHNOL
5000
View PDF
Add to collection
Cite
Hidden assumptions: markets are stationary; cross-asset and cross-market dynamics stay stable; order book dynamics and latency stay constant; model transfer from simulated to live execution is valid.
Survivorship bias: backtests rely on surviving instruments/assets; ignore delisted/delayed securities or regime shifts.
Confirmation bias: tuning to win-rate on historical data; overweighting features that worked in past without falsification tests.
Computational bottlenecks: multi-timeframe processing and deep Hawkes components can explode complexity; real-time latency budgets may be violated; risk of cascading hyperparameters.
Software design flaws: tight coupling between market simulator and trading logic; insufficient modularity for swap of models; lack of deterministic testing under latency.
Overfitting risks: over-parameterized Hawkes/deep models fitted to historic order-flow; poor out-of-sample robustness.
Data leakage: leakage from future ticks via simultaneous multi-timeframe features; improper splitting across time horizons.
Statistical weaknesses: failing to correct for multiple testing; p-hacking risk; under- or over-estimation of transaction cost and impact.
Market microstructure mistakes: assuming fair queue priority and negligible adverse selection; ignores latency quantization and exchange microstructures; ignores slippage under real congestion.
Trading mistakes: ignoring risk controls, position limits, and P&L drawdown in stress; assuming infinite liquidity at all levels.
Architecture mistakes: monolithic data/schema contracts; insufficient observability, replayability, and fault tolerance; lack of backtesting sandbox with realistic latency; no clear risk- and capital-allocation framework.
If disagreeing, the critique: the proposed design leans on realistic-but-simplified simulators without rigorous live-traffic validation and robust out-of-sample testing; better alternative: separate live execution engine and backtester with strict data-splitting, walk-forward validation, latency-aware architecture, modular PMs for order-book dynamics, and a formal risk budget with live-risk monitors.
Better alternative: adopt a modular, event-driven architecture with explicit latency budgets, plug-in risk checks, standardized data lineage, and a dedicated backtesting harness that enforces strict data hygiene, out-of-sample testing, and drift detection; incorporate market microstructure-aware models with robust cross-validation and ablation tests.
2	
Limit Order Book Dynamics in Matching Markets: Microstructure, Spread, and Execution Slippage
Yao Wu 2025
Preprint
Access with Article Galaxy
Add to collection
Cite
Hidden assumptions: assumes fixed matchings and rigid LOB spreads across regimes; ignores regime shifts and evolving liquidity; presumes internal preference states are latent yet deterministically linked to spread.
Survivorship bias: tests likely rely on surviving instruments with liquid history, ignoring illiquid or delisted assets.
Confirmation bias: emphasis on spread as sole liquidity constraint; underweights adverse selection, order-flows, and crossing-time dynamics.
Computational bottlenecks: multi-timeframe state tracking (LPSM) explodes combinatorially; threshold theorems imply complex discontinuities hard to optimize in real time.
Software design flaws: opaque internal preference state representation; tight coupling between LPSM and market data; insufficient fault tolerance for partial data and latency.
Overfitting risks: dynamic discrete choice model with time-decaying threshold tuned to past markets; may not generalize to stressed regimes.
Data leakage: potential look-ahead if θ and T are calibrated on post-trade outcomes or future order-book states.
Statistical weaknesses: reliance on equilibrium analyses that may not hold in non-stationary markets; lack of out-of-sample stress testing.
Market microstructure mistakes: treats compensation as futile and ignores order-execution costs, slippage, and hidden liquidity; ignores adverse selection risk.
Trading mistakes: assumes execution when θ crosses T; may fail during fast price moves or regime switches, increasing slippage.
Architecture mistakes: lack of modular data ingress, backtesting realism, and live risk controls; monolithic model with hard thresholds reduces robustness.
If disagreeing with any recommendation: the model’s structural claims about indecipherable compensation and rigid spreads are overly pessimistic; in practice, spread dynamics and compensation can be partial substitutes with adaptive strategies.
Better alternative: adopt a modular, regime-aware, transaction-cost-aware architecture with: (1) robust data validation and leakage controls, (2) explicit modeling of latency, slippage, and adverse selection, (3) ensemble, multi-timeframe signals with cross-validation and regularization, (4) backtesting with realistic fill models and survivorship-adjusted datasets, and (5) continuous risk budgeting and governance to prevent overfitting and data leakage.
3	
RL-Exec: Impact-Aware Reinforcement Learning for Opportunistic Optimal Liquidation, Outperforms TWAP and a Book-Liquidity VWAP on BTC-USD Replays
Enzo Duflot 2025
Preprint
Access with Article Galaxy
Add to collection
Cite
Hidden assumptions: assumes stationarity and replications in BTC-USD LOB that survive regime shifts; ignores regime dependence, regime-change risk, and non-stationary microstructure.
Survivorship bias: uses historical replay without explicit handling of regimes with missing liquidity or changed participant behavior; may overstate robustness.
Confirmation bias: selects baselines (TWAP/VWAP-like) that favor the RL agent; lacks truly diverse controls (risk-parity, passive benchmarks, zero-intensity baselines).
Computational bottlenecks: PPO training with depth-20 LOB features is heavy; real-time latency risk not quantified; replay-based training may not meet production RTT budgets.
Software design flaws: lacking modularity for feature ablation, poor separation of policy from execution logic, and insufficient fault/instrument-compatibility testing; insufficient latency budgeting and backtesting guardrails.
Overfitting risks: overfits to Feb-2020 regime; small out-of-sample windows risk optimistic gains; non-stationary markets and liquidity regimes not tested.
Data leakage: potential leakage via endogeneity (transient impact, latency) if not carefully separated between train/test and simulated execution paths.
Statistical weaknesses: single-month test, multiple comparisons, p-values sensitive to rollouts; bootstrap/HFDR adjustments may not fully account for non-iid data.
Market microstructure mistakes: ignores hidden liquidity, order-book queue dynamics beyond top-20, latency jitter, and partial-fill realizations; assumes linear, additive impact.
Trading mistakes: sell-only constraint may ignore upside hedges; disregards inventory risk, risk limits, and slippage distributions under stress.
Architecture mistakes: RL loop tightly coupled to market microstructure; lacks modular risk controls, auditability, and explainability; insufficient drift/drawdown controls and fallback strategies.
If disagreeing with a recommendation: the claim of robustness across regimes is premature without multi-regime, longer-horizon, and stress-tested out-of-sample validation.
Better alternative: implement a regime-aware, risk-controlled framework with explicit out-of-sample testing across multiple market regimes, include diverse baselines, robust latency-aware deployment, feature ablations, conservative risk controls, and a modular, auditable architecture with simulated ablation studies and pre-registered evaluation protocol.
4	
Tackling the Problem of State Dependent Execution Probability: Empirical Evidence and Order Placement
Vincent Ragel 2023
SSRN Journal
View PDF
Add to collection
Cite
Hidden assumptions: assumes stable, stationarily distributed multi-timeframe signals; ignores regime shifts and structural breaks that invalidate backtests.
Survivorship bias: backtests rely on surviving instruments/venues only, overstating robustness.
Confirmation bias: selects features and horizons that worked in past data, discounting counterexamples.
Computational bottlenecks: backtesting across many timeframes and high-resolution LOB data creates prohibitive compute and I/O demands; risk of overfitting through excessive parameter tuning.
Software design flaws: tight coupling between data feeds, feature extraction, and execution logic; lacks modularity, clear data provenance, and reproducibility.
Overfitting risks: multi-timeframe model with many overlapping signals increases chance of spurious correlations; inadequate cross-validation across regimes.
Data leakage: using future information (e.g., post-processing of fills, latency-implied features) in training or feature construction.
Statistical weaknesses: insufficient out-of-sample testing, p-hacking, multiple hypothesis testing without correction.
Market microstructure mistakes: ignores queue position dynamics, order cancellation risk, latency arbitrage, and adverse selection across venues.
Trading mistakes: assumes execution probability functions that may be miscalibrated; ignores slippage, partial fills, and market impact under real liquidity stress.
Architecture mistakes: potential single points of failure, insufficient fault tolerance, and brittle deployment; lack of clear latency budgets and determinism.
If disagreeing with a recommendation, justify by: real-world regime changes, data/latency constraints, and non-stationary liquidity provision observed in practice.
Better alternative: adopt a disciplined, regime-aware framework with rigorous out-of-sample validation, strict data governance to prevent leakage, modular architecture with explicit latency budgets, and a market microstructure–driven execution model calibrated to real order-book dynamics; use robust cross-venue, cross-asset backtesting with walk-forward validation and prespecified stopping rules to mitigate overfitting.
5	
Comparing the market microstructure between two South African exchanges
Ivan Jericevich, Patrick Chang, Tim Gebbie 2020
Preprint
4140
View PDF
Add to collection
Cite
Hidden assumptions: assumes coherent cross-timeframe signal alignment, stationary relationships across scales, and identical data quality across feeds; ignores regime shifts and event-driven risk that break cross-scale consistency.
Survivorship/selection bias: basing architecture on assets with complete history or favorable backtest periods, neglecting delisted or illiquid names that would stress the system.
Confirmation bias: prioritizes timeframes that show desired predictive coherence while discarding noisy or conflicting signals from other scales.
Computational bottlenecks: multi-timeframe data fusion at tick to daily may explode CPU/memory; real-time cross-scale calibration, backtesting drift, and latency risks are under-specified.
Software design flaws: monolithic data adapters for each timeframe, brittle schema evolution, and unclear boundary between feature extraction, signal generation, and execution; lacks explicit data provenance and testability hooks.
Overfitting risks: many handcrafted features per timeframe with potential leakage during cross-validation; risk of peek-ahead via rolling-window lookups.
Data leakage: features computed from future data or across correlated instruments in real time; insufficient isolation between training and live data streams.
Statistical weaknesses: insufficient out-of-sample testing, not accounting for multiple hypothesis testing across scales, p-hacking via lookback windows.
Market microstructure mistakes: neglects cross-venue order-book depth, latency arbitrage, and asynchronous fills that differ by timeframe; ignores impact of microstructure noise on signals.
Trading mistakes: assumes execution costs are stable across regimes; may understate slippage and adverse selection in fast markets.
Architecture mistakes: lacks clear failover, observability, and backtesting-to-live parity; no explicit risk controls or guardrails for portfolio-wide execution risk.
If disagreeing with any recommendation, the critique: the plan overestimates cross-timeframe coherence; prefers a modular, event-driven, risk-aware pipeline with strict data isolation, robust backtesting, and per-timeframe validation before cross-timeframe integration.
Better alternative: adopt a modular, streaming-architecture with explicit data provenance, per-timeframe validation, simulation-first deployment, guardrails for leakage, and a staged cross-timeframe fusion only after proven robustness across regimes; include market microstructure-aware execution models and multi-venue liquidity considerations.
6	
CoinTossX: An open-source low-latency high-throughput matching engine
Ivan Jericevich, Dharmesh Sing, Tim Gebbie 2022
SoftwareX
1000
View PDF
Add to collection
Cite
Hidden assumptions: multi-timeframe feasibility assumes synchronized data across all timeframes with identical symbol universes and no regime shifts; ignores asynchronous data, data gaps, and non-stationarity between intervals.
Survivorship bias: backtests only on liquid, continuously traded instruments; ignores delisted/illiquid assets and survivorship of symbols across historical windows.
Confirmation bias: selection of timeframes and features that retrospectively support the architecture; lacks out-of-sample and cross-market testing.
Computational bottlenecks: cross-timeframe aggregation delays, memory blow-ups from storing per-instrument histories at multiple granularities; high CPU/memory for real-time windows.
Software design flaws: tight coupling between feed handlers and strategy logic; insufficient decoupling for backtesting vs live; lack of deterministic order of operations leading to subtle race conditions.
Overfitting risks: overly complex feature sets per timeframe; hyperparameter tuning using past data without proper holdout and walk-forward validation.
Data leakage: leakage via future price/volume in multi-timeframe aggregates or look-ahead in feature computation; improper sequencing in live vs test pipelines.
Statistical weaknesses: multiple hypothesis testing without proper corrections; overreliance on p-values from in-sample metrics; instability across regimes.
Market microstructure mistakes: ignores order-book dynamics, latency, slippage, partial fills, adverse selection; assumes continuous fills across timeframes.
Trading mistakes: ignoring transaction costs, market impact, and capital constraints; failure to model risk in multi-timeframe decisions; assumes proportional liquidity across instruments.
Architecture mistakes: lack of modularity for plugging alternative data sources; single-point failure in data routing; inadequate fault tolerance, replayability, and backfill handling.
If disagreeing with recommendations, explain: recommendations that push heavy multi-timeframe coupling without robust synchronization and latency budgeting likely fail under real-time constraints; require decoupled, streaming-first design with explicit backtesting simulators and strict data provenance.
Better alternative: adopt a streaming, event-driven architecture with clear data provenance, per-instrument pipelines, independent backtester with walk-forward validation, latency-aware feature computation, and strict leakage-free test harness; use market microstructure-aware models with realistic costs, slippage, and regime-adaptive strategies; enforce modularity, strict replayability, and risk budgets per timeframe; implement robust cross-validation, out-of-sample testing, and pre-commitment to performance envelopes across regimes.

Model Predictive Control For Trade Execution
Thomas P. McAuliffe, Samuel Liew, Yuchao Li et al. 2026
Preprint
View PDF
Add to collection
Cite
Key weaknesses and risks:

Hidden assumptions: constant market impact model; stable execution budgets; full observability of volumes; neglect of regime shifts and latency effects; assumes six months NASDAQ Level 3 data generalizes to live liquidity.
Survivorship bias: uses historical fills and prices without accounting for excluded failed executions or halted venues; may overstate performance.
Confirmation bias: emphasizes MPC gains while under- or omitting negative scenarios (adverse market conditions, extreme volatility).
Computational bottlenecks: real-time quadratic program solves per step; high-lreq latency risk in production; scaling with instrument count and microstructure data.
Software design flaws: modularity claims unproven under load; dependency on accurate base policy; risk of brittle near-boundary constraints; insufficient fault tolerance, backtesting rigidity.
Overfitting risks: tuning to historical liquidity and schedule targets; risk of param drift in volatile regimes; poor out-of-sample robustness.
Data leakage: use of contemporaneous price/volume that would not be available pre-trade; leakage from future order flow or fills into model.
Statistical weaknesses: reliance on mean-variance with quadratic costs; potential mis-specification of cost structure; insufficient uncertainty quantification.
Market microstructure mistakes: ignores order-book dynamics beyond simple imbalance; neglects latency arbitrage, hidden liquidity, and adverse selection.
Trading mistakes: over-optimistic schedule adherence; insufficient handling of partial fills, cancel/replace fragility; failure to adapt to venue fragmentation.
Architecture mistakes: single-model dependency; lack of rigorous risk and compliance controls; potential single point of failure in the MPC loop.
Against proposed: MPC with fixed bounds may underperform in regime shifts; and outer-loop hyperparameter control could introduce destabilizing feedback.
Better alternative: use a robust, multi-model execution engine with explicit regime-switching, latency-aware architecture, and strong backtesting with walk-forward and leakage checks; incorporate conservative risk budgets, portfolio-level constraints, and an asynchronous, fault-tolerant design; replace static mean-variance with distributional risk (CVaR) and stochastic programming with out-of-sample validation; decouple forecasting, execution strategy, and risk management into communicating services with bounded latency.
If disagreeing with any recommendation: avoid heavy reliance on a single MPC approach; instead, adopt an ensemble of execution policies with transparent monitoring and rollback.
Propose alternative: modular, latency-aware, fault-tolerant execution fabric using event-driven microservices, separate forecasting, schedule generation, and execution decision services, with rigorous backtesting including leakage checks, regime-aware risk controls, and continuous calibration.
8	
JaxMARL-HFT: GPU-Accelerated Large-Scale Multi-Agent Reinforcement Learning for High-Frequency Trading
Valentin Mohl 2025
Preprint
View PDF
Add to collection
Cite
Hidden assumptions: assumes stationarity across timeframes and markets; assumes MARL-style agents generalize to live markets; presumes data and labels are synchronized across timeframes without leakage.
Survivorship bias: relies on historical contemporary instruments and liquid periods, ignoring delisted or illiquid periods to inflate performance.
Confirmation bias: selects features/pairs that confirm multi-timeframe benefits while downweighting counterexamples.
Computational bottlenecks: multi-timeframe data explosion, feature fusion latency, cross-timeframe backtesting load, and potential GPU/CPU bottlenecks without clear throughput guarantees.
Software design flaws: tight coupling between timeframes, brittle schema evolution, inadequate observability, and insufficient rollback/.canary paths for models.
Overfitting risks: over-tuning across multiple timeframes and hyperparameter sweeps; look-ahead in cross-timeframe validation.
Data leakage: risk of using future information when aggregating signals across timeframes; misalignment between live and backtest clocks.
Statistical weaknesses: non-stationary signals, multiple hypothesis testing without proper correction, p-hacking via extensive hyperparameter sweeps.
Market microstructure mistakes: ignores latency, partial fills, slippage, and order-impact; assumes idealized order books in architecture.
Trading mistakes: neglects execution risk, inventory constraints, risk controls, and regime shifts; over-reliance on synthetic benchmarks.
Architecture mistakes: no clear separation of concerns between data ingestion, feature computation, model training, and live-decision layers; insufficient fault tolerance and deployment safety nets; lack of standardized backtesting with realistic fill models.
If disagreeing with any recommendation, the critique should state that live deployment requires explicit market impact modeling and robust slippage/inventory risk controls.
Better alternative: adopt a modular streaming architecture with strict data lineage, leakage guards, holdout-validation with walk-forward and calendar-time fixes, incorporate market impact models, use a single-timeframe dominant signal with validated cross-timeframe ensembling, and implement rigorous risk and fault-tolerance controls; consider ABM/MARL only in controlled, batched offline research before live deployment.
9	
AgenticAITA: A Proof-Of-Concept About Deliberative Multi-Agent Reasoning for Autonomous Trading Systems
Ivan Letteri 2026
Preprint
View PDF
Add to collection
Cite
Hidden assumptions: assumes multi-timeframe signals are stationary and combinable; presumes agentic deliberation improves over offline training; assumes dry-run performance translates to live conditions; assumes deterministic safety gates don’t introduce bias or latency.
Survivorship bias: backtests and signals likely tested only on surviving assets/regimes; ignores delisted or failed assets and regime shifts.
Confirmation bias: emphasis on scenarios that validate the deliberative loop while downplaying failures or negative results; limited out-of-sample or walk-forward testing.
Computational bottlenecks: sequential deliberative pipeline with multiple LLM agents and mutex scheduling likely induces latency and has poor throughput for high-frequency contexts; scaling to hundreds of assets may be infeasible.
Software design flaws: lack of clear state management, auditability gaps for agent decisions, potential non-determinism in LLM outputs, insufficient fail-safes for agent coordination; hard gates may bottleneck or deadlock.
Overfitting risks: evaluation relies on constrained dry-runs; risk that correlation-breaking signals dominate in live regimes; reliance on agent negotiations can overfit to historical inter-agent dynamics.
Data leakage: risk from using contemporaneous market data to generate features for the same decision cycle; insufficient delays or proper data partitioning across agents.
Statistical weaknesses: no robust out-of-sample validation plan; unclear treatment of multiple testing, p-hacking, or backtest overfitting; uncertain significance metrics for signals.
Market microstructure mistakes: ignores latency, queue position, market impact modeling accuracy; assumes static liquidity profiles; uses crypto-like assumptions for execution costs that may not generalize.
Trading mistakes: potential for model-to-trade feedback loops via agent coordination; risk of over-trading or constrained risk management under volatile regimes.
Architecture mistakes: monolithic agent network may be brittle; lack of modular, testable components; insufficient use of reproducible, versioned contracts; safety layer may be reentrancy-prone and insufficient for edge cases.
If disagreeing with any recommendation: treat live deployment with caution; the paper’s dry-run does not validate slippage, latency, or risk controls under real broker and exchange conditions.
Better alternative: adopt a modular, backtest-driven, risk-first multi-timeframe framework with explicit data hygiene, out-of-sample walk-forward, and deterministic execution paths; replace autonomous LLM-based deliberation with structured rule-based decision modules plus a supervised ML ensemble with shadow-mode testing and strict latency budgets; implement end-to-end backtest with realistic transaction costs, latency, and market impact; enforce strict data-snooping controls, formal verification of contracts, and robust risk controls before live trading.
10	
FinEvo: From Isolated Backtests to Ecological Market Games for Multi-Agent Financial Strategy Evolution
Mingxi Zou, J. Chen, Aotian Luo et al. 2026
Preprint
Access with Article Galaxy
Add to collection
Cite
Significant hidden assumptions: static market regime, stationarity of relationships across timeframes, and that simulated agents adequately sample strategy space; survivorship and data-snooping biases in selecting surviving agents and features; confirmation bias in favoring ecological dynamics without rigorous out-of-sample stress tests; bottlenecks from cross-agent synchronization, large-order simulations, and complex backtesting loops; software design flaws in modularity of multi-timeframe data feeds, clock drift, and deterministic replay; overfitting risk from tuning to historical microstructure and RSI/imbalance features; data leakage via using future order flow or news signals for current decisions; statistical weaknesses from nonstationary, non-Gaussian returns and multiple testing; market microstructure mistakes by assuming static liquidity and ignoring latency, queueing, and adverse selection; trading mistakes from naive order sizing, random wakeups, and lack of transaction cost modeling; architecture flaws in coupling ecological game with backtest accelerator, potential non-determinism, and brittle integration; likely, the FinEvo-like ecological framework may overstate robustness to regime shifts and external shocks without out-of-sample validation; propose a better alternative: a single framework that explicitly isolates a heterogeneous portfolio of backtested strategies, with strict out-of-sample live-simulated testing, cross-asset and cross-market regime stress tests, end-to-end data governance, latency-aware architecture, and a formalized risk-and-robustness metric suite; avoid ecological multi-agent fuzziness, rely on calibrated market-impact models, rigorous cross-validation with walk-forward, and preclude leakage by time-slicing data and using forward-looking signals only in future-handling simulations. If disagreeing with a recommendation, the critique: avoid relying on multi-agent ecological dynamics as a sole robustness proxy; replace with regime-aware, latency-aware backtesting plus live-trade sandbox with controlled exposure. Better alternative: modular, latency-conscious architecture with explicit data provenance, strict backtest-to-live handoff, robust risk controls, and validated market-microstructure models; implement a framework that uses portfolio-agnostic, out-of-sample evaluation and prevents overfitting via pre-registered hypotheses and closed testing.
11	
Geodesic Execution Slippage: A Statistical Physics Framework for Cryptocurrency Liquidity Risk
Ntebogang Dinah Moroke, Lebotsa Daniel Metsileng 2026
Entropy
View PDF
Add to collection
Cite
Hidden assumptions: assumes stationary multi-timeframe relationships, perfect upstream data, and representativeness of Level-2 order book features across regimes; presumes MS-GARCH-MaxEnt model is correctly specified.
Survivorship bias: backtests likely ignore failed or halted instruments, regime shifts, and survivorship of liquid assets only.
Confirmation bias: relies on a single-signal geodesic slippage metric weighting, neglecting multi-signal corroboration and risk premia evidence.
Computational bottlenecks: online inference <1s but offline calibration ~28h; multi-signal geometry (Betti numbers, curvature, Rips filtrations) scales poorly with depth and universe size.
Software design flaws: tight coupling between geometry module and trading engine; brittle feature extraction (time-varying topological thresholds); insufficient failover for data gaps.
Overfitting risks: extensive use of geometric/topological features with small sample windows; model selection in transient crises may backfit crisis-specific patterns.
Data leakage: possible leakage from future-price–driven order-book features if snapshot timing aligns with post-trade data; calibration requires careful alignment.
Statistical weaknesses: lack of out-of-sample drift tests; no robust cross-validation across regimes; multiple hypothesis testing without correction.
Market microstructure mistakes: assumes static liquidity islands; fails to account for hidden liquidity and venue fragmentation; ignores latency and routing effects.
Trading mistakes: potential overreliance on a single framework during regime changes; delayed signaling relative to fast microstructure dynamics.
Architecture mistakes: monolithic geometry engine; no modular abstraction for alternative metrics; insufficient logging/traceability for model risk.
If you disagree with any recommendation, the main issue is overstatement of online speed as sufficient for risk control; real-time performance must be complemented with robust backtesting across regimes and explicit risk limits.
Better alternative: adopt a modular, multi-signal framework with rigorous out-of-sample validation, regime-aware ensemble that includes traditional liquidity, volatility, and order-book features, implement strict data governance to prevent leakage, and use scalable, parallelizable feature pipelines with clear model risk controls; incorporate continuous monitoring, ablation studies, and operational risk testing with backtesting against diverse market conditions.
12	
A Multi‐agent System for Policy Design of Tick Size in Stock Index Futures Markets
Lijian Wei, Wei Zhang, Xiong Xiong et al. 2014
Syst. Res.
8050
Purchase for $45.95
Rent for $21.00
Add to collection
Cite
Hidden assumptions: multi-timeframe signals imply causal, non-stationary relationships; agent heterogeneity and execution costs are often ignored. Survivorship/overfitting: backtests tuned to look-good across selected windows; lookahead data leakage from future-timeframe alignment. Confirmation bias: tuning to confirm multi-timeframe coherence; neglect of regime shifts. Bottlenecks: cross-timeframe data fusion, feature normalization, and real-time ordering latency. Design flaws: tight coupling between strategy logic and data adapters; insufficient modularity for live/desk risk checks. Data leakage: sharing stateful indicators across timeframes; training on future bars. Statistical weaknesses: overreliance on paces and spurious correlations; insufficient out-of-sample robustness tests. Market microstructure: ignores order book dynamics, latency arbitrage, and tick-time alignment across markets. Trading mistakes: assume immediate tradability of cross-timeframe signals; ignore slippage and market impact. Architecture mistakes: monolithic pipeline; lacks backtesting-fail-safes, auditing, and risk controls. Better alternative: a strictly modular, event-driven architecture with isolated data streams, formal walk-forward and regime-aware validation, explicit market impact and latency models, robust cross-timeframe feature controls, and continuous risk-auditing with live-paper trading until proven stable across multiple market regimes. If any recommendation conflicts, favor modularity and risk controls over aggressive optimization.

Limit order books: a systematic review of literature
Abhinava Tripathi, Vipul Vipul, Alok Dixit 2020
QRFM
16040
Purchase for $46.95
Rent for $26.00
Add to collection
Cite
Hidden assumptions: assumes multi-timeframe signals are additive/compatible; ignores regime shifts and non-stationarity across timeframes; presumes latency and data fidelity are uniform across venues.
Survivorship bias: uses historical data that may exclude defunct securities, exchanges, or regimes, inflating performance and stability of cross-timeframe signals.
Confirmation bias: selects features and timeframes that validate the architecture while discarding counter-evidence or unfavorable microstructure signals.
Computational bottlenecks: parallelization across timeframes increases CPU/GPU load, memory, and I/O; risk of data skew and cache coherence issues; backtesting with consentaneous clocks may cause time-slicing errors.
Software design flaws: tight coupling between timeframe modules; insufficient abstraction for data feeds, latency, and event-driven sequencing; brittle schema evolution and schema drift risk.
Overfitting risks: excessive tuning to in-sample cross-timeframe patterns; sparse cross-validation across regimes; feature leakage between timeframes during feature construction.
Data leakage: intraday-to-end-of-day aggregations may leak future information; lookahead in feature engineering across horizons; improper handling of cancellations and order-execution data.
Statistical weaknesses: non-stationarity across timeframes; multiple testing without proper corrections; p-hacking through selective horizon choice; inadequate out-of-sample robustness checks.
Market microstructure mistakes: neglects order-book dynamics, latency, and venue fragmentation; ignores adverse selection, queue-position effects, and price impact of wakes/sleeps across timeframes.
Trading mistakes: assumes continuous tradability across all horizons; ignores slippage, fill rate, and market impact variability; overreliance on model-driven signals without risk controls.
Architecture mistakes: insufficient fault tolerance, monitoring, and hot-failover for data streams; no clear data provenance/audit trails; lack of formal verification for critical components; insufficient simulation-to-live deployment path.
If disagreeing with recommendations: the proposed decoupling across timeframes may be unworkable in stressed markets due to regime shifts and correlated shocks; prefer a unified, event-driven architecture with explicit risk controls and backtest-once-in-production governance.
Better alternative: adopt a modular, event-driven architecture with explicit data provenance, backtest-to-live bridging, cross-timeframe risk budgets, and rigorous out-of-sample and regime-aware validation; incorporate limit-order-book-aware features, latency-aware data handling, and robust guardrails for leakage and overfitting; employ cross-timeframe validation with bootstrap or walk-forward analysis and strict multiple-testing corrections.
14	
PredictionMarketBench: A SWE-bench-Style Framework for Backtesting Trading Agents on Prediction Markets
Avi Arora, Ritesh Malpani 2026
Preprint
0040
Access with Article Galaxy
Add to collection
Cite
Hidden assumptions: assumes backtests fully capture real-time market microstructure, execution costs, and settlement risk; assumes prediction-market-like environments generalize to live equities; assumes stable maker/taker fee regimes and liquidity across episodes.
Survivorship bias: uses historical streams that may omit delisted or illiquid periods; may overlook regime shifts or market regime-specific risks.
Confirmation bias: benchmarks favoring simple, fee-aware alphas while discounting robust risk controls or drawdown behavior under stress.
Computational bottlenecks: event-driven replay with full LOB data is heavy; potential CPU/memory blowups for high-frequency paths; replay determinism may throttle exploratory testing.
Software design flaws: coupling to multiple market types via a single simulator; insufficiently modular architecture for swap/tests of new microstructure models; potential non-determinism in parallelized replay.
Overfitting risks: episodes chosen from past data enabling tailor-made strategies; risk of optimizing to known microstructure quirks; insufficient out-of-sample or walk-forward testing.
Data leakage: settlement and lifecycle events synchronized to UTC may leak future state into the agent; retrospective order-book shaping can bias results.
Statistical weaknesses: lacks robust out-of-sample significance testing, multiple-hypothesis correction, and proper bench-marking against transaction-cost-adjusted baselines; potential hindsight bias in episode construction.
Market microstructure mistakes: assumes LMSR and automated market makers; may ignore latency, queue-position dynamics, partial fills, slippage, and exchange-specific rules; underestimates impact of fees and settlement risk on real PnL.
Trading mistakes: insufficient risk controls for concentration, leverage, and stop-out logic; needs realistic slippage and latency models; ignores post-execution risk like option greeks or correlation breaks.
Architecture mistakes: monolithic backtester with tight coupling to episodes; lacks formal verification, observability, and reproducibility guarantees; insufficient cross-asset abstraction and capability to plug new microstructure models or live-feed interfaces.
If disagreeing with a recommendation: the proposed emphasis on fee-aware alphas without rigorous cross-asset risk, stress-testing, and live execution validation is insufficient for hedge-fund readiness.
Better alternative: adopt a modular, risk-focused backtesting framework with explicit out-of-sample walk-forward, full transaction-cost modeling, latency and liquidity-aware execution, and independent microstructure simulators; run diverse, regime-shifted episodes with proper statistical rigor and cross-asset validation; incorporate live-constraint testing and formal code reviews.
One-sentence synthesis: the design underestimates data leakage, overfitting, microstructure risk, and scalability, and should be re-architected into a modular, cash-and-carry aware, stress-tested, latency-aware backtester with sound statistical validation and independent microstructure simulation.
15	
Will the Market Fix the Market? A Theory of Stock Exchange Competition and Innovation
Eric Budish, Robin S. Lee, John J. Shim 2019
SSRN Journal
13051
View PDF
Add to collection
Cite
Hidden assumptions: assumes multi-timeframe signals are commensurate and serially tradeable without regime change; ignores regime risk and non-stationarity across timeframes.
Survivorship bias: relies on backtests that exclude delisted or failed securities and survivorship-prone data.
Confirmation bias: selects indicators that align with desired outcomes; ignores falsified or neutral results.
Computational bottlenecks: cross-timeframe feature generation, synchronization, and latency-optimized paths risk CPU/GPU saturation; backtesting scale may be infeasible in production.
Software design flaws: tight coupling between backtest and live engines; brittle time-alignment logic; inadequate failover, observability, and data lineage.
Overfitting risks: excessive tuning to historical multi-timeframe windows; lack of holdout and walk-forward validation.
Data leakage: look-ahead leakage across timeframes; improper handling of timestamp alignment and price/quote data.
Statistical weaknesses: multiple hypothesis testing without proper correction; nonstationary variance across regimes; inadequate out-of-sample testing.
Market microstructure mistakes: ignores latency, order-book dynamics, slippage, and adverse selection in live trading.
Trading mistakes: assumes instantaneous execution and ignores market impact and capacity constraints.
Architecture mistakes: monolithic pipelines; no modular microservices for data ingest, feature computation, and risk checks; insufficient risk controls and kill switches.
If disagreeing with a prior recommendation, the root cause is that proposed cross-timeframe architectures often mask regime shifts and data-snooping; better alternative: implement a modular, regime-aware framework with strict out-of-sample validation, robust data governance, and explicit handling of latency, market impact, and order-execution realism.
Better alternative: adopt a hybrid architecture with separate data-integration, feature-engineering, backtesting, and live-trading layers, formalized data lineage, walk-forward and cross-validation with pre-registered hypotheses, conservative risk controls, and explicit latency/market-impact models; use event-time processing and real-time latency budgets to prevent leakage and ensure realism.
16	
An Impulse Control Approach to Market Making in a Hawkes LOB Market
Konark Jain 2025
Preprint
Access with Article Galaxy
Add to collection
Cite
Hidden assumptions: assumes LOB dynamics and Hawkes clustering fully capture microstructure; assumes discrete impulse interventions suffice for continuous-time risk; assumes RL generalizes from simulated to live markets.
Survivorship bias: relies on simulated or historical data that may exclude failed strategies, liquidity droughts, or regime shifts.
Confirmation bias: selects models and metrics (e.g., high Sharpe) that favor the proposed architecture while underreporting drawdowns, transaction costs, and slippage.
Computational bottlenecks: high-dimensional HJB-QVI and RL components are expensive; real-time decision latency and feature computation may fail under peak load.
Software design flaws: coupling of non-stationary impulse control with RL can cause brittle interfaces; risk of data leakage between training and live deployment; insufficient modularity for swapping microstructure models.
Overfitting risks: RL agents tuned to simulated LOB scenarios may overfit to those environments; lack of out-of-sample stress testing across regimes.
Data leakage: potential leakage from future event information into state representations; inadvertent exposure of test data during hyperparameter tuning.
Statistical weaknesses: reliance on synthetic performance (e.g., Sharpe > 30) without robust turnover, drawdown, and liquidity-adjusted metrics; improper handling of market impact and slippage in evaluation.
Market microstructure mistakes: Hawkes-based realism may still idealize order-book resiliency, latency, and queue dynamics; impulse control discretization could misrepresent reaction times and execution quality.
Trading mistakes: insufficient consideration of inventory risk, adverse selection, and risk constraints under regime shifts; insufficient guardrails for extreme events.
Architecture mistakes: unclear separation of concerns between model, data, and execution layers; potential non-determinism in RL policies; difficulty validating and auditing decisions in live markets.
If disagreeing with recommendations: reliance on deep RL for high-stakes trading without rigorous risk controls and explainability is unacceptable; a model-based, robust, and auditable control framework with stress-tested sim-to-live transfer is preferable.
Better alternative: a modular, model-based replication of microstructure dynamics with explicit risk budgets, deterministic-like fallback policies, rigorous out-of-sample regime testing, and a lightweight, verifiable execution layer augmented by offline policy evaluation and safe-on-live-rollout constraints; replace end-to-end RL with parametric, statistical decision rules plus conservative Monte Carlo risk assessments, and implement continuous monitoring with kill-switches and Aurora-style backtests.
17	
Explainable Patterns in Cryptocurrency Microstructure
Bartosz Bieganowski, Robert Ślepaczuk 2026
Preprint
Access with Article Galaxy
Add to collection
Cite
Hidden assumptions: stable cross-asset microstructure signals generalize across regimes and time; backtests assume future liquidity and participation resemble historical periods.
Survivorship bias: uses assets and data that survived to present, excluding delisted/extinct instruments and regime-change events.
Confirmation bias: SHAP-based interpretations may overstate causal relevance of engineered features while ignoring confounders.
Data leakage: time-series cross-validation must ensure no future information leaks into training; look-ahead risk if feature dynamics lag validation windows.
Overfitting risks: high feature dimensionality with universal feature libraries risks memorizing idiosyncrasies; rolling folds must avoid leakage from slow-moving features.
Statistical weaknesses: reliance on SHAP without out-of-sample robustness tests; insufficient stress testing under regime shifts and microstructure shocks.
Market microstructure mistakes: backtests on top-of-book/taker and fixed-depth maker may ignore hidden liquidity, latency, queueing, and order routing frictions; ignores tick-size and price impact under stress.
Trading mistakes: assumes tradability of signals without considering execution costs, slippage, and market impact at scale; adversarial behavior during crashes not fully explored.
Architecture mistakes: monolithic pipeline may hinder modular testing of microstructure components; potential single-point-of-failure in feature computation and data ingestion; insufficient failover and data lineage tooling.
Computational bottlenecks: 1-second freq data with CatBoost and SHAP explanations can be heavy; real-time inference and backtesting at scale may exceed budget.
Data leakage risks: careful separation of features with slow dynamics is required; cross-validation design must preserve temporal ordering and avoid leakage from future information.
Overfitting risks in hyperparameters: depth, iterations, and learning rate tuned on historical periods may not generalize; need robust out-of-sample validation.
Better alternative: adopt a modular, regime-aware architecture with explicit risk controls: separate data ingestion, feature engineering, model training, and execution, with progressive backtesting across multiple market regimes, explicit transaction cost models, and conservative, time-aware cross-validation plus out-of-sample walk-forward tests; incorporate microstructure realism through simulated latency, queue dynamics, and market-impact models; emphasize robust, sparse, and interpretable features with pre-registered hypothesis tests to reduce multiple testing and overfitting.
If disagreeing with a recommendation: explain that universal cross-asset features in crypto may not transfer to traditional equity/fixed income microstructures due to different liquidity, latency, and participant behavior; require asset-class-specific feature libraries and validation.
18	
Market Microstructure Knowledge Needed for Controlling an Intra-Day Trading Process
Charles‐Albert Lehalle 2013
170110
Purchase for $38.95
Add to collection
Cite
Hidden assumptions: multi-timeframe signals imply stable cross-timeframe relationships; ignores regime changes and non-stationarity; assumes data alignment across frequencies without latency/clock drift handling.
Survivorship bias: backtests likely exclude delisted assets, survivorship of instruments, and ignored corporate actions; overstates robustness.
Confirmation bias: cherry-picks timeframes that fit the hypothesis; ignores falsification tests and out-of-sample drift.
Computational bottlenecks: data alignment and cross-asset conditioning across many timeframes explode memory and CPU; real-time latency becomes prohibitive; improper parallelization leads to race conditions.
Software design flaws: monolithic data flow; tight coupling between data ingestion, feature generation, and trading logic; weak backtesting fidelity; insufficient logging, observability, and reproducibility hooks.
Overfitting risks: excessive feature engineering per timeframe; parameter tuning on in-sample periods; lack of walk-forward validation.
Data leakage: intraday-to-daily leakage through look-ahead or timestamp misalignment; stale data in feature pipelines; improper handling of precipitation of trading data (latency, market opens/ closes).
Statistical weaknesses: non-stationary performance metrics; multiple hypothesis testing without correction; spurious correlations across timeframes; improper handling of transaction costs and slippage.
Market microstructure mistakes: ignoring latency, order book depth, bid-ask dynamics, and price impact; assuming perfect execution across venues; underestimating friction in intraday liquidity.
Trading mistakes: assuming universal profitability across regimes; neglecting regime-switching risk and capacity constraints; ignoring risk of model decay and negative skew.
Architecture mistakes: lack of modularity for plug-in microstructure models; brittle deployment with hard real-time constraints; insufficient risk controls, kill switches, and scenario testing; inadequate data lineage and auditability.
If any recommendation is kept, justify why it still fits despite flaws; otherwise, propose a better alternative: adopt a modular, regime-aware, backtest-validated framework with strict data-siloing, robust cross-validation (including walk-forward and out-of-sample stress tests), explicit latency/edge-case handling, microstructure-aware execution models, and scalable streaming architecture with verifiable reproducibility.
Better alternative: separate research (feature-generation) and trading (execution) layers; use backtestable, latency-aware simulators; implement strict data governance, leakage checks, and multi-regime evaluation; employ probabilistic risk metrics and transaction-cost-aware optimization; validate with out-of-sample live paper trading and degrade gracefully under regime shifts.

Optimization of High-Frequency Trading Strategies Using Deep Reinforcement Learning
Guanghe Cao, Yitian Zhang, Qi Lou et al. 2024
JAIGS
9000
View PDF
Add to collection
Cite
Key weaknesses: hidden/implicit assumptions about stationarity and cross-market generalizability; survivorship bias in backtests (only liquid NASDAQ stocks used, limited horizon); confirmation bias in reporting Sharpe uplift without out-of-sample or regime testing; computational bottlenecks from high-dimensional DRL (CNN/LSTM) on tick data; design flaws in data handling (potential data leakage from train/test split on time series, look-ahead risk); overfitting risk from hyperparameter sensitivity and small evaluation window; market microstructure simplifications (latency, order types, market impact ignored); trading mistakes (reward tuned to Sharpe with transaction costs undervalued, risk of excessive trading); architecture mistakes (multi-timeframe DRL adds complexity with diminishing returns; lack of robust risk controls, explainability, and monitoring); statistical weaknesses (no robust out-of-sample, p-hacking risk); architecture alternative: recession-resistant, modular backtest with strict walk-forward, A/B testing across regimes, simpler signal pipelines with explicit risk budgeting, latency-aware microstructure simulator, and hybrid rule-based/ML with conservative risk limits; better approach: implement a low-lidelity, latency-conscious, backtested, regime-aware framework with clear data lineage, strict leakage controls, and formal validation before live deployment.
20	
Order flow analysis of cryptocurrency markets
Eduard Silantyev 2019
Digit Finance
15080
Access with Article Galaxy
Add to collection
Cite
Hidden assumptions: assumes multi-timeframe signals are additive and synchronizable despite differing data resolutions and latency; ignores regime shifts and non-stationarity across timeframes.
Survivorship/overfitting/data leakage: backtests likely cherry-pick timeframes and assets that fit; look-ahead bias across feature generation (future data used for current signals) not addressed.
Confirmation bias: selects timeframes that confirm the hypothesis; ignores divergent signals or periods of regime change.
Computational bottlenecks: cross-timeframe feature generation and backtesting explode combinatorially; real-time latency, data ingest, and storage costs understate risk.
Software design flaws: tight coupling between data feeds and strategy logic; lacking modularity, testability, and reproducibility; insufficient logging for auditability.
Overfitting risks: parameter tuning per timeframe without out-of-sample or walk-forward validation; risk of curve-fitting to historical microstructure noise.
Data leakage: potential leakage from future order-flow events into current signals; improper handling of end-of-day and rollovers across contracts.
Statistical weaknesses: assuming linear relationships in order-flow-to-return mapping; multiple testing without proper correction; non-stationary error distributions.
Market microstructure mistakes: ignores latency, slippage, and bid-ask bounce; neglects impact of large traders on order flow; assumes order-flow imbalance translates to price moves contemporaneously.
Trading mistakes: ignores transaction costs, market impact, and capacity constraints; assumes liquid markets across all multi-timeframe windows.
Architecture mistakes: lacks a robust data governance layer, versioned feature stores, and backtest integrity checks; insufficient failover and observability for live trading.
If disagreeing with any recommendation: propose eliminating multi-timeframe stacking in favor of a single, regime-aware adaptive model with robust walk-forward validation and explicit transaction cost modeling.
Better alternative: adopt a modular, latency-aware architecture with a single, validated feature set derived from a rigorous walk-forward framework, explicit market microstructure calibration, backtest with transaction costs and slippage, and strong data governance; incorporate regime detection and non-linear, robust statistics (e.g., ML models with cross-validation and out-of-sample tests) to mitigate overfitting.
21	
Frequent Batch Auctions and Informed Trading
Steffen Eibelshäuser, Fabian Smetak 2022
SSRN Journal
3000
View PDF
Add to collection
Cite
Hidden assumptions: assumes MTFs produce richer signal without data leakage; assumes latency arbitrage mitigated by design without empirical proof; presumes synchronization across timeframes without causality validation.
Survivorship bias: backtests likely only on surviving assets/instruments, ignoring delisted or failed securities and regime shifts.
Confirmation bias: selection of timeframes that align with desired signals; ignores negative results across regimes.
Computational bottlenecks: cross-timeframe data fusion and alignment spikes CPU/RAM; test-and-trade latency may exceed tolerances; risk of excessive memory churn.
Software design flaws: tight coupling between adapters and strategy logic; insufficient fault isolation; brittle schema evolution for multi-timeframe data; lack of clear data provenance.
Overfitting risks: multiple timeframe combinations raise risk of data-snooping; hyperparameter tuning across timeframes without out-of-sample guardrails.
Data leakage: potential leakage from future bars or aggregated statistics into real-time signals; improper handling of look-ahead in feature engineering.
Statistical weaknesses: multiple testing without proper correction; nonstationary features across regimes; insufficient out-of-sample robustness checks.
Market microstructure mistakes: assumes uniform response across venues; ignores latency, queue dynamics, and adverse selection in multi-timeframe signaling.
Trading mistakes: over-trading from converging signals; excessive turnover leading to slippage; ignoring transaction costs and slippage in signals.
Architecture mistakes: no clear SLA for data freshness; monolithic ETL/compute path hindering scalability; lack of modularity for swap of data sources or venues.
If disagreeing with a recommendation, justify: avoid complex multi-timeframe tricks without rigorous ablation studies and cross-venue validation; risk of systemic fragility.
Better alternative: start with a single, robust, validated signal pipeline with strict out-of-sample testing, then progressively layer time-aligned, calibrated features with formal leakage checks; implement modular, event-driven microservices with explicit data lineage, volatility-robust features, and microstructure-aware costs; incorporate FBA-like market design insights only after empirical, venue-specific liquidity and latency analyses; enforce proper cross-validation, multiple hypothesis correction, and guardrails against overfitting; simulate with realistic transaction costs and slippage in all backtests.
22	
An Agent-Based Computational Finance Simulation Model to Study Market Efficiency
Wei Feng, Keng Siau, Wee‐Yeap Lau et al. 2025
journal of global information management
View PDF
Add to collection
Cite
Hidden assumptions: assumes immediate, frictionless execution and representative agent behavior; ignores execution latency, queue dynamics, and behavioral regime shifts across regimes.
Survivorship bias: relies on post-hoc, cleaned data without addressing delisted/inactive assets or regime-dependent survivorship in multi-timeframe signals.
Confirmation bias: tendency to favor T+0 benefits (price discovery, liquidity) without stress-testing under volatility spikes, regime changes, or during market stress.
Computational bottlenecks: simulating cross-timeframe interactions with fine-grained microstructure can explode state space; risk of combinatorial explosion in feature sets and backtesting scenarios.
Software design flaws: tight coupling between timeframes; brittle data pipelines; lacking clear data provenance, feature lineage, and rollback/apt rollback for replays; inadequate observability and reproducibility controls.
Overfitting risks: extensive backtesting across multiple horizons with many features risks overfitting to historical microstructure idiosyncrasies.
Data leakage: potential leakage from future information across timeframes if synchronization not strictly causal; look‑ahead in cross-timeframe aggregations.
Statistical weaknesses: non-stationarity across timeframes; multiple hypothesis testing without proper p-value adjustment; risk of p-hacking via retrospective horizon selection.
Market microstructure mistakes: ignores order queue dynamics, latency, slippage, race conditions, and adverse selection in real-time execution; assumes immediate fill for modeled trades.
Trading mistakes: assumes costless or simplified execution costs; ignores regime-dependent liquidity dry-ups and market impact of large orders; insufficient risk controls around adverse selection.
Architecture mistakes: lack of modularity for independent timeframe engines; monolithic data model; insufficient fault isolation and replayability.
If disagreeing with a recommendation: the push for tighter cross-timeframe integration often amplifies data latency and coherence requirements, increasing risk of misalignment across venues and timesteps.
Better alternative: adopt a modular, event-driven architecture with explicit data lineage, strict causality across timeframes, robust backtesting with walk-forward and cross-validation, explicit handling of latency, slippage, and market impact, and a risk-focused framework with instrumentation for stress-testing microstructure under regime shifts.
Brief recommended fix: implement decoupled timeframes with a central orchestrator; use standardized, latency-aware data interfaces; enforce strict no-look-ahead rules; incorporate transaction cost models, slippage, latency figures, and market impact into simulations; require out-of-sample and walk-forward validation to mitigate overfitting.
23	
Evaluating LLMs in Finance Requires Explicit Bias Consideration
Yaxuan Kong, Hoyoung Lee, Yoontae Hwang et al. 2026
Preprint
Access with Article Galaxy
Add to collection
Cite
Hidden assumptions: assumes perfect cross-timeframe synchronization, homogeneous data quality across windows, and stationarity of regime behavior; ignores regime shifts and non-stationarity between timeframes.
Survivorship bias: potential backtesting only on surviving assets/strategies, overestimating robustness across drawdowns and new market entrants.
Confirmation bias: architecture may favor inputs/indicators that validate multi-timeframe coherence while downplaying conflicting signals or microstructure frictions.
Computational bottlenecks: combinatorial explosion of features across N timeframes; risk of data duplication and excessive memory; latency from cross-timeframe aggregation harming latency-sensitive trading.
Software design flaws: tight coupling between components; lack of clear data lineage and versioning; inadequate real-time guarantees and fault tolerance; insufficient modularity for swapping models/timeframes.
Overfitting risks: risk of overfitting to historical multi-timeframe patterns; in-sample coherence across timeframes may not generalize; complex feature interactions inflate variance.
Data leakage: leakage across timeframes via overlapping lookbacks, future data used in training, or misaligned sampling between training/validation and live data.
Statistical weaknesses: multiple hypothesis testing without proper corrections; non-stationary correlations; heavy-tailed distributions not accounted for; insufficient out-of-sample validation.
Market microstructure mistakes: ignores bid-ask bounce, slippage, order impact, latency, and discrete price levels; assumes continuous pricing across horizons.
Trading mistakes: ignores execution risk, risk of regime-dependent performance, and portfolio concentration from correlated signals.
Architecture mistakes: no clear backtesting-to-live risk controls, insufficient monitoring/telemetry, and lack of robust kill-switches; potential single points of failure in cross-timeframe data fusion.
If disagreeing with any recommendation: reject overly optimistic assumptions about zero or negligible latency and instantaneous execution; real-time constraints and slippage must be central.
Better alternative: adopt a structurally valid evaluation framework with explicit bias checks, separate backtest sanctuaries for each timeframe, robust out-of-sample and walk-forward testing, cross-timeframe causality analysis, and architecture that models latency, slippage, and microstructure explicitly; include leakage-robust data pipelines, modular components with clear data lineage, and continual stress-testing under regime changes.
24	
The New Quant: A Survey of Large Language Models in Financial Prediction and Trading
Weilong Fu 2025
Preprint
0010
View PDF
Add to collection
Cite
Hidden assumptions: assumes stable multi-timeframe signals transfer across regimes and that higher-timeframe trends reliably imply actionable lower-timeframe signals; ignores regime shifts and non-stationarity.
Survivorship bias: backtests only on surviving assets; ignores delisted/delayed data and survivorship in multi-timeframe aggregation.
Confirmation bias: selects indicators/timeframes that confirm a preferred narrative; ignores falsifying signals and out-of-sample discipline.
Computational bottlenecks: full-resolution, multi-timeframe stitching expands memory, I/O, and latency; backtests may be infeasible in live latency targets.
Software design flaws: tight coupling between data streams and strategy logic; unclear data lineage, versioning, and rollback; insufficient testability for edge cases.
Overfitting risks: multiple timeframes increase feature dimensionality; risk of curve-fitting to historical noise; inadequate out-of-sample and walk-forward testing.
Data leakage: cross-timeframe leakage via overlapping data windows, look-ahead in feature engineering, and misaligned timestamping.
Statistical weaknesses: non-stationary correlations across timeframes; multiple hypothesis testing without proper correction; p-hacking through extensive parameter sweeps.
Market microstructure mistakes: ignores latency, order book depth, queueing, slippage, and price impact across timeframes; assumes instantaneous execution.
Trading mistakes: improper risk controls across timeframes; ignores turnover, capacity, and edge effects; execution risk underrated.
Architecture mistakes: monolithic data fusion layer complicating audit trails; insufficient modularity for backtesting vs. live execution; lack of principled timing guarantees.
If any recommendation is disagreed with, its reliance on backtest realism and latency budgets must be justified with live-stakes constraints; otherwise, refactor toward separate signal generation, risk management, and execution layers with strict time-alignment.
Better alternative: adopt a modular, time-aligned pipeline with explicit backtesting mocks, regime-aware validation, survivorship controls, and robust latency budgets; use a single-source-of-truth symbol universe, fixed data windows, walk-forward testing, and a market-microstructure aware execution layer that enforces slippage and capacity limits; ensure data lineage, access controls, and auditable pipelines; apply rigorous leakage checks and multiple-horizon cross-validation, plus explicit guardrails against overfitting and leakage.

Toward Reliable Evaluation of LLM-Based Financial Multi-Agent Systems: Taxonomy, Coordination Primacy, and Cost Awareness
Phat Nguyen, Thang D. Pham 2026
Preprint
0010
View PDF
Add to collection
Cite
Key critique: the architecture likely embeds hidden assumptions about stable relevance across time, uniform latency tolerances, and perfect coordination signals; it risks survivorship and look-ahead biases in data pipelines; backtesting overfitting and regime-shift blindness are probable without explicit CBS-style evaluation; potential data leakage from RAG/timestamped data and lookback windows; coordination primacy may mask model quality issues and overfit to aggregator signals; software design flaws include brittle memory layers, single points of failure in the manager/arbitration layer, and inadequate auditability; market microstructure and transaction cost models may be oversimplified, ignoring slippage, latency, and order-execution dynamics; computational bottlenecks arise from multi-agent synchronization, memory decay, and real-time data ingress; architecture mistakes include overreliance on LLMs for trading decisions, insufficient backtesting infrastructure, and lack of robust failover; biases include confirmation bias in assuming coordination improves outcomes regardless of cost; data leakage through timestamp misalignment or feature leakage; overfitting risks from over-parameterized coordination rules and excessive historical fitting; propose replacing with a modular, strictly backtestable, plug-and-play architecture with formalized CBS evaluation, strict data lineage, leakage checks, and a conservative risk budget; alternative: build a single-agent, high-fidelity simulation with end-to-end market microstructure model, deterministic backtesting guardrails, and a separate validation harness for cross-asset, cross-venue, and regime robustness, then incrementally add coordination only after proven net value.