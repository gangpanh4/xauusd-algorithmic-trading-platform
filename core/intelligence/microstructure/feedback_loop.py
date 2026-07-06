from __future__ import annotations

from typing import List

from core.trading_pipeline.models import MarketBar
from core.intelligence.contracts.feedback_state import FeedbackState
from core.intelligence.contracts.enums import Timeframe
from core.intelligence.contracts.explanation import Explanation


class MicrostructureFeedbackEngine:
    """
    Sprint 4 — Microstructure Feedback Loop Engine

    PURPOSE:
        Learn from failed impulse → sweep → no follow-through sequences.

    KEY IDEA:
        Market inefficiencies repeat — but only if we detect failure patterns.
    """

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.failure_memory = 0.0  # lightweight adaptive memory

    # --------------------------------------------------
    # MAIN ENTRY
    # --------------------------------------------------
    def process(self, bars: List[MarketBar], micro_result: dict) -> FeedbackState:

        failed_sweeps = self._detect_failed_sweeps(bars, micro_result)
        weak_impulses = self._detect_weak_impulses(micro_result)

        failure_score = self._compute_failure_score(failed_sweeps, weak_impulses)

        self._update_memory(failure_score)

        adjusted_confidence = self._adjust_confidence(failure_score)

        explanations = self._build_explanations(
            failed_sweeps,
            weak_impulses,
            failure_score,
        )

        return FeedbackState(
            timestamp=bars[-1].timestamp,
            symbol=self.symbol,
            timeframe=Timeframe.M5,
            engine_version="MicrostructureFeedbackEngine-1.0.0",
            failed_sweeps=failed_sweeps,
            weak_impulses=weak_impulses,
            failure_score=failure_score,
            adjusted_confidence=adjusted_confidence,
            memory=self.failure_memory,
            explanations=tuple(explanations),
            metadata={
                "mode": "adaptive_microstructure_learning",
            },
        )

    # --------------------------------------------------
    # FAILURE DETECTION
    # --------------------------------------------------
    def _detect_failed_sweeps(self, bars, micro) -> int:
        if micro.impulse_probability < 0.4:
            return micro.sweeps
        return 0

    def _detect_weak_impulses(self, micro) -> int:
        return max(0, 3 - micro.impulses)

    # --------------------------------------------------
    # FAILURE SCORE MODEL
    # --------------------------------------------------
    def _compute_failure_score(self, sweeps, weak) -> float:
        return min(1.0, (sweeps * 0.5 + weak * 0.5) / 5.0)

    # --------------------------------------------------
    # ADAPTIVE MEMORY UPDATE
    # --------------------------------------------------
    def _update_memory(self, score: float):

        # exponential smoothing memory
        self.failure_memory = (
            self.failure_memory * 0.8 +
            score * 0.2
        )

    # --------------------------------------------------
    # CONFIDENCE ADJUSTMENT
    # --------------------------------------------------
    def _adjust_confidence(self, score: float) -> float:

        return max(0.0, 1.0 - score)

    # --------------------------------------------------
    # EXPLANATIONS
    # --------------------------------------------------
    def _build_explanations(self, failed, weak, score):

        return [
            Explanation(
                source="MICROSTRUCTURE_FEEDBACK",
                timeframe=Timeframe.M5,
                rule="FAILURE_SCORE",
                category="ADAPTIVE",
                message=f"Failure score: {score:.3f}",
                confidence=0.9,
                metadata={},
            ),
            Explanation(
                source="MICROSTRUCTURE_FEEDBACK",
                timeframe=Timeframe.M5,
                rule="MEMORY",
                category="ADAPTIVE",
                message=f"Failure memory: {self.failure_memory:.3f}",
                confidence=0.9,
                metadata={},
            ),
        ]