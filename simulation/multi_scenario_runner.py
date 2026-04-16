from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from engine.models import ScenarioInput
from engine.simulation import simulate
from rules.rules_engine import evaluate_business_controls
from rules.marketing_rules import marketing_efficiency, marketing_marginal_profit_delta
from rules.promo_rules import validate_promo_rate


@dataclass
class ScenarioSweepResult:
    label: str
    sales: int
    revenue: float
    profit: float
    margin: float
    market_share: float
    marketing_efficiency: float
    marginal_profit_delta: float


def run_promo_sales_test(base: ScenarioInput) -> List[ScenarioSweepResult]:
    promo_levels = [0.0, -0.02, -0.05, -0.10]
    results: List[ScenarioSweepResult] = []
    baseline_profit = None
    for promo in promo_levels:
        ok, msg = validate_promo_rate(promo)
        if not ok:
            continue
        scenario = base.model_copy(update={"promotion_rate": promo, "scenario_name": f"Promo {promo*100:.0f}%"})
        sim = simulate(scenario)
        if baseline_profit is None:
            baseline_profit = sim.profit
        results.append(
            ScenarioSweepResult(
                label=f"promo_{promo:.2f}" if ok else msg,
                sales=sim.sales,
                revenue=sim.revenue,
                profit=sim.profit,
                margin=sim.margin,
                market_share=sim.market_share,
                marketing_efficiency=marketing_efficiency(sim.sales, scenario.marketing_budget),
                marginal_profit_delta=marketing_marginal_profit_delta(baseline_profit, sim.profit),
            )
        )
    return results


def run_marketing_short_term_test(base: ScenarioInput) -> List[ScenarioSweepResult]:
    marketing_steps = [0.0, 0.02, 0.04, 0.06, 0.08, 0.10]
    baseline_budget = base.marketing_budget
    baseline_profit = None
    results: List[ScenarioSweepResult] = []
    for step in marketing_steps:
        budget = baseline_budget * (1.0 + step)
        scenario = base.model_copy(update={"marketing_budget": budget, "scenario_name": f"MKT +{step*100:.0f}%"})
        sim = simulate(scenario)
        if baseline_profit is None:
            baseline_profit = sim.profit
        results.append(
            ScenarioSweepResult(
                label=f"step_{step:.2f}",
                sales=sim.sales,
                revenue=sim.revenue,
                profit=sim.profit,
                margin=sim.margin,
                market_share=sim.market_share,
                marketing_efficiency=marketing_efficiency(sim.sales, budget),
                marginal_profit_delta=marketing_marginal_profit_delta(baseline_profit, sim.profit),
            )
        )
    return results


def run_all_scenarios(base: ScenarioInput) -> List[Dict]:
    """
    Execute the 6 predefined pedagogical scenarios with full simulation and controls.
    """
    scenario_overrides = {
        "Equilibre_Optimal": {
            "promotion_rate": -0.02,
            "marketing_budget": base.marketing_budget * 1.02,
            "price": max(base.price, 3000),
        },
        "Marketing_Optimal": {
            "promotion_rate": 0.0,
            "marketing_budget": base.marketing_budget * 1.10,
        },
        "Promo_Agressive": {
            "promotion_rate": -0.10,
            "liquidation": True,
        },
        "Prix_Incoherent": {
            "price": 2400.0 if base.model_range == "mid" else 3000.0,
        },
        "Nouveau_Produit": {
            "new_model_launch": True,
            "product_status": "pre_launch",
            "production": max(base.production, 1800),
        },
        "Liquidation_Modele": {
            "liquidation": True,
            "product_status": "withdrawal",
            "promotion_rate": -0.10,
        },
    }

    outputs: List[Dict] = []
    for name, updates in scenario_overrides.items():
        scenario = base.model_copy(update={"scenario_name": name, **updates})
        sim = simulate(scenario)
        controls = evaluate_business_controls(scenario, sim)
        outputs.append(
            {
                "scenario": name,
                "scenario_input": scenario,
                "result": sim,
                "controls": controls,
                "profit": sim.profit,
                "profit_rate": sim.profit_rate,
                "sales": sim.sales,
                "market_share": sim.market_share,
                "marketing_efficiency": sim.marketing_efficiency,
                "production_rate": sim.production_efficiency,
                "alerts": controls["alerts"] + sim.alerts,
            }
        )
    return outputs


def compare_scenarios(results: List[Dict]) -> List[Dict]:
    """
    Build a concise comparison view and winner markers.
    """
    if not results:
        return []
    best_profit = max(results, key=lambda x: x["profit"])["scenario"]
    best_profit_rate = max(results, key=lambda x: x["profit_rate"])["scenario"]

    rows = []
    for row in results:
        rows.append(
            {
                "Scenario": row["scenario"],
                "Profit ($)": row["profit"],
                "Profit rate (%)": row["profit_rate"] * 100,
                "Ventes": row["sales"],
                "Part de marche (%)": row["market_share"] * 100,
                "Efficacite marketing": row["marketing_efficiency"],
                "Taux production (%)": row["production_rate"] * 100,
                "Meilleur profit": "🏆" if row["scenario"] == best_profit else "",
                "Meilleur profit_rate": "🏆" if row["scenario"] == best_profit_rate else "",
                "Statut global": row["controls"]["global_status"],
            }
        )
    return rows
