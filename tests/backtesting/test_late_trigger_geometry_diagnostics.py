from __future__ import annotations

from types import SimpleNamespace

from core.backtesting.post_expiry_trigger_tracker import (
    PostExpiryTriggerTracker,
)
from core.strategies.enums import SetupDirection


def _reference(price: float):
    return SimpleNamespace(price=price)


def _strategy(minimum: float = 1.0):
    return SimpleNamespace(
        config=SimpleNamespace(
            minimum_target_reward_risk=minimum,
        )
    )


def test_geometry_diagnostic_reports_no_target_beyond_entry() -> None:
    setup = SimpleNamespace(
        direction=SetupDirection.BUY,
        stop_reference=_reference(95.0),
        target_references=(_reference(99.0),),
    )
    trigger = SimpleNamespace(trigger_price=100.0)

    code, reason = PostExpiryTriggerTracker._diagnose_geometry(
        strategy=_strategy(),
        setup=setup,
        trigger=trigger,
    )

    assert code == "NO_TARGET_BEYOND_ENTRY"
    assert "beyond" in reason.lower()


def test_geometry_diagnostic_reports_reward_risk_below_minimum() -> None:
    setup = SimpleNamespace(
        direction=SetupDirection.SELL,
        stop_reference=_reference(110.0),
        target_references=(_reference(95.0),),
    )
    trigger = SimpleNamespace(trigger_price=100.0)

    code, reason = PostExpiryTriggerTracker._diagnose_geometry(
        strategy=_strategy(minimum=1.0),
        setup=setup,
        trigger=trigger,
    )

    assert code == "REWARD_RISK_BELOW_MINIMUM"
    assert "0.500000" in reason
    assert "1.000000" in reason


def test_geometry_diagnostic_reports_zero_risk() -> None:
    setup = SimpleNamespace(
        direction=SetupDirection.BUY,
        stop_reference=_reference(100.0),
        target_references=(_reference(110.0),),
    )
    trigger = SimpleNamespace(trigger_price=100.0)

    code, reason = PostExpiryTriggerTracker._diagnose_geometry(
        strategy=_strategy(),
        setup=setup,
        trigger=trigger,
    )

    assert code == "ZERO_RISK_DISTANCE"
    assert "equals" in reason.lower()
