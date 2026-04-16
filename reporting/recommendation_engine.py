from __future__ import annotations

from typing import List

from engine.models import ScenarioInput, SimulationResult


def build_recommendations(scenario: ScenarioInput, result: SimulationResult) -> List[str]:
    recs: List[str] = []
    if result.price_range_consistency_status != "ok":
        recs.append("Ajuster le prix pour le rendre coherent avec la gamme.")
    if result.production_efficiency < 0.75:
        recs.append("Reduire la production pour limiter le risque de surstock.")
    if result.profit_rate < 0.05:
        recs.append("Ameliorer le mix prix/couts pour atteindre au moins 5% de profit.")
    if result.profit_rate > 0.10:
        recs.append("Marge elevee: tester une baisse moderee du prix pour gagner en part de marche.")
    if result.marketing_efficiency < 0.02 and scenario.marketing_budget > 0:
        recs.append("Le rendement marketing est faible: reallouer les depenses vers les canaux les plus performants.")
    if result.withdrawal_limit_status != "ok":
        recs.append("Differer le retrait produit pour respecter les limites de simulation.")
    if result.liquidation_next_period_production_flag:
        recs.append("Liquidation active: planifier la substitution du modele car la production N+1 sera nulle.")
    if result.new_product_first_year_flag:
        recs.append("Nouveau produit: calibrer le plan commercial autour de la diffusion plafonnee de premiere annee.")
    if not recs:
        recs.append("Scenario globalement coherent: poursuivre et monitorer les KPI de profit, service et PDM.")
    return recs


def generate_recommendations(result: SimulationResult) -> List[str]:
    """
    Lightweight recommendations API requested by product brief.
    """
    recs: List[str] = []
    if result.production_efficiency < 0.70:
        recs.append("Reduire production: surproduction detectee.")
    if result.price_range_consistency_status != "ok":
        recs.append("Ajuster le prix pour rester coherent avec la gamme.")
    if result.profit_rate < 0.05:
        recs.append("Augmenter le prix net ou reduire les couts pour relever la rentabilite.")
    if result.marketing_efficiency < 0.02:
        recs.append("Ajuster le marketing: rendement marginal faible.")
    if result.margin > 0.10:
        recs.append("Revoir la promo/prix pour accelerer la conquete part de marche.")
    if not recs:
        recs.append("Maintenir la strategie actuelle et suivre les KPI.")
    return recs
