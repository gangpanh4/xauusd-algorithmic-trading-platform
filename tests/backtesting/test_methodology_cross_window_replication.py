from __future__ import annotations

import json
from copy import deepcopy

import pytest

from core.backtesting.methodology_cross_window_replication import (
    MethodologyCrossWindowReplication,
)


def _variant(
    name: str,
    direction: str,
    *,
    sample: int,
    direction_count: int,
    favorable: int,
    unfavorable: int,
    retention: float,
    favorable_rate: float,
    average_return: float,
) -> dict[str, object]:
    return {
        "variant": name,
        "direction": direction,
        "shadow_eligible_count": sample,
        "direction_observation_count": direction_count,
        "shadow_retention_rate": retention,
        "shadow_favorable_rate": favorable_rate,
        "shadow_average_return_percent": average_return,
        "research_classification_counts": {
            "SHADOW_TRUE_POSITIVE": favorable,
            "SHADOW_FALSE_POSITIVE": unfavorable,
        },
    }


def _report(*, later: bool) -> dict[str, object]:
    if later:
        variants = [
            _variant(
                MethodologyCrossWindowReplication.VARIANT_A,
                "BULLISH",
                sample=118,
                direction_count=914,
                favorable=65,
                unfavorable=53,
                retention=0.12910284463894967,
                favorable_rate=0.5508474576271186,
                average_return=0.031746391525303334,
            ),
            _variant(
                MethodologyCrossWindowReplication.VARIANT_B,
                "BEARISH",
                sample=1787,
                direction_count=3288,
                favorable=977,
                unfavorable=810,
                retention=0.5434914841849149,
                favorable_rate=0.5467263570229435,
                average_return=0.03760383798100628,
            ),
        ]
        end = "2026-07-27T23:59:00+00:00"
        common_start = "2026-04-10T21:05:00+00:00"
        common_end = "2026-07-27T20:55:00+00:00"
        aligned = 6661
    else:
        variants = [
            _variant(
                MethodologyCrossWindowReplication.VARIANT_A,
                "BULLISH",
                sample=469,
                direction_count=2473,
                favorable=301,
                unfavorable=168,
                retention=0.18964820056611403,
                favorable_rate=0.6417910447761194,
                average_return=0.10043234151814158,
            ),
            _variant(
                MethodologyCrossWindowReplication.VARIANT_B,
                "BEARISH",
                sample=1213,
                direction_count=2409,
                favorable=603,
                unfavorable=610,
                retention=0.5035284350352843,
                favorable_rate=0.4971145919208574,
                average_return=0.03758408172200323,
            ),
        ]
        end = "2026-04-09T23:59:00+00:00"
        common_start = "2025-12-24T10:05:00+00:00"
        common_end = "2026-04-09T20:55:00+00:00"
        aligned = 6665

    return {
        "horizon_bars": 24,
        "aligned_audit_count": aligned,
        "unmatched_audit_count": 0,
        "common_window": {
            "start": common_start,
            "end": common_end,
            "alignment_coverage_rate_inside_window": 1.0,
        },
        "window_metadata": {"requested_end_time": end},
        "variants": variants,
        "observational_only": True,
        "trade_authority": False,
        "active_decision_modified": False,
        "active_pipeline_modified": False,
        "future_information_used_for_research_only": True,
    }


def test_calculates_frozen_cross_window_replication() -> None:
    payload = MethodologyCrossWindowReplication().calculate(
        _report(later=False),
        _report(later=True),
    )

    variant_a, variant_b = payload["variants"]

    assert variant_a["replication_status"] == (
        "REPLICATED_POSITIVE_BUT_EFFECT_WEAKENED"
    )
    assert variant_a["promotion_eligible"] is False
    assert (
        variant_a["observational_shadow_scoring_eligible"]
        is False
    )
    assert variant_a["absolute_drift"]["eligible_sample_count"] == -351
    assert variant_a["combined_descriptive"][
        "eligible_sample_count"
    ] == 587
    assert variant_a["combined_descriptive"]["favorable_count"] == 366
    assert variant_a["combined_descriptive"]["unfavorable_count"] == 221

    assert variant_b["replication_status"] == (
        "CROSS_WINDOW_REPLICATED"
    )
    assert variant_b["promotion_eligible"] is False
    assert (
        variant_b["observational_shadow_scoring_eligible"]
        is True
    )
    assert variant_b["combined_descriptive"][
        "eligible_sample_count"
    ] == 3000
    assert variant_b["combined_descriptive"]["favorable_count"] == 1580
    assert variant_b["combined_descriptive"]["unfavorable_count"] == 1420
    assert variant_b["combined_descriptive"]["favorable_rate"] == (
        1580 / 3000
    )
    assert payload["trade_authority"] is False
    assert payload["active_pipeline_modified"] is False


def test_exports_compact_json(tmp_path) -> None:
    older_path = tmp_path / "older.json"
    later_path = tmp_path / "later.json"
    older_path.write_text(
        json.dumps(_report(later=False)),
        encoding="utf-8",
    )
    later_path.write_text(
        json.dumps(_report(later=True)),
        encoding="utf-8",
    )

    output = MethodologyCrossWindowReplication().export(
        older_path,
        later_path,
        output_directory=tmp_path / "output",
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert output.name == (
        "methodology_cross_window_replication.json"
    )
    assert len(payload["variants"]) == 2
    assert payload["sources"]["older_window"] == str(older_path)
    assert payload["observational_only"] is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("observational_only", False),
        ("trade_authority", True),
        ("active_decision_modified", True),
        ("active_pipeline_modified", True),
        ("future_information_used_for_research_only", False),
        ("horizon_bars", 12),
        ("unmatched_audit_count", 1),
    ],
)
def test_rejects_ineligible_source_reports(
    field: str,
    value: object,
) -> None:
    older = _report(later=False)
    older[field] = value

    with pytest.raises(ValueError):
        MethodologyCrossWindowReplication().calculate(
            older,
            _report(later=True),
        )


def test_rejects_incomplete_common_window_coverage() -> None:
    older = _report(later=False)
    older["common_window"][
        "alignment_coverage_rate_inside_window"
    ] = 0.99

    with pytest.raises(ValueError):
        MethodologyCrossWindowReplication().calculate(
            older,
            _report(later=True),
        )


def test_rejects_changed_variant_set() -> None:
    older = _report(later=False)
    older["variants"] = deepcopy(older["variants"][:-1])

    with pytest.raises(ValueError):
        MethodologyCrossWindowReplication().calculate(
            older,
            _report(later=True),
        )
