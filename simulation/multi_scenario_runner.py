from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

from engine.models import ScenarioInput
from engine.simulation import build_next_period_scenario, simulate
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


def run_production_levels_test(
    base: ScenarioInput,
    *,
    levels: Sequence[int] = (1500, 2000, 2500, 3000),
) -> List[ScenarioSweepResult]:
    results: List[ScenarioSweepResult] = []
    baseline_profit = None
    for lvl in levels:
        scenario = base.model_copy(update={"production": int(lvl), "scenario_name": f"PROD {lvl}"})
        sim = simulate(scenario)
        if baseline_profit is None:
            baseline_profit = sim.profit
        results.append(
            ScenarioSweepResult(
                label=f"prod_{lvl}",
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


def run_evolving_production_test(
    base: ScenarioInput,
    *,
    start_production: int,
    growth_rates: Sequence[float] = (0.10, 0.12, 0.15),
    periods: int = 8,
) -> List[Dict]:
    """
    Simule une trajectoire multi-périodes où la production augmente d'un pourcentage fixe chaque année.
    Retourne une liste de lignes (dict) prêtes à afficher/exporter.
    """
    outputs: List[Dict] = []
    for g in growth_rates:
        sc = base.model_copy(update={"period": 1, "production": int(start_production), "opening_stock": 0})
        prev_sc = sc
        prev_res = simulate(prev_sc)
        outputs.append(
            {
                "policy": f"start_{start_production}_plus{int(g*100)}pct",
                "period": prev_res.period,
                "production": prev_sc.production,
                "demand": prev_res.demand,
                "sales": prev_res.sales,
                "ending_stock": prev_res.forecast_ending_stock_units,
                "profit": prev_res.profit,
                "margin": prev_res.margin,
                "coverage": prev_res.forecast_coverage_rate,
            }
        )
        for p in range(2, periods + 1):
            next_sc = build_next_period_scenario(prev_sc, prev_res, next_period=p)
            next_sc = next_sc.model_copy(update={"production": int(round(prev_sc.production * (1.0 + g)))})
            res = simulate(next_sc)
            outputs.append(
                {
                    "policy": f"start_{start_production}_plus{int(g*100)}pct",
                    "period": res.period,
                    "production": next_sc.production,
                    "demand": res.demand,
                    "sales": res.sales,
                    "ending_stock": res.forecast_ending_stock_units,
                    "profit": res.profit,
                    "margin": res.margin,
                    "coverage": res.forecast_coverage_rate,
                }
            )
            prev_sc, prev_res = next_sc, res
    return outputs


def run_liquidation_10pct_with_production_2500(base: ScenarioInput) -> Dict:
    """
    Scénario demandé par le plan final: production 2 500 et promotion liquidation 10%.
    """
    scenario = base.model_copy(
        update={
            "production": 2500,
            "liquidation": True,
            "product_status": "withdrawal",
            "promotion_rate": -0.10,
            "scenario_name": "PROD_2500_LIQ_-10",
        }
    )
    sim = simulate(scenario)
    controls = evaluate_business_controls(scenario, sim)
    return {
        "scenario": scenario.scenario_name,
        "scenario_input": scenario,
        "result": sim,
        "controls": controls,
        "alerts": controls["alerts"] + sim.alerts,
    }


def run_promo_sales_test(base: ScenarioInput) -> List[ScenarioSweepResult]:
    promo_levels = [0.0, -0.02, -0.05, -0.10]
    results: List[ScenarioSweepResult] = []
    baseline_profit = None
    for promo in promo_levels:
        ok, msg = validate_promo_rate(promo, liquidation=(promo <= -0.10))
        if not ok:
            continue
        scenario = base.model_copy(update={"promotion_rate": promo, "scenario_name": f"Promo {promo*100:.0f}%"})
        if promo <= -0.10:
            scenario = scenario.model_copy(update={"liquidation": True, "product_status": "withdrawal"})
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
