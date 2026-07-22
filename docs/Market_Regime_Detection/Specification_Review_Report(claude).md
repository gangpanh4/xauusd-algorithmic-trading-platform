# Specification Review Report
**Document reviewed:** Market_Regime_Detection_Spec_v1_0.md
**Review type:** Architecture/consistency review (no redesign, no edits to source)
**Scope:** Duplicate requirements, contradictions, undefined terminology, inconsistent thresholds, missing dependencies, ambiguous wording, unfinished ideas

---

## 1. Document Structure Issue (affects everything below)

**1.1 — Table of contents does not match the body.**
The front-matter outline (lines 4–84) lists Section 3 = "Input Data," Section 4 = "Feature Engineering," Section 5 = "Threshold Selection." The actual body instead has Section 3 = "Indicators" (whose content is Input Data), Section 4 = "Thresholds" (whose content is actually Feature Engineering / indicator selection), and Section 5 = "Adaptive Calibration" (whose content is actually Threshold Selection). Every cross-reference elsewhere in the document that points to "Section 5" thresholds or "Section 3" input handling is technically pointing at a section whose *title* says something else, which will confuse anyone navigating by heading name rather than by content.

**1.2 — Inconsistent presence of "ChatGPT Review Notes" appendices.**
Sections 2, 3, 4, 5, 6, and 7 each end with an "Adopt / Simplify for v2.3 / Defer to Future Versions" block. Sections 8, 9, 10, and 11 have no such block. It's unclear whether this is intentional (later sections finalized, earlier ones still under negotiation) or simply incomplete — there's no statement anywhere clarifying the status or authority of these review-note blocks relative to the main spec text.

**1.3 — Leftover tool/rendering artifacts embedded in spec text.**
Several places in the document contain raw, non-prose fragments that appear to be artifacts of a document-generation or diagramming tool, left in the text rather than rendered or removed, e.g.:
- Lines 247–253, 265–271, 325–331, 347–353, 375–381 (`::view-transition-group(*)...`, `VvisualizeVvisualize show_widget`)
These break the reading flow and, in at least one case (line 346–353), interrupt a sentence describing the efficiency/choppiness indicator family. They should be flagged for cleanup regardless of content correctness.

**1.4 — A malformed timestamp in the example log JSON.**
Line 1017: `"computation_timestamp": "2026-01-20T21:00:003Z"` — this is not a valid ISO-8601 timestamp (extra digit "003" before the timezone marker). Anyone copying this as a canonical example will copy a syntax error.

---

## 2. Contradictory Requirements

**2.1 — "Adopt" vs. "Defer/Simplify" notes directly contradict the main spec they're attached to.**
This is the most consequential conflict in the document. The main body of nearly every section specifies a sophisticated design, while the trailing "ChatGPT Review Notes" in the same section repeatedly defer or simplify away the exact things just specified:

| Section | Main spec requires | Review Notes say |
|---|---|---|
| 2 (Regime Definitions) | Hurst exponent as a formal regime criterion (Q2); full posterior probability vectors (Q4); six+ named regimes | "Defer": Hurst Exponent, Posterior probability vectors, HMMs. "Simplify": 4 regimes only (TREND/RANGE/VOLATILE/UNKNOWN), confidence score instead of probability distributions |
| 3 (Indicators/Input Data) | Multi-symbol architecture as "architecturally non-negotiable" (Q5); cross-asset and macro layers (Layers 3–4) | "Simplify": single symbol (XAUUSD) only, ignore cross-asset and macro entirely. "Defer": cross-asset correlation, multi-symbol optimization |
| 4 (Thresholds/Feature Engineering) | Full indicator family incl. Hurst, TSMOM, LR R², VIX/IV-RV spread, cross-asset correlation, breadth, adaptive feature config | "Defer": every one of those items, by name |
| 5 (Adaptive Calibration) | Dual-layer fixed+adaptive thresholds, percentile anchoring, GARCH-informed baseline (this is the entire content of the section) | Section 2's "Simplify" block already says "use fixed thresholds" — directly conflicting with Section 5's central thesis that fixed-only thresholds are insufficient |
| 6 (Transition Logic) | Five-condition conjunctive gate including macro compatibility (Condition 4); asymmetric crisis hysteresis; weighted conflict resolution; 5-state `conflict_state` enum | "Simplify": four gates only, omitting macro; fixed (non-adaptive) confirmation counts; 3-state conflict enum (AGREE/WEAK_AGREEMENT/CONFLICT). "Defer": macro checks, asymmetric hysteresis, weighted conflict resolution, probability smoothing |
| 7 (Confidence) | 7-factor weighted composite, full probability vector, isotonic calibration | (Review notes here are largely compatible but still imply "confidence score" as a simplified substitute elsewhere — see 2.1 row for Section 2) |

