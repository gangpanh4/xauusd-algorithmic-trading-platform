"""Durably retire incompatible active live-parity evidence."""

from __future__ import annotations

import ctypes
import json
import os
import tempfile
from ctypes import wintypes
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final

from . import parity_provenance
from .config import LiveTradingConfig
from .execution_concurrency import ExecutionConcurrencyError
from .parity_evidence import LiveParityEvidence, _parity_evidence_lifecycle_lock
from .parity_provenance import (
    PARITY_EVIDENCE_SCHEMA_VERSION,
    ParityAnalyticalProvenance,
)

_ACTIVE_PATH: Final = Path("runtime/live_parity_evidence.jsonl")
_ARCHIVE_ROOT: Final = Path("runtime/archive/live_parity_evidence")


class ParityEvidenceLifecycleError(RuntimeError):
    """Raised when parity evidence cannot be retired without data loss."""


@dataclass(frozen=True, slots=True)
class ParityEvidenceRetirementResult:
    """Durable retirement outcome for one active evidence artifact."""

    active_path: Path
    retired: bool
    evidence_count: int
    legacy_unversioned_count: int
    provenance_mismatch_count: int
    artifact_sha256: str | None
    archive_path: Path | None


def retire_incompatible_parity_evidence(
    *,
    config: LiveTradingConfig,
    active_path: Path = _ACTIVE_PATH,
    archive_root: Path = _ARCHIVE_ROOT,
) -> ParityEvidenceRetirementResult:
    """Archive and clear only known legacy/incompatible evidence."""

    path = Path(active_path)
    archive_directory = Path(archive_root)

    try:
        with _parity_evidence_lifecycle_lock(path).hold():
            if not os.path.lexists(path):
                return ParityEvidenceRetirementResult(
                    active_path=path,
                    retired=False,
                    evidence_count=0,
                    legacy_unversioned_count=0,
                    provenance_mismatch_count=0,
                    artifact_sha256=None,
                    archive_path=None,
                )
            if path.is_symlink() or not path.is_file():
                raise ParityEvidenceLifecycleError(
                    "Active parity evidence path is not a regular file."
                )

            exact_bytes = _read_exact_bytes(path)
            if not exact_bytes:
                return ParityEvidenceRetirementResult(
                    active_path=path,
                    retired=False,
                    evidence_count=0,
                    legacy_unversioned_count=0,
                    provenance_mismatch_count=0,
                    artifact_sha256=sha256(exact_bytes).hexdigest(),
                    archive_path=None,
                )

            evidence_count, legacy_count, provenance_mismatch_count = (
                _require_only_incompatible_rows(exact_bytes=exact_bytes, config=config)
            )
            if evidence_count == 0:
                raise ParityEvidenceLifecycleError(
                    "Non-empty active parity evidence contains no valid rows."
                )

            digest = sha256(exact_bytes).hexdigest()
            archive_path = _archive_exact_bytes_durably(
                archive_directory=archive_directory,
                digest=digest,
                exact_bytes=exact_bytes,
            )
            if _read_exact_bytes(path) != exact_bytes:
                raise ParityEvidenceLifecycleError(
                    "Active parity evidence changed before retirement."
                )
            _install_empty_active_durably(
                active_path=path,
                original_bytes=exact_bytes,
            )
    except ExecutionConcurrencyError as exc:
        raise ParityEvidenceLifecycleError(
            "Parity evidence lifecycle ownership is uncertain."
        ) from exc

    return ParityEvidenceRetirementResult(
        active_path=path,
        retired=True,
        evidence_count=evidence_count,
        legacy_unversioned_count=legacy_count,
        provenance_mismatch_count=provenance_mismatch_count,
        artifact_sha256=digest,
        archive_path=archive_path,
    )


