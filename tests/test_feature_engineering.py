"""
Tests for the Feature Engineering Engine.

These tests verify the baseline behavior of the Feature
Engineering subsystem. They intentionally validate engine
correctness rather than feature quality.
"""

from core.feature_engineering.engine import (
    FeatureEngineeringEngine,
)

from core.feature_engineering.models import (
    FeatureVector,
)


def test_process_returns_feature_vector() -> None:
    """
    process() should always return a FeatureVector.
    """

    engine = FeatureEngineeringEngine()

    evidence = engine.create_evidence()

    vector = engine.process(evidence)

    assert isinstance(vector, FeatureVector)


def test_processed_count_increments() -> None:
    """
    Processing should increment the internal counter.
    """

    engine = FeatureEngineeringEngine()

    evidence = engine.create_evidence()

    assert engine.state.processed_count == 0

    engine.process(evidence)

    assert engine.state.processed_count == 1


def test_latest_features_updated() -> None:
    """
    Latest features should reference the most recent
    FeatureVector produced by the engine.
    """

    engine = FeatureEngineeringEngine()

    evidence = engine.create_evidence()

    vector = engine.process(evidence)

    assert engine.state.latest_features is vector


def test_feature_count_matches_vector_size() -> None:
    """
    feature_count should always match the latest vector size.
    """

    engine = FeatureEngineeringEngine()

    evidence = engine.create_evidence()

    vector = engine.process(evidence)

    assert engine.feature_count == vector.size


def test_reset_clears_runtime_state() -> None:
    """
    Reset should clear runtime state.
    """

    engine = FeatureEngineeringEngine()

    evidence = engine.create_evidence()

    engine.process(evidence)

    assert engine.state.processed_count == 1

    engine.reset()

    assert engine.state.processed_count == 0
    assert engine.feature_count == 0


def test_feature_confidence_is_normalized() -> None:
    """
    Every feature confidence should remain inside [0, 1].
    """

    engine = FeatureEngineeringEngine()

    evidence = engine.create_evidence()

    vector = engine.process(evidence)

    for feature in vector.features:
        assert 0.0 <= feature.confidence <= 1.0


def test_normalized_features_are_bounded() -> None:
    """
    Normalized features should remain inside [0, 1].
    """

    engine = FeatureEngineeringEngine()

    evidence = engine.create_evidence()

    vector = engine.process(evidence)

    for feature in vector.features:
        if feature.normalized:
            assert 0.0 <= feature.value <= 1.0


def test_feature_metadata_is_present() -> None:
    """
    Every produced feature should include the required metadata.
    """

    engine = FeatureEngineeringEngine()

    evidence = engine.create_evidence()

    vector = engine.process(evidence)

    for feature in vector.features:
        assert feature.name
        assert feature.family
        assert feature.source