"""
Core simulation engine for the VAE marketing simulation.

Demand model (attraction / logit):
  attractiveness_i = base * price_effect * marketing_effect * status_factor
                     * innovation_bonus * sustainability_bonus
  market_share_seg  = attractiveness_i / (attractiveness_i + competitor_attractiveness)
  demand            = market_share_seg * segment_size
  sales             = min(demand, production)

Market growth (single phase, Excel parameters):
  Reference year 2026: 110,000 units
  Period 1 = 2027: 110,000 * 1.12 = 123,200 units
  Growth: +12%/yr for all 8 decision periods (2027-2034)
  Formula: base_market_size * (1 + growth_rate) ** period

COGS model (Excel parameters):
  unit_cost = effective_price * cogs_ratio[range] * inflation(period)
  cogs_ratio: entry=60%, mid=57%, premium=55%
"""
import math
from typing import Dict, List, Optional, Tuple

from config.market_config import MARKET_CONFIG
from engine.financials import (
    aftersales_cost_from_ref_budget,
    operating_cost_from_ref_budget,
    sustainability_cost_from_tranches,
    sustainability_revenue_premium_rate,
)
from engine.models import ScenarioInput, SimulationResult
from engine.rules import validate_scenario
from reporting.baseline_2026 import build_2026_baseline_summary
from rules.marketing_rules import marketing_efficiency, profit_rate_status
from rules.price_rules import check_price_range_consistency, price_range_penalty_multiplier
from rules.product_lifecycle_rules import (
    apply_new_product_first_year_sales_cap,
    liquidation_next_period_production_flag,
)
from rules.stock_production_alerts import build_stock_production_diagnostics
from rules.production_rules import production_efficiency, recommend_next_period_production
from rules.withdrawal_rules import check_withdrawal_limits


# ─── Market size helpers ──────────────────────────────────────────────────────

def total_market_size(period: int) -> float:
    """Return total market size (units) for the given period.

    period 1 = 2027: 110,000 * 1.12^1 = 123,200
    period 8 = 2034: 110,000 * 1.12^8 = 272,378
    """
    base = MARKET_CONFIG["base_market_size"]   # 110,000 (reference year 2026)
    g = MARKET_CONFIG["growth_rate"]            # 0.12
    return base * ((1 + g) ** period)


def segment_size(period: int, segment: str) -> float:
    share = MARKET_CONFIG["segments"][segment]["share"]
    return total_market_size(period) * share


def period_to_year(period: int) -> int:
    """period 1 → 2027, period 8 → 2034."""
    return MARKET_CONFIG["base_year"] + (period - 1)


def period_inflation_factor(period: int) -> float:
    """Inflation factor vs reference year (2026) for a given period."""
    infl = MARKET_CONFIG.get("price_inflation_rate", 0.0)
    return (1.0 + infl) ** max(period, 0)


# ─── Attractiveness ───────────────────────────────────────────────────────────

def calc_attractiveness(s: ScenarioInput) -> float:
    cfg = MARKET_CONFIG
    seg_cfg = cfg["segments"][s.segment]
    status_factor = cfg["product_status_factors"][s.product_status]

    if status_factor == 0:
        return 0.0

    # Effective price after promotion
    effective_price = s.price * (1.0 + s.promotion_rate)   # promotion_rate <= 0

    # Price effect: logit-type ratio vs segment reference price
    ref_price = seg_cfg["reference_price"]
    elasticity = seg_cfg["price_elasticity"]
    price_ratio = ref_price / max(effective_price, 1.0)
    price_effect = price_ratio ** elasticity

    # Marketing effect (log-diminishing returns)
    k = cfg["marketing_efficiency_k"]
    seg_mkt_base = segment_size(s.period, s.segment) * ref_price * 0.001
    marketing_effect = 1.0 + k * math.log(1.0 + s.marketing_budget / max(seg_mkt_base, 1.0))

    # Innovation bonus
    innovation_bonus = 1.0 + 0.08 * (s.previous_innovation_score / 10.0)

    # Sustainability bonus
    sustainability_bonus = 1.0 + 0.04 * (s.previous_sustainability_score / 10.0)

    # Range base multiplier
    range_base = {"entry": 0.80, "mid": 1.00, "premium": 1.20}[s.model_range]

    attractiveness = (
        range_base
        * seg_cfg["base_attractiveness"]
        * price_effect
        * marketing_effect
        * status_factor
        * innovation_bonus
        * sustainability_bonus
    )
    attractiveness *= price_range_penalty_multiplier(s.price, s.model_range)

    return max(attractiveness, 0.0)


