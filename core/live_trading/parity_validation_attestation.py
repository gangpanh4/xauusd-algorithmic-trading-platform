"""Durable pre-authorization attestation for expensive live parity validation."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Final

from . import parity_provenance
from .config import LiveTradingConfig
from .parity_evidence_prepare import _fsync_directory
from .parity_provenance import (
    CURRENT_PARITY_HISTORY_CONTRACT_VERSION,
    PARITY_EVIDENCE_SCHEMA_VERSION,
    ParityAnalyticalProvenance,
    validate_history_contract_version,
    validate_pipeline_config_fingerprint,
    validate_source_commit,
)
from .parity_report import LiveParityReporter

PARITY_VALIDATION_ATTESTATION_SCHEMA_VERSION: Final = 1
_HASH_BUFFER_BYTES: Final = 1024 * 1024


class ParityValidationAttestationError(RuntimeError):
    """Raised when a parity attestation cannot be created or trusted."""


@dataclass(frozen=True, slots=True)
class ParityValidationAttestation:
    """Exact analytical-parity proof bound to source, config, and evidence bytes."""

    schema_version: int
    validated_at: datetime
    parity_evidence_path: str
    parity_evidence_sha256: str
    parity_evidence_size_bytes: int
    parity_evidence_schema_version: int
    analytical_contract_version: str
    history_contract_version: str
    source_commit: str
    pipeline_config_fingerprint: str
    total_evidence_count: int
    compatible_evidence_count: int
    legacy_unversioned_count: int
    provenance_mismatch_count: int
    parity_pass_count: int
    parity_fail_count: int
    parse_error_count: int
    validation_passed: bool
    live_execution_enabled: bool
    shadow_only: bool
    trade_executed: bool

    def __post_init__(self) -> None:
        if self.schema_version != PARITY_VALIDATION_ATTESTATION_SCHEMA_VERSION:
            raise ValueError("unsupported parity validation attestation schema")
        object.__setattr__(
            self,
            "validated_at",
            _aware_utc(self.validated_at, "validated_at"),
        )
        if (
            not isinstance(self.parity_evidence_path, str)
            or not self.parity_evidence_path
            or self.parity_evidence_path != self.parity_evidence_path.strip()
        ):
            raise ValueError("parity_evidence_path must be a non-empty exact string")
        _validate_sha256(self.parity_evidence_sha256, "parity_evidence_sha256")
        if (
            isinstance(self.parity_evidence_size_bytes, bool)
            or not isinstance(self.parity_evidence_size_bytes, int)
            or self.parity_evidence_size_bytes <= 0
        ):
            raise ValueError("parity_evidence_size_bytes must be a positive integer")
        if self.parity_evidence_schema_version != PARITY_EVIDENCE_SCHEMA_VERSION:
            raise ValueError("parity evidence schema version is not current")
        if (
            not isinstance(self.analytical_contract_version, str)
            or not self.analytical_contract_version
            or self.analytical_contract_version
            != self.analytical_contract_version.strip()
        ):
            raise ValueError(
                "analytical_contract_version must be a non-empty exact string"
            )
        validate_history_contract_version(self.history_contract_version)
        validate_source_commit(self.source_commit)
        validate_pipeline_config_fingerprint(self.pipeline_config_fingerprint)

        counts = (
            self.total_evidence_count,
            self.compatible_evidence_count,
            self.legacy_unversioned_count,
            self.provenance_mismatch_count,
            self.parity_pass_count,
            self.parity_fail_count,
            self.parse_error_count,
        )
        if any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
            for value in counts
        ):
            raise ValueError("parity attestation counts must be non-negative integers")
        if self.total_evidence_count <= 0:
            raise ValueError("parity attestation requires at least one evidence row")
        if self.validation_passed is not True:
            raise ValueError("parity attestation must represent a passing validation")
        if (
            self.live_execution_enabled is not False
            or self.shadow_only is not True
            or self.trade_executed is not False
        ):
            raise ValueError("parity attestation must represent analysis-only validation")
        if (
            self.legacy_unversioned_count != 0
            or self.provenance_mismatch_count != 0
            or self.parity_fail_count != 0
            or self.parse_error_count != 0
            or self.compatible_evidence_count != self.total_evidence_count
            or self.parity_pass_count != self.compatible_evidence_count
        ):
            raise ValueError("parity attestation counts do not prove full compatibility")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "validated_at": self.validated_at.isoformat(),
            "parity_evidence_path": self.parity_evidence_path,
            "parity_evidence_sha256": self.parity_evidence_sha256,
            "parity_evidence_size_bytes": self.parity_evidence_size_bytes,
            "parity_evidence_schema_version": self.parity_evidence_schema_version,
            "analytical_contract_version": self.analytical_contract_version,
            "history_contract_version": self.history_contract_version,
            "source_commit": self.source_commit,
            "pipeline_config_fingerprint": self.pipeline_config_fingerprint,
            "total_evidence_count": self.total_evidence_count,
            "compatible_evidence_count": self.compatible_evidence_count,
            "legacy_unversioned_count": self.legacy_unversioned_count,
            "provenance_mismatch_count": self.provenance_mismatch_count,
            "parity_pass_count": self.parity_pass_count,
            "parity_fail_count": self.parity_fail_count,
            "parse_error_count": self.parse_error_count,
            "validation_passed": self.validation_passed,
            "live_execution_enabled": self.live_execution_enabled,
            "shadow_only": self.shadow_only,
            "trade_executed": self.trade_executed,
        }

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, object],
    ) -> ParityValidationAttestation:
        expected = {
            "schema_version",
            "validated_at",
            "parity_evidence_path",
            "parity_evidence_sha256",
            "parity_evidence_size_bytes",
            "parity_evidence_schema_version",
            "analytical_contract_version",
            "history_contract_version",
            "source_commit",
            "pipeline_config_fingerprint",
            "total_evidence_count",
            "compatible_evidence_count",
            "legacy_unversioned_count",
            "provenance_mismatch_count",
            "parity_pass_count",
            "parity_fail_count",
            "parse_error_count",
            "validation_passed",
            "live_execution_enabled",
            "shadow_only",
            "trade_executed",
        }
        if set(payload) != expected:
            raise ValueError("parity validation attestation schema is invalid")
        validated_at_raw = payload["validated_at"]
        if not isinstance(validated_at_raw, str):
            raise TypeError("validated_at must be a string")
        try:
            validated_at = datetime.fromisoformat(validated_at_raw)
        except ValueError as exc:
            raise ValueError("validated_at is invalid") from exc

        return cls(
            schema_version=_strict_int(payload["schema_version"], "schema_version"),
            validated_at=validated_at,
            parity_evidence_path=_strict_str(
                payload["parity_evidence_path"],
                "parity_evidence_path",
            ),
            parity_evidence_sha256=_strict_str(
                payload["parity_evidence_sha256"],
                "parity_evidence_sha256",
            ),
            parity_evidence_size_bytes=_strict_int(
                payload["parity_evidence_size_bytes"],
                "parity_evidence_size_bytes",
            ),
            parity_evidence_schema_version=_strict_int(
                payload["parity_evidence_schema_version"],
                "parity_evidence_schema_version",
            ),
            analytical_contract_version=_strict_str(
                payload["analytical_contract_version"],
                "analytical_contract_version",
            ),
            history_contract_version=_strict_str(
                payload["history_contract_version"],
                "history_contract_version",
            ),
            source_commit=_strict_str(payload["source_commit"], "source_commit"),
            pipeline_config_fingerprint=_strict_str(
                payload["pipeline_config_fingerprint"],
                "pipeline_config_fingerprint",
            ),
            total_evidence_count=_strict_int(
                payload["total_evidence_count"],
                "total_evidence_count",
            ),
            compatible_evidence_count=_strict_int(
                payload["compatible_evidence_count"],
                "compatible_evidence_count",
            ),
            legacy_unversioned_count=_strict_int(
                payload["legacy_unversioned_count"],
                "legacy_unversioned_count",
            ),
            provenance_mismatch_count=_strict_int(
                payload["provenance_mismatch_count"],
                "provenance_mismatch_count",
            ),
            parity_pass_count=_strict_int(
                payload["parity_pass_count"],
                "parity_pass_count",
            ),
            parity_fail_count=_strict_int(
                payload["parity_fail_count"],
                "parity_fail_count",
            ),
            parse_error_count=_strict_int(
                payload["parse_error_count"],
                "parse_error_count",
            ),
            validation_passed=_strict_bool(
                payload["validation_passed"],
                "validation_passed",
            ),
            live_execution_enabled=_strict_bool(
                payload["live_execution_enabled"],
                "live_execution_enabled",
            ),
            shadow_only=_strict_bool(payload["shadow_only"], "shadow_only"),
            trade_executed=_strict_bool(
                payload["trade_executed"],
                "trade_executed",
            ),
        )


def prepare_parity_validation_attestation(
    *,
    config: LiveTradingConfig,
    now: datetime,
) -> ParityValidationAttestation:
    """Run the expensive replay once, then persist an exact durable proof."""

    observed_at = _aware_utc(now, "now")
    _require_safe_disabled_config(config)

    before_identity = _parity_evidence_identity(config.parity_evidence_path)
    provenance_before = _current_provenance(config)

    report = LiveParityReporter(
        input_path=config.parity_evidence_path,
        output_directory=config.parity_report_directory,
    ).calculate()
    counts = _require_passing_report(report)

    after_identity = _parity_evidence_identity(config.parity_evidence_path)
    if after_identity != before_identity:
        raise ParityValidationAttestationError(
            "Parity evidence changed while full replay validation was running."
        )

    provenance_after = _current_provenance(config)
    if provenance_after != provenance_before:
        raise ParityValidationAttestationError(
            "Analytical provenance changed while full replay validation was running."
        )

    digest, size = before_identity
    attestation = ParityValidationAttestation(
        schema_version=PARITY_VALIDATION_ATTESTATION_SCHEMA_VERSION,
        validated_at=observed_at,
        parity_evidence_path=config.parity_evidence_path.as_posix(),
        parity_evidence_sha256=digest,
        parity_evidence_size_bytes=size,
        parity_evidence_schema_version=PARITY_EVIDENCE_SCHEMA_VERSION,
        analytical_contract_version=provenance_before.analytical_contract_version,
        history_contract_version=CURRENT_PARITY_HISTORY_CONTRACT_VERSION,
        source_commit=provenance_before.source_commit,
        pipeline_config_fingerprint=provenance_before.pipeline_config_fingerprint,
        total_evidence_count=counts["total_evidence_count"],
        compatible_evidence_count=counts["compatible_evidence_count"],
        legacy_unversioned_count=counts["legacy_unversioned_count"],
        provenance_mismatch_count=counts["provenance_mismatch_count"],
        parity_pass_count=counts["parity_pass_count"],
        parity_fail_count=counts["parity_fail_count"],
        parse_error_count=counts["parse_error_count"],
        validation_passed=True,
        live_execution_enabled=False,
        shadow_only=True,
        trade_executed=False,
    )
    _write_attestation_durably(
        config.parity_validation_attestation_path,
        attestation,
    )
    return verify_parity_validation_attestation(config=config)


def verify_parity_validation_attestation(
    *,
    config: LiveTradingConfig,
) -> ParityValidationAttestation:
    """Verify a prepared attestation without re-running the expensive replay."""

    attestation = load_parity_validation_attestation(
        config.parity_validation_attestation_path
    )
    if attestation.validated_at > datetime.now(UTC):
        raise ParityValidationAttestationError(
            "Parity validation attestation is dated in the future."
        )
    if attestation.parity_evidence_path != config.parity_evidence_path.as_posix():
        raise ParityValidationAttestationError(
            "Parity validation attestation is bound to a different evidence path."
        )

    current = _current_provenance(config)
    mismatches: list[str] = []
    if attestation.analytical_contract_version != current.analytical_contract_version:
        mismatches.append("analytical_contract_version")
    if (
        attestation.history_contract_version
        != CURRENT_PARITY_HISTORY_CONTRACT_VERSION
    ):
        mismatches.append("history_contract_version")
    if attestation.source_commit != current.source_commit:
        mismatches.append("source_commit")
    if (
        attestation.pipeline_config_fingerprint
        != current.pipeline_config_fingerprint
    ):
        mismatches.append("pipeline_config_fingerprint")
    if mismatches:
        raise ParityValidationAttestationError(
            "Parity validation attestation provenance mismatch: "
            + ", ".join(mismatches)
        )

    digest, size = _parity_evidence_identity(config.parity_evidence_path)
    if (
        digest != attestation.parity_evidence_sha256
        or size != attestation.parity_evidence_size_bytes
    ):
        raise ParityValidationAttestationError(
            "Parity evidence bytes changed after attestation."
        )
    return attestation


def load_parity_validation_attestation(
    path: str | Path,
) -> ParityValidationAttestation:
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ParityValidationAttestationError(
            "Parity validation attestation file does not exist as a regular file."
        )
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ParityValidationAttestationError(
            "Parity validation attestation could not be read."
        ) from exc
    if not isinstance(payload, Mapping):
        raise ParityValidationAttestationError(
            "Parity validation attestation must be a JSON object."
        )
    try:
        return ParityValidationAttestation.from_payload(payload)
    except (TypeError, ValueError) as exc:
        raise ParityValidationAttestationError(
            "Parity validation attestation is malformed."
        ) from exc


def _require_safe_disabled_config(config: LiveTradingConfig) -> None:
    if (
        config.live_execution_enabled
        or config.demo_execution_approved
        or not config.execution_kill_switch_enabled
    ):
        raise ParityValidationAttestationError(
            "Full parity attestation must run from safe-disabled controls."
        )


def _current_provenance(
    config: LiveTradingConfig,
) -> ParityAnalyticalProvenance:
    try:
        return parity_provenance.current_parity_provenance(config.pipeline)
    except (RuntimeError, TypeError, ValueError) as exc:
        raise ParityValidationAttestationError(
            "Current analytical provenance cannot be trusted."
        ) from exc


def _require_passing_report(report: Mapping[str, object]) -> dict[str, int]:
    count_names = (
        "total_evidence_count",
        "compatible_evidence_count",
        "legacy_unversioned_count",
        "provenance_mismatch_count",
        "parity_pass_count",
        "parity_fail_count",
        "parse_error_count",
    )
    counts = {
        name: _strict_nonnegative_int(report.get(name), name)
        for name in count_names
    }
    if (
        report.get("validation_passed") is not True
        or report.get("live_execution_enabled") is not False
        or report.get("shadow_only") is not True
        or report.get("trade_executed") is not False
        or counts["total_evidence_count"] <= 0
        or counts["compatible_evidence_count"] != counts["total_evidence_count"]
        or counts["legacy_unversioned_count"] != 0
        or counts["provenance_mismatch_count"] != 0
        or counts["parity_pass_count"] != counts["compatible_evidence_count"]
        or counts["parity_fail_count"] != 0
        or counts["parse_error_count"] != 0
    ):
        raise ParityValidationAttestationError(
            "Production live-versus-replay parity validation did not pass cleanly."
        )
    return counts


def _parity_evidence_identity(path: Path) -> tuple[str, int]:
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ParityValidationAttestationError(
            "Parity evidence does not exist as a regular file."
        )
    digest = sha256()
    size = 0
    try:
        with source.open("rb") as handle:
            while True:
                chunk = handle.read(_HASH_BUFFER_BYTES)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
    except OSError as exc:
        raise ParityValidationAttestationError(
            "Parity evidence could not be read."
        ) from exc
    if size <= 0:
        raise ParityValidationAttestationError("Parity evidence is empty.")
    return digest.hexdigest(), size


def _write_attestation_durably(
    path: Path,
    attestation: ParityValidationAttestation,
) -> None:
    destination = Path(path)
    if os.path.lexists(destination) and destination.is_symlink():
        raise ParityValidationAttestationError(
            "Parity validation attestation path cannot be a symlink."
        )
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ParityValidationAttestationError(
            "Unable to create parity attestation directory."
        ) from exc

    data = (
        json.dumps(
            attestation.to_payload(),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
        temporary_path = None
        _fsync_directory(destination.parent)
    except OSError as exc:
        raise ParityValidationAttestationError(
            "Unable to durably install parity validation attestation."
        ) from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def _aware_utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _strict_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    return value


def _strict_nonnegative_int(value: object, name: str) -> int:
    normalized = _strict_int(value, name)
    if normalized < 0:
        raise ValueError(f"{name} cannot be negative")
    return normalized


def _strict_bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")
    return value


def _strict_str(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    return value


def _validate_sha256(value: str, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must be lowercase SHA-256 hex")
    return value
