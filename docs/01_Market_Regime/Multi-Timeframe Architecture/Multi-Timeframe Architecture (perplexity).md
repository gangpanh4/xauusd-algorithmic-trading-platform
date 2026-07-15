<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# You are a senior quantitative researcher, institutional algorithmic trader, market microstructure researcher, and software architect.

Your objective is NOT to write code.

Your objective is to design the highest-quality Multi-Timeframe (MTF) architecture for a professional XAUUSD algorithmic trading platform.

Assume this platform already has the following architecture:

MarketData
↓
MarketStructureEngine
Swing
BOS
CHOCH
Liquidity
↓
PriceActionEngine
Order Block
Fair Value Gap
↓
ConfluenceEngine
↓
SignalGenerator
↓
RiskManager
↓
Execution

The platform is already fully modular and engine-based.

Your job is ONLY to research and design the optimal Multi-Timeframe framework.

Requirements

Do NOT give opinions.

Support every recommendation using one or more of:

• academic research
• institutional trading principles
• market microstructure
• ICT concepts
• Smart Money Concepts
• quantitative finance
• statistical reasoning
• professional discretionary trading
• practical implementation concerns

Whenever something cannot be proven, clearly state that it is a hypothesis.

================================================

Answer ALL of the following.

PART 1

What timeframe hierarchy is best for XAUUSD?

Should the platform use:

Monthly
Weekly
Daily
H4
H1
M15
M5
M1

or only some?

Explain why.

================================================

PART 2

For EACH timeframe explain its responsibility.

Example:

Weekly
Purpose:
What decisions should ONLY Weekly make?

Daily
Purpose:

H4
Purpose:

H1
Purpose:

M15
Purpose:

M5
Purpose:

Should M1 exist?

================================================

PART 3

How should information flow?

Should information only move downward?

Example

Weekly
↓

Daily
↓

H4
↓

H1
↓

M15
↓

M5

or can lower timeframes invalidate higher timeframes?

Explain.

================================================

PART 4

For EACH timeframe determine whether it should detect:

Swing

BOS

CHOCH

Liquidity

Equal High

Equal Low

Displacement

Market Structure Shift

Order Block

Fair Value Gap

Premium Discount

Balanced Price Range

Liquidity Void

Volume Imbalance

Explain why.

================================================

PART 5

Should every timeframe own a complete MarketStructureEngine and PriceActionEngine?

OR

Should lower timeframes reuse higher timeframe information?

Design the architecture.

================================================

PART 6

How should conflicts be resolved?

Example

Daily Bullish

H4 Bullish

H1 Bearish

M15 Bullish

M5 Bullish

Trade?

Reject?

Wait?

Explain.

================================================

PART 7

How should confluence scoring work?

Should higher timeframes receive more weight?

Example

Weekly 40%

Daily 30%

H4 15%

H1 10%

M15 5%

or something else?

================================================

PART 8

How should historical data be stored?

How many candles should each timeframe maintain?

Discuss memory usage and computational efficiency.

================================================

PART 9

Design the complete software architecture.

Include classes.

Include engines.

Include result objects.

Include data flow.

Include UML or diagrams if useful.

================================================

PART 10

Discuss common mistakes made by retail trading bots using Multi-Timeframe analysis.

Explain how to avoid them.

================================================

PART 11

If you were building a hedge-fund-grade XAUUSD trading platform from scratch today, how would your Multi-Timeframe subsystem look?

Be extremely detailed.

================================================

Output Format

Architecture

Reasoning

Evidence

Tradeoffs

Recommended Design

Potential Weaknesses

Future Extensions

Do NOT write any Python code.

Focus only on architecture, quantitative reasoning, and trading research.

Below is a hedge-fund-style **multi-timeframe (MTF) architecture** for XAUUSD that treats higher timeframes as the source of regime, medium timeframes as the source of setup, and lower timeframes as the source of execution. The design follows market microstructure principles that price formation, liquidity, and execution quality differ by horizon, while ICT/SMC concepts are used as operational abstractions for liquidity, displacement, order blocks, and imbalance mapping.[^1][^2]

## Architecture

The optimal framework is a **hierarchical but partially bidirectional** MTF system, not a flat stack where every timeframe independently recalculates everything. The cleanest professional design is: Monthly/Weekly for macro regime, Daily for directional bias and dealing range, H4/H1 for swing context and setup location, M15/M5 for trigger refinement, and M1 only as an execution microstructure feed if the platform can model spread, slippage, and queue-sensitive entry quality. This matches institutional-style top-down alignment, where higher timeframes define inventory, liquidity targets, and operating regime, while lower timeframes only refine entry and invalidation.[^1][^3][^4]

