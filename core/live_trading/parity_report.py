"""Research-only live-versus-replay analytical parity reporting."""

from __future__ import annotations

import csv
import json
from dataclasses import fields
from datetime import timedelta
from math import isclose
from pathlib import Path
from typing import Any

from core.multi_timeframe.enums import Timeframe
from core.trading_pipeline.models import PipelineObservationAudit

from .config import LiveTradingConfig
from .engine import LiveTradingEngine
from .multi_timeframe_buffer import LiveMultiTimeframeBuffer
from .parity_evidence import LiveParityEvidence


class LiveParityReporter:
    """Replay persisted live evidence and compare authoritative audit fields."""

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

        if self.input_path.exists():
            for line_number, line in enumerate(
                self.input_path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    evidence = LiveParityEvidence.from_payload(payload)
                    replayed = self._replay(evidence)
                    mismatches = self.compare_audits(
                        evidence.expected_audit,
                        replayed,
                        float_tolerance=self.float_tolerance,
                    )
                    rows.append(
                        {
                            "line": line_number,
                            "timestamp": evidence.observation_timestamp.isoformat(),
                            "symbol": evidence.symbol,
                            "parity_passed": not mismatches,
                            "mismatch_count": len(mismatches),
                            "mismatches": mismatches,
                        }
                    )
                except (TypeError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
                    parse_error_count += 1
                    rows.append(
                        {
                            "line": line_number,
                            "timestamp": None,
                            "symbol": None,
                            "parity_passed": False,
                            "mismatch_count": 1,
                            "mismatches": [
                                {
                                    "field": "evidence",
                                    "live_value": None,
                                    "replay_value": None,
                                    "error": str(exc),
                                }
                            ],
                        }
                    )

        passed = sum(1 for row in rows if row["parity_passed"])
        failed = len(rows) - passed
        return {
            "input_path": str(self.input_path),
            "total_evidence_count": len(rows),
            "parity_pass_count": passed,
            "parity_fail_count": failed,
            "parse_error_count": parse_error_count,
            "validation_passed": bool(rows) and failed == 0 and parse_error_count == 0,
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
                    "parity_passed",
                    "mismatch_count",
                ),
            )
            writer.writeheader()
            for row in report["results"]:
                writer.writerow(
                    {
                        key: row[key]
                        for key in writer.fieldnames
                    }
                )
        return csv_path, json_path

    def _replay(self, evidence: LiveParityEvidence) -> PipelineObservationAudit:
        config = LiveTradingConfig(
            live_execution_enabled=False,
            shadow_recording_enabled=False,
            parity_recording_enabled=False,
        )
        engine = LiveTradingEngine(config)
        buffer = LiveMultiTimeframeBuffer(
            window_bars=max(
                len(values)
                for values in evidence.bars_by_timeframe.values()
            )
        )
        for timeframe in (Timeframe.M5, Timeframe.M15, Timeframe.H1, Timeframe.H4):
            buffer.load(timeframe, evidence.bars_by_timeframe[timeframe])

        for m5_bar in evidence.bars_by_timeframe[Timeframe.M5]:
            boundary = m5_bar.timestamp + timedelta(minutes=5)
            snapshot = buffer.snapshot(boundary)
            is_target = m5_bar.timestamp == evidence.observation_timestamp
            if snapshot is None:
                engine.process_bar(
                    m5_bar,
                    account_balance=evidence.account_balance,
                    stop_loss_distance=evidence.stop_loss_distance,
                    pip_value=evidence.pip_value,
                    warmup=not is_target,
                )
            else:
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
                break

        audit = engine.pipeline.last_observation_audit
        if audit is None:
            raise RuntimeError("parity replay produced no pipeline audit")
        if audit.timestamp != evidence.observation_timestamp:
            raise RuntimeError("parity replay audit timestamp does not match evidence")
        return audit

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
