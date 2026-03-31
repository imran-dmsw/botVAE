"""
Core simulation engine for the VAE marketing simulation.

Demand model (attraction / logit):
  attractiveness_i = base * price_effect * marketing_effect * status_factor
                     * innovation_bonus * sustainability_bonus
  market_share_seg  = attractiveness_i / (attractiveness_i + competitor_attractiveness)
  demand            = market_share_seg * segment_size
  sales             = min(demand, production)

Market growth (two-phase):
  Phase 1 — periods 1-9  (2026-2034): +15%/yr units
  Phase 2 — periods 10-15 (2035-2040): +17.5%/yr units
"""
import math
from typing import List

from config.market_config import MARKET_CONFIG
from engine.models import ScenarioInput, SimulationResult
from engine.rules import validate_scenario


# ─── Market size helpers ──────────────────────────────────────────────────────

def total_market_size(period: int) -> float:
    """Return total market size (units) for the given period using two-phase growth."""
    cfg = MARKET_CONFIG
    base = cfg["base_market_size"]
    g1 = cfg["growth_rate_phase1"]
    g2 = cfg["growth_rate_phase2"]
    change = cfg["phase_change_period"]

    if period <= change:
        return base * ((1 + g1) ** (period - 1))
    else:
        size_at_change = base * ((1 + g1) ** (change - 1))
        return size_at_change * ((1 + g2) ** (period - change))


def segment_size(period: int, segment: str) -> float:
    share = MARKET_CONFIG["segments"][segment]["share"]
    return total_market_size(period) * share


def period_to_year(period: int) -> int:
    return MARKET_CONFIG["base_year"] + (period - 1)


# ─── Attractiveness ───────────────────────────────────────────────────────────

def calc_attractiveness(s: ScenarioInput) -> float:
    cfg = MARKET_CONFIG
    seg_cfg = cfg["segments"][s.segment]
    range_cfg = cfg["ranges"][s.model_range]
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


# ─── Unit production cost ─────────────────────────────────────────────────────

def get_unit_production_cost(s: ScenarioInput) -> float:
    """Return unit production cost: product_type base cost if available, else range fallback."""
    pt_cfg = MARKET_CONFIG["product_types"].get(s.product_type)
    if pt_cfg:
        return float(pt_cfg["base_cost"])
    return float(MARKET_CONFIG["ranges"][s.model_range]["unit_production_cost"])


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

    # Profitability
    if margin >= 0.20:
        interp.append(f"Excellente rentabilite : marge de {margin*100:.1f}% tres au-dessus du seuil minimal.")
    elif margin >= 0.10:
        interp.append(f"Bonne rentabilite : marge de {margin*100:.1f}%, au-dessus de la moyenne.")
    elif margin >= cfg["min_profit_rate"]:
        interp.append(f"Rentabilite correcte mais faible ({margin*100:.1f}%). Surveiller les couts.")
    elif margin >= 0:
        interp.append(f"Rentabilite insuffisante ({margin*100:.1f}%) : en dessous du seuil reglementaire de 2 %.")
    else:
        interp.append(f"Scenario deficitaire : perte de {-profit:,.0f} $. Revoir la strategie de prix ou de couts.")

    # Price vs cost hint
    effective_price = s.price * (1.0 + s.promotion_rate)
    range_cfg = MARKET_CONFIG["ranges"][s.model_range]
    target_price = unit_cost + range_cfg["target_margin_per_unit"]
    if effective_price < unit_cost * 1.05:
        interp.append(
            f"Attention : prix effectif ({effective_price:,.0f} $) proche ou inferieur au cout unitaire "
            f"({unit_cost:,.0f} $). Marge brute tres reduite."
        )
    elif effective_price < target_price:
        interp.append(
            f"Prix effectif ({effective_price:,.0f} $) inferieur au prix cible gamme "
            f"({target_price:,.0f} $, soit cout + {range_cfg['target_margin_per_unit']:,} $). "
            f"Envisager une hausse de prix."
        )

    # Marketing intensity
    if s.marketing_budget >= marketing_max * 0.95:
        interp.append("Budget marketing au maximum reglementaire : toute hausse supplementaire est impossible.")
    elif s.marketing_budget >= marketing_max * 0.75:
        interp.append("Budget marketing eleve : effort commercial fort, surveiller l'impact sur la rentabilite.")
    elif s.marketing_budget == 0:
        interp.append("Aucun budget marketing : visibilite tres reduite, parts de marche a risque.")

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
            f"impact sur les couts a court terme, benefice image et fidelite long terme."
        )

    # Service rate
    if service_rate < 0.70:
        interp.append(
            f"Taux de service critique ({service_rate*100:.0f}%) : la demande depasse fortement la capacite, "
            f"risque majeur de perte de clients au profit des concurrents."
        )
    elif service_rate < 0.90:
        interp.append(
            f"Taux de service moyen ({service_rate*100:.0f}%) : demande partiellement non satisfaite, "
            f"envisager d'augmenter la production."
        )

    # Product lifecycle
    status_msgs = {
        "pre_launch":  "Produit en phase de pre-lancement : contribution aux ventes faible, phase de montee en puissance.",
        "withdrawal":  "Produit en phase de retrait : ventes declinantes, planifier le successeur.",
        "development": "Produit en developpement : aucune vente generee cette periode.",
        "inactive":    "Produit inactif : aucune vente generee.",
    }
    if s.product_status in status_msgs:
        interp.append(status_msgs[s.product_status])

    # New model launch
    if s.new_model_launch:
        interp.append("Lancement d'un nouveau modele : boost innovation active, rentabilite court terme reduite.")

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
    seg_cfg = cfg["segments"][scenario.segment]

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

    # Sales capped by production
    sales = min(int(demand), scenario.production)
    service_rate = sales / max(demand, 1.0)

    # Production alerts
    if scenario.production < demand * 0.75 and demand > 0:
        all_alerts.append(
            f"Production insuffisante : demande estimee {demand:,.0f} unites, "
            f"production {scenario.production:,} ({service_rate*100:.0f}% couvert)."
        )
    if scenario.production > demand * 1.6 and demand > 0:
        unsold = scenario.production - int(demand)
        all_alerts.append(
            f"Production excessive : environ {unsold:,} unites non vendues - risque de surstockage."
        )

    # ── Financial calculations ────────────────────────────────────────────────
    effective_price = scenario.price * (1.0 + scenario.promotion_rate)
    revenue = sales * effective_price

    unit_cost = get_unit_production_cost(scenario)
    production_cost = sales * unit_cost
    distribution_cost = revenue * range_cfg["distribution_rate"]
    marketing_cost = scenario.marketing_budget
    rd_cost = scenario.rd_budget
    operating_cost = revenue * range_cfg["operating_rate"] + cfg["fixed_overhead"]
    aftersales_cost = revenue * range_cfg["aftersales_rate"]
    sustainability_cost = scenario.sustainability_investment

    total_cost = (
        production_cost
        + distribution_cost
        + marketing_cost
        + rd_cost
        + operating_cost
        + aftersales_cost
        + sustainability_cost
    )

    profit = revenue - total_cost
    margin = profit / max(revenue, 1.0)

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

    return SimulationResult(
        firm_name=scenario.firm_name,
        period=scenario.period,
        scenario_name=scenario.scenario_name,
        demand=demand,
        sales=sales,
        service_rate=service_rate,
        revenue=revenue,
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
    )


# ─── Multi-scenario runner ────────────────────────────────────────────────────

def simulate_multi(scenarios: list) -> list:
    return [simulate(s) for s in scenarios]