## Reasoning

Market microstructure research shows that liquidity and price discovery are horizon-dependent, so a single timeframe cannot optimally represent both macro positioning and intraday execution costs. XAUUSD is especially sensitive to session liquidity, volatility bursts, and spread/slippage expansion, which makes lower-timeframe signals useful only when nested inside a higher-timeframe narrative. ICT/SMC frameworks also consistently use Daily/4H for bias, 1H/15M for setup, and 5M/1M for trigger, which is a practical decomposition of regime, location, and execution.[^1][^5][^6][^2][^7]

## Part 1: Best hierarchy

Use all of these layers, but not all as equal decision-makers:

- Monthly: optional macro regime filter.
- Weekly: mandatory macro structure and liquidity regime.
- Daily: mandatory directional bias and dealing range.
- H4: mandatory swing structure and intraday narrative.
- H1: mandatory setup refinement.
- M15: mandatory trigger refinement.
- M5: mandatory execution trigger.
- M1: optional execution microstructure layer, not a signal layer.

This hierarchy is preferred because the higher the timeframe, the more stable the structural information and the less noise it contains; the lower the timeframe, the more useful it becomes for precise timing but the more vulnerable it becomes to noise and false structure breaks. For XAUUSD, the practical trade-off is that M1 can improve entry precision but often increases overfitting and spread sensitivity, so it should not be mandatory unless the strategy is very execution-centric.[^6][^2][^7]

## Part 2: Timeframe responsibility

| Timeframe | Responsibility | What it should decide |
| :-- | :-- | :-- |
| Monthly | Macro regime filter | Rare structural shifts, long-cycle liquidity landscape, no trade triggers [^2] |
| Weekly | Primary macro bias | Bullish/bearish regime, major swing highs/lows, long-term liquidity pools [^4] |
| Daily | Dealing range and directional bias | Premium/discount context, highest-probability side, major BOS/CHOCH significance [^1] |
| H4 | Active swing narrative | Current swing leg, intraday liquidity roadmap, setup location [^1] |
| H1 | Setup selection | Best POI, FVG/OB refinement, swing-to-entry transition [^3] |
| M15 | Trigger qualification | Session timing, sweep-and-displace confirmation, SMT/confirmation structure [^1] |
| M5 | Execution trigger | Actual entry timing, local BOS/CHOCH, tight invalidation [^4] |
| M1 | Microstructure execution | Spread, wick quality, micro pullback, slippage control only [^6] |

Monthly should not decide trade entries because its structure changes too slowly and is too coarse for XAUUSD execution. Weekly should own the macro liquidity map because institutions typically express inventory over longer horizons, and daily should own directional bias because it balances stability and responsiveness. H4/H1/M15/M5 should progressively reduce uncertainty until the platform reaches an executable state.[^1][^4][^2]

## Part 3: Information flow

Information should flow **primarily downward**, but invalidation must be allowed **upward only through structural break qualification**, not by every lower-timeframe fluctuation. In other words, a lower timeframe can suggest that a higher-timeframe setup is failing, but it should not instantly erase higher-timeframe bias unless the lower-timeframe break is confirmed and structurally meaningful on the next higher aggregation. This avoids the common retail mistake of letting M1 or M5 “argue” against Weekly or Daily context after only a minor sweep.[^1][^7]

A practical rule is:

- Weekly defines macro regime.
- Daily defines active bias.
- H4 defines operational swing.
- H1/M15 define setup.
- M5 defines execution.
- M1 only refines fills.

Upward invalidation should occur only when lower timeframe weakness becomes a confirmed CHOCH/BOS sequence that propagates into the next higher timeframe’s structure, not because of a single wick or momentum burst. That is a hypothesis in implementation terms, but it is consistent with the microstructure idea that transient price impact is not the same as durable price discovery.[^4][^2][^7][^1]

## Part 4: What each timeframe detects