# ─── Scores ───────────────────────────────────────────────────────────────────

def calc_scores(s: ScenarioInput):
    cfg = MARKET_CONFIG
    decay = cfg["innovation_decay_rate"]
    adj = max(s.adjusted_budget, 1.0)

    # Innovation
    rd_intensity = s.rd_budget / adj
    innov_boost = min(rd_intensity * 60.0, 3.0)
    if s.new_model_launch:
        innov_boost = min(innov_boost + 1.5, 4.0)
    new_innov = s.previous_innovation_score * (1.0 - decay) + innov_boost
    new_innov = max(0.0, min(10.0, new_innov))

    # Sustainability
    sustain_intensity = s.sustainability_investment / adj
    sustain_boost = min(sustain_intensity * 50.0, 2.5)
    compound = 1.0 + 0.1 * min(s.sustainability_periods - 1, 5) if s.sustainability_periods > 1 else 1.0
    sustain_boost *= compound
    new_sustain = s.previous_sustainability_score * 0.92 + sustain_boost
    new_sustain = max(0.0, min(10.0, new_sustain))

    return new_innov, new_sustain


# ─── COGS-based unit production cost (Excel model) ────────────────────────────

def get_unit_production_cost(s: ScenarioInput) -> float:
    """Return unit production cost with period cost inflation."""
    cogs_ratio = MARKET_CONFIG["cogs_ratios"][s.model_range]
    effective_price = s.price * (1.0 + s.promotion_rate)
    base_unit_cost = effective_price * cogs_ratio
    return base_unit_cost * period_inflation_factor(s.period)


# ─── Production suggestion for next period ────────────────────────────────────

def suggest_next_production(scenario: ScenarioInput, result: SimulationResult) -> int:
    """
    Suggest production quantity for the next period based on current results.

    Rules:
    - Liquidation → 0 (no production after liquidation)
    - Withdrawal  → 0
    - High demand (service_rate > 0.95): grow by 20%
    - Demand met (0.85-0.95): grow by 10%
    - Partial (0.70-0.85): maintain + 5% buffer
    - Low demand (service_rate < 0.70): reduce to demand * 0.95
    - New product (pre_launch): cap at 2,000 units
    """
    cfg = MARKET_CONFIG["constraints"]

    if scenario.liquidation or scenario.withdraw_model:
        return 0

    demand = max(result.demand, 1.0)
    sr = result.service_rate

    if scenario.product_status == "pre_launch":
        suggested = min(int(demand * 1.10), cfg["new_product_max_units"])
    elif sr > 0.95:
        suggested = int(demand * 1.20)   # undersupplied: grow 20%
    elif sr > 0.85:
        suggested = int(demand * 1.10)   # well served: grow 10%
    elif sr > 0.70:
        suggested = int(demand * 1.05)   # adequate: slight buffer
    else:
        suggested = int(demand * 0.95)   # oversupplied: reduce to near-demand

    return max(suggested, 0)


def build_next_period_scenario(
    previous_scenario: ScenarioInput,
    previous_result: SimulationResult,
    *,
    next_period: Optional[int] = None,
    new_model_launch: Optional[bool] = None,
) -> ScenarioInput:
    """
    Build a coherent N+1 scenario from period N outcome.

    Applied rules:
    - Liquidation/withdrawal in N => production = 0 in N+1.
    - Otherwise, production is suggested from demand/service in N.
    - period increments by 1 (or uses provided next_period).
    """
    target_period = next_period if next_period is not None else previous_scenario.period + 1
    suggested = suggest_next_production(previous_scenario, previous_result)
    launch_flag = previous_scenario.new_model_launch if new_model_launch is None else new_model_launch

    return previous_scenario.model_copy(
        update={
            "period": target_period,
            "production": suggested,
            "opening_stock": previous_result.forecast_ending_stock_units,
            "new_model_launch": launch_flag,
            "previous_innovation_score": previous_result.innovation_score,
            "previous_sustainability_score": previous_result.sustainability_score,
            # New period baseline: no liquidation unless explicitly re-triggered.
            "liquidation": False,
            "withdraw_model": False,
        }
    )


