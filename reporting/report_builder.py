from __future__ import annotations

from engine.models import ScenarioInput, SimulationResult
from reporting.baseline_2026 import build_2026_baseline_summary
from reporting.recommendation_engine import build_recommendations


def build_enriched_report_payload(scenario: ScenarioInput, result: SimulationResult) -> dict:
    baseline = build_2026_baseline_summary(scenario, result)
    recommendations = build_recommendations(scenario, result)
    controls = {
        "price_range_consistency_status": result.price_range_consistency_status,
        "profit_rate_status": result.profit_rate_status,
        "withdrawal_limit_status": result.withdrawal_limit_status,
        "liquidation_next_period_production_flag": result.liquidation_next_period_production_flag,
        "new_product_first_year_flag": result.new_product_first_year_flag,
    }
    return {
        "executive_summary": {
            "scenario": result.scenario_name,
            "firm": result.firm_name,
            "period": result.period,
            "segment": scenario.segment,
            "is_valid": result.is_valid,
        },
        "main_results": {
            "sales": result.sales,
            "revenue": result.revenue,
            "profit": result.profit,
            "profit_rate": result.profit_rate,
            "margin": result.margin,
            "market_share": result.market_share,
            "service_rate": result.service_rate,
            "innovation_score": result.innovation_score,
            "sustainability_score": result.sustainability_score,
        },
        "controls": controls,
        "baseline_2026": baseline,
        "recommendations": recommendations,
    }
