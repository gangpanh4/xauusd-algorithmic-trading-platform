# Patch List — Market Regime Detection Spec v1.0
Derived from the Specification Review Report. The specification itself has not been modified; this is a checklist for the spec owner to apply manually.

Each item: Section | Exact sentence to replace | Replacement sentence | Reason | Breaking/Non-breaking

---

### ☐ Patch 1
**Section:** Front matter (outline, lines 1–84) vs. Section 3 heading
**Exact sentence to replace:**
> Section 3: Input Data

(in the outline) — conflicts with the body heading `# 3. Indicators`
**Replacement sentence:**
> Section 3: Indicators (Input Data)

**Reason:** Outline and body heading disagree, making the document hard to navigate by section name.
**Breaking/Non-breaking:** Non-breaking (cosmetic/navigational only)

---

### ☐ Patch 2
**Section:** Front matter (outline) vs. Section 4 heading
**Exact sentence to replace:**
> Section 4: Feature Engineering

(in the outline) — conflicts with body heading `# 4. Thresholds`, whose content is actually feature/indicator selection
**Replacement sentence:**
> Section 4: Feature Engineering (Indicator Selection and Rationale)

**Reason:** Outline label and body heading/content mismatch; Section 4's actual content is indicator selection, not threshold values (those are in Section 5).
**Breaking/Non-breaking:** Non-breaking

---

### ☐ Patch 3
**Section:** Front matter (outline) vs. Section 5 heading
**Exact sentence to replace:**
> Section 5: Threshold Selection

(in the outline) — conflicts with body heading `# 5. Adaptive Calibration`
**Replacement sentence:**
> Section 5: Threshold Selection and Adaptive Calibration

**Reason:** Aligns outline with body heading; Section 5 is where threshold selection logic actually lives.
**Breaking/Non-breaking:** Non-breaking

---

### ☐ Patch 4
**Section:** 2, "ChatGPT Review Notes → Defer to Future Versions" (line ~233–238)
**Exact sentence to replace:**
> Hurst Exponent
> Cross-asset correlation
> Hidden Markov Models
> Posterior probability vectors
> Macro risk-off detection

**Replacement sentence:**
> [Remove this "Defer to Future Versions" block from Section 2, or explicitly retitle it: "Non-normative v2.3 simplification notes — superseded by Section 2 Q2 and Q4 for v1.0 production scope."]

**Reason:** Directly contradicts Section 2's own formal regime definitions (Q2, which require the Hurst exponent) and design principles (Q4, which mandate posterior probability vectors). As written, a reader cannot tell which requirement set is authoritative.
**Breaking/Non-breaking:** Breaking (changes which requirements an implementer is told to build; resolves a live contradiction, so any implementation built against the "Defer" list must be revisited)

---

### ☐ Patch 5
**Section:** 3, "ChatGPT Review Notes → Simplify for v2.3" (line ~302–307)
**Exact sentence to replace:**
> Single symbol (XAUUSD) only.
> Ignore cross-asset relationships.
> Ignore macroeconomic inputs.

**Replacement sentence:**
> [Remove or explicitly label this block as superseded by Section 3, Q5, which states multi-symbol support is "architecturally non-negotiable for a production system serving a multi-instrument book."]

**Reason:** Directly contradicts Q5 in the same section. Leaving both in the document with no precedence statement means the multi-symbol requirement cannot be safely relied upon by implementers or testers.
**Breaking/Non-breaking:** Breaking

---

### ☐ Patch 6
**Section:** 10.1 (Primary class constructor signature)
**Exact sentence to replace:**
> clock: Clock = SystemClock(),

**Replacement sentence:**
> clock: Clock | None = None,  # resolved to SystemClock() inside __init__ if None

**Reason:** Violates the spec's own Section 11.5 Q2 requirement: "No function or method in the module may use a mutable default argument." `SystemClock()` is instantiated once at function-definition time and shared across all instances unless explicitly overridden — exactly the anti-pattern Q2 warns against.
**Breaking/Non-breaking:** Breaking (changes the public constructor signature/behavior)

---

### ☐ Patch 7
**Section:** 10.4 (Dependency injection pattern constructor signature)
**Exact sentence to replace:**
> clock: Clock = SystemClock(),

**Replacement sentence:**
> clock: Clock | None = None,  # resolved to SystemClock() inside __init__ if None

**Reason:** Same mutable-default-argument violation as Patch 6, recurring in the second code listing of the same constructor.
**Breaking/Non-breaking:** Breaking

---

### ☐ Patch 8
**Section:** 10.1 / 10.5 vs. 3, Q5
**Exact sentence to replace:**
> The interface is deliberately instrument-scoped. One MarketRegimeDetector instance manages one instrument. Multi-instrument orchestration is the caller's responsibility — a RegimeDetectorRegistry or similar container lives outside this module.

**Replacement sentence:**
> The interface is instrument-scoped for trend/volatility computation, but cross-instrument features required by Section 3 (cross-asset correlation matrices, breadth, aggregate regime) are computed once by a shared FeatureGraph object and injected into each MarketRegimeDetector instance, per Section 3, Q5. Multi-instrument *orchestration* (scheduling, registry lookup) remains the caller's responsibility; shared *feature computation* does not.