This pattern suggests the document is actually **two specs interleaved**: an ambitious "v1.0 production" spec, and a separate, much smaller "v2.3 simplification" plan layered on top via review comments. As written, a reader cannot tell which one is authoritative. This should be resolved explicitly (e.g., by separating the documents or labeling one as non-normative).

**2.2 — Per-instrument architecture vs. shared cross-symbol computation graph.**
Section 3, Q5 (lines 283–288) states multi-symbol support is "architecturally non-negotiable" and that "the module's core compute unit is a symbol registry with a shared feature computation graph, **not N independent single-symbol instances**," with cross-asset features "computed once at the graph level and referenced by all symbol-level computations."

Section 10.1 and 10.5 directly contradict this: `MarketRegimeDetector` is explicitly "one instance per instrument" (line 1076), multi-instrument orchestration is declared "the caller's responsibility" living "outside this module" (line 1295), and Section 10.5 states plainly: "It does not share state between instrument detectors — cross-instrument correlation logic, if required, is a separate higher-order service" (line 1540).

These cannot both be true of the same module. Either the shared feature graph (Section 3) or the fully independent per-instrument detector (Section 10) describes the actual architecture — not both.

**2.3 — Code example violates the spec's own code-quality requirement.**
Section 11.5, Q2 states: "No function or method in the module may use a mutable default argument" (line 1859). Yet the public interface examples in Section 10.1 (line 1088) and Section 10.4 (line 1460) both declare `clock: Clock = SystemClock()` — a mutable default argument instantiated at function-definition time, the canonical Python anti-pattern Q2 is warning against.

**2.4 — Mandatory vs. conditional field overlap is logically inconsistent.**
Section 8.2 lists `regime_entropy` and `uncertainty_type` as unconditionally mandatory fields, computed from `regime_probability_distribution`. But Section 7.5 says aleatoric/epistemic uncertainty flags depend on "active flags" and calibration availability, and Section 8.2 separately says `confidence_interval_low/high` "may be null only during the initialization period before minimum calibration history has accumulated." If entropy and uncertainty_type are unconditionally mandatory but their *inputs* (the full probability distribution, calibration-dependent flags) are not guaranteed during initialization, it's unclear what value these fields should hold pre-initialization — the spec doesn't define entropy/uncertainty_type behavior during the `UNKNOWN`/initialization state explicitly, only confidence (which is pinned to exactly 0.0, per the acceptance criteria in 11.4).

---

## 3. Inconsistent or Underspecified Thresholds

**3.1 — Volatility percentile cut-points differ across sections without reconciliation.**
- Section 2, Q2 (formal regime definitions): Bull trend requires vol **below 70th percentile**; Bear trend requires vol "often above 60th percentile" (line 150); High-vol expansion requires **above 85th percentile**; Low-vol compression requires **below 20th percentile**.
- Section 5.3/5.4 (threshold determination): Low = `<P33`, Normal = `P33–P67`, Elevated = `>P67`, Crisis = `>P90`.
These are two different percentile schemes for what is supposedly the same volatility-regime concept, and the document never maps one onto the other. Notably, Section 2's 60th–70th percentile band is **ambiguous territory shared by both bull and bear trend definitions** — a market at the 65th percentile of realized vol satisfies neither regime's volatility condition exclusively, nor is it clearly in Section 5's "Normal" (P33–67) or "Elevated" (>P67) band consistently with Section 2's cutoffs.

