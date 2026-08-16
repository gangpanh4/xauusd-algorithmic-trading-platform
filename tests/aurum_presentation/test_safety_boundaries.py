from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[2] / "core" / "aurum_presentation"


def _source() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in PACKAGE.glob("*.py"))


def test_forbidden_execution_network_intelligence_and_legacy_surfaces_are_absent() -> None:
    source = _source()
    forbidden = (
        "MetaTrader5",
        "order_send",
        "order_check",
        "positions_get",
        "orders_get",
        "MT5Executor",
        "ExecutionAdapter",
        "OrderRequest",
        "_authorize_broker_mutation",
        "IntelligencePipeline",
        "core.legacy",
        "import requests",
        "import socket",
        "urllib",
        "aiohttp",
    )
    for token in forbidden:
        assert token not in source


def test_no_analytical_engine_invocation_is_present() -> None:
    source = _source()
    forbidden = (
        "TradingPipeline(",
        "MarketStructureEngine(",
        "MarketRegimeDetector(",
        "DecisionEngine(",
        "SignalGenerator(",
        ".process_bar(",
        ".generate_signal(",
    )
    for token in forbidden:
        assert token not in source


def test_no_dynamic_typing_workarounds_are_present() -> None:
    source = _source()
    forbidden = (
        "from typing import Any",
        "typing.Any",
        "getattr(",
        "cast(",
        "type: ignore",
    )
    for token in forbidden:
        assert token not in source


def test_snapshot_inputs_have_no_news_ai_diagnostic_or_engine_authority_inputs() -> None:
    from dataclasses import fields

    from core.aurum_presentation.builder import AurumSnapshotInputs

    names = {field.name for field in fields(AurumSnapshotInputs)}
    assert "quote" in names
    assert "news" not in names
    assert "ai" not in names
    assert "methodology" not in names
    assert "intelligence" not in names
    assert "trading_pipeline" not in names
    assert "decision_engine" not in names
    assert "signal_generator" not in names


def test_only_designated_quote_adapter_imports_metatrader5() -> None:
    quote_source = (PACKAGE.parents[0] / "data" / "quote.py").read_text(encoding="utf-8")
    presentation_source = _source()

    assert "import MetaTrader5 as mt5" in quote_source
    assert "MetaTrader5" not in presentation_source


def test_publication_has_no_network_mt5_or_analytical_engine_surface() -> None:
    source = (PACKAGE / "publication.py").read_text(encoding="utf-8")
    forbidden = (
        "MetaTrader5",
        "requests",
        "socket",
        "urllib",
        "aiohttp",
        "TradingPipeline",
        "MarketStructureEngine",
        "MarketRegimeDetector",
        "DecisionEngine",
        "SignalGenerator",
    )
    for token in forbidden:
        assert token not in source
