"""
Signal Generator Gatekeeper.

Determines whether a trading signal is allowed
to proceed to signal generation.
"""

from __future__ import annotations

from .context import SignalContext


class SignalGatekeeper:
    """Apply upstream approval vetoes before signal generation."""

    def approve(
        self,
        context: SignalContext,
    ) -> bool:
        """
        Return whether the supplied opportunity may proceed.

        Optional upstream results preserve the legacy behaviour when absent.
        When a result is supplied, an explicit rejection from any upstream
        subsystem vetoes signal generation.
        """

        if (
            context.probability is not None
            and not context.probability.accepted
        ):
            return False

        if (
            context.trade_quality is not None
            and not context.trade_quality.approved
        ):
            return False

        if (
            context.confluence is not None
            and not context.confluence.approved
        ):
            return False

        if (
            context.decision is not None
            and not context.decision.approved
        ):
            return False

        return True
