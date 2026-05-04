"""
Jeux de scénarios prêts à l'emploi pour rapports PDF / comparaisons pédagogiques.
"""
from __future__ import annotations

from typing import List, Tuple

from engine.models import ScenarioInput, MarketingChannels, SimulationResult
from engine.simulation import simulate
from rules.promo_rules import validate_promo_rate
from simulation.multi_scenario_runner import run_all_scenarios


def _ch(mkt: float) -> MarketingChannels:
    return MarketingChannels(
        digital=mkt * 0.4,
        social_media=mkt * 0.25,
        influencers=mkt * 0.15,
        display=mkt * 0.1,
        events=mkt * 0.1,
    )


def default_base_scenario() -> ScenarioInput:
    return ScenarioInput(
        firm_name="AVE",
        period=1,
        scenario_name="Base",
        model_name="AVE-SwiftRide M1",
        product_type="ville_quotidien",
        segment="urbains_presses",
        model_range="mid",
        product_status="active",
        marketing_budget=80_000,
        marketing_channels=_ch(80_000),
        rd_budget=15_000,
        price=3200,
        production=1500,
        adjusted_budget=1_200_000,
        competitor_attractiveness=18.0,
    )


def collect_default_batch() -> Tuple[List[ScenarioInput], List[SimulationResult]]:
    """
    Construit la même série de simulations que l'analyse « lot » (hors marché complet agrégé).
    """
    base = default_base_scenario()
    scenarios: List[ScenarioInput] = []
    results: List[SimulationResult] = []

    for pack in run_all_scenarios(base):
        scenarios.append(pack["scenario_input"])
        results.append(pack["result"])

    for pr in [0.0, -0.02, -0.05, -0.10]:
        ok, _ = validate_promo_rate(pr)
        if not ok:
            continue
        sc = base.model_copy(
            update={"promotion_rate": pr, "scenario_name": f"Sweep_promo_{int(pr * 100)}%"}
        )
        scenarios.append(sc)
        results.append(simulate(sc))

    sc = base.model_copy(
        update={
            "marketing_budget": 88_000,
            "marketing_channels": _ch(88_000),
            "scenario_name": "MKT_plus10pct",
        }
    )
    scenarios.append(sc)
    results.append(simulate(sc))

    for p in (4, 8):
        sc = base.model_copy(update={"period": p, "scenario_name": f"Base_periode_{p}"})
        scenarios.append(sc)
        results.append(simulate(sc))

    sc = ScenarioInput(
        firm_name="TRE",
        period=2,
        scenario_name="TRE_Enduro_Premium",
        model_name="TRE-Rush",
        product_type="route_connecte",
        segment="endurants_performants",
        model_range="premium",
        product_status="active",
        marketing_budget=120_000,
        marketing_channels=_ch(120_000),
        rd_budget=40_000,
        price=5200,
        production=2000,
        adjusted_budget=2_000_000,
        competitor_attractiveness=14.0,
    )
    scenarios.append(sc)
    results.append(simulate(sc))

    sc = base.model_copy(
        update={
            "liquidation": True,
            "promotion_rate": -0.20,
            "scenario_name": "Liquidation_moins20",
        }
    )
    scenarios.append(sc)
    results.append(simulate(sc))

    sc = base.model_copy(
        update={"scenario_name": "Durabilite_2_tranches", "sustainability_tranches": 2}
    )
    scenarios.append(sc)
    results.append(simulate(sc))

    return scenarios, results
