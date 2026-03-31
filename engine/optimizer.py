"""
Inverse / goal-seek optimization engine.

Given a ScenarioInput as a base and a target metric + value,
this module finds the combination of pilotable parameters that
best achieves the objective while respecting all business constraints.

Pilotable variables: marketing_budget, rd_budget, price, production
"""
import copy
from typing import List, Optional

import numpy as np
from scipy.optimize import differential_evolution

from config.market_config import MARKET_CONFIG
from engine.models import ScenarioInput, OptimizationResult, SimulationResult
from engine.simulation import simulate

SUPPORTED_METRICS = {
    "profit": "Profit (CAD $)",
    "margin": "Marge (%)",
    "market_share": "Part de marché totale (%)",
    "market_share_segment": "Part de marché segment (%)",
    "innovation_score": "Score innovation (/10)",
    "sustainability_score": "Score durabilité (/10)",
}


def _get_metric(result: SimulationResult, metric: str) -> float:
    return getattr(result, metric, 0.0)


def _build_bounds(base: ScenarioInput) -> list:
    """Return (min, max) bounds for [marketing_budget, rd_budget, price, production]."""
    cfg = MARKET_CONFIG
    adj = base.adjusted_budget
    price_min, price_max = cfg["ranges"][base.model_range]["price_range"]
    # Widen price range slightly to allow exploration
    return [
        (0.0, adj * cfg["constraints"]["marketing_max_pct"]),
        (0.0, adj * cfg["constraints"]["rd_max_pct"]),
        (max(price_min * 0.8, 500.0), price_max * 1.2),
        (1, 30000),
    ]


def _decode(x: np.ndarray, base: ScenarioInput) -> ScenarioInput:
    s = base.model_copy(deep=True)
    s.marketing_budget = float(x[0])
    s.rd_budget = float(x[1])
    s.price = float(x[2])
    s.production = int(round(x[3]))
    # Prorate marketing channels proportionally to new budget
    old_total = base.marketing_channels.total()
    if old_total > 0:
        ratio = s.marketing_budget / old_total
        mc = base.marketing_channels
        from engine.models import MarketingChannels
        s.marketing_channels = MarketingChannels(
            digital=mc.digital * ratio,
            social_media=mc.social_media * ratio,
            influencers=mc.influencers * ratio,
            display=mc.display * ratio,
            events=mc.events * ratio,
        )
    return s


def _objective_factory(base: ScenarioInput, metric: str, target: float, maximize: bool = False):
    """Return an objective function for differential_evolution (minimization)."""
    def objective(x: np.ndarray) -> float:
        s = _decode(x, base)
        result = simulate(s)

        current = _get_metric(result, metric)

        # Primary: minimize squared distance to target
        distance = (current - target) ** 2

        # Penalty for constraint violations
        penalty = 0.0
        cfg = MARKET_CONFIG["constraints"]
        if result.revenue > 0:
            if result.profit < result.revenue * cfg["min_profit_rate"]:
                penalty += 1e6 * abs(result.profit - result.revenue * cfg["min_profit_rate"])
        if result.profit < 0:
            penalty += 1e7 * abs(result.profit)

        return distance + penalty

    if maximize:
        def obj_maximize(x: np.ndarray) -> float:
            s = _decode(x, base)
            result = simulate(s)
            return -_get_metric(result, metric)
        return obj_maximize

    return objective


def find_parameters_for_target(
    base_scenario: ScenarioInput,
    target_metric: str,
    target_value: float,
    tolerance: float = 0.02,
    max_iter: int = 300,
    popsize: int = 12,
) -> OptimizationResult:
    """
    Search for ScenarioInput parameters that achieve target_value on target_metric.

    Returns OptimizationResult with the best found parameters and explanation.
    """
    if target_metric not in SUPPORTED_METRICS:
        raise ValueError(
            f"Métrique '{target_metric}' non supportée. "
            f"Choisissez parmi : {list(SUPPORTED_METRICS.keys())}"
        )

    bounds = _build_bounds(base_scenario)
    objective = _objective_factory(base_scenario, target_metric, target_value)

    de_result = differential_evolution(
        objective,
        bounds,
        maxiter=max_iter,
        popsize=popsize,
        tol=1e-8,
        seed=42,
        mutation=(0.5, 1.5),
        recombination=0.7,
        polish=True,
    )

    best_scenario = _decode(de_result.x, base_scenario)
    best_result = simulate(best_scenario)
    achieved = _get_metric(best_result, target_metric)
    gap = abs(achieved - target_value)

    # Determine success
    if target_metric in ("margin", "market_share", "market_share_segment"):
        relative_gap = gap / max(abs(target_value), 0.001)
        success = relative_gap <= tolerance
    else:
        relative_gap = gap / max(abs(target_value), 1.0)
        success = relative_gap <= tolerance

    # Build explanation
    explanation = _build_explanation(
        base=base_scenario,
        optimized=best_scenario,
        result=best_result,
        target_metric=target_metric,
        target_value=target_value,
        achieved=achieved,
        success=success,
    )

    msg = (
        f"Objectif atteint : {SUPPORTED_METRICS[target_metric]} = {_fmt(achieved, target_metric)} "
        f"(cible : {_fmt(target_value, target_metric)}, écart : {_fmt(gap, target_metric)})."
        if success
        else
        f"Objectif partiellement atteint : meilleur résultat trouvé = {_fmt(achieved, target_metric)} "
        f"pour une cible de {_fmt(target_value, target_metric)} (écart : {_fmt(gap, target_metric)})."
    )

    return OptimizationResult(
        success=success,
        target_metric=target_metric,
        target_value=target_value,
        achieved_value=achieved,
        gap=gap,
        message=msg,
        recommended_scenario=best_scenario,
        simulation_result=best_result,
        explanation=explanation,
    )


