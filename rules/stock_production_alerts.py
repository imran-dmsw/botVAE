"""
Indicateurs et seuils d'alerte production / stock / demande.
Réf. pédagogique : seuils_alertes_production_stock_simulation_VAE.docx
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from config.market_config import MARKET_CONFIG


@dataclass
class StockProductionDiagnostics:
    stock_available: int
    coverage_rate: float
    lost_sales_units: float
    lost_sales_pct_of_demand: float
    ending_stock_units: int
    ending_stock_pct_of_demand: float
    estimated_storage_cost: float
    coverage_level: str
    detail_messages: List[str] = field(default_factory=list)
    short_messages: List[str] = field(default_factory=list)
    alert_severities: List[Tuple[str, str]] = field(default_factory=list)


def build_stock_production_diagnostics(
    demand: float,
    opening_stock: int,
    production: int,
    sales: int,
    unit_cost: float,
    gross_profit: float,
) -> StockProductionDiagnostics:
    """
    Stock disponible prévu = stock départ + production.
    Taux de couverture = stock disponible / demande prévue.
    Ventes perdues estimées = max(0, demande - stock disponible).
    Stock final prévu = stock disponible - ventes réalisées (min demande, stock).
    Coût stockage estimé = stock final × coût unitaire × taux (config).
    """
    cref = MARKET_CONFIG["constraints"]
    rate = float(cref.get("inventory_carrying_rate", 0.025))

    stock_available = max(0, opening_stock + production)
    ending_stock = max(0, stock_available - sales)
    storage_cost = ending_stock * max(unit_cost, 0.0) * rate

    if demand <= 0:
        return StockProductionDiagnostics(
            stock_available=stock_available,
            coverage_rate=0.0,
            lost_sales_units=0.0,
            lost_sales_pct_of_demand=0.0,
            ending_stock_units=ending_stock,
            ending_stock_pct_of_demand=0.0,
            estimated_storage_cost=storage_cost,
            coverage_level="na",
        )

    coverage = stock_available / demand
    lost_sales = max(0.0, demand - float(stock_available))
    lost_pct = lost_sales / demand
    end_pct = ending_stock / demand

    red_u = float(cref.get("stock_coverage_red_under", 0.90))
    orange_u = float(cref.get("stock_coverage_orange_under", 1.0))
    green_max = float(cref.get("stock_coverage_green_max", 1.10))
    yellow_max = float(cref.get("stock_coverage_yellow_max", 1.20))
    lost_alert = float(cref.get("stock_lost_sales_alert_pct", 0.10))
    end_warn = float(cref.get("stock_final_warn_pct_of_demand", 0.10))
    end_surplus = float(cref.get("stock_final_surplus_pct_of_demand", 0.20))
    stor_gp = float(cref.get("stock_storage_vs_gross_profit_pct", 0.05))

    details: List[str] = []
    shorts: List[str] = []
    sev: List[Tuple[str, str]] = []

    if coverage < red_u:
        level = "red_under"
        details.append(
            "Risque élevé de ventes perdues : la production semble insuffisante. "
            "Risque important de ventes perdues et de perte de part de marché."
        )
        shorts.append(
            "Alerte rupture : votre production ne couvre pas suffisamment la demande prévue."
        )
        sev.append(("error", shorts[-1]))
    elif coverage < orange_u:
        level = "orange_low"
        details.append(
            "Production prudente : risque modéré de rupture si la demande se réalise."
        )
        shorts.append(
            "Production prudente : vous limitez le stock, mais vous risquez des ventes perdues."
        )
        sev.append(("warning", shorts[-1]))
    elif coverage <= green_max:
        level = "green"
        details.append(
            "Production équilibrée : bon compromis entre disponibilité et stock."
        )
        shorts.append(
            "Production équilibrée : votre décision couvre la demande avec une marge raisonnable."
        )
        sev.append(("info", shorts[-1]))
    elif coverage <= yellow_max:
        level = "yellow"
        details.append(
            "Production sécuritaire : stock possible si la demande est plus faible que prévue."
        )
        shorts.append("Vérifiez le coût de stockage avant de confirmer.")
        sev.append(("warning", shorts[-1]))
    else:
        level = "red_over"
        details.append(
            "Risque de surproduction : stock final potentiellement élevé "
            "(coût de stockage important et risque d'invendus)."
        )
        shorts.append(
            "Risque surproduction : réduire la production sauf stratégie de disponibilité élevée."
        )
        sev.append(("error", shorts[-1]))

    if lost_pct > lost_alert:
        msg = (
            "Risque important de ventes perdues et de perte de part de marché "
            f"({lost_pct * 100:.1f} % de la demande non servie)."
        )
        details.append(msg)
        if lost_pct >= 0.20:
            sev.append(("error", msg))
        else:
            sev.append(("warning", msg))

    if end_pct > end_surplus:
        shorts.append("Alerte surstock : votre production dépasse fortement la demande prévue.")
        sev.append(("warning", shorts[-1]))
    elif end_pct > end_warn:
        shorts.append(
            "Attention : votre décision peut créer du surstockage et des coûts de stockage."
        )
        sev.append(("warning", shorts[-1]))

    if gross_profit > 0 and storage_cost > stor_gp * gross_profit:
        shorts.append("Attention : le stockage risque de réduire fortement votre profit.")
        sev.append(("warning", shorts[-1]))

    return StockProductionDiagnostics(
        stock_available=stock_available,
        coverage_rate=coverage,
        lost_sales_units=lost_sales,
        lost_sales_pct_of_demand=lost_pct,
        ending_stock_units=ending_stock,
        ending_stock_pct_of_demand=end_pct,
        estimated_storage_cost=storage_cost,
        coverage_level=level,
        detail_messages=details,
        short_messages=shorts,
        alert_severities=sev,
    )
