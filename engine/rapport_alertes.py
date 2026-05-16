from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config.market_config import MARKET_CONFIG
from engine.budget_allocation import firm_rd_allowed_pcts
from engine.models import ScenarioInput, SimulationResult
from rules.promo_rules import validate_promo_rate
from rules.withdrawal_rules import check_withdrawal_limits

RANGE_PRICE_FLOORS = {
    "entry": 2500.0,
    "mid": 3500.0,
    "premium": 5500.0,
}
CATALOGUE_FLOORS = {
    "Basic": 2500.0,
    "Bas": 2500.0,
    "Standard": 3500.0,
    "Medium": 3500.0,
    "Moyen": 3500.0,
    "Premium": 5500.0,
    "Haut": 5500.0,
}


@dataclass(frozen=True)
class PrioritizedAlert:
    level: str
    code: str
    message: str


def _fmt_money(x: float) -> str:
    return f"{int(round(x)):,}".replace(",", " ")


def build_prioritized_alerts(
    *,
    scenario: ScenarioInput,
    result: SimulationResult,
    product: Any | None = None,
    withdrawal_history: dict[str, list[int]] | None = None,
) -> dict[str, list[PrioritizedAlert]]:
    grouped: dict[str, list[PrioritizedAlert]] = {
        "critique": [],
        "attention": [],
        "information": [],
    }

    def add(level: str, code: str, message: str) -> None:
        grouped[level].append(PrioritizedAlert(level=level, code=code, message=message))

    adj = max(float(scenario.adjusted_budget or 0.0), 1.0)

    if result.margin < 0.05:
        add(
            "critique",
            "profit_cible",
            (
                f"Marge {result.margin * 100:.1f} % sous la cible minimale de 5 % "
                f"(profit {_fmt_money(result.profit)} $)."
            ),
        )
    elif result.margin < 0.10:
        add(
            "attention",
            "profit_cible",
            (
                f"Marge {result.margin * 100:.1f} % sous la cible confort de 10 % "
                f"(profit {_fmt_money(result.profit)} $)."
            ),
        )

    if scenario.production > 0 and result.forecast_ending_stock_units > 0.15 * scenario.production:
        add(
            "attention",
            "surproduction",
            (
                f"Surproduction probable : stock final {result.forecast_ending_stock_units} u. "
                f"> 15 % de la production ({scenario.production} u.)."
            ),
        )
    if result.forecast_coverage_rate > 1.05:
        add(
            "attention",
            "surproduction",
            (
                f"Taux de couverture {result.forecast_coverage_rate * 100:.0f} % au-dessus "
                "de la zone idéale 95-105 %."
            ),
        )

    if result.service_rate < 0.85:
        add(
            "attention",
            "sous_production",
            (
                f"Sous-production : taux de service {result.service_rate * 100:.0f} % "
                f"(demande non servie {max(0, int(round(result.demand - result.sales)))} u.)."
            ),
        )

    if scenario.period == 1 and scenario.rd_budget > 0:
        add(
            "critique",
            "rd_p1",
            "Budget R&D en période 1 : le chiffrier impose une activation R&D à partir de la période 2.",
        )

    if scenario.period >= 2 and scenario.rd_budget > 0:
        intensity = scenario.rd_budget / adj
        add(
            "information",
            "rd_niveaux",
            (
                f"R&D à {intensity * 100:.2f} % du budget ajusté.\n"
                "- 2 % → Amélioration des modèles existants uniquement, "
                "aucun nouveau lancement autorisé.\n"
                "- 5 % → Amélioration des existants + lancement de "
                "1 nouveau modèle autorisé à cette période.\n"
                "- 8 % → Amélioration des existants + lancement de "
                "2 nouveaux modèles autorisés à cette période."
            ),
        )

    mkt_max = adj * MARKET_CONFIG["constraints"]["marketing_max_pct"]
    if scenario.marketing_budget > mkt_max * 1.02:
        add(
            "attention",
            "marketing_eleve",
            (
                f"Marketing {_fmt_money(scenario.marketing_budget)} $ dépasse le plafond "
                f"réglementaire ({_fmt_money(mkt_max)} $, {MARKET_CONFIG['constraints']['marketing_max_pct'] * 100:.0f} % du budget ajusté)."
            ),
        )

    promo_ok, promo_msg = validate_promo_rate(
        scenario.promotion_rate,
        liquidation=bool(scenario.liquidation or scenario.product_status == "withdrawal"),
    )
    if not promo_ok:
        add("critique", "promotion", promo_msg)
    elif scenario.promotion_rate != 0.0:
        add("information", "promotion", promo_msg)

    history = withdrawal_history or {}
    if scenario.product_status == "withdrawal" or scenario.liquidation:
        allowed, withdrawal_msg = check_withdrawal_limits(
            scenario.firm_name,
            scenario.period,
            history,
        )
        if not allowed:
            add("critique", "retrait", withdrawal_msg)
        else:
            add("information", "retrait", withdrawal_msg)

    for alert in result.alerts:
        low = alert.lower()
        if "plage recommand" in low or "au-dessus de la plage" in low:
            continue
        if "critique" in low or "bloquant" in low:
            add("critique", "moteur", alert)
        elif "attention" in low or "risque" in low:
            add("attention", "moteur", alert)
        else:
            add("information", "moteur", alert)

    return grouped


def flatten_prioritized_alerts(grouped: dict[str, list[PrioritizedAlert]]) -> list[PrioritizedAlert]:
    order = ("critique", "attention", "information")
    out: list[PrioritizedAlert] = []
    for level in order:
        out.extend(grouped.get(level, []))
    return out
