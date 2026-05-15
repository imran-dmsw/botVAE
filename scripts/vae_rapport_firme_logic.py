"""Règles d'analyse stratégique pour les rapports firme / modèle VAE."""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from engine.models import ScenarioInput, SimulationResult
from vae_report_tables import canonical_gamme_label
PRICE_FLOORS: dict[str, float] = {
    "Basic": 2500.0,
    "Bas": 2500.0,
    "Standard": 3500.0,
    "Medium": 3500.0,
    "Moyen": 3500.0,
    "Premium": 5500.0,
    "Haut": 5500.0,
}


@dataclass(frozen=True)
class StrategicRecommendation:
    action: str
    impact: str
    horizon: str
    priority: str  # Haute | Moyenne | Critique


def fmt_money(x: float) -> str:
    return f"{int(round(x)):,}".replace(",", " ")


def price_floor(range_raw: str) -> float | None:
    key = str(range_raw or "").strip()
    if not key:
        return None
    if key in PRICE_FLOORS:
        return PRICE_FLOORS[key]
    low = key.lower()
    for k, v in PRICE_FLOORS.items():
        if k.lower() == low:
            return v
    return None


def price_floor_alert(range_raw: str, catalogue_price: float) -> str | None:
    floor = price_floor(range_raw)
    if floor is None or catalogue_price >= floor:
        return None
    return (
        f"Attention : prix catalogue {fmt_money(catalogue_price)} $ inférieur au plancher "
        f"{range_raw} ({fmt_money(floor)} $). Correction requise dès P3."
    )


def _gamme_key(p: Any) -> str:
    return canonical_gamme_label(getattr(p, "range_raw", None))


def products_same_segment(prods: list[Any], prod: Any) -> list[Any]:
    return [p for p in prods if p.segment_idx == prod.segment_idx and p.product_key != prod.product_key]


def products_same_segment_same_gamme(prods: list[Any], prod: Any) -> list[Any]:
    g = _gamme_key(prod)
    return [
        p
        for p in prods
        if p.segment_idx == prod.segment_idx and p.product_key != prod.product_key and _gamme_key(p) == g
    ]


def cannibalisation_warning(prods: list[Any], prod: Any) -> str | None:
    peers = products_same_segment_same_gamme(prods, prod)
    if not peers:
        return None
    codes = ", ".join(p.product_key for p in peers)
    return (
        f"Attention — cannibalisation interne : {len(peers)} autre(s) modèle(s) de la firme sur ce segment "
        f"et la même gamme ({codes}). Risque de fragmentation de la demande."
    )


def portfolio_cannibalisation_notes(prods: list[Any]) -> list[str]:
    by_key: dict[tuple[int, str], list[Any]] = defaultdict(list)
    for p in prods:
        by_key[(p.segment_idx, _gamme_key(p))].append(p)
    notes: list[str] = []
    for (seg, gam), items in sorted(by_key.items()):
        if len(items) < 2:
            continue
        codes = ", ".join(p.product_key for p in items)
        notes.append(
            f"Segment {seg}, gamme {gam} : {len(items)} références ({codes}) — risque de cannibalisation interne."
        )
    return notes


def optimal_production_units(res: SimulationResult) -> int:
    if res.demand <= 0:
        return max(res.sales, 0)
    return int(math.ceil(res.demand * 1.05 / 100.0) * 100)


def firm_marketing_reference_budgets(results: list[tuple[str, str, ScenarioInput, SimulationResult]]) -> list[float]:
    budgets: list[float] = []
    seen: set[str] = set()
    for _sid, owner, scen, _res in results:
        if owner in seen:
            continue
        seen.add(owner)
        budgets.append(float(scen.marketing_budget))
    return budgets


