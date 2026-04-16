from __future__ import annotations

from config.market_config import MARKET_CONFIG
from engine.models import ScenarioInput, SimulationResult


def build_2026_baseline_summary(scenario: ScenarioInput, result: SimulationResult) -> dict:
    market_2026 = MARKET_CONFIG["base_market_size"]
    avg_price_2026 = MARKET_CONFIG["base_average_price"]
    baseline_revenue = market_2026 * avg_price_2026
    baseline_share = result.sales / max(market_2026, 1)
    baseline_profitability = result.profit / max(result.revenue, 1)
    return {
        "market_size_2026": market_2026,
        "firm_baseline_revenue_2026": baseline_revenue,
        "segment_baseline_share_2026": MARKET_CONFIG["segments"][scenario.segment]["share"],
        "baseline_price_2026": avg_price_2026,
        "baseline_market_share_2026": baseline_share,
        "baseline_profitability_2026": baseline_profitability,
        "scenario_vs_baseline_revenue_delta": result.revenue - baseline_revenue,
        "scenario_vs_baseline_share_delta": result.market_share - baseline_share,
    }
