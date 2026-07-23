from __future__ import annotations

import math

import pytest

import core.mt5_execution.orders as orders
from core.mt5_execution.models import OrderStatus


@pytest.mark.parametrize(
    ("retcode", "expected"),
    [
        (orders.mt5.TRADE_RETCODE_DONE, OrderStatus.FILLED),
        (
            getattr(orders.mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010),
            OrderStatus.PARTIALLY_FILLED,
        ),
        (
            getattr(orders.mt5, "TRADE_RETCODE_PLACED", 10008),
            OrderStatus.PENDING,
        ),
        (
            getattr(orders.mt5, "TRADE_RETCODE_CANCEL", 10007),
            OrderStatus.CANCELLED,
        ),
        (
            getattr(orders.mt5, "TRADE_RETCODE_INVALID_STOPS", 10016),
            OrderStatus.REJECTED,
        ),
        (
            getattr(orders.mt5, "TRADE_RETCODE_NO_MONEY", 10019),
            OrderStatus.REJECTED,
        ),
    ],
)
def test_trade_retcode_mapping(retcode: int, expected: OrderStatus) -> None:
    assert orders._map_trade_retcode(retcode) is expected


def test_unknown_retcode_is_rejected_and_named() -> None:
    assert orders._map_trade_retcode(999999) is OrderStatus.REJECTED
    assert orders._retcode_name(999999) == "UNKNOWN_RETCODE"


@pytest.mark.parametrize(
    "executed_volume",
    [0.01, 0.010000000000000002],
)
def test_filled_acknowledgement_accepts_exact_requested_volume(
    executed_volume: float,
) -> None:
    valid, message = orders._validate_execution_acknowledgement(
        status=OrderStatus.FILLED,
        requested_volume=0.01,
        executed_volume=executed_volume,
    )

    assert valid is True
    assert "valid" in message.lower()


@pytest.mark.parametrize(
    "executed_volume",
    [0.0, -0.01, 0.005, 0.02, math.nan, math.inf, -math.inf],
)
def test_filled_acknowledgement_rejects_invalid_volume(
    executed_volume: float,
) -> None:
    valid, message = orders._validate_execution_acknowledgement(
        status=OrderStatus.FILLED,
        requested_volume=0.01,
        executed_volume=executed_volume,
    )

    assert valid is False
    assert message


def test_partial_acknowledgement_accepts_positive_subrequest_volume() -> None:
    valid, message = orders._validate_execution_acknowledgement(
        status=OrderStatus.PARTIALLY_FILLED,
        requested_volume=0.01,
        executed_volume=0.005,
    )

    assert valid is True
    assert "valid" in message.lower()


@pytest.mark.parametrize(
    "executed_volume",
    [0.0, -0.01, 0.01, 0.02, math.nan, math.inf, -math.inf],
)
def test_partial_acknowledgement_rejects_invalid_volume(
    executed_volume: float,
) -> None:
    valid, message = orders._validate_execution_acknowledgement(
        status=OrderStatus.PARTIALLY_FILLED,
        requested_volume=0.01,
        executed_volume=executed_volume,
    )

    assert valid is False
    assert message


def test_non_execution_status_does_not_require_volume_acknowledgement() -> None:
    valid, message = orders._validate_execution_acknowledgement(
        status=OrderStatus.PENDING,
        requested_volume=0.01,
        executed_volume=0.0,
    )

    assert valid is True
    assert "not required" in message.lower()