def maximize_metric(
    base_scenario: ScenarioInput,
    metric: str,
    constraint_min_profit_rate: Optional[float] = None,
    max_iter: int = 300,
) -> OptimizationResult:
    """
    Maximize a metric (e.g., profit, market_share) subject to constraints.
    Uses a very large target to force maximization via the squared-distance objective.
    """
    large_target = 1e12 if metric == "profit" else 1.0
    return find_parameters_for_target(
        base_scenario=base_scenario,
        target_metric=metric,
        target_value=large_target,
        max_iter=max_iter,
    )


# ─── Formatting helper ────────────────────────────────────────────────────────

def _fmt(value: float, metric: str) -> str:
    if metric in ("margin", "market_share", "market_share_segment"):
        return f"{value*100:.2f}%"
    if metric in ("innovation_score", "sustainability_score"):
        return f"{value:.2f}/10"
    return f"{value:,.0f} $"


# ─── Explanation builder ─────────────────────────────────────────────────────

def _build_explanation(
    base: ScenarioInput,
    optimized: ScenarioInput,
    result: SimulationResult,
    target_metric: str,
    target_value: float,
    achieved: float,
    success: bool,
) -> List[str]:
    exp = []
    cfg = MARKET_CONFIG["constraints"]

    if success:
        exp.append(f"L'objectif de {_fmt(target_value, target_metric)} a été atteint.")
    else:
        exp.append(
            f"L'objectif de {_fmt(target_value, target_metric)} n'a pas été pleinement atteint. "
            f"Meilleure valeur trouvée : {_fmt(achieved, target_metric)}."
        )
        # Diagnose why
        mkt_max = base.adjusted_budget * cfg["marketing_max_pct"]
        rd_max = base.adjusted_budget * cfg["rd_max_pct"]
        if optimized.marketing_budget >= mkt_max * 0.98:
            exp.append("Le budget marketing est déjà au maximum autorisé (15%). Impossible d'augmenter davantage.")
        if optimized.rd_budget >= rd_max * 0.98:
            exp.append("Le budget R&D est déjà au maximum autorisé (8%). Impossible d'augmenter davantage.")
        if result.margin < cfg["min_profit_rate"] and target_metric != "profit":
            exp.append(
                "La contrainte de rentabilité minimale (2%) limite les paramètres disponibles. "
                "Un objectif agressif de part de marché ou d'innovation peut entrer en conflit avec la rentabilité."
            )
        if target_metric in ("market_share", "market_share_segment") and achieved < target_value:
            exp.append(
                "La part de marché cible est élevée. Elle dépend de la force des concurrents dans le segment, "
                "qui est un facteur exogène non pilotable."
            )

    # Parameter changes
    changes = []
    if abs(optimized.marketing_budget - base.marketing_budget) > 100:
        changes.append(
            f"Marketing : {base.marketing_budget:,.0f} $ → {optimized.marketing_budget:,.0f} $"
        )
    if abs(optimized.rd_budget - base.rd_budget) > 100:
        changes.append(f"R&D : {base.rd_budget:,.0f} $ → {optimized.rd_budget:,.0f} $")
    if abs(optimized.price - base.price) > 10:
        changes.append(f"Prix : {base.price:,.0f} $ → {optimized.price:,.0f} $")
    if abs(optimized.production - base.production) > 10:
        changes.append(f"Production : {base.production:,} → {optimized.production:,} unités")

    if changes:
        exp.append("Modifications recommandées par rapport au scénario de base :")
        exp.extend([f"  • {c}" for c in changes])

    # Financial impact summary
    exp.append(
        f"Résultat financier : revenu {result.revenue:,.0f} $, profit {result.profit:,.0f} $, "
        f"marge {result.margin*100:.1f}%."
    )

    return exp
