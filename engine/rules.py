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
            f"Budget marketing ({scenario.marketing_budget:,.0f} $) depasse le plafond de 15 % "
            f"du budget ajuste ({mkt_max:,.0f} $).",
        ))

    rd_max = scenario.adjusted_budget * cfg["rd_max_pct"]
    if scenario.rd_budget > rd_max:
        alerts.append((
            "error",
            f"Budget R&D ({scenario.rd_budget:,.0f} $) depasse le plafond de 8 % "
            f"du budget ajuste ({rd_max:,.0f} $).",
        ))

    # ── Promotion limits ─────────────────────────────────────────────────────
    if scenario.liquidation:
        if scenario.promotion_rate < cfg["promo_liquidation_max"]:
            alerts.append((
                "error",
                f"Promotion de liquidation ({scenario.promotion_rate*100:.1f}%) depasse le maximum "
                f"autorise de -10 %. Reduction maximale en liquidation : 10 %.",
            ))
    else:
        if scenario.promotion_rate < cfg["promo_standard_max"]:
            alerts.append((
                "error",
                f"Promotion standard ({scenario.promotion_rate*100:.1f}%) depasse le maximum "
                f"autorise de -5 %. Utilisez le mode liquidation pour aller jusqu'a -10 %.",
            ))

    # ── Price vs range coherence (with severity threshold) ───────────────────
    price_min, price_max = ranges_cfg[scenario.model_range]["price_range"]
    range_label = MARKET_CONFIG["ranges"][scenario.model_range]["label"]

    if not (price_min <= scenario.price <= price_max):
        # Compute deviation from nearest bound
        if scenario.price < price_min:
            deviation = (price_min - scenario.price) / price_min
        else:
            deviation = (scenario.price - price_max) / price_max

        if deviation > cfg["price_coherence_error_pct"]:
            severity = "error"
            detail = f"Ecart de {deviation*100:.0f}% > seuil d'erreur ({cfg['price_coherence_error_pct']*100:.0f}%)."
        elif deviation > cfg["price_coherence_warning_pct"]:
            severity = "warning"
            detail = f"Ecart de {deviation*100:.0f}% > seuil d'alerte ({cfg['price_coherence_warning_pct']*100:.0f}%)."
        else:
            severity = "warning"
            detail = f"Ecart de {deviation*100:.0f}% (dans la tolerance de 10%)."

        alerts.append((
            severity,
            f"Prix ({scenario.price:,.0f} $) incohérent avec la gamme '{range_label}' "
            f"(plage recommandee : {price_min:,} - {price_max:,} $). {detail}",
        ))

    # ── Liquidation → next period production = 0 ────────────────────────────
    if scenario.liquidation:
        alerts.append((
            "info",
            "Mode liquidation : la production doit etre mise a 0 a la periode suivante "
            "(regle : aucune fabrication apres liquidation d'un modele).",
        ))

    # ── Production constraints ────────────────────────────────────────────────
    if scenario.production == 0 and scenario.product_status == "active":
        alerts.append((
            "error",
            "Production nulle pour un produit actif : aucune vente possible.",
        ))

    # ── New product launch: 1,000-2,000 units in first year ──────────────────
    if scenario.new_model_launch or scenario.product_status == "pre_launch":
        min_u = cfg["new_product_min_units"]
        max_u = cfg["new_product_max_units"]
        if scenario.production < min_u:
            alerts.append((
                "error",
                f"Nouveau produit : production ({scenario.production:,}) trop faible. "
                f"La premiere annee exige entre {min_u:,} et {max_u:,} unites vendues.",
            ))
        elif scenario.production > max_u:
            alerts.append((
                "warning",
                f"Nouveau produit : production ({scenario.production:,}) superieure au plafond "
                f"recommande de {max_u:,} unites pour la 1re annee.",
            ))

    # ── Withdrawal limit rules ───────────────────────────────────────────────
    if scenario.withdraw_model:
        max_total = cfg["withdrawal_max_total"]
        min_gap = cfg["withdrawal_min_periods_between"]

        if scenario.total_withdrawals_used >= max_total:
            alerts.append((
                "error",
                f"Limite de retraits atteinte : {max_total} retraits maximum sur la simulation. "
                f"Vous en avez deja utilise {scenario.total_withdrawals_used}.",
            ))
        elif scenario.last_withdrawal_period > 0:
            gap = scenario.period - scenario.last_withdrawal_period
            if gap < min_gap:
                alerts.append((
                    "error",
                    f"Delai entre retraits insuffisant : minimum {min_gap} periodes requises "
                    f"(dernier retrait P{scenario.last_withdrawal_period}, periode actuelle P{scenario.period}, "
                    f"ecart = {gap} periode(s)).",
                ))

        remaining = max_total - scenario.total_withdrawals_used - (1 if scenario.withdraw_model else 0)
        if scenario.total_withdrawals_used < max_total:
            alerts.append((
                "info",
                f"Retrait planifie. Retraits restants apres cette periode : {remaining}/{max_total}.",
            ))

    # ── Product status / commercial consistency ──────────────────────────────
    if scenario.product_status in ("development", "inactive"):
        alerts.append((
            "info",
            f"Produit en statut '{scenario.product_status}' : aucune vente directe generee cette periode.",
        ))

    if scenario.liquidation and scenario.product_status not in ("withdrawal", "active"):
        alerts.append((
            "warning",
            "Mode liquidation active mais le produit n'est pas en statut 'actif' ou 'retrait'.",
        ))

    # ── Marketing channel total vs declared budget ────────────────────────────
    ch_total = scenario.marketing_channels.total()
    if ch_total > 0 and abs(ch_total - scenario.marketing_budget) > scenario.marketing_budget * 0.01:
        alerts.append((
            "warning",
            f"La somme des canaux marketing ({ch_total:,.0f} $) ne correspond pas au budget total "
            f"declare ({scenario.marketing_budget:,.0f} $). Les canaux ont ete normalises automatiquement.",
        ))

    # ── R&D: projects without budget ────────────────────────────────────────
    if scenario.rd_projects > 0 and scenario.rd_budget == 0:
        alerts.append((
            "warning",
            f"{scenario.rd_projects} projet(s) R&D declare(s) mais aucun budget R&D alloue.",
        ))

    if scenario.new_model_launch and scenario.rd_budget == 0:
        alerts.append((
            "warning",
            "Lancement d'un nouveau modele declare sans budget R&D : l'effet innovation sera nul.",
        ))

    # ── Period logic ─────────────────────────────────────────────────────────
    if scenario.period == 1 and scenario.previous_innovation_score != 5.0:
        alerts.append((
            "info",
            "Periode 1 : les scores initiaux sont normalement a 5.0. "
            "Verifiez si vous souhaitez personnaliser les scores de depart.",
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