def build_firm_recommendations(
    *,
    firm: str,
    legend: str,
    prods: list[Any],
    focal_prod: Any,
    ref_scen: ScenarioInput,
    ref_res: SimulationResult,
    r_p8: SimulationResult | None,
    results: list[tuple[str, str, ScenarioInput, SimulationResult]],
) -> list[StrategicRecommendation]:
    recs: list[StrategicRecommendation] = []

    floor = price_floor(focal_prod.range_raw)
    if floor is not None and ref_scen.price < floor:
        target = int(round(floor))
        recs.append(
            StrategicRecommendation(
                action=(
                    f"Porter le prix catalogue de {fmt_money(ref_scen.price)} $ à au moins "
                    f"{fmt_money(target)} $ (plancher {focal_prod.range_raw}) sur {focal_prod.product_key}."
                ),
                impact="Conformité CONTROLE_DECISIONS / PriceFit ; évite pénalités d'attractivité.",
                horizon="P3",
                priority="Haute",
            )
        )

    prod = ref_scen.production
    if prod > 0 and ref_res.forecast_ending_stock_units > 0.15 * prod:
        target_prod = max(int(prod * 0.85), ref_res.sales)
        recs.append(
            StrategicRecommendation(
                action=(
                    f"Réduire la production planifiée de {prod} à environ {target_prod} unités "
                    f"(stock final {ref_res.forecast_ending_stock_units} u. > 15 % de la production)."
                ),
                impact=f"Limiter le coût de stockage (est. {fmt_money(ref_res.inventory_carrying_cost)} $).",
                horizon="P2–P3",
                priority="Haute",
            )
        )

    if ref_res.service_rate < 0.85:
        opt = optimal_production_units(ref_res)
        recs.append(
            StrategicRecommendation(
                action=(
                    f"Augmenter la production vers ~{opt} unités (service actuel "
                    f"{ref_res.service_rate * 100:.0f} %, demande non servie "
                    f"{max(0, int(round(ref_res.demand - ref_res.sales)))} u.)."
                ),
                impact="Réduction des ventes perdues sur le scénario vedette.",
                horizon="P2",
                priority="Haute",
            )
        )

    peer_budgets = firm_marketing_reference_budgets(results)
    if peer_budgets:
        avg_mkt = sum(peer_budgets) / len(peer_budgets)
        if ref_scen.marketing_budget > 3.0 * avg_mkt:
            target_mkt = int(round(avg_mkt * 1.2))
            recs.append(
                StrategicRecommendation(
                    action=(
                        f"Ramener le budget marketing de {fmt_money(ref_scen.marketing_budget)} $ vers "
                        f"~{fmt_money(target_mkt)} $ (référence moyenne firmes ≈ {fmt_money(avg_mkt)} $)."
                    ),
                    impact="Réallocation vers marge ou canaux à meilleur coefficient.",
                    horizon="P2–P3",
                    priority="Haute",
                )
            )

    if len({p.segment_idx for p in prods}) < len(prods):
        crowded = [s for s, n in Counter(p.segment_idx for p in prods).items() if n > 1]
        recs.append(
            StrategicRecommendation(
                action=(
                    f"Rationaliser le portefeuille : segments en double {crowded} — arbitrer prix, "
                    f"promotion ou retrait d'une référence par segment."
                ),
                impact="Limite la cannibalisation interne et concentre le marketing.",
                horizon="P3–P4",
                priority="Moyenne",
            )
        )

    if r_p8 is not None and r_p8.profit < 0:
        recs.append(
            StrategicRecommendation(
                action=(
                    "Réviser chaque période prix, production et mix marketing : la stratégie figée "
                    f"affiche un profit P8 de {fmt_money(r_p8.profit)} $."
                ),
                impact="Évite la dérive sur un marché en croissance (+12 % / an).",
                horizon="P1–P8",
                priority="Critique",
            )
        )

    if len(recs) < 5:
        recs.append(
            StrategicRecommendation(
                action=(
                    f"Aligner le mix marketing du segment {focal_prod.segment_idx} sur les coefficients "
                    f"MARKETING_MATRIX (priorité canaux les plus élevés)."
                ),
                impact="Gain de parts sans dépasser le plafond réglementaire.",
                horizon="P3–P4",
                priority="Moyenne",
            )
        )
        recs.append(
            StrategicRecommendation(
                action=(
                    f"Valider les décisions {firm} dans CONTROLE_DECISIONS avant soumission officielle "
                    f"({legend})."
                ),
                impact="Cohérence avec le chiffrier Excel et les seuils pédagogiques.",
                horizon="P1",
                priority="Moyenne",
            )
        )

    return recs[:8]