**3.2 — ADX thresholds mix raw values and percentile ranks inconsistently.**
- Section 2, Q2 (Mean-reverting definition): "ADX (average directional index) is low (typically < 20–25)" — a **raw, absolute** ADX value.
- Section 4 (indicator table, line 338) and Section 5.2 (line 448): "trending regimes historically begin to exhibit meaningful persistence above ADX ≈ 20–25," with hysteresis band "20 (entry) / 17 (exit)" — also raw values, consistent with Section 2 here.
- However, Section 5.6 default table (line 502) and Section 10.3 config schema (lines 1351–1355) define `trend_entry_threshold` / `trend_exit_threshold` as **P60 / P45 of normalized ADX** — i.e., percentile ranks, not raw ADX values.
- Section 5.4's percentile table (line 462) gives yet a third ADX percentile scheme: Low `<P30`, Normal `P30–P60`, High `>P60`.
The spec never states the mapping between "ADX ≈ 20–25 raw" and "ADX at the P60 percentile rank" — these are only guaranteed to coincide for one specific historical calibration window, but the spec presents them as if they were the same threshold in three different sections, with three different percentile cut values (P60/P45 vs. P30/P60) attached to the same indicator.

**3.3 — Confirmation/dwell period counts are stated multiple times with different default framings.**
Section 5.6 (line 502) gives `trend_min_dwell_periods = 3 days`, described as a single generic dwell requirement. Section 6.3's table (line 577) instead specifies confirmation counts that vary by *specific transition pair* (e.g., Ranging→Weakly Trending = 3, Weakly→Strongly Trending = 2, Trending→Ranging = 4). Section 10.3's config schema (lines 1356–1358) reflects the Section 6.3 per-transition values, not the single Section 5.6 value. The spec never clarifies whether `trend_min_dwell_periods` (5.5/5.6) is a distinct, more primitive gate that sits *underneath* the per-transition confirmation counts of 6.3, or whether one of these two specifications is meant to supersede the other.

**3.4 — Confidence-tier naming mismatch.**
Section 7.6 (line 735) and Section 8.1 (line 822) both define the tier enum as `VERY_LOW, LOW, MODERATE, HIGH, VERY_HIGH`. The Section 7 "ChatGPT Review Notes" (line 745) instead list tiers as `VERY_LOW, LOW, MEDIUM, HIGH, VERY_HIGH` — `MODERATE` vs. `MEDIUM` is a literal naming inconsistency for what's presented as the same enum.

**3.5 — Conflict-state vocabulary mismatch.**
Section 6.6 (line 618) defines `conflict_state` as a 5-value enum: `NONE, MINORITY_DISSENT, EVEN_SPLIT, MAGNITUDE_CONFLICT, SCALE_CONFLICT`. Section 6's Review Notes (lines 643–646) instead propose a 3-value scheme: `AGREE, WEAK_AGREEMENT, CONFLICT`. As with 2.1, it's unclear which enum is the actual contract.

---

## 4. Undefined or Inconsistently Used Terminology