| Feature | Monthly | Weekly | Daily | H4 | H1 | M15 | M5 | M1 |
| :-- | --: | --: | --: | --: | --: | --: | --: | --: |
| Swing | Yes | Yes | Yes | Yes | Yes | Limited | Limited | No |
| BOS | No | Rare | Yes | Yes | Yes | Yes | Yes | Limited |
| CHOCH | No | Rare | Yes | Yes | Yes | Yes | Yes | Limited |
| Liquidity | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Equal High | No | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Equal Low | No | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Displacement | No | Rare | Yes | Yes | Yes | Yes | Yes | Yes |
| Market Structure Shift | No | Rare | Yes | Yes | Yes | Yes | Yes | Limited |
| Order Block | No | Rare | Yes | Yes | Yes | Yes | Yes | Limited |
| Fair Value Gap | No | Rare | Yes | Yes | Yes | Yes | Yes | Limited |
| Premium Discount | Yes | Yes | Yes | Yes | Yes | Yes | No | No |
| Balanced Price Range | No | Rare | Yes | Yes | Yes | Yes | Limited | No |
| Liquidity Void | No | Rare | Yes | Yes | Yes | Yes | Limited | No |
| Volume Imbalance | No | Rare | Yes | Yes | Yes | Yes | Limited | No |

Higher timeframes should own the strongest structural concepts because the signal-to-noise ratio is better and the zones are more durable. Lower timeframes can still detect the same concepts, but the system should treat them as execution-grade only, not regime-grade, because low-horizon BOS/CHOCH and OB/FVGs are often too granular and frequently mitigated or invalidated by spread and auction noise.[^1][^6][^2][^7]

## Part 5: Engine ownership

Not every timeframe should own a fully independent MarketStructureEngine and PriceActionEngine. The better architecture is a **tiered ownership model** where each timeframe has a lightweight local detector, but the platform stores higher-timeframe outputs as reusable priors for lower-timeframe engines. This reduces duplicated computation, prevents contradictory interpretations, and makes lower-timeframe processing conditional on higher-timeframe context.[^1]

Recommended design:

- Weekly engine produces macro structure objects.
- Daily engine consumes Weekly objects and adds bias/dealing-range state.
- H4 engine consumes Daily/Weekly context and produces active swing context.
- H1/M15/M5 engines consume all higher-timeframe priors and only search for confirmatory patterns inside allowed zones.
- M1 is not a full pattern engine; it is a micro-execution service.

This is consistent with institutional execution logic: location first, then setup, then trigger, then fill quality. The hypothesis is that reusing higher-timeframe priors improves precision and lowers false positives because the search space is constrained.[^3][^1]

## Part 6: Conflict resolution

In your example:

- Daily bullish.
- H4 bullish.
- H1 bearish.
- M15 bullish.
- M5 bullish.

The platform should not trade immediately just because the majority of lower frames are bullish. Instead, it should classify the H1 bearish leg as either:

- a countertrend retracement inside a bullish higher-timeframe structure, or
- a true higher-priority failure if H1 bearishness expands into a confirmed breakdown of the H4/Daily bullish swing.[^1][^4]

The default action is **wait**, not trade, until one of two things happens:

1. The bearish H1 leg is absorbed and a bullish displacement reasserts alignment.
2. The H1 bearish move propagates into a higher timeframe invalidation.

This approach avoids overreacting to tactical pullbacks and is aligned with institutional-style trend following, where retracements are allowed inside the dominant bias until structure is broken. If the setup is long, only long entries should be allowed unless the higher-timeframe regime itself is being reassessed.[^4][^7]

## Part 7: Confluence scoring

Yes, higher timeframes should receive more weight, but the weights should not be fixed only by intuition. A robust approach is to weight by a combination of **structural durability, information value, and execution relevance**, with higher timeframes dominating bias and lower timeframes dominating timing. A practical starting scheme is:[^2]

- Weekly: 25%
- Daily: 25%
- H4: 20%
- H1: 12%
- M15: 10%
- M5: 8%

M1 should usually be excluded from confluence scoring and used only for fill quality or slippage control. This is a hypothesis, but it is consistent with market microstructure: lower horizons have higher noise, while higher horizons carry more stable information about price discovery and liquidity. For XAUUSD intraday systems, you can also use asymmetric scoring where Weekly/Daily determine “permission to trade,” and H4/M15/M5 determine “entry quality.”[^7][^2]

## Part 8: Historical storage

Store more history on higher timeframes in bar count, but less in memory cost per decision because they update slowly. A good operational target is:

- Monthly: 60–120 candles.
- Weekly: 300–500 candles.
- Daily: 800–1,500 candles.
- H4: 2,000–4,000 candles.
- H1: 5,000–10,000 candles.
- M15: 10,000–20,000 candles.
- M5: 20,000–50,000 candles.
- M1: only if needed for execution, 50,000–200,000 candles depending on storage budget.