# ─── Reference scenario for full-market simulation ───────────────────────────

def _make_reference_scenario(firm_key: str, segment: str, period: int) -> ScenarioInput:
    """Build a reference ScenarioInput for a competing firm in a given segment."""
    firm_cfg = MARKET_CONFIG["firms"][firm_key]
    seg_cfg = MARKET_CONFIG["segments"][segment]
    range_key = firm_cfg.get("default_range", "mid")
    range_cfg = MARKET_CONFIG["ranges"][range_key]

    # Price: segment reference price × range multiplier × period inflation
    infl = period_inflation_factor(period)
    price = seg_cfg["reference_price"] * range_cfg.get("price_multiplier", 1.0) * infl

    # Budget estimated from reference units × price
    estimated_revenue = firm_cfg["units_ref"] * price
    adjusted_budget = max(estimated_revenue, 100_000.0)
    marketing = adjusted_budget * 0.08   # 8% of budget (typical)

    return ScenarioInput(
        firm_name=firm_key,
        period=period,
        scenario_name=f"{firm_key} ref",
        model_name=f"{firm_key} produit",
        product_type="ville_quotidien",
        segment=segment,
        model_range=range_key,
        product_status="active",
        price=max(price, 100.0),
        production=firm_cfg["units_ref"],
        marketing_budget=marketing,
        adjusted_budget=adjusted_budget,
        previous_innovation_score=firm_cfg.get("base_rep", 5.0),
        previous_sustainability_score=5.0,
        competitor_attractiveness=10.0,
    )


def _make_reference_firm_template(firm_key: str, period: int) -> ScenarioInput:
    """Build a reference ScenarioInput for a firm (shared baseline for all segments)."""
    firm_cfg = MARKET_CONFIG["firms"][firm_key]
    default_segment = firm_cfg.get("default_segment", "urbains_presses")
    return _make_reference_scenario(firm_key, default_segment, period)


# ─── Full market simulation (all 9 firms, all segments) ───────────────────────

