"""Internal capability gate for modern broker mutation."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar


class BrokerMutationAuthorityError(RuntimeError):
    """Raised when broker mutation is attempted outside its authority."""


_BROKER_MUTATION_AUTHORIZED: ContextVar[bool] = ContextVar(
    "broker_mutation_authorized",
    default=False,
)


@contextmanager
def _authorize_broker_mutation() -> Iterator[None]:
    """Temporarily authorize one internal modern broker-mutation call chain."""

    token = _BROKER_MUTATION_AUTHORIZED.set(True)
    try:
        yield
    finally:
        _BROKER_MUTATION_AUTHORIZED.reset(token)


def _require_broker_mutation_authority() -> None:
    """Fail closed unless the modern live engine opened the authority scope."""

    if not _BROKER_MUTATION_AUTHORIZED.get():
        raise BrokerMutationAuthorityError(
            "Broker mutation is restricted to the modern live execution "
            "authority."
        )
