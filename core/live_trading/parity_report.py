"""Research-only live-versus-replay analytical parity reporting."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from dataclasses import fields
from datetime import timedelta
from math import isclose
from pathlib import Path
from typing import Any

from core.multi_timeframe.enums import Timeframe
from core.trading_pipeline.models import PipelineObservationAudit

from . import parity_provenance
from .config import LiveTradingConfig
from .engine import LiveTradingEngine
from .multi_timeframe_buffer import LiveMultiTimeframeBuffer
from .parity_evidence import LiveParityEvidence
from .parity_provenance import (
    PARITY_EVIDENCE_SCHEMA_VERSION,
    ParityAnalyticalProvenance,
    ParityResultClassification,
)


class LiveParityReporter:
    """Replay only provenance-compatible evidence and compare audit fields."""

    def __init__(
        self,
        *,
        input_path: Path,
        output_directory: Path,
        float_tolerance: float = 1e-12,
    ) -> None:
        if float_tolerance < 0.0:
            raise ValueError("float_tolerance cannot be negative")
        self.input_path = input_path
        self.output_directory = output_directory
        self.float_tolerance = float_tolerance

    def calculate(self) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        parse_error_count = 0
        compatible_evidence_count = 0
        legacy_unversioned_count = 0
        provenance_mismatch_count = 0

        current_provenance: ParityAnalyticalProvenance | None = None
        current_provenance_error: str | None = None

        if self.input_path.exists():
            for line_number, line in enumerate(
                self.input_path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    if not isinstance(payload, Mapping):
                        raise TypeError("parity evidence row must be a JSON object")

                    schema = payload.get("schema_version")
                    if schema == 1:
                        evidence = LiveParityEvidence.from_payload(payload)
                        legacy_unversioned_count += 1
                        rows.append(
                            self._legacy_row(
                                line_number=line_number,
                                evidence=evidence,
                            )
                        )
                        continue

                    if schema != PARITY_EVIDENCE_SCHEMA_VERSION:
                        provenance_mismatch_count += 1
                        rows.append(
                            self._provenance_row(
                                line_number=line_number,
                                payload=payload,
                                diagnostics=(
                                    {
                                        "field": "schema_version",
                                        "evidence_value": schema,
                                        "current_value": PARITY_EVIDENCE_SCHEMA_VERSION,
                                        "error": "Parity evidence schema_version is unsupported.",
                                    },
                                ),
                            )
                        )
                        continue

                    missing = tuple(
                        field_name
                        for field_name in (
                            "analytical_contract_version",
                            "source_commit",
                            "pipeline_config_fingerprint",
                        )
                        if not isinstance(payload.get(field_name), str)
                        or not payload.get(field_name)
                    )
                    if missing:
                        provenance_mismatch_count += 1
                        rows.append(
                            self._provenance_row(
                                line_number=line_number,
                                payload=payload,
                                diagnostics=tuple(
                                    {
                                        "field": field_name,
                                        "evidence_value": payload.get(field_name),
                                        "current_value": None,
                                        "error": "Required analytical provenance is missing.",
                                    }
                                    for field_name in missing
                                ),
                            )
                        )
                        continue

                    evidence = LiveParityEvidence.from_payload(payload)

                    if current_provenance is None and current_provenance_error is None:
                        try:
                            current_provenance = parity_provenance.current_parity_provenance(
                                self._replay_config().pipeline
                            )
                        except (RuntimeError, TypeError, ValueError) as exc:
                            current_provenance_error = str(exc)

                    if current_provenance_error is not None:
                        provenance_mismatch_count += 1
                        rows.append(
                            self._provenance_row(
                                line_number=line_number,
                                payload=payload,
                                diagnostics=(
                                    {
                                        "field": "current_source_commit",
                                        "evidence_value": evidence.source_commit,
                                        "current_value": None,
                                        "error": current_provenance_error,
                                    },
                                ),
                            )
                        )
                        continue
                    if current_provenance is None:
                        raise RuntimeError("current parity provenance is unavailable")

                    assessment = parity_provenance.assess_payload_provenance(
                        payload,
                        current_provenance,
                    )
                    if not assessment.compatible:
                        provenance_mismatch_count += 1
                        rows.append(
                            self._provenance_row(
                                line_number=line_number,
                                payload=payload,
                                diagnostics=assessment.diagnostics,
                            )
                        )
                        continue

                    compatible_evidence_count += 1
                    replayed = self._replay(evidence)
                    mismatches = self.compare_audits(
                        evidence.expected_audit,
                        replayed,
                        float_tolerance=self.float_tolerance,
                    )
                    classification = (
                        ParityResultClassification.PARITY_MATCH
                        if not mismatches
                        else ParityResultClassification.ANALYTICAL_MISMATCH
                    )
                    rows.append(
                        {
                            "line": line_number,
                            "timestamp": evidence.observation_timestamp.isoformat(),
                            "symbol": evidence.symbol,
                            "classification": classification.value,
                            "parity_passed": not mismatches,
                            "mismatch_count": len(mismatches),
                            "mismatches": mismatches,
                        }
                    )
                except (
                    TypeError,
                    ValueError,
                    RuntimeError,
                    json.JSONDecodeError,
                ) as exc:
                    parse_error_count += 1
                    rows.append(
                        self._parse_error_row(
                            line_number=line_number,
                            error=str(exc),
                        )
                    )

        passed = sum(1 for row in rows if row["parity_passed"])
        failed = len(rows) - passed
        return {
            "input_path": str(self.input_path),
            "total_evidence_count": len(rows),
            "compatible_evidence_count": compatible_evidence_count,
            "legacy_unversioned_count": legacy_unversioned_count,
            "provenance_mismatch_count": provenance_mismatch_count,
            "parity_pass_count": passed,
            "parity_fail_count": failed,
            "parse_error_count": parse_error_count,
            "validation_passed": (
                compatible_evidence_count > 0
                and passed == compatible_evidence_count
                and failed == 0
                and parse_error_count == 0
            ),
            "live_execution_enabled": False,
            "shadow_only": True,
            "trade_executed": False,
            "results": rows,
        }

    def export(self) -> tuple[Path, Path]:
        report = self.calculate()
        self.output_directory.mkdir(parents=True, exist_ok=True)
        json_path = self.output_directory / "live_parity_report.json"
        csv_path = self.output_directory / "live_parity_report.csv"
        json_path.write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        with csv_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=(
                    "line",
                    "timestamp",
                    "symbol",
                    "classification",
                    "parity_passed",
                    "mismatch_count",
                ),
            )
            writer.writeheader()
            for row in report["results"]:
                writer.writerow({key: row[key] for key in writer.fieldnames})
        return csv_path, json_path

    def _replay(self, evidence: LiveParityEvidence) -> PipelineObservationAudit:
        config = self._replay_config()
        engine = LiveTradingEngine(config)
        buffer = LiveMultiTimeframeBuffer(
            window_bars=max(
                len(values) for values in evidence.bars_by_timeframe.values()
            )
        )
        for timeframe in (Timeframe.M5, Timeframe.M15, Timeframe.H1, Timeframe.H4):
            buffer.load(timeframe, evidence.bars_by_timeframe[timeframe])

        target_processed = False
        for m5_bar in evidence.bars_by_timeframe[Timeframe.M5]:
            boundary = m5_bar.timestamp + timedelta(minutes=5)
            snapshot = buffer.snapshot(boundary)
            is_target = m5_bar.timestamp == evidence.observation_timestamp
            if snapshot is None:
                if is_target:
                    raise RuntimeError(
                        "parity target lacks a complete synchronized M5 snapshot"
                    )
                continue
            engine.process_multi_timeframe(
                snapshot,
                account_balance=evidence.account_balance,
                stop_loss_distance=evidence.stop_loss_distance,
                pip_value=evidence.pip_value,
                tick_size=evidence.tick_size,
                lot_step=evidence.lot_step,
                minimum_lot=evidence.minimum_lot,
                maximum_lot=evidence.maximum_lot,
                warmup=not is_target,
            )
            if is_target:
                target_processed = True
                break

        if not target_processed:
            raise RuntimeError("parity target M5 observation was not processed")

        audit = engine.pipeline.last_observation_audit
        if audit is None:
            raise RuntimeError("parity replay produced no pipeline audit")
        if audit.timestamp != evidence.observation_timestamp:
            raise RuntimeError("parity replay audit timestamp does not match evidence")
        return audit

    @staticmethod
    def _replay_config() -> LiveTradingConfig:
        return LiveTradingConfig(
            live_execution_enabled=False,
            shadow_recording_enabled=False,
            parity_recording_enabled=False,
        )

    @staticmethod
    def _legacy_row(
        *,
        line_number: int,
        evidence: LiveParityEvidence,
    ) -> dict[str, Any]:
        classification = (
            ParityResultClassification.LEGACY_UNVERSIONED_ANALYTICAL_BASELINE
        )
        return {
            "line": line_number,
            "timestamp": evidence.observation_timestamp.isoformat(),
            "symbol": evidence.symbol,
            "classification": classification.value,
            "parity_passed": False,
            "mismatch_count": 1,
            "mismatches": [
                {
                    "field": "analytical_provenance",
                    "live_value": "schema_version=1",
                    "replay_value": None,
                    "error": classification.value,
                }
            ],
        }

    @staticmethod
    def _provenance_row(
        *,
        line_number: int,
        payload: Mapping[str, object],
        diagnostics: tuple[dict[str, object], ...],
    ) -> dict[str, Any]:
        return {
            "line": line_number,
            "timestamp": payload.get("observation_timestamp"),
            "symbol": payload.get("symbol"),
            "classification": ParityResultClassification.PROVENANCE_MISMATCH.value,
            "parity_passed": False,
            "mismatch_count": max(1, len(diagnostics)),
            "mismatches": [
                {
                    "field": item.get("field"),
                    "live_value": item.get("evidence_value"),
                    "replay_value": item.get("current_value"),
                    "error": item.get("error"),
                }
                for item in diagnostics
            ]
            or [
                {
                    "field": "analytical_provenance",
                    "live_value": None,
                    "replay_value": None,
                    "error": "PROVENANCE_MISMATCH",
                }
            ],
        }

    @staticmethod
    def _parse_error_row(*, line_number: int, error: str) -> dict[str, Any]:
        return {
            "line": line_number,
            "timestamp": None,
            "symbol": None,
            "classification": ParityResultClassification.PARSE_ERROR.value,
            "parity_passed": False,
            "mismatch_count": 1,
            "mismatches": [
                {
                    "field": "evidence",
                    "live_value": None,
                    "replay_value": None,
                    "error": error,
                }
            ],
        }

    @staticmethod
    def compare_audits(
        live: PipelineObservationAudit,
        replay: PipelineObservationAudit,
        *,
        float_tolerance: float = 1e-12,
    ) -> list[dict[str, object]]:
        mismatches: list[dict[str, object]] = []
        for field in fields(PipelineObservationAudit):
            live_value = getattr(live, field.name)
            replay_value = getattr(replay, field.name)
            if isinstance(live_value, float) or isinstance(replay_value, float):
                equal = (
                    live_value is not None
                    and replay_value is not None
                    and isclose(
                        float(live_value),
                        float(replay_value),
                        rel_tol=float_tolerance,
                        abs_tol=float_tolerance,
                    )
                )
            else:
                equal = live_value == replay_value
            if not equal:
                mismatches.append(
                    {
                        "field": field.name,
                        "live_value": LiveParityReporter._json_scalar(live_value),
                        "replay_value": LiveParityReporter._json_scalar(replay_value),
                    }
                )
        return mismatches

    @staticmethod
    def _json_scalar(value: object) -> object:
        if hasattr(value, "value"):
            return value.value
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return value