def simulate_full_market(
    period: int,
    user_firm: Optional[str],
    user_scenario: Optional[ScenarioInput],
) -> dict:
    """
    Simulate competition between all 9 firms across all 6 segments.

    When user_scenario is provided, its price/marketing/range/status apply to
    ALL segments for that firm (not just one), giving a true full-market view.
    Reference profiles are used for all competing firms.

    Returns a dict with:
      - period, year, total_market
      - firms: {firm_key: {total_sales, total_revenue, market_share, profit_estimate,
                            segments: {seg: {share, sales}}}}
      - segment_breakdown: {seg_key: {firm_key: {sales, revenue, segment_share}}}
      - segment_leaders: {seg_key: firm_key with highest share}
    """
    cfg = MARKET_CONFIG
    firms_cfg = cfg["firms"]

    firm_templates: Dict[str, ScenarioInput] = {}
    for firm_key in firms_cfg:
        if user_firm and user_scenario and firm_key == user_firm:
            firm_templates[firm_key] = user_scenario.model_copy(update={"period": period})
        else:
            firm_templates[firm_key] = _make_reference_firm_template(firm_key, period)

    unconstrained_demand: Dict[str, Dict[str, float]] = {seg: {} for seg in cfg["segments"]}
    seg_results: Dict[str, Dict[str, dict]] = {}
    segment_firm_scenarios: Dict[Tuple[str, str], ScenarioInput] = {}

    for seg_key in cfg["segments"]:
        seg_sz = segment_size(period, seg_key)
        firm_attrs: Dict[str, float] = {}

        for firm_key, template in firm_templates.items():
            seg_scenario = template.model_copy(update={"segment": seg_key, "period": period})
            segment_firm_scenarios[(seg_key, firm_key)] = seg_scenario
            firm_attrs[firm_key] = max(calc_attractiveness(seg_scenario), 0.001)

        total_attr = sum(firm_attrs.values())
        for firm_key, attr in firm_attrs.items():
            share = attr / total_attr if total_attr > 0 else 0.0
            unconstrained_demand[seg_key][firm_key] = seg_sz * share

    total_unconstrained_by_firm = {
        firm: sum(unconstrained_demand[seg][firm] for seg in cfg["segments"])
        for firm in firms_cfg
    }
    capacity_ratio_by_firm = {}
    for firm, template in firm_templates.items():
        unconstrained_total = total_unconstrained_by_firm[firm]
        capacity_ratio_by_firm[firm] = (
            min(1.0, template.production / unconstrained_total)
            if unconstrained_total > 0
            else 1.0
        )

    for seg_key in cfg["segments"]:
        seg_results[seg_key] = {}
        seg_sales_total = 0
        for firm_key in firms_cfg:
            seg_scenario = segment_firm_scenarios[(seg_key, firm_key)]
            demand = unconstrained_demand[seg_key][firm_key]
            sales = int(demand * capacity_ratio_by_firm[firm_key])
            seg_sales_total += sales
            effective_price = seg_scenario.price * (1.0 + seg_scenario.promotion_rate)
            seg_results[seg_key][firm_key] = {
                "sales": sales,
                "revenue": sales * effective_price,
                "segment_share": sales / max(seg_sales_total, 1),  # temporary, corrected below
            }
        # Correct segment shares after all firm sales are known.
        seg_sales_total = sum(seg_results[seg_key][f]["sales"] for f in firms_cfg)
        for firm_key in firms_cfg:
            seg_results[seg_key][firm_key]["segment_share"] = (
                seg_results[seg_key][firm_key]["sales"] / max(seg_sales_total, 1)
            )

    total_mkt = total_market_size(period)
    firm_totals: Dict[str, dict] = {}

    for firm_key, template in firm_templates.items():
        tot_sales = sum(seg_results[s][firm_key]["sales"] for s in seg_results)
        tot_revenue_base = sum(seg_results[s][firm_key]["revenue"] for s in seg_results)
        ref_b = max(template.adjusted_budget, 0.0)
        prem_fm = sustainability_revenue_premium_rate(template.sustainability_tranches)
        tot_revenue = tot_revenue_base * (1.0 + prem_fm)

        range_cfg = cfg["ranges"][template.model_range]
        production_cost = 0.0
        for seg_key in cfg["segments"]:
            seg_scenario = segment_firm_scenarios[(seg_key, firm_key)]
            production_cost += seg_results[seg_key][firm_key]["sales"] * get_unit_production_cost(seg_scenario)

        distribution_cost = tot_revenue_base * range_cfg["distribution_rate"]
        operating_cost = operating_cost_from_ref_budget(ref_b) + cfg["fixed_overhead"]
        aftersales_cost = aftersales_cost_from_ref_budget(ref_b)
        marketing_cost = template.marketing_budget
        rd_cost = template.rd_budget
        sustainability_cost = sustainability_cost_from_tranches(template.sustainability_tranches, ref_b)
        total_cost = (
            production_cost
            + distribution_cost
            + operating_cost
            + aftersales_cost
            + marketing_cost
            + rd_cost
            + sustainability_cost
        )
        profit_est = tot_revenue - total_cost
        margin_est = profit_est / max(tot_revenue, 1.0)

        firm_totals[firm_key] = {
            "total_sales": tot_sales,
            "total_revenue": tot_revenue,
            "total_revenue_before_premium": tot_revenue_base,
            "sustainability_revenue_premium_rate": prem_fm,
            "market_share": tot_sales / max(total_mkt, 1),
            "profit_estimate": profit_est,
            "margin_estimate": margin_est,
            "total_cost_estimate": total_cost,
            "demand_unconstrained": total_unconstrained_by_firm[firm_key],
            "capacity_ratio": capacity_ratio_by_firm[firm_key],
            "segments": {
                seg: {
                    "share": seg_results[seg][firm_key]["segment_share"],
                    "sales": seg_results[seg][firm_key]["sales"],
                }
                for seg in seg_results
            },
        }

    # Identify segment leaders
    segment_leaders = {
        seg_key: max(
            seg_results[seg_key].items(),
            key=lambda x: x[1]["segment_share"],
        )[0]
        for seg_key in seg_results
    }

    return {
        "period": period,
        "year": period_to_year(period),
        "total_market": total_mkt,
        "firms": firm_totals,
        "segment_breakdown": seg_results,
        "segment_leaders": segment_leaders,
        "user_firm": user_firm,
    }


