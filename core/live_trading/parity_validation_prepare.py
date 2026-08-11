"""Prepare a durable analytical-parity attestation before demo authorization."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from .config import LiveTradingConfig
from .parity_validation_attestation import (
    ParityValidationAttestationError,
    prepare_parity_validation_attestation,
)


def main() -> int:
    config = LiveTradingConfig(
        live_execution_enabled=False,
        demo_execution_approved=False,
        execution_kill_switch_enabled=True,
        shadow_recording_enabled=False,
        parity_recording_enabled=False,
    )
    try:
        attestation = prepare_parity_validation_attestation(
            config=config,
            now=datetime.now(UTC),
        )
    except (
        ParityValidationAttestationError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"Parity validation attestation preparation failed closed: {exc}")
        return 2

    print(
        json.dumps(
            {
                "schema_version": attestation.schema_version,
                "validated_at": attestation.validated_at.isoformat(),
                "parity_evidence_path": attestation.parity_evidence_path,
                "parity_evidence_sha256": attestation.parity_evidence_sha256,
                "parity_evidence_size_bytes": attestation.parity_evidence_size_bytes,
                "source_commit": attestation.source_commit,
                "analytical_contract_version": (
                    attestation.analytical_contract_version
                ),
                "history_contract_version": attestation.history_contract_version,
                "pipeline_config_fingerprint": (
                    attestation.pipeline_config_fingerprint
                ),
                "total_evidence_count": attestation.total_evidence_count,
                "compatible_evidence_count": attestation.compatible_evidence_count,
                "parity_pass_count": attestation.parity_pass_count,
                "validation_passed": attestation.validation_passed,
                "live_execution_enabled": attestation.live_execution_enabled,
                "trade_executed": attestation.trade_executed,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