def build_model_recommendations(
    prod: Any,
    bundle: dict[str, Any],
    mm_rows: list[list[str]],
) -> list[StrategicRecommendation]:
    levers: list[tuple[str, SimulationResult]] = bundle["levers"]
    ref_res: SimulationResult = bundle["ref_res"]
    ref_scen: ScenarioInput = bundle["ref_scen"]
    best_lab, best_r = max(levers, key=lambda x: x[1].profit)
    ref_p1 = levers[0][1]
    promo_r = levers[2][1]

    recs: list[StrategicRecommendation] = [
        StrategicRecommendation(
            action=f"Prioriser le levier « {best_lab} » (profit {fmt_money(best_r.profit)} $).",
            impact="Maximise le résultat sur les quatre tirages P1 du modèle.",
            horizon="P2",
            priority="Haute",
        )
    ]

    if ref_res.service_rate < 0.85:
        opt = optimal_production_units(ref_res)
        recs.append(
            StrategicRecommendation(
                action=f"Monter la production vers ~{opt} unités (service {ref_res.service_rate * 100:.0f} %).",
                impact="Limite les ventes perdues sur la référence P2.",
                horizon="P2",
                priority="Haute",
            )
        )
    elif ref_res.forecast_ending_stock_units > max(1, int(0.15 * ref_scen.production)):
        recs.append(
            StrategicRecommendation(
                action=(
                    f"Réduire la production ou stimuler la demande (stock final "
                    f"{ref_res.forecast_ending_stock_units} u.)."
                ),
                impact="Baisse du coût de stockage estimé.",
                horizon="P2–P3",
                priority="Moyenne",
            )
        )
    else:
        recs.append(
            StrategicRecommendation(
                action="Maintenir la capacité actuelle ; surveiller le stock final chaque période.",
                impact="Stabilité du taux de service.",
                horizon="P2",
                priority="Moyenne",
            )
        )

    mm_line = next((r for r in mm_rows if r[0] == str(prod.segment_idx)), None)
    if mm_line:
        recs.append(
            StrategicRecommendation(
                action=(
                    f"Réallouer le marketing segment {prod.segment_idx} (Digital {mm_line[1]}, "
                    f"Influenceur {mm_line[3]}, Événements {mm_line[5]})."
                ),
                impact="Alignement sur les coefficients MARKETING_MATRIX.",
                horizon="P3",
                priority="Moyenne",
            )
        )

    if promo_r.profit > ref_p1.profit:
        recs.append(
            StrategicRecommendation(
                action="Appliquer une promotion nette de −5 % sur le prix catalogue.",
                impact=f"Profit promo {fmt_money(promo_r.profit)} $ vs référence {fmt_money(ref_p1.profit)} $.",
                horizon="P2",
                priority="Haute",
            )
        )
    else:
        recs.append(
            StrategicRecommendation(
                action="Maintenir 0 % de promotion ou relever le prix catalogue si la demande le permet.",
                impact=f"La promo −5 % dégrade le profit ({fmt_money(promo_r.profit)} $ vs {fmt_money(ref_p1.profit)} $).",
                horizon="P2–P3",
                priority="Haute",
            )
        )

    r_p8: SimulationResult = bundle["r_p8"]
    recs.append(
        StrategicRecommendation(
            action="Réviser prix et capacité à chaque période (projection figée P1→P8).",
            impact=f"Profit P8 figé : {fmt_money(r_p8.profit)} $ — éviter l'inertie décisionnelle.",
            horizon="P1–P8",
            priority="Critique" if r_p8.profit < 0 else "Moyenne",
        )
    )
    return recs


def executive_priority_levers(recs: list[StrategicRecommendation], limit: int = 3) -> list[str]:
    order = {"Critique": 0, "Haute": 1, "Moyenne": 2}
    ranked = sorted(recs, key=lambda r: order.get(r.priority, 9))
    return [r.action for r in ranked[:limit]]


# ─── API rapport v2 (données + vues) ─────────────────────────────────────────

from pathlib import Path as _Path

from config.market_config import MARKET_CONFIG as _MARKET_CONFIG

FIRMES_VALIDES = sorted(_MARKET_CONFIG["firms"].keys())
FIRM_CODE_ALIASES = {"VAE": "AVE"}

PLANCHERS_PRIX = PRICE_FLOORS
CROISSANCE_ANNUELLE = 0.12
MARCHE_REF = 110_000


def resolve_firm_code(raw: str) -> str:
    u = raw.upper().strip()
    return FIRM_CODE_ALIASES.get(u, u)


def default_excel_path() -> _Path:
    root = _Path(__file__).resolve().parent.parent
    candidates = [
        _Path("/Users/imran/Downloads/VAE_tout_inclus_01_05_2026_Final1_v6.xlsx"),
        root / "VAE_tout_inclus_01_05_2026_Final1.xlsx",
        _Path("/Users/imran/Downloads/VAE_tout_inclus_01_05_2026_Final1.xlsx"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


def charger_donnees_firme(excel_path: _Path, code_firme: str) -> dict[str, Any]:
    """Charge le classeur, simule les scénarios et prépare le contexte rapport."""
    from generate_rapport_vae_style_pdf import build_report_payload

    firm = resolve_firm_code(code_firme)
    if firm not in FIRMES_VALIDES:
        raise ValueError(f"Firme '{code_firme}' inconnue. Valeurs : {FIRMES_VALIDES}")
    path = _Path(excel_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Classeur introuvable : {path}")
    return build_report_payload(path, firm)


def calculer_vue_firme(donnees: dict[str, Any]) -> dict[str, Any]:
    return donnees["vue_firme"]


def calculer_vue_modele(donnees: dict[str, Any], produit: Any) -> dict[str, Any]:
    key = produit.product_key if hasattr(produit, "product_key") else produit["Code_Produit"]
    return donnees["fiches_modeles"][key]


def generer_recommandations_firme(vue_firme: dict[str, Any], donnees: dict[str, Any]) -> list[StrategicRecommendation]:
    del vue_firme
    return donnees["recommandations_firme"]