def simulate_full_market_all_periods(
    user_firm: Optional[str],
    user_scenario_template: Optional[ScenarioInput],
) -> list:
    """
    Run simulate_full_market for all 8 periods.
    Returns a list of 8 market result dicts.
    """
    results = []
    for p in range(1, 9):
        if user_scenario_template:
            scenario_p = user_scenario_template.model_copy(update={"period": p})
        else:
            scenario_p = None
        results.append(simulate_full_market(p, user_firm, scenario_p))
    return results


# ─── Interpretations ─────────────────────────────────────────────────────────

def _build_interpretations(
    s: ScenarioInput,
    demand: float,
    sales: int,
    revenue: float,
    profit: float,
    margin: float,
    service_rate: float,
    marketing_max: float,
    innovation_score: float,
    sustainability_score: float,
    unit_cost: float,
) -> List[str]:
    interp = []
    cfg = MARKET_CONFIG["constraints"]

    # Profitability vs target zone
    if margin >= cfg["profit_target_max"]:
        interp.append(f"Excellente rentabilite : marge de {margin*100:.1f}% - au-dessus de la zone cible (5-10%).")
    elif margin >= cfg["profit_target_min"]:
        interp.append(f"Bonne rentabilite : marge de {margin*100:.1f}% dans la zone cible (5-10%).")
    elif margin >= cfg["min_profit_rate"]:
        interp.append(f"Rentabilite correcte mais sous la cible ({margin*100:.1f}% < 5%). Chercher a optimiser le mix.")
    elif margin >= 0:
        interp.append(f"Rentabilite insuffisante ({margin*100:.1f}%) : en dessous du seuil reglementaire de 2 %.")
    else:
        interp.append(f"Scenario deficitaire : perte de {-profit:,.0f} $. Revoir la strategie de prix ou de couts.")

    # Price vs COGS hint
    effective_price = s.price * (1.0 + s.promotion_rate)
    cogs_ratio = MARKET_CONFIG["cogs_ratios"][s.model_range]
    dist_pct = MARKET_CONFIG["ranges"][s.model_range]["distribution_rate"]
    cref = MARKET_CONFIG["constraints"]
    sav_pct_b = cref["aftersales_ref_budget_pct"]
    op_pct_b = cref["operating_ref_budget_pct"]
    interp.append(
        f"Structure des couts (gamme {MARKET_CONFIG['ranges'][s.model_range]['label']}) : "
        f"COGS {cogs_ratio*100:.0f}% du prix net, distribution {dist_pct*100:.0f}% du CA hors prime ; "
        f"SAV {sav_pct_b*100:.0f}% + frais generaux {op_pct_b*100:.0f}% du budget ajuste ({s.adjusted_budget:,.0f} $)."
    )
    prem_rt = sustainability_revenue_premium_rate(s.sustainability_tranches)
    if prem_rt > 0:
        interp.append(
            f"Prime CA durabilite (tranches={s.sustainability_tranches}) : +{prem_rt*100:.2f}% "
            f"— sans effet sur prix affiche ni demande."
        )

    # Marketing intensity vs ROI (target 0-10% of revenue)
    mkt_over_rev = s.marketing_budget / max(revenue, 1.0) if revenue > 0 else 0
    if s.marketing_budget >= marketing_max * 0.95:
        interp.append("Budget marketing au maximum reglementaire : toute hausse supplementaire est impossible.")
    elif mkt_over_rev > 0.10:
        interp.append(
            f"Budget marketing eleve ({mkt_over_rev*100:.1f}% du CA) — cible : 0-10 % du CA pour un bon ROI."
        )
    elif s.marketing_budget == 0:
        interp.append("Aucun budget marketing : visibilite tres reduite, parts de marche a risque.")
    else:
        interp.append(
            f"Budget marketing : {mkt_over_rev*100:.1f}% du CA "
            f"({'dans la cible' if mkt_over_rev <= 0.10 else 'au-dessus de la cible'} 0-10%)."
        )

    # R&D / innovation
    if s.rd_budget > 0:
        interp.append(
            f"Investissement R&D actif ({s.rd_budget:,.0f} $) : score innovation prevu a {innovation_score:.1f}/10."
        )
    else:
        interp.append(
            f"Aucun investissement R&D : score innovation en declin (prevu {innovation_score:.1f}/10)."
        )

    # Sustainability
    if s.sustainability_investment > 0:
        interp.append(
            f"Investissement durabilite ({s.sustainability_investment:,.0f} $) : "
            f"impact sur les couts a court terme, benefice image long terme."
        )

    # Service rate
    if service_rate < 0.70:
        interp.append(
            f"Taux de service critique ({service_rate*100:.0f}%) : demande depasse fortement la capacite."
        )
    elif service_rate < 0.90:
        interp.append(
            f"Taux de service moyen ({service_rate*100:.0f}%) : envisager d'augmenter la production."
        )

    # Promotion scenario hint
    promo_pct = abs(s.promotion_rate) * 100
    if s.liquidation:
        interp.append(
            f"Scenario liquidation (-{promo_pct:.0f}%) : production de la periode suivante = 0 obligatoire."
        )
    elif s.promotion_rate < 0:
        interp.append(
            f"Promotion de -{promo_pct:.0f}% appliquee : impact direct sur la marge brute."
        )

    # Product lifecycle
    status_msgs = {
        "pre_launch":  "Produit en pre-lancement : ventes limitees a 1,000-2,000 unites recommandees.",
        "withdrawal":  "Produit en retrait : ventes declinantes, planifier le successeur.",
        "development": "Produit en developpement : aucune vente generee cette periode.",
        "inactive":    "Produit inactif : aucune vente generee.",
    }
    if s.product_status in status_msgs:
        interp.append(status_msgs[s.product_status])

    # Market year info
    year = period_to_year(s.period)
    mkt_size = total_market_size(s.period)
    interp.append(
        f"Annee simulee : {year} — taille totale du marche : {mkt_size:,.0f} unites."
    )

    return interp