def _require_only_incompatible_rows(
    *,
    exact_bytes: bytes,
    config: LiveTradingConfig,
) -> tuple[int, int, int]:
    try:
        text = exact_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParityEvidenceLifecycleError(
            "Active parity evidence is not valid UTF-8."
        ) from exc

    current: ParityAnalyticalProvenance | None = None
    evidence_count = 0
    legacy_count = 0
    provenance_mismatch_count = 0

    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ParityEvidenceLifecycleError(
                f"Parity evidence line {line_number} is malformed JSON."
            ) from exc
        if not isinstance(payload, dict):
            raise ParityEvidenceLifecycleError(
                f"Parity evidence line {line_number} is not a JSON object."
            )

        schema = payload.get("schema_version")
        if schema == 1:
            try:
                LiveParityEvidence.from_payload(payload)
            except (TypeError, ValueError) as exc:
                raise ParityEvidenceLifecycleError(
                    f"Legacy parity evidence line {line_number} is malformed."
                ) from exc
            evidence_count += 1
            legacy_count += 1
            continue

        if schema == 2:
            try:
                LiveParityEvidence.from_payload(payload)
            except (TypeError, ValueError) as exc:
                raise ParityEvidenceLifecycleError(
                    f"Schema-v2 parity evidence line {line_number} is malformed."
                ) from exc
            evidence_count += 1
            provenance_mismatch_count += 1
            continue

        if schema != PARITY_EVIDENCE_SCHEMA_VERSION:
            raise ParityEvidenceLifecycleError(
                f"Parity evidence line {line_number} has unknown schema."
            )
        try:
            LiveParityEvidence.from_payload(payload)
        except (TypeError, ValueError) as exc:
            raise ParityEvidenceLifecycleError(
                f"Schema-v{PARITY_EVIDENCE_SCHEMA_VERSION} parity evidence "
                f"line {line_number} is malformed."
            ) from exc

        if current is None:
            try:
                current = parity_provenance.current_parity_provenance(config.pipeline)
            except (RuntimeError, TypeError, ValueError) as exc:
                raise ParityEvidenceLifecycleError(
                    "Current analytical provenance cannot be trusted, so current "
                    "schema evidence cannot be retired."
                ) from exc

        assessment = parity_provenance.assess_payload_provenance(payload, current)
        if assessment.compatible:
            raise ParityEvidenceLifecycleError(
                "Current-compatible parity evidence is active and must not be "
                "retired automatically."
            )
        if assessment.classification is None:
            raise ParityEvidenceLifecycleError(
                "Parity evidence provenance classification is unavailable."
            )

        evidence_count += 1
        provenance_mismatch_count += 1

    return evidence_count, legacy_count, provenance_mismatch_count


def _archive_exact_bytes_durably(
    *,
    archive_directory: Path,
    digest: str,
    exact_bytes: bytes,
) -> Path:
    try:
        archive_directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ParityEvidenceLifecycleError(
            "Unable to create parity evidence archive directory."
        ) from exc

    archive_path = archive_directory / f"{digest}.jsonl"
    if os.path.lexists(archive_path):
        if archive_path.is_symlink() or not archive_path.is_file():
            raise ParityEvidenceLifecycleError(
                "Parity evidence archive collision is not a regular file."
            )
        if _read_exact_bytes(archive_path) != exact_bytes:
            raise ParityEvidenceLifecycleError(
                "Parity evidence archive collision contains different bytes."
            )
        try:
            _fsync_directory(archive_directory)
        except OSError as exc:
            raise ParityEvidenceLifecycleError(
                "Unable to durably confirm parity evidence archive."
            ) from exc
        return archive_path

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=archive_directory,
            prefix=f".{digest}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(exact_bytes)
            handle.flush()
            os.fsync(handle.fileno())

        try:
            os.link(temporary_path, archive_path)
        except FileExistsError:
            if (
                archive_path.is_symlink()
                or not archive_path.is_file()
                or _read_exact_bytes(archive_path) != exact_bytes
            ):
                raise ParityEvidenceLifecycleError(
                    "Parity evidence archive collision contains different bytes."
                )
        temporary_path.unlink()
        temporary_path = None
        _fsync_directory(archive_directory)
    except ParityEvidenceLifecycleError:
        raise
    except OSError as exc:
        raise ParityEvidenceLifecycleError(
            "Unable to durably archive parity evidence."
        ) from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

    return archive_path


