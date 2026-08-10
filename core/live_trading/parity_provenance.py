"""Versioned analytical provenance for live parity evidence."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from hashlib import sha256
from math import isfinite
from pathlib import Path
from typing import Final

from core.trading_pipeline.config import TradingPipelineConfig

PARITY_EVIDENCE_SCHEMA_VERSION: Final = 3
PARITY_HISTORY_CONTRACT_V1: Final = (
    "SOURCE_M5_M15_H1_H4_DERIVE_D1_W1_FROM_H4_V1"
)
CURRENT_PARITY_HISTORY_CONTRACT_VERSION: Final = PARITY_HISTORY_CONTRACT_V1
M5_ANALYTICAL_CONTRACT_V1: Final = "M5_ANALYTICAL_CONTRACT_V1"
CURRENT_ANALYTICAL_CONTRACT_VERSION: Final = M5_ANALYTICAL_CONTRACT_V1
_PIPELINE_CONFIG_FINGERPRINT_CONTRACT: Final = "TRADING_PIPELINE_ANALYTICAL_CONFIG_V1"
_ANALYTICAL_PIPELINE_CONFIG_FIELDS: Final = (
    "regime_detector",
    "market_structure",
    "signal_generator",
    "confluence_engine",
    "risk_manager",
)
_NON_ANALYTICAL_FIELD_NAMES: Final = frozenset({"debug_logging"})
_GIT_COMMIT_RE: Final = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
_SHA256_RE: Final = re.compile(r"^[0-9a-f]{64}$")


class ParityProvenanceError(RuntimeError):
    """Raised when current analytical provenance cannot be trusted."""


class ParityResultClassification(str, Enum):
    """Explicit classification for each active parity-evidence row."""

    PARITY_MATCH = "PARITY_MATCH"
    ANALYTICAL_MISMATCH = "ANALYTICAL_MISMATCH"
    LEGACY_UNVERSIONED_ANALYTICAL_BASELINE = "LEGACY_UNVERSIONED_ANALYTICAL_BASELINE"
    PROVENANCE_MISMATCH = "PROVENANCE_MISMATCH"
    PARSE_ERROR = "PARSE_ERROR"


@dataclass(frozen=True, slots=True)
class ParityAnalyticalProvenance:
    """Current source/config identity used to produce or replay evidence."""

    analytical_contract_version: str
    source_commit: str
    pipeline_config_fingerprint: str


@dataclass(frozen=True, slots=True)
class ProvenanceAssessment:
    """Compatibility result before any analytical replay occurs."""

    compatible: bool
    classification: ParityResultClassification | None
    diagnostics: tuple[dict[str, object], ...]


def current_parity_provenance(config: TradingPipelineConfig) -> ParityAnalyticalProvenance:
    """Resolve the trustworthy current source and analytical configuration."""

    return ParityAnalyticalProvenance(
        analytical_contract_version=CURRENT_ANALYTICAL_CONTRACT_VERSION,
        source_commit=resolve_source_commit(require_clean=True),
        pipeline_config_fingerprint=pipeline_config_fingerprint(config),
    )


def resolve_source_commit(
    *,
    require_clean: bool,
    repository_root: Path | None = None,
) -> str:
    """Return exact local HEAD, rejecting source trees that cannot match HEAD."""

    expected_root = (
        Path(__file__).resolve().parents[2]
        if repository_root is None
        else Path(repository_root).resolve()
    )
    reported_root = Path(_run_git(expected_root, "rev-parse", "--show-toplevel")).resolve()
    if reported_root != expected_root:
        raise ParityProvenanceError(
            "Parity provenance repository root does not match the source tree."
        )

    commit = _run_git(expected_root, "rev-parse", "--verify", "HEAD").strip().lower()
    validate_source_commit(commit)

    if require_clean:
        status = _run_git(
            expected_root,
            "status",
            "--porcelain=v1",
            "--untracked-files=normal",
        )
        if status.strip():
            raise ParityProvenanceError(
                "Fresh parity evidence requires a clean Git working tree."
            )
    return commit


def pipeline_config_fingerprint(config: TradingPipelineConfig) -> str:
    """Hash the TradingPipeline configuration that is actually wired into output.

    The current TradingPipeline constructor directly consumes regime, market
    structure, signal, confluence, and risk configuration. Parameterless
    analytical engines are versioned by ``source_commit`` and the explicit
    analytical contract. Logging-only fields and live execution controls are
    intentionally excluded.
    """

    if not isinstance(config, TradingPipelineConfig):
        raise TypeError("config must be a TradingPipelineConfig")

    analytical_fields: dict[str, object] = {}
    for name in _ANALYTICAL_PIPELINE_CONFIG_FIELDS:
        if not hasattr(config, name):
            raise ParityProvenanceError(
                f"TradingPipelineConfig is missing analytical field: {name}"
            )
        analytical_fields[name] = _canonicalize(getattr(config, name))

    payload = {
        "fingerprint_contract": _PIPELINE_CONFIG_FINGERPRINT_CONTRACT,
        "config_type": _type_name(config),
        "analytical_fields": analytical_fields,
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(serialized).hexdigest()


def assess_payload_provenance(
    payload: Mapping[str, object],
    current: ParityAnalyticalProvenance,
) -> ProvenanceAssessment:
    """Classify evidence provenance without replaying analytical outputs."""

    raw_schema = payload.get("schema_version")
    if isinstance(raw_schema, bool) or not isinstance(raw_schema, int):
        return _provenance_mismatch(
            "schema_version",
            raw_schema,
            PARITY_EVIDENCE_SCHEMA_VERSION,
            "Parity evidence schema_version is missing or invalid.",
        )
    if raw_schema == 1:
        return ProvenanceAssessment(
            compatible=False,
            classification=(
                ParityResultClassification.LEGACY_UNVERSIONED_ANALYTICAL_BASELINE
            ),
            diagnostics=(
                {
                    "field": "analytical_provenance",
                    "evidence_value": "schema_version=1",
                    "current_value": current.analytical_contract_version,
                    "error": "Schema-v1 parity evidence has no versioned analytical baseline.",
                },
            ),
        )
    if raw_schema != PARITY_EVIDENCE_SCHEMA_VERSION:
        return _provenance_mismatch(
            "schema_version",
            raw_schema,
            PARITY_EVIDENCE_SCHEMA_VERSION,
            "Parity evidence schema_version is unsupported.",
        )

    diagnostics: list[dict[str, object]] = []
    required = (
        ("analytical_contract_version", current.analytical_contract_version),
        ("source_commit", current.source_commit),
        ("pipeline_config_fingerprint", current.pipeline_config_fingerprint),
        (
            "history_contract_version",
            CURRENT_PARITY_HISTORY_CONTRACT_VERSION,
        ),
    )
    for field_name, expected in required:
        observed = payload.get(field_name)
        if not isinstance(observed, str) or not observed:
            diagnostics.append(
                {
                    "field": field_name,
                    "evidence_value": observed,
                    "current_value": expected,
                    "error": "Required analytical provenance is missing.",
                }
            )
            continue
        try:
            if field_name == "source_commit":
                validate_source_commit(observed)
            elif field_name == "pipeline_config_fingerprint":
                validate_pipeline_config_fingerprint(observed)
        except ValueError as exc:
            diagnostics.append(
                {
                    "field": field_name,
                    "evidence_value": observed,
                    "current_value": expected,
                    "error": str(exc),
                }
            )
            continue
        if observed != expected:
            diagnostics.append(
                {
                    "field": field_name,
                    "evidence_value": observed,
                    "current_value": expected,
                    "error": "Analytical provenance does not match current replay.",
                }
            )

    if diagnostics:
        return ProvenanceAssessment(
            compatible=False,
            classification=ParityResultClassification.PROVENANCE_MISMATCH,
            diagnostics=tuple(diagnostics),
        )
    return ProvenanceAssessment(compatible=True, classification=None, diagnostics=())


def validate_history_contract_version(value: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(
            "history_contract_version must be a non-empty exact string"
        )
    return value


def validate_source_commit(value: str) -> str:
    """Validate a full Git object ID without inventing fallback provenance."""

    if not isinstance(value, str) or _GIT_COMMIT_RE.fullmatch(value) is None:
        raise ValueError("source_commit must be a full lowercase Git object ID")
    return value


def validate_pipeline_config_fingerprint(value: str) -> str:
    """Validate the SHA-256 analytical configuration fingerprint."""

    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError("pipeline_config_fingerprint must be lowercase SHA-256 hex")
    return value


def _run_git(root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ParityProvenanceError(
            "Unable to resolve trustworthy local Git provenance."
        ) from exc
    return completed.stdout.strip()


def _canonicalize(value: object) -> object:
    if isinstance(value, Enum):
        return {"__enum__": _type_name(value), "value": _canonicalize(value.value)}
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ParityProvenanceError(
                "Analytical configuration contains a non-finite float."
            )
        return value
    if isinstance(value, Path):
        return {"__path__": value.as_posix()}
    if is_dataclass(value) and not isinstance(value, type):
        payload: dict[str, object] = {}
        for field in fields(value):
            if field.name in _NON_ANALYTICAL_FIELD_NAMES:
                continue
            payload[field.name] = _canonicalize(getattr(value, field.name))
        return {"__dataclass__": _type_name(value), "fields": payload}
    if isinstance(value, Mapping):
        items = [
            (_canonicalize(key), _canonicalize(item))
            for key, item in value.items()
        ]
        items.sort(key=lambda pair: _canonical_json(pair[0]))
        return {"__mapping__": [[key, item] for key, item in items]}
    if isinstance(value, tuple):
        return {"__tuple__": [_canonicalize(item) for item in value]}
    if isinstance(value, (set, frozenset)):
        items = [_canonicalize(item) for item in value]
        items.sort(key=_canonical_json)
        return {"__set__": items}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return {"__sequence__": [_canonicalize(item) for item in value]}
    raise ParityProvenanceError(
        f"Unsupported analytical configuration value: {_type_name(value)}"
    )


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _type_name(value: object) -> str:
    value_type = type(value)
    return f"{value_type.__module__}.{value_type.__qualname__}"


def _provenance_mismatch(
    field: str,
    observed: object,
    current: object,
    error: str,
) -> ProvenanceAssessment:
    return ProvenanceAssessment(
        compatible=False,
        classification=ParityResultClassification.PROVENANCE_MISMATCH,
        diagnostics=(
            {
                "field": field,
                "evidence_value": observed,
                "current_value": current,
                "error": error,
            },
        ),
    )
