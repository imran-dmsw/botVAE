"""
Grilles de scénarios pour couvrir « tous les modèles » (catalogue) et les tests pédagogiques.
"""
from __future__ import annotations

from typing import List

from config.market_config import MARKET_CONFIG
from engine.models import ScenarioInput
from engine.simulation import simulate, simulate_full_market
from rules.promo_rules import validate_promo_rate


def scenarios_all_product_types(base: ScenarioInput) -> List[ScenarioInput]:
    """Un scénario par type de produit du catalogue (8 types VAE)."""
    rows: List[ScenarioInput] = []
    for pt_key in MARKET_CONFIG["product_types"]:
        rows.append(
            base.model_copy(
                update={
                    "product_type": pt_key,
                    "scenario_name": f"Catalogue — {pt_key}",
                }
            )
        )
    return rows


def run_catalog_simulations(base: ScenarioInput):
    """Exécute `simulate` pour chaque type de produit ; retourne liste de (scenario, result)."""
    return [(s, simulate(s)) for s in scenarios_all_product_types(base)]


def promotion_grid(base: ScenarioInput) -> List[ScenarioInput]:
    """Taux de promotion autorisés (0 %, -2 % … -5 %, -10 %, liquidation selon config)."""
    rates = MARKET_CONFIG["plan_2026"]["promotion_test_rates"]
    out: List[ScenarioInput] = []
    for r in rates:
        ok, _ = validate_promo_rate(r, liquidation=False)
        if not ok:
            continue
        out.append(base.model_copy(update={"promotion_rate": r, "scenario_name": f"Promo {r*100:.0f}%"}))
    return out


def full_market_all_firms_all_segments(period: int = 1):
    """Vue marché complet : 9 firmes × 6 segments (profils de référence)."""
    return simulate_full_market(period=period, user_firm=None, user_scenario=None)
