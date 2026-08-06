"""Immutable replay evidence for live-versus-backtest parity research."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise
from math import isfinite
from numbers import Integral
from pathlib import Path

from core.data.models import MarketBar
from core.multi_timeframe.enums import Timeframe
from core.trading_pipeline.models import (
    PipelineDisposition,
    PipelineObservationAudit,
    PipelineStage,
)

_REQUIRED_TIMEFRAMES = tuple(Timeframe)


def _require_aware_utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _require_finite(value: float, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    numeric = float(value)
    if not isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    if positive and numeric <= 0.0:
        raise ValueError(f"{name} must be greater than zero")
    return numeric


def _bar_payload(bar: MarketBar) -> dict[str, object]:
    timestamp = _require_aware_utc(bar.timestamp, "bar.timestamp")
    tick_volume = getattr(bar, "tick_volume", None)
    if tick_volume is None:
        tick_volume = getattr(bar, "volume", None)
    if isinstance(tick_volume, bool) or not isinstance(tick_volume, Integral):
        raise TypeError("bar tick volume must be an integer")
    normalized_tick_volume = int(tick_volume)
    if normalized_tick_volume < 0:
        raise ValueError("bar tick volume cannot be negative")
    return {
        "timestamp": timestamp.isoformat(),
        "open": _require_finite(bar.open, "bar.open"),
        "high": _require_finite(bar.high, "bar.high"),
        "low": _require_finite(bar.low, "bar.low"),
        "close": _require_finite(bar.close, "bar.close"),
        "tick_volume": normalized_tick_volume,
    }


def _bar_from_payload(payload: Mapping[str, object]) -> MarketBar:
    try:
        timestamp = datetime.fromisoformat(str(payload["timestamp"]))
        tick_volume = payload["tick_volume"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid parity bar payload") from exc
    if isinstance(tick_volume, bool) or not isinstance(tick_volume, Integral):
        raise TypeError("tick_volume must be an integer")
    normalized_tick_volume = int(tick_volume)
    bar = MarketBar(
        timestamp=_require_aware_utc(timestamp, "bar timestamp"),
        open=_require_finite(payload["open"], "open"),
        high=_require_finite(payload["high"], "high"),
        low=_require_finite(payload["low"], "low"),
        close=_require_finite(payload["close"], "close"),
        tick_volume=normalized_tick_volume,
    )
    if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close):
        raise ValueError("parity bar OHLC values are inconsistent")
    return bar


def audit_to_payload(audit: PipelineObservationAudit) -> dict[str, object]:
    return {
        "timestamp": audit.timestamp.isoformat(),
        "disposition": audit.disposition.value,
        "stage_reached": audit.stage_reached.value,
        "rejection_stage": (
            audit.rejection_stage.value if audit.rejection_stage is not None else None
        ),
        "reason_code": audit.reason_code,
        "reason": audit.reason,
        "regime_confirmed": audit.regime_confirmed,
        "bos_present": audit.bos_present,
        "choch_present": audit.choch_present,
        "liquidity_present": audit.liquidity_present,
        "feature_count": audit.feature_count,
        "probability_calculated": audit.probability_calculated,
        "probability_accepted": audit.probability_accepted,
        "probability_value": audit.probability_value,
        "trade_quality_calculated": audit.trade_quality_calculated,
        "trade_quality_approved": audit.trade_quality_approved,
        "trade_quality_score": audit.trade_quality_score,
        "confluence_available": audit.confluence_available,
        "confluence_approved": audit.confluence_approved,
        "confluence_score": audit.confluence_score,
        "signal_generated": audit.signal_generated,
        "risk_approved": audit.risk_approved,
    }


def audit_from_payload(payload: Mapping[str, object]) -> PipelineObservationAudit:
    try:
        rejection = payload.get("rejection_stage")
        return PipelineObservationAudit(
            timestamp=datetime.fromisoformat(str(payload["timestamp"])),
            disposition=PipelineDisposition(str(payload["disposition"])),
            stage_reached=PipelineStage(str(payload["stage_reached"])),
            rejection_stage=(PipelineStage(str(rejection)) if rejection else None),
            reason_code=(str(payload["reason_code"]) if payload.get("reason_code") else None),
            reason=(str(payload["reason"]) if payload.get("reason") else None),
            regime_confirmed=bool(payload["regime_confirmed"]),
            bos_present=bool(payload["bos_present"]),
            choch_present=bool(payload["choch_present"]),
            liquidity_present=bool(payload["liquidity_present"]),
            feature_count=int(payload["feature_count"]),
            probability_calculated=bool(payload["probability_calculated"]),
            probability_accepted=bool(payload["probability_accepted"]),
            probability_value=(
                None if payload.get("probability_value") is None
                else float(payload["probability_value"])
            ),
            trade_quality_calculated=bool(payload["trade_quality_calculated"]),
            trade_quality_approved=bool(payload["trade_quality_approved"]),
            trade_quality_score=(
                None if payload.get("trade_quality_score") is None
                else float(payload["trade_quality_score"])
            ),
            confluence_available=bool(payload["confluence_available"]),
            confluence_approved=bool(payload["confluence_approved"]),
            confluence_score=(
                None if payload.get("confluence_score") is None
                else float(payload["confluence_score"])
            ),
            signal_generated=bool(payload["signal_generated"]),
            risk_approved=bool(payload["risk_approved"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid pipeline audit payload") from exc


@dataclass(frozen=True, slots=True)
class LiveParityEvidence:
    """Complete deterministic input and expected output for one live decision."""

    captured_at: datetime
    observation_timestamp: datetime
    symbol: str
    bars_by_timeframe: Mapping[Timeframe, tuple[MarketBar, ...]]
    account_balance: float
    stop_loss_distance: float
    pip_value: float
    tick_size: float
    lot_step: float
    minimum_lot: float | None
    maximum_lot: float | None
    expected_audit: PipelineObservationAudit
    live_execution_enabled: bool = False
    shadow_only: bool = True
    trade_executed: bool = False
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "captured_at", _require_aware_utc(self.captured_at, "captured_at"))
        object.__setattr__(
            self,
            "observation_timestamp",
            _require_aware_utc(self.observation_timestamp, "observation_timestamp"),
        )
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")
        if self.schema_version != 1:
            raise ValueError("unsupported parity evidence schema_version")
        if self.live_execution_enabled or not self.shadow_only or self.trade_executed:
            raise ValueError("parity evidence must remain analysis-only")

        normalized: dict[Timeframe, tuple[MarketBar, ...]] = {}
        for timeframe in _REQUIRED_TIMEFRAMES:
            values = tuple(self.bars_by_timeframe.get(timeframe, ()))
            if not values:
                raise ValueError(f"missing {timeframe.value} parity history")
            timestamps = [
                _require_aware_utc(bar.timestamp, f"{timeframe.value} timestamp")
                for bar in values
            ]
            if any(current <= prior for prior, current in pairwise(timestamps)):
                raise ValueError(f"{timeframe.value} parity history must increase strictly")
            normalized[timeframe] = values
        object.__setattr__(self, "bars_by_timeframe", normalized)

        if normalized[Timeframe.M5][-1].timestamp.astimezone(UTC) != self.observation_timestamp:
            raise ValueError("latest M5 bar must match observation_timestamp")
        if self.expected_audit.timestamp != self.observation_timestamp:
            raise ValueError("expected audit timestamp must match observation_timestamp")

        for name, positive in (
            ("account_balance", True),
            ("stop_loss_distance", True),
            ("pip_value", True),
            ("tick_size", True),
            ("lot_step", True),
        ):
            object.__setattr__(self, name, _require_finite(getattr(self, name), name, positive=positive))
        for name in ("minimum_lot", "maximum_lot"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _require_finite(value, name, positive=True))
        if (
            self.minimum_lot is not None
            and self.maximum_lot is not None
            and self.minimum_lot > self.maximum_lot
        ):
            raise ValueError("minimum_lot cannot exceed maximum_lot")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "captured_at": self.captured_at.isoformat(),
            "observation_timestamp": self.observation_timestamp.isoformat(),
            "symbol": self.symbol,
            "bars_by_timeframe": {
                timeframe.value: [_bar_payload(bar) for bar in values]
                for timeframe, values in self.bars_by_timeframe.items()
            },
            "account_balance": self.account_balance,
            "stop_loss_distance": self.stop_loss_distance,
            "pip_value": self.pip_value,
            "tick_size": self.tick_size,
            "lot_step": self.lot_step,
            "minimum_lot": self.minimum_lot,
            "maximum_lot": self.maximum_lot,
            "expected_audit": audit_to_payload(self.expected_audit),
            "live_execution_enabled": self.live_execution_enabled,
            "shadow_only": self.shadow_only,
            "trade_executed": self.trade_executed,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> LiveParityEvidence:
        try:
            raw_histories = payload["bars_by_timeframe"]
            if not isinstance(raw_histories, Mapping):
                raise TypeError("bars_by_timeframe must be a mapping")
            histories: dict[Timeframe, tuple[MarketBar, ...]] = {}
            for timeframe in _REQUIRED_TIMEFRAMES:
                raw_values = raw_histories.get(timeframe.value)
                if not isinstance(raw_values, Sequence) or isinstance(raw_values, (str, bytes)):
                    raise TypeError(f"{timeframe.value} history must be a sequence")
                histories[timeframe] = tuple(
                    _bar_from_payload(value)
                    for value in raw_values
                    if isinstance(value, Mapping)
                )
                if len(histories[timeframe]) != len(raw_values):
                    raise TypeError(f"{timeframe.value} history contains invalid bars")
            expected = payload["expected_audit"]
            if not isinstance(expected, Mapping):
                raise TypeError("expected_audit must be a mapping")
            return cls(
                schema_version=int(payload["schema_version"]),
                captured_at=datetime.fromisoformat(str(payload["captured_at"])),
                observation_timestamp=datetime.fromisoformat(str(payload["observation_timestamp"])),
                symbol=str(payload["symbol"]),
                bars_by_timeframe=histories,
                account_balance=float(payload["account_balance"]),
                stop_loss_distance=float(payload["stop_loss_distance"]),
                pip_value=float(payload["pip_value"]),
                tick_size=float(payload["tick_size"]),
                lot_step=float(payload["lot_step"]),
                minimum_lot=(None if payload.get("minimum_lot") is None else float(payload["minimum_lot"])),
                maximum_lot=(None if payload.get("maximum_lot") is None else float(payload["maximum_lot"])),
                expected_audit=audit_from_payload(expected),
                live_execution_enabled=bool(payload["live_execution_enabled"]),
                shadow_only=bool(payload["shadow_only"]),
                trade_executed=bool(payload["trade_executed"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid live parity evidence payload") from exc


def append_parity_evidence(path: Path, evidence: LiveParityEvidence) -> None:
    """Append one complete JSONL record and recover from a truncated tail.

    A process interruption can leave the previous JSON object without its final
    newline. On restart, insert a separator before the next complete record so
    the reporter can classify the truncated row independently and still parse
    all later evidence.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    needs_separator = False
    if path.exists() and path.stat().st_size > 0:
        with path.open("rb") as existing:
            existing.seek(-1, 2)
            needs_separator = existing.read(1) != b"\n"

    with path.open("a", encoding="utf-8") as file:
        if needs_separator:
            file.write("\n")
        file.write(json.dumps(evidence.to_payload(), sort_keys=True) + "\n")
