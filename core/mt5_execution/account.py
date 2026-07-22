"""
MT5 Account information.
"""

from __future__ import annotations

import MetaTrader5 as mt5

from .models import AccountInfo


def get_account_info() -> AccountInfo:
    """
    Retrieve account information from MT5.
    """

    account = mt5.account_info()

    if account is None:
        raise RuntimeError(
            "Unable to retrieve MT5 account information."
        )

    return AccountInfo(
        login=account.login,
        server=account.server,
        balance=account.balance,
        equity=account.equity,
        margin=account.margin,
        free_margin=account.margin_free,
        leverage=account.leverage,
        currency=account.currency,
    )