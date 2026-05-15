"""
Business rules validation for the VAE simulation.
All constraint checks return a list of (severity, message) tuples.
severity: "error" | "warning" | "info"
"""
from typing import List, Tuple

from config.market_config import MARKET_CONFIG
from engine.budget_allocation import firm_rd_allowed_pcts
from rules.price_rules import check_price_range_consistency
from rules.promo_rules import validate_promo_rate
from rules.withdrawal_rules import check_withdrawal_limits

Alert = Tuple[str, str]   # (severity, message)


def validate_scenario(scenario) -> List[Alert]:
    """Run all business rule checks against a ScenarioInput. Returns list of alerts."""
    alerts: List[Alert] = []
    cfg = MARKET_CONFIG["constraints"]

    # ── R&D : interdit en période 1 (lancement effectif à partir de P2) ───────
    if scenario.period == 1 and scenario.rd_budget > 0:
        alerts.append((
            "error",
            "Budget R&D en periode 1 : la regle chiffrier impose un lancement R&D a partir de la periode 2.",
        ))

    # ── Marketing : P2+ minimum 3 % du budget ajusté (si budget marketing > 0) ─
    mkt_min = scenario.adjusted_budget * cfg.get("marketing_min_pct", 0.0)
    if scenario.period >= 2 and scenario.marketing_budget > 0 and scenario.marketing_budget + 1e-6 < mkt_min:
        alerts.append((
            "warning",
            f"Periode {scenario.period} : marketing ({scenario.marketing_budget:,.0f} $) sous le plancher "
            f"P2+ ({cfg.get('marketing_min_pct', 0.0)*100:.0f}% du budget ajuste = {mkt_min:,.0f} $).",
        ))

    # ── Production active (hors lancement) : plage chiffrier 1 500–3 000 u. ─
    pmin = int(cfg.get("production_min_units_active", 0) or 0)
    pmax = int(cfg.get("production_max_units_active", 0) or 0)
    if (
        pmin > 0
        and pmax > 0
        and scenario.product_status == "active"
        and not scenario.new_model_launch
        and scenario.production > 0
        and (scenario.production < pmin or scenario.production > pmax)
    ):
        alerts.append((
            "warning",
            f"Production ({scenario.production:,} u.) hors plage chiffrier recommandee "
            f"{pmin:,}–{pmax:,} u. pour un modele actif.",
        ))

    # ── Budget caps ──────────────────────────────────────────────────────────
    mkt_max = scenario.adjusted_budget * cfg["marketing_max_pct"]
    if scenario.marketing_budget > mkt_max:
        alerts.append((
            "error",
            f"Budget marketing ({scenario.marketing_budget:,.0f} $) depasse le plafond "
            f"({cfg['marketing_max_pct']*100:.0f}% du budget ajuste = {mkt_max:,.0f} $).",
        ))

    rd_max = scenario.adjusted_budget * cfg["rd_max_pct"]
    if scenario.rd_budget > rd_max:
        alerts.append((
            "error",
            f"Budget R&D ({scenario.rd_budget:,.0f} $) depasse le plafond de 8 % "
            f"du budget ajuste ({rd_max:,.0f} $).",
        ))

    # ── R&D: choix discrets (2%, 5%, 8%) ─────────────────────────────────────
    allowed_pcts = cfg.get("rd_allowed_pcts", [])
    if scenario.rd_budget > 0 and allowed_pcts:
        intensity = scenario.rd_budget / max(scenario.adjusted_budget, 1.0)
        # tolérance pour la saisie en dollars
        tol = 0.0025
        if not any(abs(intensity - p) <= tol for p in allowed_pcts):
            allowed_lbl = ", ".join(f"{p*100:.0f}%" for p in allowed_pcts)
            alerts.append((
                "error",
                f"Budget R&D invalide ({intensity*100:.2f}% du budget ajusté). "
                f"Valeurs permises : {allowed_lbl}.",
            ))

    # ── Lancement nouveau modèle: pas en période 1 ───────────────────────────
    if scenario.new_model_launch and scenario.period == 1:
        alerts.append((
            "error",
            "Lancement bloque en periode 1 : un lancement est autorise a partir de la periode 2 "
            "apres un investissement R&D prealable.",
        ))

    # ── Promotion limits ─────────────────────────────────────────────────────
    promo_ok, promo_msg = validate_promo_rate(
        scenario.promotion_rate, liquidation=scenario.liquidation
    )
    if not promo_ok:
        alerts.append(("error", promo_msg))

    # ── Price vs range coherence (with severity threshold) ───────────────────
    consistency, consistency_msg = check_price_range_consistency(scenario.price, scenario.model_range)
    if consistency == "error":
        alerts.append(("error", consistency_msg))
    elif consistency == "warning":
        alerts.append(("warning", consistency_msg))

    if scenario.liquidation:
        alerts.append((
            "info",
            "Mode liquidation : production de la periode suivante = 0 ; promotion liquidation plafonnee ; "
            "regle pedagogique — au plus une liquidation par an par enseigne.",
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
        if scenario.total_withdrawals_used >= cfg["withdrawal_max_total"]:
            alerts.append((
                "error",
                f"Retrait impossible : {scenario.total_withdrawals_used} retrait(s) deja utilises "
                f"(plafond {cfg['withdrawal_max_total']} sur la simulation).",
            ))
        elif scenario.last_withdrawal_period > 0 and (
            scenario.period - scenario.last_withdrawal_period < cfg["withdrawal_min_periods_between"]
        ):
            alerts.append((
                "error",
                f"Delai minimum entre retraits : {cfg['withdrawal_min_periods_between']} periodes "
                f"(dernier retrait : periode {scenario.last_withdrawal_period}).",
            ))
        else:
            history = {scenario.firm_name: [scenario.last_withdrawal_period] if scenario.last_withdrawal_period else []}
            allowed, message = check_withdrawal_limits(
                scenario.firm_name,
                scenario.period,
                history,
                max_per_year=1,
                max_total=cfg["withdrawal_max_total"],
                min_period_gap=cfg["withdrawal_min_periods_between"],
            )
            alerts.append(("error" if not allowed else "info", message))

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


def portfolio_model_count_alerts(firm: str, n_models: int) -> List[Alert]:
    """Comparer le nombre de modèles du portefeuille à une baseline optionnelle (feuille Excel / règle jeu)."""
    firm_cfg = MARKET_CONFIG["firms"].get(firm, {})
    base_n = firm_cfg.get("portfolio_baseline_models")
    if base_n is None:
        return []
    max_extra = int(MARKET_CONFIG["constraints"].get("portfolio_max_extra_models", 2))
    cap = int(base_n) + max_extra
    if n_models <= cap:
        return []
    return [
        (
            "error",
            f"Portefeuille ({n_models} modeles) : plafond chiffrier {cap} "
            f"(baseline {int(base_n)} + {max_extra} au plus).",
        )
    ]


def get_budget_caps(adjusted_budget: float) -> dict:
    """Return the maximum allowed budgets for marketing and R&D."""
    cfg = MARKET_CONFIG["constraints"]
    return {
        "marketing_max": adjusted_budget * cfg["marketing_max_pct"],
        "rd_max": adjusted_budget * cfg["rd_max_pct"],
        "marketing_pct": cfg["marketing_max_pct"],
        "rd_pct": cfg["rd_max_pct"],
        "rd_allowed_pcts": firm_rd_allowed_pcts(),
    }


def is_scenario_feasible(scenario) -> bool:
    """Return True if no error-level alerts exist."""
    alerts = validate_scenario(scenario)
    return not any(sev == "error" for sev, _ in alerts)