**Reason:** Resolves the direct contradiction between Section 3 Q5 ("not N independent single-symbol instances," shared feature computation graph) and Section 10's fully independent, non-state-sharing detector design.
**Breaking/Non-breaking:** Breaking (changes constructor dependencies and the architecture diagram in 10.5)

---

### ☐ Patch 9
**Section:** 10.5
**Exact sentence to replace:**
> It does not share state between instrument detectors — cross-instrument correlation logic, if required, is a separate higher-order service that consumes from multiple instrument topics and maintains its own state.

**Replacement sentence:**
> Per-instrument detector state (regime epoch, confirmation counters, persistence) is not shared between instruments. Cross-instrument *input features* (correlation matrices, breadth, aggregate regime), however, are computed once by the shared FeatureGraph described in Section 3, Q5, and referenced by each detector — see Patch 8.

**Reason:** Same contradiction as Patch 8, restated at the integration-topology level; needs the same correction for consistency.
**Breaking/Non-breaking:** Breaking

---

### ☐ Patch 10
**Section:** 2, Q2 (Bull trend / Bear trend definitions)
**Exact sentence to replace:**
> realized volatility is below its 70th percentile

**Replacement sentence:**
> realized volatility is below its 67th percentile (Low/Normal boundary per Section 5.4)

**Reason:** Aligns Section 2's bull-trend volatility cutoff with the canonical percentile bands defined in Section 5.4 (Low <P33, Normal P33–67, High >P67), removing the 60th–70th percentile zone that currently satisfies neither the bull nor the bear trend definition cleanly.
**Breaking/Non-breaking:** Breaking (changes a classification boundary)

---

### ☐ Patch 11
**Section:** 2, Q2 (Bear trend definition)
**Exact sentence to replace:**
> realized volatility is elevated (often above 60th percentile)

**Replacement sentence:**
> realized volatility is elevated (above its 67th percentile, per the Elevated band in Section 5.4)

**Reason:** Same as Patch 10 — removes the ambiguous 60–70th percentile overlap between bull and bear trend definitions by anchoring both to Section 5.4's single canonical percentile scheme.
**Breaking/Non-breaking:** Breaking

---

### ☐ Patch 12
**Section:** 5.6 (Trend defaults table)
**Exact sentence to replace:**
> trend_entry_threshold | P60 of normalized ADX

**Replacement sentence:**
> trend_entry_threshold | P60 of normalized ADX (cross-reference: this percentile rank is calibrated to correspond approximately to raw ADX ≈ 20–25 per Section 2, Q2 and Section 5.2; the two are not guaranteed to coincide outside the reference calibration window and must be re-derived per instrument)

**Reason:** Section 2 (Q2) and Section 5.2 define ADX thresholds in raw units (ADX ≈ 20–25); Section 5.6 and the config schema (10.3) define them as a percentile rank (P60/P45). The spec never states the relationship between these two representations of "the same" threshold.
**Breaking/Non-breaking:** Non-breaking (clarification only, no behavior change)

---

### ☐ Patch 13
**Section:** 7.6 (Confidence tier table) vs. 7 "ChatGPT Review Notes → Adopt"
**Exact sentence to replace:**
> Include confidence tiers (VERY_LOW, LOW, MEDIUM, HIGH, VERY_HIGH).

**Replacement sentence:**
> Include confidence tiers (VERY_LOW, LOW, MODERATE, HIGH, VERY_HIGH).

**Reason:** Section 7.6 and Section 8.1 both define the canonical enum with `MODERATE`; the Review Notes list `MEDIUM` for the same enum. This is a literal naming mismatch for what is supposed to be a single controlled vocabulary.
**Breaking/Non-breaking:** Non-breaking (text-only correction; no enum value actually changes once corrected)

---

### ☐ Patch 14
**Section:** 6, "ChatGPT Review Notes → Simplify for v2.3" (line ~643–646)
**Exact sentence to replace:**
> Represent conflicts as:
> AGREE
> WEAK_AGREEMENT
> CONFLICT

**Replacement sentence:**
> [Remove this alternate conflict_state enum, or explicitly mark it superseded by the 5-value enum defined in Section 6.6: NONE, MINORITY_DISSENT, EVEN_SPLIT, MAGNITUDE_CONFLICT, SCALE_CONFLICT.]

**Reason:** Two incompatible `conflict_state` enums exist for the same field — one in the normative Section 6.6 text, one in the Review Notes — with no statement of which is authoritative.
**Breaking/Non-breaking:** Breaking (output schema enum values differ between the two versions)

---

### ☐ Patch 15
**Section:** 8.3 (TransitionRecord definition)
**Exact sentence to replace:**
> Each TransitionRecord contains: from_regime, to_regime, transition_timestamp, trigger_code, confidence_at_transition.

**Replacement sentence:**
> Each TransitionRecord contains: from_regime, to_regime, transition_timestamp, trigger_code, confidence_at_transition, prior_candidate_abort_count, status_flags_at_transition.

