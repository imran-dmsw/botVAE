from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Tuple

from engine.models import ScenarioInput, SimulationResult
from reporting.recommendation_engine import build_recommendations


@dataclass(frozen=True)
class PortfolioLine:
    model_name: str
    segment: str
    model_range: str
    price: float
    production: int
    demand: float
    sales: int
    ending_stock: int
    margin: float
    profit: float
    alerts_count: int


def _to_portfolio_line(s: ScenarioInput, r: SimulationResult) -> PortfolioLine:
    return PortfolioLine(
        model_name=s.model_name,
        segment=s.segment,
        model_range=s.model_range,
        price=float(s.price),
        production=int(s.production),
        demand=float(r.demand),
        sales=int(r.sales),
        ending_stock=int(r.forecast_ending_stock_units),
        margin=float(r.margin),
        profit=float(r.profit),
        alerts_count=len(r.alerts or []),
    )


def generate_company_markdown_report(
    firm_name: str,
    records: Iterable[Tuple[ScenarioInput, SimulationResult]],
    *,
    title: str | None = None,
) -> str:
    """
    Rapport compact « par compagnie » basé sur une liste de scénarios (souvent l'historique).
    Vise une lecture 3–5 pages lorsqu'il est exporté en PDF/Word (ici: Markdown).
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = title or f"Rapport compagnie — {firm_name}"

    lines = [f"# {title}", f"**Généré le :** {now}", "", "---", ""]

    pairs: List[Tuple[ScenarioInput, SimulationResult]] = [
        (s, r) for (s, r) in records if (r.firm_name == firm_name or s.firm_name == firm_name)
    ]
    if not pairs:
        return "\n".join(lines + ["Aucun scénario trouvé pour cette compagnie."])

    # Executive summary
    profits = [r.profit for _, r in pairs]
    margins = [r.margin for _, r in pairs]
    service = [r.service_rate for _, r in pairs]
    lines += [
        "## 1. Résumé",
        "",
        f"- Nombre de scénarios: **{len(pairs)}**",
        f"- Profit total (somme): **{sum(profits):,.0f} $**",
        f"- Profit moyen: **{(sum(profits)/len(profits)):,.0f} $**",
        f"- Marge moyenne: **{(sum(margins)/len(margins))*100:.1f}%**",
        f"- Taux de service moyen: **{(sum(service)/len(service))*100:.1f}%**",
        "",
        "---",
        "",
    ]

    # Portfolio table
    portfolio = [_to_portfolio_line(s, r) for s, r in pairs]
    portfolio.sort(key=lambda x: (-x.profit, -x.margin))
    lines += [
        "## 2. Portefeuille (vue rapide)",
        "",
        "| Modèle | Segment | Gamme | Prix | Prod | Demande | Ventes | Stock fin | Marge | Profit | Alertes |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for p in portfolio:
        lines.append(
            "| "
            + " | ".join(
                [
                    p.model_name,
                    p.segment,
                    p.model_range,
                    f"{p.price:,.0f}",
                    f"{p.production:,}",
                    f"{p.demand:,.0f}",
                    f"{p.sales:,}",
                    f"{p.ending_stock:,}",
                    f"{p.margin*100:.1f}%",
                    f"{p.profit:,.0f}",
                    str(p.alerts_count),
                ]
            )
            + " |"
        )

    # Alerts & recommendations (participants)
    lines += ["", "---", "", "## 3. Alertes clés", ""]
    top_alerts: List[str] = []
    for _, r in pairs:
        for a in (r.alerts or [])[:6]:
            top_alerts.append(a)
    # de-dup
    seen = set()
    uniq = []
    for a in top_alerts:
        k = a.strip().lower()
        if k and k not in seen:
            seen.add(k)
            uniq.append(a)
    if uniq:
        for a in uniq[:12]:
            lines.append(f"- ⚠️ {a}")
    else:
        lines.append("Aucune alerte récurrente détectée.")

    lines += ["", "---", "", "## 4. Recommandations (participants)", ""]
    recs: List[str] = []
    for s, r in pairs:
        recs.extend(build_recommendations(s, r))
    seen = set()
    out = []
    for r in recs:
        k = r.strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(r)
    for r in out[:12]:
        lines.append(f"- {r}")
    if not out:
        lines.append("- Maintenir la stratégie actuelle et suivre les KPI.")

    # Internal calibration notes
    lines += ["", "---", "", "## 5. Notes internes (calibration)", ""]
    lines += [
        "- Vérifier la cohérence des paramètres (croissance, inflation, COGS, plafonds) avant toute interprétation.",
        "- Contrôler les cas limites: liquidation (promo -10%/-20%), retraits, lancement P2+ et R&D discrète (2/5/8%).",
        "- Rejouer les scénarios de référence (1500/2000/2500/3000, +10/+12/+15%) après chaque ajustement moteur.",
    ]

    return "\n".join(lines)

