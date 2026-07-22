"""
Position-sizing calculations for the risk-management package.

The module is broker-independent. Callers must provide the monetary value of
one price tick for one lot and, when available, the symbol's tick size.
"""

from __future__ import annotations

from decimal import Decimal
import math


class PositionSizer:
    """Calculate risk-based, fixed, and balance-scaled position sizes."""

    MIN_LOT = 0.01
    MAX_LOT = 100.0
    LOT_STEP = 0.01

    @classmethod
    def calculate_position_size(
        cls,
        account_balance: float,
        risk_percent: float,
        stop_loss_distance: float,
        pip_value: float,
        *,
        tick_size: float = 1.0,
        minimum_lot: float = MIN_LOT,
        maximum_lot: float = MAX_LOT,
        lot_step: float = LOT_STEP,
    ) -> float:
        """Return a broker-valid risk-based lot size.

        Parameters
        ----------
        account_balance:
            Account balance in the account currency.
        risk_percent:
            Fraction of account balance at risk. For example, ``0.01`` means
            one percent. Values expressed as whole percentages are rejected to
            prevent accidental over-risking.
        stop_loss_distance:
            Absolute distance between the entry and stop-loss prices.
        pip_value:
            Monetary value of one ``tick_size`` price movement for one lot.
            The name is retained for backward compatibility with the existing
            risk-manager interface.
        tick_size:
            Minimum price increment used by the supplied ``pip_value``. The
            legacy default of ``1.0`` preserves current call-site behaviour;
            production callers should supply the broker symbol specification.
        minimum_lot, maximum_lot, lot_step:
            Broker volume constraints.

        Raises
        ------
        ValueError
            If an input is invalid or the calculated size is below the broker
            minimum. Returning a minimum lot in those cases could exceed the
            intended monetary risk, so invalid calculations fail closed.
        """

        cls._require_positive_finite(account_balance, "account_balance")
        cls._require_risk_fraction(risk_percent)
        cls._require_positive_finite(stop_loss_distance, "stop_loss_distance")
        cls._require_positive_finite(pip_value, "pip_value")
        cls._require_positive_finite(tick_size, "tick_size")
        cls._validate_broker_limits(
            minimum=minimum_lot,
            maximum=maximum_lot,
            step=lot_step,
        )

        risk_amount = account_balance * risk_percent
        ticks_to_stop = stop_loss_distance / tick_size
        loss_per_lot = ticks_to_stop * pip_value

        cls._require_positive_finite(risk_amount, "risk_amount")
        cls._require_positive_finite(loss_per_lot, "loss_per_lot")

        raw_lot = risk_amount / loss_per_lot

        if raw_lot < minimum_lot:
            raise ValueError(
                "Calculated position size is below the broker minimum; "
                "the trade must be rejected rather than rounded up."
            )

        return cls.apply_broker_limits(
            raw_lot,
            minimum=minimum_lot,
            maximum=maximum_lot,
            step=lot_step,
        )

    @classmethod
    def calculate_fixed_lot(
        cls,
        lot_size: float,
        *,
        minimum_lot: float = MIN_LOT,
        maximum_lot: float = MAX_LOT,
        lot_step: float = LOT_STEP,
    ) -> float:
        """Validate and normalize a configured fixed lot size."""

        cls._require_positive_finite(lot_size, "lot_size")
        cls._validate_broker_limits(
            minimum=minimum_lot,
            maximum=maximum_lot,
            step=lot_step,
        )

        if lot_size < minimum_lot:
            raise ValueError("lot_size is below the broker minimum")

        return cls.apply_broker_limits(
            lot_size,
            minimum=minimum_lot,
            maximum=maximum_lot,
            step=lot_step,
        )

    @classmethod
    def calculate_dynamic_lot(
        cls,
        balance: float,
        *,
        base_balance: float = 100.0,
        base_lot: float = 0.01,
        minimum_lot: float = MIN_LOT,
        maximum_lot: float = MAX_LOT,
        lot_step: float = LOT_STEP,
    ) -> float:
        """Scale a base lot linearly with balance and apply broker limits.

        This mode is not risk-based because stop distance is not part of the
        calculation. It should only be used when that limitation is explicit.
        """

        cls._require_positive_finite(balance, "balance")
        cls._require_positive_finite(base_balance, "base_balance")
        cls._require_positive_finite(base_lot, "base_lot")
        cls._validate_broker_limits(
            minimum=minimum_lot,
            maximum=maximum_lot,
            step=lot_step,
        )

        raw_lot = base_lot * (balance / base_balance)

        if raw_lot < minimum_lot:
            raise ValueError(
                "Calculated dynamic lot is below the broker minimum; "
                "the trade must be rejected rather than rounded up."
            )

        return cls.apply_broker_limits(
            raw_lot,
            minimum=minimum_lot,
            maximum=maximum_lot,
            step=lot_step,
        )

    @classmethod
    def apply_broker_limits(
        cls,
        lot: float,
        *,
        minimum: float,
        maximum: float,
        step: float,
    ) -> float:
        """Cap and floor a lot size to the broker's valid volume grid.

        Flooring is intentional: rounding upward can exceed the approved
        monetary risk. Values below the minimum are rejected instead of being
        increased to a riskier executable size.
        """

        cls._require_positive_finite(lot, "lot")
        cls._validate_broker_limits(
            minimum=minimum,
            maximum=maximum,
            step=step,
        )

        if lot < minimum:
            raise ValueError("lot is below the broker minimum")

        bounded_lot = min(lot, maximum)

        lot_decimal = Decimal(str(bounded_lot))
        minimum_decimal = Decimal(str(minimum))
        step_decimal = Decimal(str(step))

        step_count = (lot_decimal - minimum_decimal) // step_decimal
        normalized = minimum_decimal + (step_count * step_decimal)

        if normalized < minimum_decimal:
            raise ValueError("normalized lot is below the broker minimum")

        precision = max(
            cls._decimal_places(minimum_decimal),
            cls._decimal_places(step_decimal),
        )

        return round(float(normalized), precision)

    @staticmethod
    def _require_risk_fraction(risk_percent: float) -> None:
        PositionSizer._require_positive_finite(risk_percent, "risk_percent")

        if risk_percent > 1.0:
            raise ValueError(
                "risk_percent must be a fraction in the interval (0, 1]; "
                "use 0.01 for one percent"
            )

    @staticmethod
    def _require_positive_finite(value: float, name: str) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a real number")

        if not math.isfinite(float(value)) or value <= 0:
            raise ValueError(f"{name} must be finite and greater than zero")

    @classmethod
    def _validate_broker_limits(
        cls,
        *,
        minimum: float,
        maximum: float,
        step: float,
    ) -> None:
        cls._require_positive_finite(minimum, "minimum")
        cls._require_positive_finite(maximum, "maximum")
        cls._require_positive_finite(step, "step")

        if minimum > maximum:
            raise ValueError("minimum lot cannot exceed maximum lot")

    @staticmethod
    def _decimal_places(value: Decimal) -> int:
        return max(0, -value.as_tuple().exponent)
