"""
Business rules validation for the VAE simulation.
All constraint checks return a list of (severity, message) tuples.
severity: "error" | "warning" | "info"
"""
from typing import List, Tuple
from config.market_config import MARKET_CONFIG

Alert = Tuple[str, str]   # (severity, message)


def validate_scenario(scenario) -> List[Alert]:
    """Run all business rule checks against a ScenarioInput. Returns list of alerts."""
    alerts: List[Alert] = []
    cfg = MARKET_CONFIG["constraints"]
    ranges_cfg = MARKET_CONFIG["ranges"]

    # ── Budget caps ──────────────────────────────────────────────────────────
    mkt_max = scenario.adjusted_budget * cfg["marketing_max_pct"]
    if scenario.marketing_budget > mkt_max:
        alerts.append((
            "error",
            f"Budget marketing ({scenario.marketing_budget:,.0f} $) dépasse le plafond de 15 % "
            f"du budget ajusté ({mkt_max:,.0f} $).",
        ))

    rd_max = scenario.adjusted_budget * cfg["rd_max_pct"]
    if scenario.rd_budget > rd_max:
        alerts.append((
            "error",
            f"Budget R&D ({scenario.rd_budget:,.0f} $) dépasse le plafond de 8 % "
            f"du budget ajusté ({rd_max:,.0f} $).",
        ))

    # ── Promotion limits ─────────────────────────────────────────────────────
    if scenario.liquidation:
        if scenario.promotion_rate < cfg["promo_liquidation_max"]:
            alerts.append((
                "error",
                f"Promotion de liquidation ({scenario.promotion_rate*100:.1f}%) dépasse le maximum autorisé de -20 %.",
            ))
    else:
        if scenario.promotion_rate < cfg["promo_standard_max"]:
            alerts.append((
                "error",
                f"Promotion standard ({scenario.promotion_rate*100:.1f}%) dépasse le maximum autorisé de -5 %. "
                f"Utilisez le mode liquidation pour aller au-delà.",
            ))

    # ── Price vs range coherence ─────────────────────────────────────────────
    price_min, price_max = ranges_cfg[scenario.model_range]["price_range"]
    if not (price_min <= scenario.price <= price_max):
        alerts.append((
            "warning",
            f"Prix ({scenario.price:,.0f} $) incohérent avec la gamme "
            f"'{MARKET_CONFIG['ranges'][scenario.model_range]['label']}' "
            f"(plage recommandée : {price_min:,} – {price_max:,} $).",
        ))

    # ── Production ───────────────────────────────────────────────────────────
    if scenario.production == 0 and scenario.product_status == "active":
        alerts.append((
            "error",
            "Production nulle pour un produit actif : aucune vente possible.",
        ))

    # ── Product status / commercial consistency ──────────────────────────────
    if scenario.product_status in ("development", "inactive"):
        alerts.append((
            "info",
            f"Produit en statut '{scenario.product_status}' : aucune vente directe générée cette période.",
        ))

    if scenario.liquidation and scenario.product_status not in ("withdrawal", "active"):
        alerts.append((
            "warning",
            "Mode liquidation activé mais le produit n'est pas en statut 'actif' ou 'retrait'.",
        ))

    if scenario.withdraw_model and scenario.product_status == "active":
        alerts.append((
            "info",
            "Retrait planifié : le produit passera en statut 'retrait' à la prochaine période.",
        ))

    # ── Marketing channel total vs declared budget ────────────────────────────
    ch_total = scenario.marketing_channels.total()
    if ch_total > 0 and abs(ch_total - scenario.marketing_budget) > scenario.marketing_budget * 0.01:
        alerts.append((
            "warning",
            f"La somme des canaux marketing ({ch_total:,.0f} $) ne correspond pas au budget total "
            f"déclaré ({scenario.marketing_budget:,.0f} $). Les canaux ont été normalisés automatiquement.",
        ))

    # ── R&D: projects without budget ────────────────────────────────────────
    if scenario.rd_projects > 0 and scenario.rd_budget == 0:
        alerts.append((
            "warning",
            f"{scenario.rd_projects} projet(s) R&D déclaré(s) mais aucun budget R&D alloué.",
        ))

    if scenario.new_model_launch and scenario.rd_budget == 0:
        alerts.append((
            "warning",
            "Lancement d'un nouveau modèle déclaré sans budget R&D : l'effet innovation sera nul.",
        ))

    # ── Period logic ─────────────────────────────────────────────────────────
    if scenario.period == 1 and scenario.previous_innovation_score != 5.0:
        alerts.append((
            "info",
            "Période 1 : les scores initiaux sont normalement à 5.0. "
            "Vérifiez si vous souhaitez personnaliser les scores de départ.",
        ))

    return alerts


def get_budget_caps(adjusted_budget: float) -> dict:
    """Return the maximum allowed budgets for marketing and R&D."""
    cfg = MARKET_CONFIG["constraints"]
    return {
        "marketing_max": adjusted_budget * cfg["marketing_max_pct"],
        "rd_max": adjusted_budget * cfg["rd_max_pct"],
        "marketing_pct": cfg["marketing_max_pct"],
        "rd_pct": cfg["rd_max_pct"],
    }


def is_scenario_feasible(scenario) -> bool:
    """Return True if no error-level alerts exist."""
    alerts = validate_scenario(scenario)
    return not any(sev == "error" for sev, _ in alerts)
