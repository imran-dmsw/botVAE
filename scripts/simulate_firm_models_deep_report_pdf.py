"""
Rapport PDF approfondi : pour une firme donnée, chaque ligne de gamme (modele catalogue)
est testee sous 4 archetypes de scenario (reference, marketing au plafond, promo -5%,
production elargie). Introduction « entreprise », methodologie, conclusion synthetique.
Utilise le moteur simulate() + vae_report_style (ReportLab).

Usage:
  python3 scripts/simulate_firm_models_deep_report_pdf.py --firm CAN
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.market_config import MARKET_CONFIG
from engine.models import MarketingChannels, ScenarioInput
from engine.simulation import period_inflation_factor, segment_size, simulate, total_market_size

sys.path.insert(0, os.path.dirname(__file__))
from vae_report_style import (
    CONTENT_WIDTH,
    GREEN_LT,
    H1,
    PageBreak,
    Paragraph,
    P_INS,
    P_JUST,
    P_SMALL,
    Spacer,
    box_info,
    build_doc,
    cover_banner,
    pdf_escape,
    table_standard,
    toc_block,
)

OUT_REL = Path("reports/Rapport_modeles_scenarios_{firm}_VAE.pdf")
DOWNLOADS = Path("/Users/imran/Downloads")


@dataclass(frozen=True)
class ModelLine:
    key: str
    title: str
    product_type: str
    segment: str
    model_range: str
    share_target: float


# Portefeuilles pedagogiques (3-4 modeles / firme, alignes segments types VAE)
CUSTOM_PORTFOLIOS: dict[str, list[ModelLine]] = {
    "AVE": [
        ModelLine("VQ-URB", "SwiftRide quotidien+", "ville_quotidien", "urbains_presses", "mid", 0.062),
        ModelLine("VC-URB", "Court rayon ville", "ville_courte", "urbains_presses", "entry", 0.052),
        ModelLine("VTC-NOM", "Polyvalent loisirs", "vtc_polyvalent", "nomades_multimodaux", "mid", 0.045),
        ModelLine("VTC-PRU", "Confort prudent", "vtc_polyvalent", "prudentes_confort", "mid", 0.04),
    ],
    "CAN": [
        ModelLine("RC-PERF", "Route connecte performance", "route_connecte", "endurants_performants", "mid", 0.052),
        ModelLine("SP45", "Speed pedelec 45", "speed_pedelec", "endurants_performants", "mid", 0.046),
        ModelLine("VTT-TT", "VTT enduro tout-terrain", "vtt_enduro", "aventuriers_tt", "premium", 0.038),
        ModelLine("VTC-NOM", "VTC loisirs", "vtc_polyvalent", "nomades_multimodaux", "mid", 0.042),
    ],
    "EBI": [
        ModelLine("VQ-PRU", "Quotidien confort", "ville_quotidien", "prudentes_confort", "entry", 0.058),
        ModelLine("VC-PRU", "Entree legere", "ville_courte", "prudentes_confort", "entry", 0.05),
        ModelLine("VTC-PRU", "Polyvalent securise", "vtc_polyvalent", "prudentes_confort", "mid", 0.044),
        ModelLine("VQ-URB", "Navette urbaine", "ville_quotidien", "urbains_presses", "mid", 0.036),
    ],
    "GIA": [
        ModelLine("CG-FAM", "Cargo familial", "cargo_familial", "familles_cargo", "mid", 0.055),
        ModelLine("VQ-FAM", "Transport mixte", "ville_quotidien", "familles_cargo", "mid", 0.042),
        ModelLine("VTC-NOM", "Week-end polyvalent", "vtc_polyvalent", "nomades_multimodaux", "mid", 0.04),
        ModelLine("VC-URB", "Compact urbain", "ville_courte", "urbains_presses", "entry", 0.038),
    ],
    "PED": [
        ModelLine("VQ-PRU", "Ville confort", "ville_quotidien", "prudentes_confort", "mid", 0.056),
        ModelLine("VTC-PRU", "Balades polyvalentes", "vtc_polyvalent", "prudentes_confort", "mid", 0.048),
        ModelLine("RC-PERF", "Sport route", "route_connecte", "endurants_performants", "mid", 0.035),
        ModelLine("VC-URB", "Urbain leger", "ville_courte", "urbains_presses", "entry", 0.036),
    ],
    "RID": [
        ModelLine("VTT-TT", "VTT exigeant", "vtt_exigeant", "aventuriers_tt", "premium", 0.048),
        ModelLine("VTT-END", "Enduro longues distances", "vtt_enduro", "aventuriers_tt", "premium", 0.042),
        ModelLine("RC-PERF", "Route competition", "route_connecte", "endurants_performants", "premium", 0.038),
        ModelLine("SP45", "Speed perf.", "speed_pedelec", "endurants_performants", "mid", 0.032),
    ],
    "SUR": [
        ModelLine("VTC-NOM", "Multimodal loisirs", "vtc_polyvalent", "nomades_multimodaux", "mid", 0.054),
        ModelLine("VQ-URB", "Quotidien urbain", "ville_quotidien", "urbains_presses", "mid", 0.046),
        ModelLine("SP45", "Rapide polyvalent", "speed_pedelec", "nomades_multimodaux", "mid", 0.038),
        ModelLine("VC-URB", "Compact", "ville_courte", "urbains_presses", "entry", 0.036),
    ],
    "TRE": [
        ModelLine("VQ-URB-P", "Premium urbain", "ville_quotidien", "urbains_presses", "premium", 0.052),
        ModelLine("SP45", "Speed premium", "speed_pedelec", "endurants_performants", "mid", 0.044),
        ModelLine("RC-PERF", "Route haut rendement", "route_connecte", "endurants_performants", "premium", 0.036),
        ModelLine("VTC-NOM", "Loisirs haut de gamme", "vtc_polyvalent", "nomades_multimodaux", "premium", 0.032),
    ],
    "VEL": [
        ModelLine("VC-END", "Endurance entree", "ville_courte", "endurants_performants", "entry", 0.05),
        ModelLine("SP45", "Speed accessible", "speed_pedelec", "endurants_performants", "entry", 0.046),
        ModelLine("RC-PERF", "Route milieu", "route_connecte", "endurants_performants", "mid", 0.04),
        ModelLine("VTT-END", "VTT milieu", "vtt_enduro", "aventuriers_tt", "mid", 0.032),
    ],
}

COMPANY_INTRO: dict[str, str] = {
    "AVE": (
        "<b>AVE</b> est historiquement ancree sur les <b>urbains presses</b> et le confort prudent : "
        "la strategie repose sur des volumes solides (~13 500 u. ref.) et une image innovation (~7,5/10). "
        "Le portefeuille ci-dessous alterne citadins agiles, entrees de gamme et offres loisirs pour limiter "
        "la dependance a un seul sous-segment."
    ),
    "CAN": (
        "<b>CAN</b> incarne la <b>performance routiere et sportive</b> (~14 800 u. ref.), avec une reputation "
        "technique forte (~8,2/10). Les modeles simules couvrent route connectee, speed pedelec, VTT premium "
        "et une ligne polyvalente loisirs pour diversifier les flux de marge."
    ),
    "EBI": (
        "<b>EBI</b> vise la <b>accessibilite et la prudence</b> (~11 200 u.), avec un positionnement "
        "<b>entree et milieu de gamme</b>. La simulation met l'accent sur le comfort prudent et des ponts "
        "vers l'urbain pour capter la croissance du velo quotidien."
    ),
    "GIA": (
        "<b>GIA</b> est orientee <b>familles et cargo</b> (~12 400 u.) : les scenarios testent le cargo dedie, "
        "des velos mixtes famille et des derives urbaines pour equilibrer saisonnalite et panier moyen."
    ),
    "PED": (
        "<b>PED</b> combine <b>prudentes confort</b> et touches sport (~10 800 u.). Les lignes modelisees "
        "refletent une marque « confiance » cherchant a monter en gamme sans abandonner l'entree de prix."
    ),
    "RID": (
        "<b>RID</b> est la firme <b>TT / premium performance</b> (~13 200 u., rep. ~7,8). "
        "Le rapport explore plusieurs niveaux de prix sur VTT et route, avec un speed pedelec pour elargir "
        "la base clientele."
    ),
    "SUR": (
        "<b>SUR</b> joue la carte <b>polyvalence loisirs</b> (~9 800 u.) avec une reputation plus modeste : "
        "les scenarios alternent innovation marketing, prix et capacite pour tester la resilience sur un marche exigeant."
    ),
    "TRE": (
        "<b>TRE</b> est le <b>leader volume premium urbain</b> (~15 300 u., rep. ~8,5). "
        "Les modeles combines melangent premium urbain, speed et route haut de gamme pour illustrer "
        "des compromis marge / part de segment."
    ),
    "VEL": (
        "<b>VEL</b> se positionne sur <b>endurance accessible</b> (~9 800 u.) : entree et milieu de gamme "
        "sur segments sportifs, avec un objectif de montee en volume sans exploser les couts fixes."
    ),
}


def auto_portfolio(firm_key: str) -> list[ModelLine]:
    fc = MARKET_CONFIG["firms"][firm_key]
    ds, dr = fc["default_segment"], fc["default_range"]
    candidates: list[tuple[str, str]] = []
    for pt, meta in MARKET_CONFIG["product_types"].items():
        if ds in meta.get("target_segments", []):
            candidates.append((pt, meta["label"]))
    if len(candidates) < 3:
        candidates.extend(
            [
                ("ville_quotidien", MARKET_CONFIG["product_types"]["ville_quotidien"]["label"]),
                ("vtc_polyvalent", MARKET_CONFIG["product_types"]["vtc_polyvalent"]["label"]),
            ]
        )
    seen = set()
    uniq: list[tuple[str, str]] = []
    for pt, lbl in candidates:
        if pt not in seen:
            seen.add(pt)
            uniq.append((pt, lbl))
    lines = []
    for i, (pt, lbl) in enumerate(uniq[:4]):
        rng = dr if i < 2 else ("premium" if dr == "mid" and i == 3 else dr)
        lines.append(
            ModelLine(
                key=f"AUTO{i}",
                title=lbl,
                product_type=pt,
                segment=ds,
                model_range=rng,
                share_target=0.056 - i * 0.006,
            )
        )
    return lines


def portfolio(firm_key: str) -> list[ModelLine]:
    if firm_key in CUSTOM_PORTFOLIOS:
        return CUSTOM_PORTFOLIOS[firm_key]
    return auto_portfolio(firm_key)


def build_reference_scenario(firm_key: str, line: ModelLine, period: int = 1) -> ScenarioInput:
    cfg = MARKET_CONFIG
    firm_cfg = cfg["firms"][firm_key]
    seg_cfg = cfg["segments"][line.segment]
    rng_cfg = cfg["ranges"][line.model_range]
    infl = period_inflation_factor(period)
    price = max(100.0, seg_cfg["reference_price"] * rng_cfg["price_multiplier"] * infl)
    seg_sz = segment_size(period, line.segment)
    production = max(350, int(seg_sz * line.share_target))
    adjusted_budget = max(float(production * price * 1.08), 120_000.0)
    mkt = adjusted_budget * 0.08
    rd = adjusted_budget * 0.02
    return ScenarioInput(
        firm_name=firm_key,
        period=period,
        scenario_name=f"{firm_key}-{line.key}-ref",
        model_name=line.title,
        product_type=line.product_type,
        segment=line.segment,
        model_range=line.model_range,
        product_status="active",
        price=price,
        production=production,
        promotion_rate=0.0,
        marketing_budget=round(mkt, 2),
        marketing_channels=MarketingChannels(),
        rd_budget=round(rd, 2),
        adjusted_budget=round(adjusted_budget, 2),
        previous_innovation_score=float(firm_cfg["base_rep"]),
        previous_sustainability_score=5.0,
        sustainability_tranches=1,
        competitor_attractiveness=15.0,
        opening_stock=0,
    )


def scenario_variants(base: ScenarioInput) -> list[tuple[str, ScenarioInput]]:
    adj = max(base.adjusted_budget, 1.0)
    m_max = adj * MARKET_CONFIG["constraints"]["marketing_max_pct"]
    m_ref = base.marketing_budget

    out: list[tuple[str, ScenarioInput]] = []

    out.append(
        (
            "1 — Reference equilibree",
            base.model_copy(update={"scenario_name": base.scenario_name + "|ref"}),
        )
    )

    m_push = min(m_ref * 1.65, m_max)
    out.append(
        (
            "2 — Levier marketing (plafond reglementaire)",
            base.model_copy(
                update={
                    "scenario_name": base.scenario_name + "|mkt",
                    "marketing_budget": round(m_push, 2),
                }
            ),
        )
    )

    out.append(
        (
            "3 — Politique prix (-5 %)",
            base.model_copy(
                update={
                    "scenario_name": base.scenario_name + "|promo",
                    "promotion_rate": -0.05,
                }
            ),
        )
    )

    prod_ext = int(base.production * 1.38)
    out.append(
        (
            "4 — Capacite etendue (+38 % prod.)",
            base.model_copy(
                update={
                    "scenario_name": base.scenario_name + "|cap",
                    "production": prod_ext,
                }
            ),
        )
    )

    return out


def fmt_money(x: float) -> str:
    return f"{int(round(x)):,}".replace(",", " ") + " $"


def fmt_pct(x: float) -> str:
    return f"{100.0 * x:.1f} %"


def run_all(firm_key: str) -> list[tuple[ModelLine, list[tuple[str, object]]]]:
    """Pour chaque ligne de gamme : [(scenario_label, SimulationResult), ...]."""
    rows_block: list[tuple[ModelLine, list[tuple[str, object]]]] = []
    for line in portfolio(firm_key):
        ref = build_reference_scenario(firm_key, line)
        pair_results = []
        for label, scen in scenario_variants(ref):
            pair_results.append((label, simulate(scen)))
        rows_block.append((line, pair_results))
    return rows_block


def build_pdf(firm_key: str, blocks: list[tuple[ModelLine, list[tuple[str, object]]]], out: Path) -> None:
    cfg = MARKET_CONFIG
    label = cfg["firms"][firm_key]["label"]
    intro_company = COMPANY_INTRO.get(
        firm_key,
        f"<b>{label}</b> — profil genere depuis la configuration marche (segments et volumes ref.).",
    )

    story: list = []

    story.append(
        cover_banner(
            "RAPPORT MODELES & SCENARIOS — SIMULATION VAE",
            f"{label} ({firm_key}) — Analyse multi-modeles x 4 archetypes — Periode 1 (2027)",
        )
    )
    story.append(Spacer(1, 10))

    toc_titles = [
        "Presentation de la compagnie",
        "Methodologie des scenarios",
        "Resultats par modele",
        "Conclusion et pistes strategiques",
    ]
    story.extend(toc_block(toc_titles))
    story.append(Spacer(1, 14))

    H1(story, "Presentation de la compagnie")
    story.append(Paragraph(intro_company, P_JUST))
    story.append(Spacer(1, 8))
    meta = (
        f"<b>Unites de reference (config) :</b> {cfg['firms'][firm_key]['units_ref']:,} unités<br/>"
        f"<b>Segment pivot :</b> {cfg['segments'][cfg['firms'][firm_key]['default_segment']]['label']}<br/>"
        f"<b>Marche total periode 1 :</b> {total_market_size(1):,.0f} unités<br/>"
        f"<b>Nombre de lignes simulees :</b> {len(blocks)}"
    )
    story.append(box_info(Paragraph(meta, P_INS)))
    story.append(Spacer(1, 12))

    H1(story, "Methodologie des scenarios")
    meth = (
        "Chaque <b>modele</b> du portefeuille part d'un jeu coherent : prix de liste issu du prix segment × "
        "coefficient de gamme × inflation periode 1, production calibree comme fraction de la taille du segment, "
        "budget ajuste derive du CA potentiel, marketing a 8 % et R&D a 2 % du budget ajuste (niveau autorise). "
        "Quatre variations sont appliquees : reference ; marketing pousse jusqu'au plafond 10 % du budget ajuste ; "
        "promotion nette -5 % ; hausse de production (+38 %) pour tester saturation et taux de service. "
        "Le moteur <b>simulate()</b> calcule demande logit sur le segment, ventes bornees par le stock disponible, "
        "marge et alertes reglementaires."
    )
    story.append(Paragraph(pdf_escape(meth), P_JUST))
    story.append(PageBreak())

    best_per_model: list[tuple[str, str, float, float]] = []

    H1(story, "Resultats par modele")
    for line, pairs in blocks:
        H1(story, f"{line.title} ({line.key})")
        seg_lab = cfg["segments"][line.segment]["label"]
        rng_lab = cfg["ranges"][line.model_range]["label"]
        story.append(
            Paragraph(
                pdf_escape(
                    f"Segment : {seg_lab} — Gamme : {rng_lab} — Type catalogue : {line.product_type}"
                ),
                P_SMALL,
            )
        )
        story.append(Spacer(1, 6))

        tab_rows = []
        fills = []
        best_profit = float("-inf")
        best_label = ""
        for scen_label, res in pairs:
            assert hasattr(res, "profit")
            tab_rows.append(
                [
                    scen_label.split("—")[-1].strip(),
                    str(res.sales),
                    f"{res.demand:,.0f}".replace(",", " "),
                    fmt_pct(res.service_rate),
                    fmt_money(res.revenue),
                    fmt_pct(res.margin),
                    fmt_money(res.profit),
                    fmt_pct(res.market_share_segment),
                    "Oui" if res.is_valid else "Non",
                ]
            )
            fills.append(GREEN_LT if res.profit > best_profit else None)
            if res.profit > best_profit:
                best_profit = res.profit
                best_label = scen_label
        # second pass fills: highlight max profit row
        profits = [float(pairs[i][1].profit) for i in range(len(pairs))]
        ix_best = max(range(len(profits)), key=lambda i: profits[i])
        fills = [GREEN_LT if i == ix_best else None for i in range(len(pairs))]
        best_per_model.append((line.title, pairs[ix_best][0], profits[ix_best], float(pairs[ix_best][1].margin)))

        w = CONTENT_WIDTH
        cw = [w * 0.22, w * 0.09, w * 0.09, w * 0.09, w * 0.13, w * 0.09, w * 0.13, w * 0.09, w * 0.07]
        story.append(
            table_standard(
                [
                    "Scenario",
                    "Ventes",
                    "Demande",
                    "Tx serv.",
                    "CA",
                    "Marge",
                    "Profit",
                    "PDM seg.",
                    "OK regl.",
                ],
                tab_rows,
                cw,
                row_fills=fills,
            )
        )
        story.append(Spacer(1, 10))

    story.append(PageBreak())
    H1(story, "Conclusion et pistes strategiques")

    conc_intro = (
        "Le tableau ci-dessous retient, pour chaque modele, le scenario qui maximise le <b>profit</b> "
        "sur la periode 1 (autres objectifs — part de segment, taux de service — peuvent diverger)."
    )
    story.append(Paragraph(conc_intro, P_JUST))
    story.append(Spacer(1, 8))

    recap = [[pdf_escape(m), pdf_escape(s.split("—")[-1].strip()), fmt_money(p), fmt_pct(mar)] for m, s, p, mar in best_per_model]
    story.append(
        table_standard(
            ["Modele", "Scenario gagnant", "Profit", "Marge"],
            recap,
            [CONTENT_WIDTH * 0.28, CONTENT_WIDTH * 0.38, CONTENT_WIDTH * 0.17, CONTENT_WIDTH * 0.17],
        )
    )
    story.append(Spacer(1, 12))

    n_mkt = sum(1 for _, s, _, _ in best_per_model if "marketing" in s.lower() or "Levier" in s)
    n_promo = sum(1 for _, s, _, _ in best_per_model if "prix" in s.lower() or "Politique" in s)
    n_cap = sum(1 for _, s, _, _ in best_per_model if "Capacite" in s or "capacite" in s.lower())
    n_ref = sum(1 for _, s, _, _ in best_per_model if s.startswith("1"))

    synth = (
        f"Sur ce portefeuille, les tirages gagnants se repartissent ainsi : "
        f"<b>reference</b> {n_ref}x, <b>marketing plafonne</b> {n_mkt}x, "
        f"<b>promotion -5 %</b> {n_promo}x, <b>capacite etendue</b> {n_cap}x. "
        f"Lorsque le marketing domine, la firme est probablement en dessous du plafond sur la reference — "
        f"la montee en intensite permet de gagner des parts sans violer les contraintes. "
        f"Lorsque la promo ou la capacite gagnent, la demande ou le volume servi pilotent la marge : "
        f"ajuster prix vs stock devient prioritaire avant de redemarrer des campagnes couteuses."
    )
    story.append(Paragraph(pdf_escape(synth), P_JUST))
    story.append(Spacer(1, 10))
    story.append(
        Paragraph(
            pdf_escape(
                "Limite du document : concurrence simplifiee (attractivite concurrente agregee), periode unique. "
                "Pour la coherence avec les equipes et le chiffrier Excel officiel, croiser avec les feuilles "
                "CONTROLES et RAPPORT_* du classeur VAE."
            ),
            P_SMALL,
        )
    )

    build_doc(
        out,
        story,
        firm_code=firm_key,
        left_text=f"Simulation VAE — Rapport modeles & scenarios — {label}",
    )


def main():
    ap = argparse.ArgumentParser(description="Rapport PDF multi-modeles x scenarios")
    ap.add_argument("--firm", default="CAN", choices=list(MARKET_CONFIG["firms"].keys()))
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    firm = args.firm.upper()
    blocks = run_all(firm)
    out = args.out or Path(str(OUT_REL).format(firm=firm))
    if not out.is_absolute():
        out = Path.cwd() / out
    out.parent.mkdir(parents=True, exist_ok=True)
    build_pdf(firm, blocks, out)

    dl = DOWNLOADS / out.name
    try:
        shutil.copy2(out, dl)
        print(f"PDF : {out}")
        print(f"Copie : {dl}")
    except OSError:
        print(f"PDF : {out}")
    n_scen = sum(len(p) for _, p in blocks)
    print(f"{firm} — {len(blocks)} modeles x {len(blocks[0][1]) if blocks else 0} scenarios = {n_scen} simulations")


if __name__ == "__main__":
    main()
