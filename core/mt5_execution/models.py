"""
Core data models for the MT5 Execution Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class OrderSide(Enum):
    """Trading direction."""

    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    """Order execution status."""

    PENDING = "PENDING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"


@dataclass(frozen=True)
class OrderRequest:
    """Request to execute an order."""

    symbol: str
    side: OrderSide
    volume: float
    entry_price: float
    stop_loss: float
    take_profit: float
    comment: str = ""


@dataclass(frozen=True)
class OrderResult:
    """Result returned after execution."""

    timestamp: datetime
    status: OrderStatus
    ticket: int | None
    executed_price: float
    message: str
    retcode: int | None = None
    executed_volume: float = 0.0


@dataclass(frozen=True)
class AccountInfo:
    """MT5 trading account information."""

    login: int
    server: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    leverage: int
    currency: str
    trade_mode: int = -1


@dataclass(frozen=True)
class SymbolInfo:
    """MT5 symbol information."""

    name: str
    digits: int
    point: float
    spread: int
    volume_min: float
    volume_max: float
    volume_step: float
    trade_allowed: bool
    tick_size: float = 0.0
    minimum_stop_distance: float = 0.0
    filling_mode_flags: int = 0
    trade_execution_mode: int = -1


@dataclass(frozen=True)
class PositionInfo:
    """Open MT5 position."""

    ticket: int
    symbol: str
    side: OrderSide
    volume: float
    open_price: float
    stop_loss: float
    take_profit: float
    profit: float


@dataclass(frozen=True, slots=True)
class ActiveOrderInfo:
    """Authoritative active broker-order provenance."""

    ticket: int
    symbol: str
    side: OrderSide
    volume_initial: float
    volume_current: float
    price_open: float
    stop_loss: float
    take_profit: float
    magic_number: int
    comment: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class HistoricalOrderInfo:
    """Authoritative broker order-history provenance."""

    ticket: int
    symbol: str
    side: OrderSide
    volume_initial: float
    volume_current: float
    price_open: float
    stop_loss: float
    take_profit: float
    magic_number: int
    comment: str
    created_at: datetime
    completed_at: datetime
    state: int


@dataclass(frozen=True, slots=True)
class ExecutionDealInfo:
    """Authoritative opening or execution deal provenance."""

    ticket: int
    order_ticket: int
    position_id: int
    timestamp: datetime
    symbol: str
    side: OrderSide
    volume: float
    price: float
    entry: int
    magic_number: int
    comment: str
