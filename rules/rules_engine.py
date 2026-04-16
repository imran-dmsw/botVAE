from __future__ import annotations

from typing import Dict, List

from engine.models import ScenarioInput, SimulationResult
from rules.marketing_rules import profit_rate_status
from rules.price_rules import check_price_range_consistency
from rules.promo_rules import validate_promo_rate


def evaluate_business_controls(scenario: ScenarioInput, result: SimulationResult) -> Dict:
    """
    Central rules engine that evaluates business controls and returns statuses.
    """
    price_status, price_msg = check_price_range_consistency(scenario.price, scenario.model_range)
    promo_ok, promo_msg = validate_promo_rate(scenario.promotion_rate)

    prate = result.profit / max(result.revenue, 1.0)
    pstatus = profit_rate_status(prate)

    production_rate = result.sales / max(scenario.production, 1)
    if production_rate < 0.70:
        production_status = "SURPRODUCTION"
        production_msg = "Production trop elevee vs ventes."
    elif production_rate >= 0.95:
        production_status = "RISQUE_RUPTURE"
        production_msg = "Production quasi saturée, risque de rupture."
    else:
        production_status = "OK"
        production_msg = "Production coherente avec les ventes."

    marketing_ratio = scenario.marketing_budget / max(scenario.adjusted_budget, 1.0)
    if marketing_ratio > 0.13:
        marketing_status = "TROP_ELEVE"
        marketing_msg = f"Marketing eleve ({marketing_ratio*100:.1f}% du budget ajuste)."
    else:
        marketing_status = "OK"
        marketing_msg = "Niveau marketing acceptable."

    alerts: List[str] = []
    if price_status != "ok":
        alerts.append(price_msg)
    if not promo_ok:
        alerts.append(promo_msg)
    if pstatus == "faible":
        alerts.append("Profit rate faible (<5%).")
    if production_status != "OK":
        alerts.append(production_msg)
    if marketing_status != "OK":
        alerts.append(marketing_msg)

    return {
        "price_range": {"status": "OK" if price_status == "ok" else "ERREUR", "message": price_msg},
        "promotion": {"status": "OK" if promo_ok else "ERREUR", "message": promo_msg},
        "profit": {"status": pstatus.upper(), "profit_rate": prate},
        "production": {"status": production_status, "production_rate": production_rate, "message": production_msg},
        "marketing": {"status": marketing_status, "ratio": marketing_ratio, "message": marketing_msg},
        "global_status": "OK" if len(alerts) == 0 else "ALERTE",
        "alerts": alerts,
    }
