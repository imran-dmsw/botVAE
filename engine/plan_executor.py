"""
Structured execution of the 2026/2027 product-marketing action plan.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd

from config.market_config import MARKET_CONFIG
from engine.models import ScenarioInput, SimulationResult
from engine.simulation import (
    build_next_period_scenario,
    simulate,
    simulate_full_market,
)


@dataclass
class ScenarioRun:
    scenario: ScenarioInput
    result: SimulationResult
    policy: str
    promo_rate: float
    marketing_yield: float
    full_market_share: float
    full_market_rank: int
    profit_target_ok: bool
    index_2026: float


def _apply_policy_launch(policy: str, period: int) -> bool:
    launch_periods = MARKET_CONFIG["plan_2026"]["renewal_policies"][policy]["launch_periods"]
    return period in launch_periods


def _compute_2026_index(
    result: SimulationResult,
    *,
    profit_band: tuple[float, float],
) -> float:
    """
    Build a compact synthetic score (0..100) used as 2026 readiness indicator.
    """
    low, high = profit_band
    margin_score = 0.0
    if result.margin <= 0:
        margin_score = 0.0
    elif result.margin < low:
        margin_score = 60.0 * (result.margin / low)
    elif result.margin <= high:
        margin_score = 60.0 + 40.0 * ((result.margin - low) / max(high - low, 1e-6))
    else:
        margin_score = 100.0

    service_bonus = min(result.service_rate, 1.0) * 20.0
    pdm_bonus = min(result.market_share_segment / 0.20, 1.0) * 20.0
    return round(min(100.0, 0.6 * margin_score + 0.2 * service_bonus + 0.2 * pdm_bonus), 1)


def execute_plan_matrix(
    base_scenario: ScenarioInput,
    *,
    periods: int = 8,
) -> List[ScenarioRun]:
    """
    Execute plan scenarios:
    - promo tests (-10%, -25%)
    - marketing yield tests (0%, 5%, 10%)
    - renewal policy A vs B across periods
    - N+1 production rule propagation
    """
    plan_cfg = MARKET_CONFIG["plan_2026"]
    runs: List[ScenarioRun] = []

    for policy in plan_cfg["renewal_policies"]:
        for promo_rate in plan_cfg["promotion_test_rates"]:
            for mkt_yield in plan_cfg["marketing_yield_rates"]:
                scenario_p = base_scenario.model_copy(deep=True)
                scenario_p.period = 1
                scenario_p.promotion_rate = promo_rate
                scenario_p.liquidation = promo_rate <= MARKET_CONFIG["constraints"]["promo_liquidation_max"]
                scenario_p.marketing_budget = base_scenario.marketing_budget * (1.0 + mkt_yield)
                scenario_p.scenario_name = (
                    f"{policy} | promo {promo_rate*100:.0f}% | mkt+{mkt_yield*100:.0f}%"
                )

                for period in range(1, periods + 1):
                    scenario_p.period = period
                    scenario_p.new_model_launch = _apply_policy_launch(policy, period)

                    result = simulate(scenario_p)

                    market = simulate_full_market(period, scenario_p.firm_name, scenario_p)
                    ranked_firms = sorted(
                        market["firms"].items(),
                        key=lambda item: -item[1]["market_share"],
                    )
                    firm_shares: Dict[str, float] = {
                        firm: metrics["market_share"] for firm, metrics in market["firms"].items()
                    }
                    rank = next(
                        (idx for idx, (firm, _) in enumerate(ranked_firms, start=1) if firm == scenario_p.firm_name),
                        len(ranked_firms),
                    )

                    profit_target = tuple(plan_cfg["profit_target_band"])
                    runs.append(
                        ScenarioRun(
                            scenario=scenario_p.model_copy(deep=True),
                            result=result,
                            policy=policy,
                            promo_rate=promo_rate,
                            marketing_yield=mkt_yield,
                            full_market_share=firm_shares.get(scenario_p.firm_name, 0.0),
                            full_market_rank=rank,
                            profit_target_ok=profit_target[0] <= result.margin <= profit_target[1],
                            index_2026=_compute_2026_index(result, profit_band=profit_target),
                        )
                    )

                    if period < periods:
                        scenario_p = build_next_period_scenario(
                            scenario_p,
                            result,
                            new_model_launch=_apply_policy_launch(policy, period + 1),
                        )

    return runs


def runs_to_dataframe(runs: List[ScenarioRun]) -> pd.DataFrame:
    rows = []
    for run in runs:
        rows.append(
            {
                "Scenario": run.result.scenario_name,
                "Periode": run.scenario.period,
                "Politique": run.policy,
                "Promo (%)": run.promo_rate * 100,
                "Marketing uplift (%)": run.marketing_yield * 100,
                "Ventes": run.result.sales,
                "Profit ($)": run.result.profit,
                "Marge (%)": run.result.margin * 100,
                "PDM segment (%)": run.result.market_share_segment * 100,
                "PDM total (%)": run.result.market_share * 100,
                "PDM marche complet (%)": run.full_market_share * 100,
                "Rang marche complet": run.full_market_rank,
                "Taux service (%)": run.result.service_rate * 100,
                "Cible profit 5-10%": "OK" if run.profit_target_ok else "Hors cible",
                "Indice 2026": run.index_2026,
                "Valide": "OK" if run.result.is_valid else "Non",
            }
        )
    return pd.DataFrame(rows)


def compare_policies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate policy-level KPIs for decision support.
    """
    grouped = (
        df.groupby("Politique", as_index=False)
        .agg(
            profit_moyen=("Profit ($)", "mean"),
            marge_moyenne=("Marge (%)", "mean"),
            pdm_segment_moyenne=("PDM segment (%)", "mean"),
            rang_marche_moyen=("Rang marche complet", "mean"),
            taux_service_moyen=("Taux service (%)", "mean"),
            indice_2026_moyen=("Indice 2026", "mean"),
        )
        .sort_values(by=["profit_moyen", "indice_2026_moyen"], ascending=False)
    )
    return grouped
