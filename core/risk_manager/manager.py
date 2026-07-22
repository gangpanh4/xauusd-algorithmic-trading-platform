"""
Risk-management orchestration.

This module converts an accepted trading signal into a broker-independent
``TradePlan``. Invalid pricing, sizing, or monetary-risk inputs fail closed and
produce an explicit rejected plan rather than an executable minimum-lot trade.
"""

from __future__ import annotations

from datetime import UTC, datetime
import math

from core.signal_generator.models import SignalType, TradingSignal

from .config import LotSizingMode, RiskManagerConfig
from .models import RiskDecision, TradePlan
from .position_sizer import PositionSizer
from .rules import RiskContext, RiskPolicy
from .state import RiskManagerState


class RiskManager:
    """Evaluate trading signals and produce fully defined trade plans."""

    def __init__(self, config: RiskManagerConfig) -> None:
        self.config = config
        self.policy = RiskPolicy(self.config)
        self.state = RiskManagerState()

    def evaluate_signal(
        self,
        signal: TradingSignal,
        *,
        entry_price: float,
        account_balance: float,
        stop_loss_distance: float,
        pip_value: float,
        volatility_stop_distance: float | None = None,
        structural_stop_price: float | None = None,
        safety_buffer_distance: float = 0.0,
        probability: float | None = None,
        confidence: float | None = None,
        feature_count: int | None = None,
        evidence_count: int | None = None,
        regime: str | None = None,
        tick_size: float = 1.0,
        lot_step: float = PositionSizer.LOT_STEP,
    ) -> TradePlan:
        """Convert a trading signal into a broker-independent ``TradePlan``.

        ``pip_value`` is retained for backward compatibility. It must represent
        the account-currency value of one ``tick_size`` movement for one lot.
        Production callers should pass the instrument's actual tick size,
        tick value, and broker volume step.

        Stop loss and take profit are stored as absolute prices. Any invalid
        economic input causes a rejected zero-size plan.
        """

        fallback_timestamp = datetime.now(UTC)
        try:
            timestamp = self._resolve_decision_timestamp(signal)
        except (TypeError, ValueError) as exc:
            return self._finalize_plan(
                self._build_non_executable_plan(
                    timestamp=fallback_timestamp,
                    signal=signal,
                    decision=RiskDecision.REJECT,
                    reason=f"Risk calculation rejected: {exc}",
                    probability=probability,
                    confidence=confidence,
                    feature_count=feature_count,
                    evidence_count=evidence_count,
                    regime=regime,
                )
            )

        direction = getattr(
            signal,
            "direction",
            getattr(signal, "signal", SignalType.HOLD),
        )

        if direction == SignalType.HOLD:
            return self._finalize_plan(
                self._build_non_executable_plan(
                    timestamp=timestamp,
                    signal=signal,
                    decision=RiskDecision.SKIP,
                    reason="No trading opportunity.",
                    probability=probability,
                    confidence=confidence,
                    feature_count=feature_count,
                    evidence_count=evidence_count,
                    regime=regime,
                )
            )

        if direction not in (SignalType.BUY, SignalType.SELL):
            return self._finalize_plan(
                self._build_non_executable_plan(
                    timestamp=timestamp,
                    signal=signal,
                    decision=RiskDecision.REJECT,
                    reason="Unsupported trading direction.",
                    probability=probability,
                    confidence=confidence,
                    feature_count=feature_count,
                    evidence_count=evidence_count,
                    regime=regime,
                )
            )

        try:
            working_balance = self._resolve_working_balance(
                account_balance,
                timestamp=timestamp,
            )
            self._synchronize_state_for_decision(
                account_balance=account_balance,
                working_balance=working_balance,
                timestamp=timestamp,
            )
            self._validate_trade_inputs(
                entry_price=entry_price,
                stop_loss_distance=stop_loss_distance,
                pip_value=pip_value,
                tick_size=tick_size,
                lot_step=lot_step,
            )
            effective_stop_distance, stop_components = (
                self._resolve_stop_loss_distance(
                    direction=direction,
                    entry_price=entry_price,
                    minimum_stop_distance=stop_loss_distance,
                    volatility_stop_distance=volatility_stop_distance,
                    structural_stop_price=structural_stop_price,
                    safety_buffer_distance=safety_buffer_distance,
                    tick_size=tick_size,
                )
            )

            position_size = self._calculate_position_size(
                working_balance=working_balance,
                stop_loss_distance=effective_stop_distance,
                pip_value=pip_value,
                tick_size=tick_size,
                lot_step=lot_step,
            )

            risk_reward_ratio = self._validate_risk_reward_ratio(
                self.config.minimum_risk_reward_ratio
            )

            actual_risk_amount = self._calculate_monetary_risk(
                position_size=position_size,
                stop_loss_distance=effective_stop_distance,
                pip_value=pip_value,
                tick_size=tick_size,
            )
            actual_risk_fraction = actual_risk_amount / working_balance

            self._validate_actual_risk(actual_risk_fraction)

            risk_context = self._build_risk_context(
                proposed_risk_fraction=actual_risk_fraction,
            )
            approved, reason = self.policy.approve_trade(
                position_size=position_size,
                risk_reward_ratio=risk_reward_ratio,
                context=risk_context,
            )

            if not approved:
                return self._finalize_plan(
                    self._build_non_executable_plan(
                        timestamp=timestamp,
                        signal=signal,
                        decision=RiskDecision.REJECT,
                        reason=reason,
                        probability=probability,
                        confidence=confidence,
                        feature_count=feature_count,
                        evidence_count=evidence_count,
                        regime=regime,
                    )
                )

            stop_loss, take_profit = self._calculate_exit_prices(
                direction=direction,
                entry_price=entry_price,
                stop_loss_distance=effective_stop_distance,
                risk_reward_ratio=risk_reward_ratio,
            )

            risk_percent = actual_risk_fraction * 100.0
            reward_percent = risk_percent * risk_reward_ratio

            trade_plan = TradePlan(
                timestamp=timestamp,
                signal=signal,
                decision=RiskDecision.APPROVE,
                entry_price=entry_price,
                position_size=position_size,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_percent=risk_percent,
                reward_percent=reward_percent,
                risk_reward_ratio=risk_reward_ratio,
                reason=reason,
                metadata={
                    "lot_sizing_mode": self.config.lot_sizing_mode.value,
                    "working_balance": working_balance,
                    "monetary_risk": actual_risk_amount,
                    "tick_size": tick_size,
                    "tick_value_per_lot": pip_value,
                    "lot_step": lot_step,
                    "requested_stop_distance": stop_loss_distance,
                    "effective_stop_distance": effective_stop_distance,
                    "volatility_stop_distance": (
                        volatility_stop_distance
                    ),
                    "structural_stop_price": structural_stop_price,
                    "safety_buffer_distance": safety_buffer_distance,
                    "stop_distance_components": stop_components,
                    "daily_start_balance": self.state.daily_start_balance,
                    "daily_drawdown": self.state.daily_drawdown,
                    "daily_drawdown_fraction": (
                        self.state.daily_drawdown_fraction
                    ),
                    "open_position_count": self.state.open_position_count,
                    "emergency_stop": self.state.emergency_stop,
                    "daily_loss_limit_hit": (
                        self.state.daily_loss_limit_hit
                    ),
                },
                probability=probability,
                confidence=confidence,
                feature_count=feature_count,
                evidence_count=evidence_count,
                regime=regime,
            )

            return self._finalize_plan(trade_plan)

        except (ArithmeticError, RuntimeError, TypeError, ValueError) as exc:
            return self._finalize_plan(
                self._build_non_executable_plan(
                    timestamp=timestamp,
                    signal=signal,
                    decision=RiskDecision.REJECT,
                    reason=f"Risk calculation rejected: {exc}",
                    probability=probability,
                    confidence=confidence,
                    feature_count=feature_count,
                    evidence_count=evidence_count,
                    regime=regime,
                )
            )

    def synchronize_account_balance(
        self,
        balance: float,
        *,
        timestamp: datetime | None = None,
    ) -> None:
        """Synchronize the authoritative account balance used by risk controls."""

        self.state.synchronize_account_balance(
            balance,
            timestamp=timestamp,
        )
        self._refresh_daily_loss_limit()

    def register_completed_trade(
        self,
        pnl: float,
        *,
        timestamp: datetime | None = None,
        balance_after: float | None = None,
    ) -> None:
        """Register one realized net trade result with the risk state."""

        self.state.register_trade(
            pnl,
            timestamp=timestamp,
            balance_after=balance_after,
        )
        self._refresh_daily_loss_limit()

    def set_open_position_count(self, count: int) -> None:
        """Synchronize current account exposure without assuming execution."""

        self.state.set_open_position_count(count)

    def register_position_opened(self, count: int = 1) -> None:
        """Register positions only after confirmed broker/simulator execution."""

        self.state.register_position_opened(count)

    def register_position_closed(self, count: int = 1) -> None:
        """Register positions only after confirmed broker/simulator closure."""

        self.state.register_position_closed(count)

    def set_emergency_stop(self, active: bool = True) -> None:
        """Activate or clear the fail-closed emergency stop."""

        self.state.set_emergency_stop(active)

    def _calculate_position_size(
        self,
        *,
        working_balance: float,
        stop_loss_distance: float,
        pip_value: float,
        tick_size: float,
        lot_step: float,
    ) -> float:
        common_limits = {
            "minimum_lot": self.config.minimum_position_size,
            "maximum_lot": self.config.maximum_position_size,
            "lot_step": lot_step,
        }

        if self.config.lot_sizing_mode == LotSizingMode.FIXED:
            return PositionSizer.calculate_fixed_lot(
                self.config.fixed_lot_size,
                **common_limits,
            )

        if self.config.lot_sizing_mode == LotSizingMode.DYNAMIC:
            return PositionSizer.calculate_dynamic_lot(
                working_balance,
                base_balance=100.0,
                base_lot=self.config.fixed_lot_size,
                **common_limits,
            )

        if self.config.lot_sizing_mode == LotSizingMode.RISK_PERCENT:
            risk_fraction = self.config.risk_percent / 100.0
            self._validate_configured_risk(risk_fraction)

            return PositionSizer.calculate_position_size(
                account_balance=working_balance,
                risk_percent=risk_fraction,
                stop_loss_distance=stop_loss_distance,
                pip_value=pip_value,
                tick_size=tick_size,
                **common_limits,
            )

        raise ValueError(
            f"Unsupported lot sizing mode: {self.config.lot_sizing_mode!r}"
        )

    def _resolve_working_balance(
        self,
        account_balance: float,
        *,
        timestamp: datetime,
    ) -> float:
        self._require_positive_finite(account_balance, "account_balance")

        if not self.config.use_virtual_balance:
            return float(account_balance)

        self._require_positive_finite(
            self.config.virtual_balance,
            "virtual_balance",
        )

        if self.config.dynamic_virtual_balance and self.state.initialized:
            self.state.ensure_daily_session(timestamp=timestamp)
            self._require_positive_finite(
                self.state.virtual_balance,
                "state.virtual_balance",
            )
            return float(self.state.virtual_balance)

        return float(self.config.virtual_balance)

    def _synchronize_state_for_decision(
        self,
        *,
        account_balance: float,
        working_balance: float,
        timestamp: datetime,
    ) -> None:
        if self.config.use_virtual_balance:
            if not self.state.initialized:
                self.state.initialize_account(
                    working_balance,
                    timestamp=timestamp,
                )
            else:
                self.state.ensure_daily_session(timestamp=timestamp)
        else:
            self.state.synchronize_account_balance(
                account_balance,
                timestamp=timestamp,
            )

        self._refresh_daily_loss_limit()

    def _refresh_daily_loss_limit(self) -> None:
        if not self.state.initialized:
            return

        if self.config.stop_after_daily_loss:
            self.state.refresh_daily_loss_limit(
                self.config.max_daily_loss,
            )
        else:
            self.state.daily_loss_limit_hit = False

    def _build_risk_context(
        self,
        *,
        proposed_risk_fraction: float,
    ) -> RiskContext:
        if not self.state.initialized:
            raise RuntimeError(
                "risk state must be initialized before policy evaluation"
            )

        return RiskContext(
            account_balance=self.state.virtual_balance,
            daily_start_balance=self.state.daily_start_balance,
            daily_loss=self.state.daily_drawdown,
            open_position_count=self.state.open_position_count,
            proposed_risk_fraction=proposed_risk_fraction,
            emergency_stop=self.state.emergency_stop,
            daily_loss_limit_hit=self.state.daily_loss_limit_hit,
        )

    @classmethod
    def _resolve_stop_loss_distance(
        cls,
        *,
        direction: SignalType,
        entry_price: float,
        minimum_stop_distance: float,
        volatility_stop_distance: float | None,
        structural_stop_price: float | None,
        safety_buffer_distance: float,
        tick_size: float,
    ) -> tuple[float, dict[str, float | None]]:
        """Resolve a deterministic adaptive stop distance.

        ``minimum_stop_distance`` remains the backward-compatible floor.
        Optional volatility and structure evidence may widen the stop, never
        narrow it. The safety buffer is then added once and the result is
        rounded upward to the instrument tick size.
        """

        cls._require_positive_finite(
            minimum_stop_distance,
            "minimum_stop_distance",
        )
        cls._require_positive_finite(tick_size, "tick_size")
        cls._require_non_negative_finite(
            safety_buffer_distance,
            "safety_buffer_distance",
        )

        candidates = [float(minimum_stop_distance)]

        if volatility_stop_distance is not None:
            cls._require_positive_finite(
                volatility_stop_distance,
                "volatility_stop_distance",
            )
            candidates.append(float(volatility_stop_distance))

        structural_distance: float | None = None
        if structural_stop_price is not None:
            cls._require_positive_finite(
                structural_stop_price,
                "structural_stop_price",
            )

            if direction == SignalType.BUY:
                structural_distance = entry_price - structural_stop_price
            elif direction == SignalType.SELL:
                structural_distance = structural_stop_price - entry_price
            else:
                raise ValueError("adaptive stop requires BUY or SELL")

            if structural_distance <= 0.0:
                raise ValueError(
                    "structural stop must be beyond entry in the loss "
                    "direction"
                )
            candidates.append(structural_distance)

        unrounded_distance = max(candidates) + safety_buffer_distance
        effective_distance = cls._round_distance_up(
            unrounded_distance,
            tick_size=tick_size,
        )

        return effective_distance, {
            "minimum": float(minimum_stop_distance),
            "volatility": (
                float(volatility_stop_distance)
                if volatility_stop_distance is not None
                else None
            ),
            "structure": structural_distance,
            "buffer": float(safety_buffer_distance),
            "unrounded": unrounded_distance,
            "effective": effective_distance,
        }

    @classmethod
    def _round_distance_up(
        cls,
        distance: float,
        *,
        tick_size: float,
    ) -> float:
        cls._require_positive_finite(distance, "stop distance")
        cls._require_positive_finite(tick_size, "tick_size")
        ticks = math.ceil((distance / tick_size) - 1e-12)
        rounded = ticks * tick_size
        cls._require_positive_finite(rounded, "rounded stop distance")
        return float(rounded)

    def _validate_trade_inputs(
        self,
        *,
        entry_price: float,
        stop_loss_distance: float,
        pip_value: float,
        tick_size: float,
        lot_step: float,
    ) -> None:
        self._require_positive_finite(entry_price, "entry_price")
        self._require_positive_finite(
            stop_loss_distance,
            "stop_loss_distance",
        )
        self._require_positive_finite(pip_value, "pip_value")
        self._require_positive_finite(tick_size, "tick_size")
        self._require_positive_finite(lot_step, "lot_step")

    def _validate_configured_risk(self, risk_fraction: float) -> None:
        self._require_positive_finite(risk_fraction, "configured risk")
        self._require_positive_finite(
            self.config.max_risk_per_trade,
            "max_risk_per_trade",
        )

        if risk_fraction > 1.0:
            raise ValueError("configured risk cannot exceed 100%")

        if risk_fraction > self.config.max_risk_per_trade:
            raise ValueError(
                "configured risk exceeds max_risk_per_trade"
            )

    def _validate_actual_risk(self, risk_fraction: float) -> None:
        self._require_positive_finite(risk_fraction, "actual risk")
        self._require_positive_finite(
            self.config.max_risk_per_trade,
            "max_risk_per_trade",
        )

        if risk_fraction > self.config.max_risk_per_trade:
            raise ValueError(
                "actual monetary risk exceeds max_risk_per_trade"
            )

    @classmethod
    def _calculate_monetary_risk(
        cls,
        *,
        position_size: float,
        stop_loss_distance: float,
        pip_value: float,
        tick_size: float,
    ) -> float:
        ticks_to_stop = stop_loss_distance / tick_size
        monetary_risk = ticks_to_stop * pip_value * position_size
        cls._require_positive_finite(monetary_risk, "monetary_risk")
        return monetary_risk

    @classmethod
    def _validate_risk_reward_ratio(cls, value: float) -> float:
        cls._require_positive_finite(value, "risk_reward_ratio")
        return float(value)

    @staticmethod
    def _calculate_exit_prices(
        *,
        direction: SignalType,
        entry_price: float,
        stop_loss_distance: float,
        risk_reward_ratio: float,
    ) -> tuple[float, float]:
        if direction == SignalType.BUY:
            return (
                entry_price - stop_loss_distance,
                entry_price + (stop_loss_distance * risk_reward_ratio),
            )

        return (
            entry_price + stop_loss_distance,
            entry_price - (stop_loss_distance * risk_reward_ratio),
        )

    @staticmethod
    def _resolve_decision_timestamp(signal: TradingSignal) -> datetime:
        timestamp = getattr(signal, "timestamp", None)
        if not isinstance(timestamp, datetime):
            return datetime.now(UTC)

        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("signal timestamp must be timezone-aware")

        return timestamp.astimezone(UTC)

    @staticmethod
    def _require_non_negative_finite(value: float, name: str) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a real number")

        if not math.isfinite(float(value)) or value < 0:
            raise ValueError(
                f"{name} must be finite and greater than or equal to zero"
            )

    @staticmethod
    def _require_positive_finite(value: float, name: str) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a real number")

        if not math.isfinite(float(value)) or value <= 0:
            raise ValueError(f"{name} must be finite and greater than zero")

    @staticmethod
    def _build_non_executable_plan(
        *,
        timestamp: datetime,
        signal: TradingSignal,
        decision: RiskDecision,
        reason: str,
        probability: float | None,
        confidence: float | None,
        feature_count: int | None,
        evidence_count: int | None,
        regime: str | None,
    ) -> TradePlan:
        return TradePlan(
            timestamp=timestamp,
            signal=signal,
            decision=decision,
            entry_price=0.0,
            position_size=0.0,
            stop_loss=0.0,
            take_profit=0.0,
            risk_percent=0.0,
            reward_percent=0.0,
            risk_reward_ratio=0.0,
            reason=reason,
            probability=probability,
            confidence=confidence,
            feature_count=feature_count,
            evidence_count=evidence_count,
            regime=regime,
        )

    def _finalize_plan(self, trade_plan: TradePlan) -> TradePlan:
        self._update_state(trade_plan)
        return trade_plan

    def _update_state(self, trade_plan: TradePlan) -> None:
        self.state.last_trade_plan = trade_plan
        self.state.last_decision_time = trade_plan.timestamp
        self.state.processed_signal_count += 1

        if trade_plan.decision == RiskDecision.APPROVE:
            self.state.approved_trade_count += 1
        elif trade_plan.decision == RiskDecision.REJECT:
            self.state.rejected_trade_count += 1
        elif trade_plan.decision == RiskDecision.SKIP:
            self.state.skipped_trade_count += 1
