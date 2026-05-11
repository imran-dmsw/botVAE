"""
Simulation marché complet (9 firmes, 6 segments, 8 périodes) avec stratégie de référence
enrichie pour UNE firme choisie — puis rapport PDF (ReportLab + vae_report_style).

Usage:
  python3 scripts/simulate_firm_full_market_pdf.py --firm CAN
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from engine.models import MarketingChannels, ScenarioInput
from engine.simulation import _make_reference_firm_template, period_to_year, simulate_full_market
from config.market_config import MARKET_CONFIG

sys.path.insert(0, os.path.dirname(__file__))
from vae_report_style import (
    CONTENT_WIDTH,
    GREEN_LT,
    AMBER_LT,
    H1,
    Paragraph,
    P_INS,
    P_JUST,
    P_SMALL,
    Spacer,
    alerte,
    box_info,
    build_doc,
    cover_banner,
    pdf_escape,
    table_standard,
)

OUT_REL = Path("reports/Simulation_marche_complet_{firm}_VAE.pdf")
DOWNLOADS = Path("/Users/imran/Downloads")


def fmt_money(x: float) -> str:
    return f"{int(round(x)):,}".replace(",", " ") + " $"


def fmt_pct(x: float) -> str:
    return f"{100.0 * x:.2f} %"


def enrich_template(firm_key: str, period: int) -> ScenarioInput:
    """Profil cohérent par période (prix/indexation via référence moteur)."""
    base = _make_reference_firm_template(firm_key, period)
    m = float(base.marketing_budget)
    ch = MarketingChannels(
        digital=m * 0.35,
        social_media=m * 0.25,
        influencers=m * 0.15,
        display=m * 0.15,
        events=m * 0.10,
    )
    rd = round(float(base.adjusted_budget) * 0.02, 2)
    return base.model_copy(
        update={
            "scenario_name": f"{firm_key} — simulation complète (réf. enrichie)",
            "marketing_channels": ch,
            "marketing_budget": m,
            "rd_budget": rd,
            "sustainability_tranches": 2,
        }
    )


def run_eight_periods(firm_key: str) -> tuple[list[dict], ScenarioInput]:
    """8 résultats `simulate_full_market` ; gabarit enrichi P1 pour la page hypothèses."""
    results = []
    template_p1 = enrich_template(firm_key, 1)
    for p in range(1, 9):
        tmpl = enrich_template(firm_key, p)
        results.append(simulate_full_market(p, firm_key, tmpl))
    return results, template_p1


def build_pdf(firm_key: str, results: list[dict], template_p1: ScenarioInput, out: Path) -> None:
    cfg = MARKET_CONFIG
    firm_label = cfg["firms"][firm_key]["label"]

    story = []
    story.append(
        cover_banner(
            "SIMULATION MARCHÉ VAE — PARCOURS COMPLET",
            f"Firme suivie : {firm_label} — 8 périodes (2027–2034) — concurrence 9 firmes / 6 segments",
        )
    )
    story.append(Spacer(1, 12))

    intro = (
        "Le moteur Python agrège une attraction logit par segment, applique un rationnement "
        "homothétique si la production agrégée est inférieure à la demande potentielle, puis "
        "estime chiffre d'affaires, coûts et profit par firme. Les huit autres firmes suivent "
        "leur profil de référence recalibré à chaque période (inflation des prix de référence)."
    )
    story.append(Paragraph(pdf_escape(intro), P_JUST))
    story.append(Spacer(1, 14))

    # Hypothèses firme suivie (période 1 comme illustration — prix réactualisés chaque période dans la boucle)
    mkt = template_p1.marketing_budget
    meta = (
        f"<b>Firme :</b> {firm_label}<br/>"
        f"<b>Production (réf.) :</b> {template_p1.production:,} unités / an<br/>"
        f"<b>Prix (segment défaut, P1) :</b> {fmt_money(template_p1.price)}<br/>"
        f"<b>Gamme / statut :</b> {template_p1.model_range} / {template_p1.product_status}<br/>"
        f"<b>Budget marketing :</b> {fmt_money(mkt)} "
        f"(digital / réseaux / influenceurs / display / événements)<br/>"
        f"<b>R&D :</b> {fmt_money(template_p1.rd_budget)}<br/>"
        f"<b>Durabilité :</b> {template_p1.sustainability_tranches} tranche(s)<br/>"
        f"<b>Budget ajusté ref. :</b> {fmt_money(template_p1.adjusted_budget)}"
    )
    story.append(box_info(Paragraph(meta, P_INS)))
    story.append(Spacer(1, 14))

    H1(story, "Synthèse par période — firme suivie")
    rows_syn = []
    fills = []
    for res in results:
        p = res["period"]
        ft = res["firms"][firm_key]
        rows_syn.append(
            [
                str(p),
                str(res["year"]),
                f"{ft['total_sales']:,}".replace(",", " "),
                fmt_money(ft["total_revenue"]),
                fmt_pct(ft["market_share"]),
                fmt_pct(ft["margin_estimate"]),
                fmt_money(ft["profit_estimate"]),
                fmt_pct(ft["capacity_ratio"]),
            ]
        )
        if ft["margin_estimate"] < 0.02:
            fills.append(AMBER_LT)
        elif ft["margin_estimate"] >= 0.05:
            fills.append(GREEN_LT)
        else:
            fills.append(None)

    w = CONTENT_WIDTH
    story.append(
        table_standard(
            [
                "Période",
                "Année",
                "Ventes",
                "CA",
                "PDM glob.",
                "Marge",
                "Profit est.",
                "Srv capacité",
            ],
            rows_syn,
            [w * 0.09, w * 0.09, w * 0.11, w * 0.14, w * 0.11, w * 0.11, w * 0.17, w * 0.18],
            row_fills=fills,
        )
    )
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            pdf_escape(
                "Srv capacité : rapport production / demande agrégée potentielle pour la firme "
                "(homothétique sur les segments)."
            ),
            P_SMALL,
        )
    )

    last = results[-1]
    H1(story, f"Période 8 ({last['year']}) — parts par segment ({firm_label})")
    segs = last["firms"][firm_key]["segments"]
    rows_seg = []
    for seg_key, data in segs.items():
        lab = cfg["segments"][seg_key]["label"]
        rows_seg.append([lab, str(data["sales"]), fmt_pct(data["share"])])
    story.append(
        table_standard(
            ["Segment", "Ventes", "Part segment"],
            rows_seg,
            [CONTENT_WIDTH * 0.42, CONTENT_WIDTH * 0.28, CONTENT_WIDTH * 0.30],
        )
    )

    H1(story, f"Période 8 — panorama des 9 firmes (PDM globale)")
    rows_all = []
    ordered = sorted(
        cfg["firms"].keys(),
        key=lambda fk: last["firms"][fk]["market_share"],
        reverse=True,
    )
    for fk in ordered:
        ft = last["firms"][fk]
        rows_all.append([cfg["firms"][fk]["label"], str(ft["total_sales"]), fmt_pct(ft["market_share"])])
    story.append(
        table_standard(
            ["Firme", "Ventes tot.", "PDM"],
            rows_all,
            [w * 0.2, w * 0.35, w * 0.45],
        )
    )

    ft8 = last["firms"][firm_key]
    H1(story, "Lecture rapide")
    if ft8["profit_estimate"] >= 0 and ft8["margin_estimate"] >= 0.05:
        story.append(alerte("Rentabilité dans ou au-dessus de la zone cible sur la dernière période.", "ok"))
    elif ft8["profit_estimate"] < 0:
        story.append(alerte("Résultat net déficitaire en période 8 — à analyser (prix, coûts, capacité).", "critical"))
    else:
        story.append(alerte("Marge sous la zone idéale 5–10 % — pistes d’optimisation du mix.", "warning"))

    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            pdf_escape(
                "Document généré automatiquement — pas une décision d’équipe réelle. "
                "Pour la saisie Excel et les contrôles pédagogiques, utiliser le classeur VAE officiel."
            ),
            P_SMALL,
        )
    )

    build_doc(
        out,
        story,
        firm_code=firm_key,
        left_text=f"Simulation marché VAE — {firm_label} — 8 périodes",
    )


def main():
    ap = argparse.ArgumentParser(description="Simulation complète + PDF (vae_report_style)")
    ap.add_argument(
        "--firm",
        default="CAN",
        choices=list(MARKET_CONFIG["firms"].keys()),
        help="Firme suivie (les 8 autres en référence concurrentielle)",
    )
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    firm = args.firm.upper()
    results, tmpl_p1 = run_eight_periods(firm)
    out = args.out or Path(str(OUT_REL).format(firm=firm))
    if not out.is_absolute():
        out = Path.cwd() / out
    out.parent.mkdir(parents=True, exist_ok=True)

    build_pdf(firm, results, tmpl_p1, out)

    dl = DOWNLOADS / out.name
    try:
        shutil.copy2(out, dl)
        print(f"PDF : {out}")
        print(f"Copie : {dl}")
    except OSError:
        print(f"PDF : {out}")
    print(f"Firme : {firm} — {len(results)} périodes simulées.")


if __name__ == "__main__":
    main()
