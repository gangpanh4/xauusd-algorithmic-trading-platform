import json
from datetime import datetime

import pytest

from core.aurum_presentation import AurumReadModelBuilder
from core.aurum_presentation.serializer import to_json, to_json_safe, to_jsonable

from .conftest import make_inputs


def test_serializer_emits_utc_z_enums_arrays_and_capability_map() -> None:
    model = AurumReadModelBuilder.build(make_inputs())
    payload = to_jsonable(model)
    assert payload["meta"]["generated_at_utc"].endswith("Z")
    assert payload["meta"]["data_mode"] == "REAL_READ_ONLY"
    assert isinstance(payload["meta"]["capabilities"], dict)
    assert payload["meta"]["capabilities"]["quote"] is False
    assert isinstance(payload["features"]["items"], list)
    assert set(payload["bars"]) == {"W1", "D1", "H4", "H1", "M15", "M5"}
    assert set(payload["multi_timeframe"]["frames"]) == {
        "W1", "D1", "H4", "H1", "M15", "M5"
    }
    json.loads(to_json(model))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_values_are_rejected(value: float) -> None:
    with pytest.raises(ValueError, match="NaN or Infinity"):
        to_json_safe(value)


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValueError, match="naive"):
        to_json_safe(datetime(2026, 8, 16, 8, 30))  # noqa: DTZ001


def test_unsupported_arbitrary_value_is_rejected() -> None:
    class Unsupported:
        pass

    with pytest.raises(TypeError, match="unsupported JSON value"):
        to_json_safe(Unsupported())
