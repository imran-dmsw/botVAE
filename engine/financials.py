"""
Paramètres financiers alignés sur le cahier des charges (budget de référence ajusté, durabilité).

- SAV : 6 % du budget ajusté
- Frais d'exploitation (hors répartition logistique %) : 5 % du budget ajusté
- Durabilité : n × 0,5 % du budget ajusté ; prime de CA selon n (2→0,1 %, 3→0,3 %, 4→0,5 %)
"""
from __future__ import annotations

from config.market_config import MARKET_CONFIG


def sustainability_revenue_premium_rate(tranches: int) -> float:
    """Prime sur le chiffre d'affaires (sans effet sur le prix / la demande)."""
    m = MARKET_CONFIG["constraints"]["sustainability_revenue_premium_by_tranches"]
    return float(m.get(int(tranches), 0.0))


def aftersales_cost_from_ref_budget(adjusted_budget: float) -> float:
    pct = MARKET_CONFIG["constraints"]["aftersales_ref_budget_pct"]
    return max(adjusted_budget, 0.0) * pct


def operating_cost_from_ref_budget(adjusted_budget: float) -> float:
    pct = MARKET_CONFIG["constraints"]["operating_ref_budget_pct"]
    return max(adjusted_budget, 0.0) * pct


def sustainability_cost_from_tranches(tranches: int, adjusted_budget: float) -> float:
    pct = MARKET_CONFIG["constraints"]["sustainability_tranche_pct"]
    t = max(0, min(4, int(tranches)))
    return max(adjusted_budget, 0.0) * pct * t
