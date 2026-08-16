"""Strict JSON-safe serialization for ``AURUM_READ_MODEL_V1``."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from enum import Enum
from math import isfinite
from typing import TypeAlias

from .models import AurumReadModelV1, BarsV1, MetaV1

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonInput: TypeAlias = (
    JsonScalar
    | datetime
    | date
    | Enum
    | list["JsonInput"]
    | tuple["JsonInput", ...]
    | dict[str, "JsonInput"]
)


def _datetime_to_z(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("cannot serialize naive datetime")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def to_json_safe(value: JsonInput) -> JsonValue:
    """Normalize one supported value, rejecting non-finite/unknown values."""

    if isinstance(value, Enum):
        return to_json_safe(value.value)
    if isinstance(value, datetime):
        return _datetime_to_z(value)
    if isinstance(value, date):
        return value.isoformat()
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("cannot serialize NaN or Infinity")
        return value
    if isinstance(value, (list, tuple)):
        return [to_json_safe(item) for item in value]
    if isinstance(value, dict):
        result: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            result[key] = to_json_safe(item)
        return result
    raise TypeError(f"unsupported JSON value type: {type(value).__name__}")


def _meta_dict(meta: MetaV1) -> dict[str, JsonInput]:
    return {
        "schema_name": meta.schema_name,
        "schema_version": meta.schema_version,
        "backend_repository": meta.backend_repository,
        "backend_commit": meta.backend_commit,
        "generated_at_utc": meta.generated_at_utc,
        "data_mode": meta.data_mode,
        "read_only": meta.read_only,
        "decision_timeframe": meta.decision_timeframe,
        "observation_time_utc": meta.observation_time_utc,
        "decision_available_at_utc": meta.decision_available_at_utc,
        "snapshot_id": meta.snapshot_id,
        "observation_id": meta.observation_id,
        "freshness_policy_id": meta.freshness_policy_id,
        "capabilities": {
            flag.name: flag.available
            for flag in meta.capabilities
        },
    }


def _bars_dict(bars: BarsV1) -> dict[str, JsonInput]:
    frames = asdict(bars.frames)
    return {
        "W1": frames["W1"],
        "D1": frames["D1"],
        "H4": frames["H4"],
        "H1": frames["H1"],
        "M15": frames["M15"],
        "M5": frames["M5"],
    }


def to_jsonable(model: AurumReadModelV1) -> dict[str, JsonValue]:
    """Convert one typed Aurum snapshot into the frozen JSON-safe shape."""

    raw: dict[str, JsonInput] = {
        "meta": _meta_dict(model.meta),
        "market": asdict(model.market),
        "quote": asdict(model.quote),
        "bars": _bars_dict(model.bars),
        "multi_timeframe": asdict(model.multi_timeframe),
        "structure": asdict(model.structure),
        "price_action": asdict(model.price_action),
        "regime": asdict(model.regime),
        "features": asdict(model.features),
        "methodology": asdict(model.methodology),
        "intelligence_diagnostics": asdict(model.intelligence_diagnostics),
        "confluence": asdict(model.confluence),
        "probability": asdict(model.probability),
        "decision": asdict(model.decision),
        "signal": asdict(model.signal),
        "trade_quality": asdict(model.trade_quality),
        "pipeline_audit": asdict(model.pipeline_audit),
        "pipeline_consistency": asdict(model.pipeline_consistency),
        "strategy": asdict(model.strategy),
        "risk": asdict(model.risk),
        "trade_plan": asdict(model.trade_plan),
        "operator_state": asdict(model.operator_state),
        "execution": asdict(model.execution),
        "health": asdict(model.health),
        "research": asdict(model.research),
        "news": asdict(model.news),
        "ai": asdict(model.ai),
    }
    normalized = to_json_safe(raw)
    if not isinstance(normalized, dict):
        raise TypeError("AurumReadModelV1 must serialize to a JSON object")
    return normalized


def to_json(model: AurumReadModelV1, *, indent: int | None = None) -> str:
    """Serialize one Aurum snapshot with strict JSON numeric handling."""

    return json.dumps(
        to_jsonable(model),
        allow_nan=False,
        indent=indent,
        separators=None if indent is not None else (",", ":"),
        sort_keys=True,
    )
