from dataclasses import FrozenInstanceError

import pytest

from core.aurum_presentation import (
    AurumDataMode,
    AurumOperatorState,
    AurumReadModelBuilder,
)

from .conftest import make_inputs


def test_presentation_enum_values_are_exact() -> None:
    assert tuple(item.value for item in AurumDataMode) == (
        "REAL_READ_ONLY",
        "RESEARCH_REPLAY",
        "MOCK",
    )
    assert tuple(item.value for item in AurumOperatorState) == (
        "HOLD",
        "READY_BUY",
        "READY_SELL",
        "BLOCKED",
    )


def test_read_model_is_frozen_and_has_frozen_schema_identity() -> None:
    model = AurumReadModelBuilder.build(make_inputs())
    assert model.meta.schema_name == "AURUM_READ_MODEL_V1"
    assert model.meta.read_only is True
    assert model.meta.decision_timeframe == "M5"
    with pytest.raises(FrozenInstanceError):
        model.meta.schema_name = "changed"


def test_unavailable_domains_use_null_or_empty_not_fake_values() -> None:
    model = AurumReadModelBuilder.build(make_inputs())
    assert model.quote.available is False
    assert model.quote.bid is None
    assert model.strategy.available is False
    assert model.strategy.observation is None
    assert model.methodology.available is False
    assert model.intelligence_diagnostics.available is False
    assert model.news.available is False
    assert model.news.events == ()
    assert model.news.next_event is None
    assert model.ai.available is False
    assert model.regime.feature_set.available is False


def test_mock_mode_is_rejected_by_production_builder() -> None:
    with pytest.raises(ValueError, match="rejects MOCK"):
        AurumReadModelBuilder.build(make_inputs(mode=AurumDataMode.MOCK))