# ─── Main simulation function ─────────────────────────────────────────────────

def simulate(scenario: ScenarioInput) -> SimulationResult:
    cfg = MARKET_CONFIG
    range_cfg = cfg["ranges"][scenario.model_range]

    # ── Validation alerts ────────────────────────────────────────────────────
    raw_alerts = validate_scenario(scenario)
    alerts = [msg for sev, msg in raw_alerts if sev == "error"]
    warnings = [msg for sev, msg in raw_alerts if sev == "warning"]
    infos = [msg for sev, msg in raw_alerts if sev == "info"]
    all_alerts = alerts + warnings + infos
    is_valid = len(alerts) == 0

    # ── Caps ────────────────────────────────────────────────────────────────
    marketing_max = scenario.adjusted_budget * cfg["constraints"]["marketing_max_pct"]

    # ── Attractiveness & demand ──────────────────────────────────────────────
    attractiveness = calc_attractiveness(scenario)

    total_attr = attractiveness + scenario.competitor_attractiveness
    mkt_share_seg = attractiveness / total_attr if total_attr > 0 else 0.0

    seg_sz = segment_size(scenario.period, scenario.segment)
    demand = mkt_share_seg * seg_sz

    stock_available = scenario.opening_stock + scenario.production
    sales = min(int(demand), stock_available)
    sales, was_capped, cap_msg = apply_new_product_first_year_sales_cap(
        sales,
        is_new_product_first_year=(scenario.new_model_launch or scenario.product_status == "pre_launch"),
        min_units=MARKET_CONFIG["constraints"]["new_product_min_units"],
        max_units=MARKET_CONFIG["constraints"]["new_product_max_units"],
    )
    if was_capped:
        all_alerts.append(cap_msg)
    sales = min(sales, stock_available)
    service_rate = sales / max(demand, 1.0)

    # ── Financial calculations (COGS + budget de référence pour SAV / frais généraux) ─
    effective_price = scenario.price * (1.0 + scenario.promotion_rate)
    base_revenue = sales * effective_price
    prem_rt = sustainability_revenue_premium_rate(scenario.sustainability_tranches)
    revenue = base_revenue * (1.0 + prem_rt)

    unit_cost = get_unit_production_cost(scenario)      # price * cogs_ratio
    production_cost = sales * unit_cost                  # = base_revenue * cogs_ratio
    gross_profit = base_revenue - production_cost
    stock_diag = build_stock_production_diagnostics(
        demand=demand,
        opening_stock=scenario.opening_stock,
        production=scenario.production,
        sales=sales,
        unit_cost=unit_cost,
        gross_profit=gross_profit,
    )
    inventory_carrying_cost = stock_diag.estimated_storage_cost
    distribution_cost = base_revenue * range_cfg["distribution_rate"]
    marketing_cost = scenario.marketing_budget
    rd_cost = scenario.rd_budget
    ref_b = max(scenario.adjusted_budget, 0.0)
    operating_cost = operating_cost_from_ref_budget(ref_b) + cfg["fixed_overhead"]
    aftersales_cost = aftersales_cost_from_ref_budget(ref_b)
    sustainability_cost = sustainability_cost_from_tranches(
        scenario.sustainability_tranches, ref_b
    )

    total_cost = (
        production_cost
        + distribution_cost
        + marketing_cost
        + rd_cost
        + operating_cost
        + aftersales_cost
        + sustainability_cost
        + inventory_carrying_cost
    )

    profit = revenue - total_cost
    margin = profit / max(revenue, 1.0)

    carry_rate = MARKET_CONFIG["constraints"].get("inventory_carrying_rate", 0.025)
    for sev, msg in stock_diag.alert_severities:
        if sev in ("error", "warning"):
            tagged = f"[Stock] {msg}"
            if tagged not in all_alerts:
                all_alerts.append(tagged)

    # Profit constraint check
    min_profit = revenue * cfg["constraints"]["min_profit_rate"]
    if revenue > 0 and profit < min_profit:
        all_alerts.append(
            f"Profit ({profit:,.0f} $, {margin*100:.1f}%) inferieur au seuil minimal de 2 % du revenu "
            f"({min_profit:,.0f} $)."
        )
        is_valid = False
    if profit < 0:
        all_alerts.append(f"Scenario deficitaire : perte nette de {-profit:,.0f} $.")
        is_valid = False

    # ── Market shares ─────────────────────────────────────────────────────────
    market_share_segment = sales / max(seg_sz, 1.0)
    market_share_total = sales / max(total_market_size(scenario.period), 1.0)

    # ── Scores ───────────────────────────────────────────────────────────────
    innovation_score, sustainability_score = calc_scores(scenario)

    # ── Interpretations ──────────────────────────────────────────────────────
    interpretations = _build_interpretations(
        s=scenario,
        demand=demand,
        sales=sales,
        revenue=revenue,
        profit=profit,
        margin=margin,
        service_rate=service_rate,
        marketing_max=marketing_max,
        innovation_score=innovation_score,
        sustainability_score=sustainability_score,
        unit_cost=unit_cost,
    )
    if demand > 0:
        interpretations.extend(
            [
                (
                    f"Stock disponible prévu : {stock_diag.stock_available:,} u. "
                    f"(départ {scenario.opening_stock:,} + production {scenario.production:,})."
                ),
                (
                    f"Taux de couverture prévu : {stock_diag.coverage_rate * 100:.1f} % — "
                    f"ventes perdues estimées : {stock_diag.lost_sales_units:,.1f} u. — "
                    f"stock final prévu : {stock_diag.ending_stock_units:,} u."
                ),
                (
                    f"Coût de stockage estimé : {inventory_carrying_cost:,.0f} $ "
                    f"(stock final × coût unitaire × {carry_rate * 100:.1f} %)."
                ),
            ]
        )
        interpretations.extend(stock_diag.short_messages)

    # ── Extended business indicators ──────────────────────────────────────────
    profit_rate = profit / max(revenue, 1.0)
    consistency_status, consistency_msg = check_price_range_consistency(scenario.price, scenario.model_range)
    if consistency_status != "ok":
        all_alerts.append(consistency_msg)

    mkt_eff = marketing_efficiency(sales, scenario.marketing_budget)
    prod_eff = production_efficiency(sales, scenario.production)
    next_prod, next_prod_expl = recommend_next_period_production(
        sales_n=sales,
        stock_final_n=max(stock_available - sales, 0),
        market_trend=MARKET_CONFIG["growth_rate"],
        product_status=scenario.product_status,
        adjustment_factor=1.10,
    )
    if scenario.liquidation:
        next_prod = 0
        next_prod_expl = "Mode liquidation: production N+1 forcee a 0."
    interpretations.append(next_prod_expl)
    cfg_w = MARKET_CONFIG["constraints"]
    w_ok = True
    if scenario.withdraw_model:
        if scenario.total_withdrawals_used >= cfg_w["withdrawal_max_total"]:
            w_ok = False
            all_alerts.append(
                f"Retrait bloque : plafond de {cfg_w['withdrawal_max_total']} retraits atteint "
                f"({scenario.total_withdrawals_used} deja utilises)."
            )
        elif scenario.last_withdrawal_period > 0 and (
            scenario.period - scenario.last_withdrawal_period < cfg_w["withdrawal_min_periods_between"]
        ):
            w_ok = False
            all_alerts.append(
                f"Retrait bloque : delai minimum {cfg_w['withdrawal_min_periods_between']} periodes "
                f"non respecte (dernier retrait periode {scenario.last_withdrawal_period})."
            )
        else:
            w_ok, w_msg = check_withdrawal_limits(
                scenario.firm_name,
                scenario.period,
                {scenario.firm_name: [scenario.last_withdrawal_period] if scenario.last_withdrawal_period else []},
                max_total=cfg_w["withdrawal_max_total"],
                min_period_gap=cfg_w["withdrawal_min_periods_between"],
            )
            if not w_ok:
                all_alerts.append(w_msg)

    baseline_summary = build_2026_baseline_summary(scenario, SimulationResult(
        firm_name=scenario.firm_name,
        period=scenario.period,
        scenario_name=scenario.scenario_name,
        demand=demand,
        sales=sales,
        service_rate=service_rate,
        revenue=revenue,
        base_revenue_before_premium=base_revenue,
        sustainability_revenue_premium_rate=prem_rt,
        production_cost=production_cost,
        distribution_cost=distribution_cost,
        marketing_cost=marketing_cost,
        rd_cost=rd_cost,
        operating_cost=operating_cost,
        aftersales_cost=aftersales_cost,
        sustainability_cost=sustainability_cost,
        total_cost=total_cost,
        profit=profit,
        margin=margin,
        market_share=market_share_total,
        market_share_segment=market_share_segment,
        innovation_score=innovation_score,
        sustainability_score=sustainability_score,
        attractiveness=attractiveness,
        is_valid=is_valid,
        alerts=[],
        interpretations=[],
    ))

    return SimulationResult(
        firm_name=scenario.firm_name,
        period=scenario.period,
        scenario_name=scenario.scenario_name,
        demand=demand,
        sales=sales,
        service_rate=service_rate,
        revenue=revenue,
        base_revenue_before_premium=base_revenue,
        sustainability_revenue_premium_rate=prem_rt,
        production_cost=production_cost,
        distribution_cost=distribution_cost,
        marketing_cost=marketing_cost,
        rd_cost=rd_cost,
        operating_cost=operating_cost,
        aftersales_cost=aftersales_cost,
        sustainability_cost=sustainability_cost,
        total_cost=total_cost,
        profit=profit,
        margin=margin,
        market_share=market_share_total,
        market_share_segment=market_share_segment,
        innovation_score=innovation_score,
        sustainability_score=sustainability_score,
        attractiveness=attractiveness,
        is_valid=is_valid,
        alerts=all_alerts,
        interpretations=interpretations,
        profit_rate=profit_rate,
        profit_rate_status=profit_rate_status(profit_rate),
        price_range_consistency_status=consistency_status,
        marketing_efficiency=mkt_eff,
        marketing_marginal_profit_delta=0.0,
        production_efficiency=prod_eff,
        next_period_recommended_production=next_prod,
        new_product_first_year_flag=(scenario.new_model_launch or scenario.product_status == "pre_launch"),
        withdrawal_limit_status="ok" if w_ok else "blocked",
        liquidation_next_period_production_flag=liquidation_next_period_production_flag(
            scenario.product_status, scenario.liquidation
        ),
        baseline_2026_indicator=baseline_summary["baseline_market_share_2026"] * 100,
        opening_stock=scenario.opening_stock,
        stock_available_units=stock_diag.stock_available,
        forecast_coverage_rate=stock_diag.coverage_rate,
        forecast_lost_sales_units=stock_diag.lost_sales_units,
        forecast_ending_stock_units=stock_diag.ending_stock_units,
        inventory_carrying_cost=inventory_carrying_cost,
        stock_coverage_level=stock_diag.coverage_level,
    )


# ─── Multi-scenario runner ────────────────────────────────────────────────────

def simulate_multi(scenarios: list) -> list:
    return [simulate(s) for s in scenarios]