The reason is that XAUUSD sessions and regime shifts require enough lookback to map liquidity pools, dealing ranges, and swing context across multiple horizons, but the lower the timeframe, the more storage explodes and the more you risk slowing the pipeline. In practice, the system should store compressed derived features at higher levels and only keep raw M1 data if the execution module genuinely needs it.[^6][^7]

## Part 9: Software architecture

A hedge-fund-grade architecture should separate **data, context, interpretation, and execution**. The clean model is:

- MarketDataHub.
- TimeframeAggregator.
- TimeframeStateStore.
- MultiTimeframeContextEngine.
- HierarchicalStructureEngine.
- HierarchicalPriceActionEngine.
- ConflictResolver.
- ConfluenceScorer.
- TradePermissionEngine.
- ExecutionQualityEngine.
- SignalGenerator.
- RiskManager.
- ExecutionRouter.

Core class idea:

```text
MarketDataHub
  -> builds candles/ticks
TimeframeAggregator
  -> Monthly / Weekly / Daily / H4 / H1 / M15 / M5 / M1 bars
TimeframeState
  -> bias, structure, liquidity map, dealing range, active POIs
StructureNode
  -> swing, BOS, CHOCH, MSS, invalidation
PriceActionNode
  -> OB, FVG, BPR, liquidity void, imbalance
ContextGraph
  -> links parent-child timeframe states
ConfluenceReport
  -> weighted score, permissions, conflicts, regime status
TradeDecision
  -> trade / wait / reject / reduce size
```

Data flow:

```text
MarketData
  -> Aggregation
  -> Higher TF feature extraction
  -> Lower TF feature extraction conditioned on higher TF priors
  -> Context graph
  -> Conflict resolver
  -> Confluence scorer
  -> Trade permission
  -> Risk manager
  -> Execution
```

A useful implementation rule is that each timeframe returns a **state object**, not a raw signal. Signals should only be emitted after the ContextGraph says the lower-timeframe event is consistent with higher-timeframe permission. This makes the system more institutional and less reactive.[^1]

## Part 10: Common mistakes

Retail MTF bots usually fail in five ways:

- They treat every timeframe as equally important.
- They let M1 or M5 override Weekly/Daily context after a tiny wick.
- They use too many timeframe confirmations, which destroys expectancy by making entries late.
- They confuse local continuation with true structure shifts.
- They ignore session timing, spreads, and slippage on XAUUSD.[^5][^6]

The fix is to make higher timeframes determine regime, and lower timeframes determine execution only. Another fix is to model XAUUSD around liquidity sessions and volatility bursts, because gold often behaves very differently in quiet versus active windows. Finally, the bot should never require perfect agreement across all horizons, because that produces almost no trades and often enters at poor prices.[^1][^5]

## Part 11: Hedge-fund-grade design

If building this from scratch today, I would use a three-layer hierarchy:

### Layer 1: Regime

Monthly, Weekly, Daily.
This layer defines macro bias, long-term liquidity pools, and whether the market is in expansion, distribution, accumulation, or transition. It should almost never emit direct entries. It should output a regime state such as bullish-distribution, bearish-accumulation, trend-expansion, or range-reversion.

### Layer 2: Setup

H4, H1, M15.
This layer defines the active swing, premium/discount, liquidity raid targets, and the best area of interest. It should identify whether price is trading into premium or discount, whether a displacement leg created a valid imbalance, and whether the POI is still fresh.

### Layer 3: Execution

M5, optional M1.
This layer is responsible for actual entry timing, wick quality, spread awareness, and micro invalidation. It should only trade when the setup layer has permission and when execution confirms sweep + displacement + local structure shift.[^1]

The most robust institutional design is to treat lower timeframes as **conditional refiners**, not independent analysts. That means M5 does not say “bullish” in a vacuum; it says “bullish continuation entry is valid inside approved higher-timeframe bullish context.” This is the cleanest way to reduce false positives while preserving precision.[^3][^1]

## Tradeoffs

The main tradeoff is between **precision and robustness**. Adding M1 may improve entry price but worsens noise sensitivity, slippage exposure, and overfitting risk. Removing Monthly may simplify the system, but you lose macro regime awareness that can matter during major gold re-pricing phases. The best compromise is to keep Monthly as a coarse regime filter and keep M1 optional, not mandatory.[^6][^2][^7]

## Evidence

