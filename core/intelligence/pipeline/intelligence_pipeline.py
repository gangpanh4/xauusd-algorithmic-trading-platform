from __future__ import annotations

from typing import List

from core.intelligence.regime_engine.engine import MarketRegimeEngine
from core.intelligence.scarcity_engine.engine import OpportunityScarcityEngine
from core.intelligence.liquidity_engine.engine import LiquidityEngine

from core.intelligence.h4_bias_engine.engine import H4BiasEngine
from core.intelligence.h1_structure_engine.engine import H1StructureEngine
from core.intelligence.m15_setup_engine.engine import M15SetupEngine
from core.intelligence.m5_entry_engine.engine import M5EntryEngine
from core.intelligence.decision_aggregator.engine import DecisionAggregator
from core.intelligence.entropy_controller.engine import EntropyController
from core.intelligence.expectancy_engine.engine import ExpectancyEngine
from core.intelligence.liquidity_engine.directional_bias import DirectionalLiquidityEngine
from core.intelligence.confluence_engine.engine import ConfluenceEngine
from core.intelligence.m15_setup_engine.compression import M15SetupCompressionEngine
from core.intelligence.m5_entry_engine.compression import M5EntryCompressionEngine
from core.intelligence.microstructure.engine import MarketMicrostructureEngine
from core.intelligence.microstructure.feedback_loop import MicrostructureFeedbackEngine
from core.intelligence.meta.weight_adapter import MetaAdaptiveEngine
from core.intelligence.meta.stability_governor import StabilityGovernor
from core.intelligence.edge.opportunity_ranker import OpportunityRanker
from core.intelligence.pipeline.models import IntelligenceResult



class IntelligencePipeline:
    """
    Sprint 3 FULL PIPELINE (ALPHA + EDGE SYSTEM)

    Key Upgrade:
        - Liquidity Engine added (FIRST alpha-generation layer)
    """

    def __init__(self, symbol: str):
        self.symbol = symbol

        self.regime = MarketRegimeEngine(symbol)
        self.scarcity = OpportunityScarcityEngine(symbol)
        self.liquidity = LiquidityEngine(symbol)

        self.h4_bias_engine = H4BiasEngine(symbol)
        self.h1_structure_engine = H1StructureEngine(symbol)
        self.m15_setup_engine = M15SetupEngine(symbol)
        self.m5_entry_engine = M5EntryEngine(symbol)

        self.aggregator = DecisionAggregator(symbol)
        self.entropy = EntropyController(symbol)
        self.expectancy = ExpectancyEngine(symbol)
        self.directional_liquidity = DirectionalLiquidityEngine(symbol)
        self.confluence = ConfluenceEngine(symbol)
        self.m15_compression = M15SetupCompressionEngine(symbol)
        self.microstructure = MarketMicrostructureEngine(symbol)
        self.micro_feedback = MicrostructureFeedbackEngine(symbol)
        self.meta = MetaAdaptiveEngine()
        self.governor = StabilityGovernor()
        self.opportunity_ranker = OpportunityRanker()
        

    # --------------------------------------------------
    # MAIN ENTRY
    # --------------------------------------------------
    def run_pipeline(
        self,
        m15_bars,
        m5_bars,
        h1_bars,
        h4_bars,
    ):
        # --------------------------------------------------
        # 1. REGIME
        # --------------------------------------------------
        regime = self.regime.process(m5_bars)

        # --------------------------------------------------
        # 2. SCARCITY
        # --------------------------------------------------
        scarcity = self.scarcity.process(m5_bars)

        # --------------------------------------------------
        # 3. LIQUIDITY + DIRECTION
        # --------------------------------------------------
        liquidity = self.liquidity.process(m15_bars)
        directional_bias = self.directional_liquidity.process(m5_bars)

        # --------------------------------------------------
        # 4. H4 BIAS
        # --------------------------------------------------
        bias = self.h4_bias_engine.process(h4_bars)

        # --------------------------------------------------
        # 5. H1 STRUCTURE
        # --------------------------------------------------
        structure = self.h1_structure_engine.process(
            h1_bars,
            bias.trend,
        )

        # --------------------------------------------------
        # 6. CONFLUENCE (NOT DECISION OWNER)
        # --------------------------------------------------
        confluence = self.confluence.process(
            liquidity_bias=directional_bias,
            h4_bias=bias,
            structure=structure,
        )

        # --------------------------------------------------
        # 7. M15 SETUP
        # --------------------------------------------------
        setup = self.m15_setup_engine.process(
            m15_bars,
            bias.trend,
            structure.confirmation,
        )

        # --------------------------------------------------
        # 8. M5 ENTRY
        # --------------------------------------------------
        entry = self.m5_entry_engine.process(
            m5_bars,
            confluence.score,
        )

        # --------------------------------------------------
        # 9. MICROSTRUCTURE
        # --------------------------------------------------
        micro = self.microstructure.process(m5_bars)

        # --------------------------------------------------
        # 10. FEEDBACK LOOP
        # --------------------------------------------------
        feedback = self.micro_feedback.process(
            m5_bars,
            micro.__dict__ if hasattr(micro, "__dict__") else micro
        )

        # --------------------------------------------------
        # 11. META SYSTEM
        # --------------------------------------------------
        self.meta.update(
            feedback_score=feedback.failure_score,
            micro_success=micro.impulse_probability,
        )

        # APPLY STABILITY GOVERNOR
        self.meta.state = self.governor.clamp_weights(self.meta.state)

        weights = self.meta.state

        # --------------------------------------------------
        # 12. OPPORTUNITY RANKER (FINAL AUTHORITY)
        # --------------------------------------------------
        context = {
            "symbol": self.symbol,
            "liquidity": liquidity,
            "structure": structure,
            "microstructure": micro,
            "confluence": confluence,
            "entropy": self.entropy.process(m5_bars),
        }

        opportunity = self.opportunity_ranker.rank(
            context,
            regime=regime.type if hasattr(regime, "type") else None
        )

        # --------------------------------------------------
        # 13. FINAL EXECUTION GATE (ONLY THIS DECIDES TRADE)
        # --------------------------------------------------
        if opportunity.score < 0.65:
            return {
                "signal": None,
                "reason": "Rejected by OpportunityRanker",
                "opportunity": opportunity,
                "regime": regime,
            }

        # --------------------------------------------------
        # 14. EXPECTANCY (DIAGNOSTIC ONLY)
        # --------------------------------------------------
        expectancy = self.expectancy.process(
            regime,
            scarcity,
            bias,
            structure,
            setup,
            entry,
            self.entropy.process(m5_bars),
        )

        # --------------------------------------------------
        # FINAL OUTPUT
        # --------------------------------------------------
        return IntelligenceResult(
            regime=regime,
            liquidity=liquidity,
            directional_liquidity=directional_bias,
            h4_bias=bias,
            h1_structure=structure,
            m15_setup=setup,
            m5_entry=entry,
            confluence=confluence,
            opportunity=opportunity,
            expectancy=expectancy,
            microstructure=micro,
            feedback=feedback,
            meta_weights=weights,
        )