def _install_empty_active_durably(
    *,
    active_path: Path,
    original_bytes: bytes,
) -> None:
    parent = active_path.parent
    empty_temp: Path | None = None
    rollback_temp: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=parent,
            prefix=f".{active_path.name}.empty.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            empty_temp = Path(handle.name)
            handle.write(b"")
            handle.flush()
            os.fsync(handle.fileno())

        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=parent,
            prefix=f".{active_path.name}.rollback.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            rollback_temp = Path(handle.name)
            handle.write(original_bytes)
            handle.flush()
            os.fsync(handle.fileno())

        _fsync_directory(parent)
        os.replace(empty_temp, active_path)
        empty_temp = None
        try:
            _fsync_directory(parent)
        except OSError as exc:
            try:
                if rollback_temp is None:
                    raise OSError("rollback artifact is unavailable")
                os.replace(rollback_temp, active_path)
                rollback_temp = None
                _fsync_directory(parent)
            except OSError as rollback_exc:
                raise ParityEvidenceLifecycleError(
                    "Active parity evidence replacement durability failed and "
                    "restoration could not be confirmed."
                ) from rollback_exc
            raise ParityEvidenceLifecycleError(
                "Active parity evidence replacement durability failed; the original "
                "artifact was restored."
            ) from exc
    except ParityEvidenceLifecycleError:
        raise
    except OSError as exc:
        raise ParityEvidenceLifecycleError(
            "Unable to install empty active parity evidence durably."
        ) from exc
    finally:
        for temporary_path in (empty_temp, rollback_temp):
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass


def _read_exact_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ParityEvidenceLifecycleError(
            f"Unable to read parity evidence artifact: {path}"
        ) from exc


def _fsync_directory(directory: Path) -> None:
    """Durably flush directory metadata on POSIX and Windows."""

    try:
        descriptor = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        if os.name != "nt":
            raise
    else:
        try:
            os.fsync(descriptor)
            return
        except OSError:
            if os.name != "nt":
                raise
        finally:
            os.close(descriptor)

    generic_read = 0x80000000
    generic_write = 0x40000000
    file_share_read = 0x00000001
    file_share_write = 0x00000002
    file_share_delete = 0x00000004
    open_existing = 3
    file_flag_backup_semantics = 0x02000000

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    flush_file_buffers = kernel32.FlushFileBuffers
    flush_file_buffers.argtypes = (wintypes.HANDLE,)
    flush_file_buffers.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL

    handle = create_file(
        str(directory),
        generic_read | generic_write,
        file_share_read | file_share_write | file_share_delete,
        None,
        open_existing,
        file_flag_backup_semantics,
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        error = ctypes.get_last_error()
        raise OSError(error, "Unable to open directory for durable fsync.")

    try:
        if not flush_file_buffers(handle):
            error = ctypes.get_last_error()
            raise OSError(error, "Unable to fsync directory metadata.")
    finally:
        close_handle(handle)


def main() -> int:
    config = LiveTradingConfig(
        live_execution_enabled=False,
        shadow_recording_enabled=False,
        parity_recording_enabled=False,
    )
    try:
        result = retire_incompatible_parity_evidence(config=config)
    except (ParityEvidenceLifecycleError, RuntimeError, TypeError, ValueError) as exc:
        print(f"Parity evidence preparation failed closed: {exc}")
        return 2

    print(
        json.dumps(
            {
                "active_path": str(result.active_path),
                "retired": result.retired,
                "evidence_count": result.evidence_count,
                "legacy_unversioned_count": result.legacy_unversioned_count,
                "provenance_mismatch_count": result.provenance_mismatch_count,
                "artifact_sha256": result.artifact_sha256,
                "archive_path": (
                    None if result.archive_path is None else str(result.archive_path)
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