- **"Regime" vs. "regime dimension" vs. "regime epoch"** are used somewhat interchangeably in early sections (1–2) before being formally distinguished in Sections 6 and 8. A first-time reader of Section 1 has no way to know that "regime" will later split into `primary_regime`, `volatility_regime`, `trend_regime`, and `regime_epoch_id` as four distinct, separately-tracked concepts.
- **"Confidence" vs. "regime_confidence"** — Section 7.1 carefully distinguishes "instantaneous confidence" from "regime confidence," but the field actually named `confidence` in Section 8.1 corresponds to "instantaneous confidence," while a *separate* field `regime_confidence` corresponds to the persistence-adjusted quantity. The naming is non-obvious (one could easily assume `regime_confidence` is the general/parent concept and `confidence` the more specific one — it's the reverse).
- **"Trending" used as both a directional state and a strength state.** Section 2 Q3 explicitly separates "direction" (bull/neutral/bear) from "intensity"/strength, yet `primary_regime` enum values like `STRONGLY_TRENDING_UP` (Section 8.1) fuse direction and strength back into one token, while `trend_regime` (a *separate* field) re-expresses strength alone (`STRONG_TREND`/`WEAK_TREND`/`RANGING`). The relationship between these two overlapping-but-not-identical representations of "trend strength" is never made explicit.
- **"Calibration window" is never given one consistent default.** Section 5.1 says rolling calibration window example is "252 or 504 trading days." Section 5.4 recommends a minimum of "504 trading days... 756 days... preferable." Section 5.6 defaults set `trend_calibration_window_days = 504`. These are compatible but the spec presents them as three separate recommendations rather than one settled number, leaving "the calibration window" referenced elsewhere (e.g., Section 9, Section 11) without a single canonical value.
- **"Sentinel instrument"** (Section 3, Q5, line 287) is introduced and used once, with no formal definition of how a sentinel is designated, registered, or weighted — it's described only by example (VIX, HY spread, 2s10s).
- **"Asset-class-aware" / "asset class" threshold tables** (Section 4 Q8, Section 5.6) are referenced repeatedly as a requirement, but no section defines the actual enumerated list of supported asset classes, nor who owns/maintains the per-asset-class threshold config store.
- **`prior_candidate_abort_count`** is referenced in Section 9.5 (debugging Layer 4, line 1060) as a field to "check," but it is never defined as part of `TransitionRecord` in Section 8.3 (which only specifies `from_regime, to_regime, transition_timestamp, trigger_code, confidence_at_transition`). This is an undefined field referenced as if it already exists.
- **"Episode type"** (Section 11.3, line 1780) is used in the false-positive-rate validation test ("Compute separately for each episode type") without ever being formally enumerated — the reader can infer episode types loosely from context (trending/ranging/crisis) but no canonical list is given.

---

## 5. Missing Dependencies Between Sections

- **Section 10 (Architecture) does not implement Section 3's multi-symbol/shared-graph requirement.** As detailed in 2.2 above, this is not just a contradiction but a missing dependency: Section 10's interface design never references a `SymbolRegistry`, shared feature graph, or any mechanism for the cross-asset correlation features mandated in Section 3 (Layer 3) and Section 4 to be computed once and shared. `RegimeDetectorRegistry` (10.5) is a thin per-instrument container, not the shared-computation architecture Section 3 calls for.
- **Section 8's `diagnostics.transition_history` (TransitionRecord) does not carry the fields Section 9.5's debugging framework assumes exist** (`prior_candidate_abort_count`, and implicitly the status_flags active "at the time of [each] transition," referenced in Layer 4's second check but not listed as a TransitionRecord field in 8.3).
- **Section 5 (thresholds) depends on a GARCH provider and a macro context provider that are not specified architecturally until Section 10.4.** Sections 5.3 and 6.1 (Condition 2/4) assume these providers exist and behave a certain way (e.g., "GARCH conditional volatility directionally agreeing"), but the provider interfaces, failure semantics, and data contracts aren't defined until much later, and even then only at a high level (`GarchProvider`, `MacroContextProvider` types named but not specified).
- **Section 11's acceptance criteria reference quantities that earlier sections don't define a computation method for**, e.g., "Per-regime accuracy for the crisis regime class" (11.4) presumes a fixed mapping from continuous probability output to a discrete "primary regime label per bar" for measurement purposes — this mapping (argmax? tier-gated argmax? hysteresis-aware?) is implied by Section 6/8 but never explicitly pinned down as the canonical "ground-truth-comparable" label definition used in validation.
- **Section 9 (Logging) introduces `LOG_SINK_DEGRADED` (10.4, line 1451) and other flags that are not listed in Section 8.1's `status_flags` controlled vocabulary** (line 867 enumerates: OSCILLATION_WARNING, CALIBRATION_STALE, STRUCTURAL_BREAK_DETECTED, DATA_QUALITY_WARNING, DURATION_LOCK, REDUCED_CONFIDENCE, AMBIGUOUS_REGIME, TRANSITION_IN_PROGRESS, INITIALIZATION_PERIOD — no `LOG_SINK_DEGRADED`, `CALIBRATION_UPDATED`, or `MODULE_RESET`, all of which are mentioned as loggable/settable elsewhere in Sections 9–10).
- **Section 11.5 (R4) introduces `CALIBRATION_STALE` reducing confidence "by the recency decay factor"** and references a 30-day default staleness window — this should tie back to Section 7.2 Factor 7's calibration recency decay (default floor 0.85), but the two are never explicitly cross-referenced, leaving it ambiguous whether R4's halt-and-require-operator-intervention behavior and Factor 7's smooth linear decay are sequential stages of one mechanism or two separate, overlapping mechanisms.

---

## 6. Ambiguous Wording

- **Section 1, Q3** (line 117): "require strong evidence over a confirmation window (e.g., several bars of persistent signal)" — "several" is never quantified here, even though concrete confirmation counts are given later (Section 6.3). The objectives section sets an expectation in vague terms that the later, precise sections don't explicitly fulfill by reference.
- **Section 2, Q2 "Bear trend"** (line 150): "Correlation of returns across assets **may be** rising. Put/call ratio and credit spreads **may be included**" — both clauses are non-committal ("may"), leaving it unclear whether these are required corroborating conditions, optional enhancements, or merely illustrative possibilities. This matters because Section 2's definitions are supposed to be "testable conditions," yet these two clauses are not testable as written.
- **Section 2, Q3** (line 174): "This two-axis structure becomes the reference for the next diagram... Three cells (dashed borders) represent valid but lower-priority states" — refers to a diagram that does not appear anywhere in the surrounding text (likely lost in the conversion from whatever produced this document, consistent with the artifact fragments noted in 1.3). The reader cannot verify which three cells are meant.
- **Section 3, Q4** (line 277): "If fewer than M% of expected observations are present... the feature is marked unreliable" — `M` is never given a default or even an example value, unlike nearly every other threshold in the document which gets at least an illustrative number.
- **Section 5.3** (line 455): "when GARCH conditional volatility and realized volatility disagree significantly (e.g., realized has spiked but conditional has not yet caught up), flag the regime label as uncertain" — "significantly" is not quantified here, even though `vol_garch_disagreement_tolerance` exists as a config parameter elsewhere (5.5, 10.3 value 0.40) — the qualitative description and the quantitative parameter are never explicitly tied together in the same place.
- **Section 6.1, Condition 5** (line 558): "a calendar event lock (e.g., within one session of a major scheduled release where artificial signal spikes are expected)" — "major scheduled release" is not defined (earnings? Fed decisions? both?), and there's no configuration parameter anywhere in Section 10.3 corresponding to this calendar-lock mechanism, despite it being listed as one of five mandatory gating conditions.
- **Section 7.4** (line 711): "During the confirmation window (before a transition is committed), persistence is not applied to the candidate new regime — it continues to apply to the outgoing regime until the transition is committed." This is workable but ambiguous about what happens to the *outgoing* regime's persistence clock during the confirmation window — does it keep accruing toward its own τ, or freeze, while a competing candidate is being evaluated? The text only says it "continues to apply," not whether it continues to *accrue*.
- **Section 8.1** (line 801): "TRANSITIONING for periods where a regime change is confirmed but the destination regime has not yet met its own confidence floor" — this appears to conflict with the rest of the document's transition model, where a transition is by definition not "confirmed" until the confirmation-count and confidence-floor conditions (Section 6.1, Conditions 1–3) are *all* simultaneously satisfied. A transition that is "confirmed" yet hasn't "met its own confidence floor" looks like a state that the rest of the spec's gating logic shouldn't allow to exist; this sentence is either describing an edge case not explained elsewhere or is internally contradictory phrasing.
- **Section 10.4** (line 1445): "If a bar is unavailable, the caller decides whether to skip the period, impute, or raise — the module does not make this decision." This sits in tension with Section 3 Q4's extensive, module-owned policy for missing/stale data (last-value carry-forward, staleness flags, spike filters) — it's unclear whether that whole missing-data policy in Section 3 is something the module performs internally on bars it *does* receive (consistent with 10.4) or something that contradicts 10.4's claim that availability decisions are entirely the caller's responsibility.

---

## 7. Unfinished Ideas / TODO-equivalents

No literal "TODO" or "TBD" markers appear in the document, but several passages function as unfinished ideas:

- **Calendar-event lock (6.1, Condition 5)** — described as a mandatory gating condition, but with no associated configuration parameter, no definition of "major scheduled release," and no mention anywhere else in the document (not in Section 9 logging events, not in Section 10 config schema, not in Section 11 tests). This reads as a placeholder for a feature that was never fully specified.
- **The diagram referenced in Section 2 Q3** ("This two-axis structure becomes the reference for the next diagram") and the apparent diagram placeholders in Sections 3 and 4 (the `view-transition`/`show_widget` artifacts noted in 1.3) suggest visual content was planned or generated but never made it into the final markdown.
- **Section 8.2** flags `transition_trigger` and `previous_regime` as "soft mandatory" — a category introduced once, here, and never defined elsewhere as a formal tier alongside "mandatory" and "conditionally mandatory." It's unclear what validation behavior (if any) attaches to "soft mandatory" versus the other two tiers.
- **Section 9.1, Category 3** sets differing default telemetry frequencies ("every observation period in development, every 15 minutes in production real-time, every computed bar in backtesting mode") without ever stating who/what configures this or whether it's a single config key or environment-derived default — left as an implied detail rather than specified.
- **The "M%" missing-data threshold (3, Q4)** noted in Section 6 above is effectively a placeholder value never filled in.
- **Section 11.5, Q4 (Dependency surface)** requires optional dependencies to "raise ImportError only when the optional feature is actually invoked," but does not specify whether this applies to GARCH/macro providers configured at the YAML level (10.3) — i.e., if a user configures GARCH in YAML but the package isn't installed, is that a config validation error (at load time, per 10.3's "must pass validation at module initialization") or a deferred ImportError (per 11.5 Q4)? The two requirements point to different failure points and the document doesn't reconcile them.

---

## Summary

The document contains a well-developed, internally rigorous "production spec" layer, but it is undermined by:
1. A second, contradictory "simplification" layer (the per-section Review Notes) that walks back core requirements (probability vectors, multi-symbol support, Hurst exponent, adaptive thresholds) without ever being reconciled with the main text — this is the single biggest open question for implementers.
2. A genuine architectural contradiction between the shared multi-symbol computation graph required in Section 3 and the strictly isolated per-instrument detector specified in Section 10.
3. At least three threshold systems for volatility/trend classification (Section 2's percentile language, Section 4/5's percentile tables, and Section 5.6's "P60/P45 of normalized ADX" defaults) that are not shown to be equivalent or reconciled.
4. A small but real code-correctness defect (mutable default argument) that violates the spec's own later quality bar.
5. Several terms, fields, and gating conditions (sentinel instruments, calendar-event locks, `prior_candidate_abort_count`, "M%" observation threshold, episode types) that are used as if already defined but never formally specified.

None of these issues were corrected in this review; they are flagged here for resolution by the spec's owner.