**Reason:** Section 9.5 (debugging Layer 4) instructs engineers to check `prior_candidate_abort_count` and whether status flags were active "on the transition that established the incorrect regime" — both values are assumed to exist on TransitionRecord but are missing from its Section 8.3 definition.
**Breaking/Non-breaking:** Breaking (adds fields to an existing output sub-object schema)

---

### ☐ Patch 16
**Section:** 6.1, Condition 5
**Exact sentence to replace:**
> a calendar event lock (e.g., within one session of a major scheduled release where artificial signal spikes are expected)

**Replacement sentence:**
> a calendar event lock — defined via a configurable calendar_event_lock_windows parameter (Section 10.3) listing instrument-specific event types (e.g., scheduled earnings releases, central bank rate decisions) and the number of sessions before/after each event during which transitions are suppressed

**Reason:** This is listed as one of five mandatory transition-gating conditions but has no corresponding configuration parameter anywhere in Section 10.3, no logging event in Section 9.1, and no test coverage in Section 11 — it is currently an unfinished idea masquerading as a finished requirement.
**Breaking/Non-breaking:** Breaking (introduces a new required config parameter and gating behavior that does not currently exist anywhere else in the spec)

---

### ☐ Patch 17
**Section:** 3, Q4 (missing/incomplete data handling)
**Exact sentence to replace:**
> If fewer than M% of expected observations are present in the lookback window, the feature is marked unreliable.

**Replacement sentence:**
> If fewer than 80% of expected observations are present in the lookback window, the feature is marked unreliable (default; configurable via min_observation_completeness_pct in Section 10.3).

**Reason:** `M%` is an unfilled placeholder — every other threshold in the document is given at least an illustrative default value, and this one is referenced nowhere else (no corresponding config key currently exists).
**Breaking/Non-breaking:** Breaking (introduces a concrete default behavior where none currently exists)

---

### ☐ Patch 18
**Section:** 9 (example JSON log record, line ~1017)
**Exact sentence to replace:**
> "computation_timestamp": "2026-01-20T21:00:003Z"

**Replacement sentence:**
> "computation_timestamp": "2026-01-20T21:00:00.123Z"

**Reason:** The original value is not a valid ISO-8601 timestamp (stray digit before the timezone marker). The example is likely to be copied verbatim by implementers writing schema validators or test fixtures.
**Breaking/Non-breaking:** Non-breaking (example/documentation fix only)

---

### ☐ Patch 19
**Section:** 8.1 (primary_regime enum description)
**Exact sentence to replace:**
> TRANSITIONING for periods where a regime change is confirmed but the destination regime has not yet met its own confidence floor.

**Replacement sentence:**
> TRANSITIONING for periods where a candidate regime change has accumulated sufficient consecutive confirmations (Section 6.3) but the candidate's confidence score has not yet crossed the minimum confidence floor required to commit the transition (Section 6.1, Condition 3); the transition is not yet "confirmed" in the Section 6 sense until both conditions are met.

**Reason:** As originally worded, this sentence describes a "confirmed" transition that hasn't met its confidence floor, which conflicts with Section 6.1's definition of "confirmed" as requiring all five gating conditions (including the confidence floor) simultaneously. The revised wording removes the apparent internal contradiction.
**Breaking/Non-breaking:** Non-breaking (clarifies wording; does not change the underlying state machine, only removes an ambiguous description of it)

---

### ☐ Patch 20
**Section:** 10.4 (Tier 1 dependencies)
**Exact sentence to replace:**
> If a bar is unavailable, the caller decides whether to skip the period, impute, or raise — the module does not make this decision.

**Replacement sentence:**
> If a bar is unavailable, the caller decides whether to skip the period, impute, or raise before calling update(). Once a bar is passed to update(), the module applies its own internal staleness/imputation policy (Section 3, Q4) to the *features derived from that bar*, independent of how the caller sourced the bar itself.

**Reason:** As written, this sentence appears to contradict Section 3 Q4's detailed, module-owned policy for stale/missing data (carry-forward limits, staleness flags, spike filters). The revision clarifies the division of responsibility: callers own bar *sourcing*, the module owns feature-level *staleness handling* on whatever bar it receives.
**Breaking/Non-breaking:** Non-breaking (clarification of an existing, intended division of responsibility — assuming Section 3's policy was always meant to apply post-ingestion)

---

## Summary
- **Total patches:** 20
- **Breaking:** 12 (Patches 4, 5, 6, 7, 8, 9, 10, 11, 14, 15, 16, 17 — schema, config, or classification-boundary changes)
- **Non-breaking:** 8 (Patches 1, 2, 3, 12, 13, 18, 19, 20 — wording/documentation clarifications only)

Recommended order of application: resolve Patches 4–5 (Review Notes precedence) and Patches 8–9 (architecture contradiction) first, since several other patches (10–12, 15–17) depend on knowing which version of the spec — "v1.0 production" or "v2.3 simplified" — is authoritative before their replacement values can be finalized.