The strongest evidence from the retrieved material is that professional MTF workflows consistently use Daily/4H for bias, 1H/15M for setup, and 5M/1M for confirmation, with higher-timeframe premium/discount and liquidity guiding lower-timeframe execution. Market microstructure literature also supports the idea that liquidity, price discovery, and execution quality vary by trading horizon, which justifies hierarchical rather than symmetric timeframe logic. ICT-style guidance further emphasizes that order blocks, FVGs, and displacement should be interpreted in a top-down structure and session context, not as isolated low-timeframe patterns.[^1][^3][^4][^2][^7]

## Recommended Design

Use this final architecture:

- Monthly: optional macro filter.
- Weekly: macro regime and major liquidity.
- Daily: directional bias and dealing range.
- H4: active swing context.
- H1: setup refinement.
- M15: trigger confirmation.
- M5: execution.
- M1: optional fill-quality module only.

Use downward inheritance of context, with upward invalidation only when lower-timeframe structure is confirmed and meaningful enough to propagate into the next higher layer. Give higher timeframes the majority of confluence weight, but do not demand perfect alignment across every timeframe. Build the system around state inheritance, conflict resolution, and permission gates rather than a flat signal stack.[^1][^2][^7]

## Potential Weaknesses

This design still relies on several hypotheses rather than hard proof, especially where ICT/SMC terminology is used operationally rather than academically. Some concepts such as order blocks, fair value gaps, balanced price ranges, and liquidity voids are useful abstractions, but their exact statistical edge is context-dependent and can vary by broker, session, and volatility regime. Another weakness is that XAUUSD has regime shifts around news, real yields, and dollar shocks, so static weighting can become brittle unless the system adapts to volatility and session state.[^5][^6][^7]

## Future Extensions

The best extensions are:

- Regime classification using volatility clustering and session state.
- Adaptive timeframe weighting based on realized variance and execution cost.
- Cross-asset confirmation with DXY, real yields, and correlated metals.
- Session-aware models for London open, New York overlap, and news windows.
- Confidence calibration from historical hit rate by timeframe alignment.
- Liquidity state modeling for spread, slippage, and order-book proxies where available.

Would you like the same architecture converted into a formal UML-style spec with class names, methods, and object fields?
<span style="display:none">[^10][^11][^12][^13][^14][^15][^16][^17][^18][^19][^20][^8][^9]</span>

<div align="center">⁂</div>

[^1]: https://www.scribd.com/document/903060065/Market-Maker-Series-Vol-2-of-5

[^2]: https://ideas.repec.org/a/eee/riibaf/v86y2026ics027553192600111x.html

[^3]: https://www.youtube.com/watch?v=py5ERvkPoo8

[^4]: https://www.scribd.com/document/967497678/ICT-MTF-Printable-Checklist-and-Deep-Explanation

[^5]: https://www.scribd.com/document/950911487/Advanced-Gold-Research-1

[^6]: https://papers.ssrn.com/sol3/Delivery.cfm/6650958.pdf?abstractid=6650958\&mirid=1

[^7]: https://ro.uow.edu.au/articles/thesis/Market_microstructure_studies_liquidity_price_discovery_and_manipulation/27661452

[^8]: https://www.tradingview.com/script/MYrC5cy4-Time-and-Price-by-erdensedat/

[^9]: https://www.youtube.com/watch?v=n5aDpltuMCA

[^10]: https://id.scribd.com/document/955686514/bab-1-ict

[^11]: https://www.scribd.com/document/951138298/Smart-Money-Flow-Framework-SMC-Trading-Technique

[^12]: https://www.youtube.com/watch?v=QrYW_qzWmrg\&vl=en

[^13]: https://www.scribd.com/document/696186232/ICT-Workbook

[^14]: https://pure.royalholloway.ac.uk/ws/files/19365358/2014limskphd.pdf.pdf

[^15]: https://ideas.repec.org/a/cwk/eafjke/2026-19.html

[^16]: http://ijeais.org/wp-content/uploads/2025/5/IJAAR250524.pdf

[^17]: https://www.bis.org/publ/cgfs11mura_b.pdf

[^18]: https://d-nb.info/126425413X/34

[^19]: https://rpc.cfainstitute.org/sites/default/files/-/media/documents/article/position-paper/market-microstructure-impact-of-fragmentation-under-the-markets-in-financial-instruments-directive.pdf

[^20]: https://www.acsu.buffalo.edu/~keechung/MGF743/Readings/Market microstructure A surveyq.pdf

