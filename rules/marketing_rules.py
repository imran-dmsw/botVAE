from __future__ import annotations

from typing import Dict


def marketing_efficiency(sales: int, marketing_budget: float) -> float:
    if marketing_budget <= 0:
        return 0.0
    return sales / marketing_budget


def profit_rate_status(profit_rate: float) -> str:
    if profit_rate < 0.05:
        return "faible"
    if profit_rate <= 0.10:
        return "optimal"
    return "tres_bon"


def marketing_zone_assessment(marketing_pct_of_revenue: float) -> str:
    if marketing_pct_of_revenue < 0.0:
        return "invalid"
    if marketing_pct_of_revenue <= 0.10:
        return "bonne_zone"
    if marketing_pct_of_revenue <= 0.15:
        return "haute_acceptable"
    return "trop_elevee"


def marketing_marginal_profit_delta(
    baseline_profit: float,
    candidate_profit: float,
) -> float:
    return candidate_profit - baseline_profit


def best_marketing_efficiency_zone(results: list[Dict]) -> Dict:
    """
    results entries should expose keys: marketing_rate, profit, sales, marketing_efficiency.
    """
    if not results:
        return {}
    return max(results, key=lambda row: (row.get("profit", 0.0), row.get("marketing_efficiency", 0.0)))
