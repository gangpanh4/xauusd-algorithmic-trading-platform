"""
Tests for the Probability Engine.

These tests verify baseline correctness of the
Probability Engine before research-driven
improvements are introduced.
"""

from core.feature_engineering.models import FeatureVector
from core.probability_engine.engine import ProbabilityEngine
from core.probability_engine.models import ProbabilityResult


def test_process_returns_probability_result() -> None:
    """
    process() should always return a ProbabilityResult.
    """

    engine = ProbabilityEngine()

    features = FeatureVector()

    result = engine.process(features)

    assert isinstance(result, ProbabilityResult)


def test_probability_is_bounded() -> None:
    """
    Probability should remain inside [0, 1].
    """

    engine = ProbabilityEngine()

    result = engine.process(FeatureVector())

    assert 0.0 <= result.probability <= 1.0


def test_confidence_is_bounded() -> None:
    """
    Confidence should remain inside [0, 1].
    """

    engine = ProbabilityEngine()

    result = engine.process(FeatureVector())

    assert 0.0 <= result.confidence <= 1.0


def test_evidence_is_generated() -> None:
    """
    Every evaluation should generate evidence.
    """

    engine = ProbabilityEngine()

    result = engine.process(FeatureVector())

    assert result.evidence
    assert len(result.evidence) == len(engine.evaluators)


def test_feature_vector_is_preserved() -> None:
    """
    Returned ProbabilityResult should preserve
    the original FeatureVector.
    """

    engine = ProbabilityEngine()

    features = FeatureVector()

    result = engine.process(features)

    assert result.feature_vector is features


def test_latest_result_is_updated() -> None:
    """
    Engine state should reference the latest result.
    """

    engine = ProbabilityEngine()

    result = engine.process(FeatureVector())

    assert engine.state.latest_result is result


def test_processed_count_increments() -> None:
    """
    Processing should increment the internal counter.
    """

    engine = ProbabilityEngine()

    assert engine.state.processed_count == 0

    engine.process(FeatureVector())

    assert engine.state.processed_count == 1


def test_acceptance_matches_thresholds() -> None:
    """
    Acceptance should follow the configured
    probability and confidence thresholds.
    """

    engine = ProbabilityEngine()

    result = engine.process(FeatureVector())

    expected = (
        result.probability >= engine.config.minimum_probability
        and result.confidence >= engine.config.minimum_confidence
    )

    assert result.accepted is expected