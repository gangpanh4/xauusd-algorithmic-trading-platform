"""
Backtest export utilities.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import BacktestResult


class BacktestExporter:
    """
    Export backtesting results to disk.
    """

    def __init__(
        self,
        output_directory: str | Path = "output/backtests",
    ) -> None:

        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    def export_summary(
        self,
        result: BacktestResult,
    ) -> Path:
        """
        Export summary.json.
        """

        summary = {
            "total_trades": result.total_trades,
            "winning_trades": result.winning_trades,
            "losing_trades": result.losing_trades,
            "breakeven_trades": result.breakeven_trades,
            "win_rate": result.win_rate,
            "net_profit": result.net_profit,
            "gross_profit": result.gross_profit,
            "gross_loss": result.gross_loss,
            "profit_factor": result.profit_factor,
            "max_drawdown": result.max_drawdown,
        }

        path = self.output_directory / "summary.json"

        with path.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                summary,
                file,
                indent=4,
            )

        return path

    def export_trade_log(
        self,
        result: BacktestResult,
    ) -> Path:
        """
        Export trade_log.csv.
        """

        path = self.output_directory / "trade_log.csv"

        with path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as file:

            writer = csv.writer(file)

            writer.writerow(
                [
                    "Entry Time",
                    "Exit Time",
                    "Direction",
                    "Entry Price",
                    "Exit Price",
                    "Position Size",
                    "Spread Cost",
                    "Commission",
                    "Gross Profit",
                    "Net Profit",
                    "Holding Bars",
                    "Holding Time",
                    "Risk Reward",
                    "Outcome",
                    "Exit Reason",
                ]
            )

            for trade in result.trades:

                writer.writerow(
                    [
                        trade.entry_time,
                        trade.exit_time,
                        trade.direction,
                        trade.entry_price,
                        trade.exit_price,
                        trade.position_size,
                        trade.spread_cost,
                        trade.commission,
                        trade.gross_profit,
                        trade.net_profit,
                        trade.holding_bars,
                        str(trade.holding_time),
                        trade.risk_reward,
                        trade.outcome.name,
                        trade.exit_reason.name,
                    ]
                )

        return path

    def export_equity_curve(
        self,
        result: BacktestResult,
        initial_balance: float,
    ) -> Path:
        """
        Export equity_curve.csv.
        """

        path = self.output_directory / "equity_curve.csv"

        balance = initial_balance

        with path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as file:

            writer = csv.writer(file)

            writer.writerow(
                [
                    "Trade",
                    "Balance",
                ]
            )

            writer.writerow(
                [
                    0,
                    balance,
                ]
            )

            for index, trade in enumerate(
                result.trades,
                start=1,
            ):

                balance += trade.net_profit

                writer.writerow(
                    [
                        index,
                        balance,
                    ]
                )

        return path

    def export_statistics(
        self,
        statistics: dict,
    ) -> Path:
        """
        Export statistics.json.
        """

        path = self.output_directory / "statistics.json"

        with path.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                statistics,
                file,
                indent=4,
            )

        return path