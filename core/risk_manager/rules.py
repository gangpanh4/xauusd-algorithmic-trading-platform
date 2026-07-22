"""Risk-approval policies for the Risk Management package.

The policy performs deterministic, broker-independent validation of a proposed
trade. Trade-level checks remain backward compatible with the original
``approve_trade`` call. Account and portfolio controls are evaluated whenever a
:class:`RiskContext` is supplied by the orchestration layer.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from .config import RiskManagerConfig


@dataclass(frozen=True, slots=True)
class RiskContext:
    """Runtime account state required for account-level risk decisions.

    Monetary losses are represented as positive account-currency amounts.
    Fractions use decimal form: ``0.01`` means one percent.
    """

    account_balance: float | None = None
    daily_start_balance: float | None = None
    daily_loss: float = 0.0
    open_position_count: int = 0
    proposed_risk_fraction: float | None = None
    emergency_stop: bool = False
    daily_loss_limit_hit: bool = False


class RiskPolicy:
    """Evaluate trade, account, and portfolio risk invariants."""

    def __init__(self, config: RiskManagerConfig) -> None:
        self.config = config
        self._validate_config()

    def approve_trade(
        self,
        *,
        position_size: float,
        risk_reward_ratio: float,
        context: RiskContext | None = None,
    ) -> tuple[bool, str]:
        """Return whether a proposed trade satisfies every available rule.

        ``context`` is optional for backward compatibility. Without it, only
        trade-level checks can be evaluated. Supplying a context activates the
        emergency-stop, daily-loss, open-position, and proposed-risk checks.
        """

        violation = self._validate_trade_level_rules(
            position_size=position_size,
            risk_reward_ratio=risk_reward_ratio,
        )
        if violation is not None:
            return False, violation

        if context is not None:
            violation = self._validate_account_rules(context)
            if violation is not None:
                return False, violation

        return True, "Trade approved."

    def _validate_trade_level_rules(
        self,
        *,
        position_size: float,
        risk_reward_ratio: float,
    ) -> str | None:
        self._require_finite(position_size, "position_size")
        self._require_finite(risk_reward_ratio, "risk_reward_ratio")

        if position_size <= 0:
            return "Position size must be greater than zero."

        if position_size < self.config.minimum_position_size:
            return "Position size below minimum."

        if position_size > self.config.maximum_position_size:
            return "Position size above maximum."

        if risk_reward_ratio <= 0:
            return "Risk/Reward ratio must be greater than zero."

        if risk_reward_ratio < self.config.minimum_risk_reward_ratio:
            return "Risk/Reward ratio too low."

        return None

    def _validate_account_rules(self, context: RiskContext) -> str | None:
        if not isinstance(context, RiskContext):
            raise TypeError("context must be a RiskContext instance")

        self._validate_context_values(context)

        if context.emergency_stop:
            return "Emergency stop is active."

        if (
            self.config.emergency_stop_balance > 0
            and context.account_balance is None
        ):
            return "Account balance is required for emergency-stop validation."

        if (
            context.account_balance is not None
            and self.config.emergency_stop_balance > 0
            and context.account_balance <= self.config.emergency_stop_balance
        ):
            return "Account balance is at or below the emergency stop balance."

        if (
            not self.config.allow_multiple_positions
            and context.open_position_count > 0
        ):
            return "Multiple positions are disabled."

        if context.open_position_count >= self.config.maximum_open_positions:
            return "Maximum open positions reached."

        if context.proposed_risk_fraction is not None:
            if context.proposed_risk_fraction <= 0:
                return "Proposed risk must be greater than zero."

            if context.proposed_risk_fraction > self.config.max_risk_per_trade:
                return "Proposed risk exceeds maximum risk per trade."

        if self.config.stop_after_daily_loss:
            if context.daily_loss_limit_hit:
                return "Daily loss limit has already been reached."

            if context.daily_loss > 0:
                if context.daily_start_balance is None:
                    return "Daily start balance is required for daily-loss validation."

                daily_loss_fraction = (
                    context.daily_loss / context.daily_start_balance
                )
                if daily_loss_fraction >= self.config.max_daily_loss:
                    return "Daily loss limit reached."

        return None

    def _validate_context_values(self, context: RiskContext) -> None:
        if context.account_balance is not None:
            self._require_positive_finite(
                context.account_balance,
                "account_balance",
            )

        if context.daily_start_balance is not None:
            self._require_positive_finite(
                context.daily_start_balance,
                "daily_start_balance",
            )

        self._require_non_negative_finite(context.daily_loss, "daily_loss")

        if (
            isinstance(context.open_position_count, bool)
            or not isinstance(context.open_position_count, int)
        ):
            raise TypeError("open_position_count must be an integer")

        if context.open_position_count < 0:
            raise ValueError("open_position_count cannot be negative")

        if context.proposed_risk_fraction is not None:
            self._require_finite(
                context.proposed_risk_fraction,
                "proposed_risk_fraction",
            )

    def _validate_config(self) -> None:
        self._require_positive_finite(
            self.config.minimum_position_size,
            "minimum_position_size",
        )
        self._require_positive_finite(
            self.config.maximum_position_size,
            "maximum_position_size",
        )
        if self.config.maximum_position_size < self.config.minimum_position_size:
            raise ValueError(
                "maximum_position_size cannot be below minimum_position_size"
            )

        self._require_positive_finite(
            self.config.minimum_risk_reward_ratio,
            "minimum_risk_reward_ratio",
        )
        self._require_fraction(
            self.config.max_risk_per_trade,
            "max_risk_per_trade",
            allow_zero=False,
        )
        self._require_fraction(
            self.config.max_daily_loss,
            "max_daily_loss",
            allow_zero=not self.config.stop_after_daily_loss,
        )

        if (
            isinstance(self.config.maximum_open_positions, bool)
            or not isinstance(self.config.maximum_open_positions, int)
        ):
            raise TypeError("maximum_open_positions must be an integer")

        if self.config.maximum_open_positions < 1:
            raise ValueError("maximum_open_positions must be at least one")

        self._require_non_negative_finite(
            self.config.emergency_stop_balance,
            "emergency_stop_balance",
        )

    @classmethod
    def _require_fraction(
        cls,
        value: float,
        name: str,
        *,
        allow_zero: bool,
    ) -> None:
        cls._require_finite(value, name)

        if value < 0 or (not allow_zero and value == 0):
            qualifier = "zero or greater" if allow_zero else "greater than zero"
            raise ValueError(f"{name} must be {qualifier}")

        if value > 1.0:
            raise ValueError(f"{name} cannot exceed 1.0")

    @classmethod
    def _require_positive_finite(cls, value: float, name: str) -> None:
        cls._require_finite(value, name)
        if value <= 0:
            raise ValueError(f"{name} must be greater than zero")

    @classmethod
    def _require_non_negative_finite(cls, value: float, name: str) -> None:
        cls._require_finite(value, name)
        if value < 0:
            raise ValueError(f"{name} cannot be negative")

    @staticmethod
    def _require_finite(value: float, name: str) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a real number")

        if not math.isfinite(float(value)):
            raise ValueError(f"{name} must be finite")
