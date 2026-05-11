"""
Rapport PDF « style rapport_vae.pdf » : résumé exécutif, TOC, tableau de bord agrégé,
puis pour la firme et pour chaque ligne du portefeuille Excel les mêmes sections 2 à 8 —
contexte concurrentiel, portefeuille (vue firme ou focus modèle), leviers stratégiques,
scénario de référence, structure des coûts, projection P1/P4/P8 figée, recommandations —
puis synthèse décisionnelle et conclusion.

Sources : classeur VAE (FIRMS, SEGMENTS, MARKETING_MATRIX, BASE_REFERENCE_MODEL, PARAM)
         + moteur engine.simulation.simulate().

Usage:
  python3 scripts/generate_rapport_vae_style_pdf.py --firm TRE
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import openpyxl
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm

from config.market_config import MARKET_CONFIG
from engine.models import MarketingChannels, ScenarioInput, SimulationResult
from engine.simulation import (
    period_inflation_factor,
    period_to_year,
    segment_size,
    simulate,
    total_market_size,
)

sys.path.insert(0, os.path.dirname(__file__))
from vae_report_style import (
    CONTENT_WIDTH,
    GREEN_LT,
    NAVY,
    H1,
    PageBreak,
    Paragraph,
    P_INS,
    P_JUST,
    P_SMALL,
    P_TOC,
    Spacer,
    box_info,
    build_doc,
    kpi_block,
    pdf_escape,
    pdf_xml_fragment,
    table_standard,
)

DEFAULT_XLSX = Path("/Users/imran/Downloads/VAE_tout_inclus_01_05_2026_Final1_v6.xlsx")
OUT_PDF = Path("reports/Rapport_analyse_strategique_{firm}_VAE.pdf")
DOWNLOADS = Path("/Users/imran/Downloads")

# Alias courant : « VAE » pour le cadre pédagogique → firme AVE dans le classeur / moteur
FIRM_CODE_ALIASES = {"VAE": "AVE"}


def resolve_firm_code(raw: str) -> str:
    u = raw.upper().strip()
    return FIRM_CODE_ALIASES.get(u, u)


FIRM_LEGEND = {
    "TRE": "TrailRidge Mobility (TRE)",
    "AVE": "AVE Mobility (AVE)",
    "CAN": "CAN Performance (CAN)",
    "EBI": "EBI Confort (EBI)",
    "GIA": "GIA Famille (GIA)",
    "PED": "PED Prudent (PED)",
    "RID": "RID Terre & Trail (RID)",
    "SUR": "SUR Loisirs (SUR)",
    "VEL": "VEL Endurance (VEL)",
}

SEG_IDX_TO_KEY = {
    1: "urbains_presses",
    2: "prudentes_confort",
    3: "endurants_performants",
    4: "nomades_multimodaux",
    5: "familles_cargo",
    6: "aventuriers_tt",
}

RANGE_MAP = {
    "Basic": "entry",
    "Medium": "mid",
    "Standard": "mid",
    "Premium": "premium",
    "Bas": "entry",
    "Moyen": "mid",
    "Haut": "premium",
}


def product_type_for_segment(seg_idx: int) -> str:
    if seg_idx == 6:
        return "vtt_enduro"
    if seg_idx == 5:
        return "cargo_familial"
    if seg_idx == 3:
        return "route_connecte"
    if seg_idx == 4:
        return "vtc_polyvalent"
    if seg_idx == 2:
        return "vtc_polyvalent"
    return "ville_quotidien"


@dataclass
class ProdRow:
    product_key: str
    model_name: str
    segment_idx: int
    range_raw: str
    base_price: float
    units: float

    @property
    def revenue(self) -> float:
        return self.base_price * self.units


def load_products(wb: openpyxl.Workbook, firm: str) -> list[ProdRow]:
    ws = wb["BASE_REFERENCE_MODEL"]
    h = {ws.cell(1, c).value: c for c in range(1, ws.max_column + 1)}
    out: list[ProdRow] = []
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, h["Firm"]).value != firm:
            continue
        seg = ws.cell(r, h["Segment"]).value
        try:
            seg_i = int(seg)
        except (TypeError, ValueError):
            continue
        out.append(
            ProdRow(
                str(ws.cell(r, h["ProductKey"]).value),
                str(ws.cell(r, h["ModelName"]).value),
                seg_i,
                str(ws.cell(r, h["Range"]).value),
                float(ws.cell(r, h["BasePrice_RefYear"]).value or 0),
                float(ws.cell(r, h["Units_RefYear"]).value or 0),
            )
        )
    return out


def firm_ref_revenue(products: list[ProdRow]) -> float:
    return max(sum(p.revenue for p in products), 150_000.0)


def pick_focal_product(products: list[ProdRow]) -> ProdRow:
    for p in products:
        if p.segment_idx == 3 and str(p.range_raw).lower() == "premium":
            return p
    return max(products, key=lambda x: x.revenue)


def pick_ave_urbain_medium(products_ave: list[ProdRow]) -> ProdRow:
    for p in products_ave:
        if p.segment_idx == 1 and str(p.range_raw).lower() == "medium":
            return p
    return max(products_ave, key=lambda x: x.revenue)


def scenario_from_product(
    prod: ProdRow,
    firm_code: str,
    period: int,
    name: str,
    adj_budget: float,
    *,
    promo: float = 0.0,
    marketing_mult: float = 1.0,
    production_mult: float = 1.05,
    sustainability_tranches: int = 1,
    rd_pct: float | None = None,
) -> ScenarioInput:
    seg_key = SEG_IDX_TO_KEY[prod.segment_idx]
    rng = RANGE_MAP.get(prod.range_raw, "mid")
    infl = period_inflation_factor(period)
    price = max(500.0, prod.base_price * infl)
    seg_sz = segment_size(period, seg_key)
    production = max(400, int(prod.units * production_mult))
    mkt_cap = adj_budget * MARKET_CONFIG["constraints"]["marketing_max_pct"]
    mkt = min(max(adj_budget * 0.08 * marketing_mult, 30_000.0), mkt_cap)
    rd = adj_budget * (rd_pct if rd_pct is not None else 0.02)
    allowed = MARKET_CONFIG["constraints"].get("rd_allowed_pcts", [0.02, 0.05, 0.08])
    if rd_pct is None:
        rd = adj_budget * 0.02
    else:
        rd = adj_budget * rd_pct
        nearest = min(allowed, key=lambda x: abs(x - rd_pct))
        rd = adj_budget * nearest

    firm_rep = float(MARKET_CONFIG["firms"][firm_code]["base_rep"])

    return ScenarioInput(
        firm_name=firm_code,
        period=period,
        scenario_name=name,
        model_name=prod.model_name,
        product_type=product_type_for_segment(prod.segment_idx),
        segment=seg_key,
        model_range=rng,
        product_status="active",
        price=round(price, 2),
        production=production,
        promotion_rate=promo,
        marketing_budget=round(mkt, 2),
        marketing_channels=MarketingChannels(),
        rd_budget=round(rd, 2),
        adjusted_budget=round(adj_budget, 2),
        previous_innovation_score=firm_rep,
        previous_sustainability_score=5.0,
        sustainability_tranches=sustainability_tranches,
        competitor_attractiveness=14.0,
        opening_stock=0,
    )


def build_scenario_grid(
    wb: openpyxl.Workbook,
    primary_firm: str,
) -> list[tuple[str, str, ScenarioInput]]:
    """(scenario_id, firm_owner_code, scenario)"""
    pri_products = load_products(wb, primary_firm)
    ave_products = load_products(wb, "AVE")
    focal = pick_focal_product(pri_products)
    adj_pri = firm_ref_revenue(pri_products)
    adj_ave = firm_ref_revenue(ave_products)
    ave_mid = pick_ave_urbain_medium(ave_products)

    grid: list[tuple[str, str, ScenarioInput]] = []

    # Primaire — résultat vedette P2 (aligné usage pédagogique « période 2 »)
    grid.append(
        (
            f"{primary_firm}_FocalPremium_P2",
            primary_firm,
            scenario_from_product(
                focal,
                primary_firm,
                2,
                f"{primary_firm}_FocalPremium_P2",
                adj_pri,
                production_mult=1.08,
                sustainability_tranches=2,
            ),
        )
    )

    s_p1 = scenario_from_product(
        focal,
        primary_firm,
        1,
        f"{primary_firm}_FocalPremium_P1",
        adj_pri,
        production_mult=1.05,
    )
    grid.append((f"{primary_firm}_FocalPremium_P1", primary_firm, s_p1))

    # Stratégie figée : même prix/prod/marketing qu’en P1, horizons P4 et P8
    def freeze(sp: ScenarioInput, per: int, sid: str) -> ScenarioInput:
        return sp.model_copy(update={"period": per, "scenario_name": sid})

    grid.append((f"{primary_firm}_Figee_P4", primary_firm, freeze(s_p1, 4, f"{primary_firm}_Figee_P4")))
    grid.append((f"{primary_firm}_Figee_P8", primary_firm, freeze(s_p1, 8, f"{primary_firm}_Figee_P8")))

    for pr in [0.0, -0.02, -0.05, -0.10]:
        lab = f"Sweep_promo_{int(pr * 100)}pct_AVE"
        grid.append(
            (
                lab,
                "AVE",
                scenario_from_product(
                    ave_mid,
                    "AVE",
                    1,
                    lab,
                    adj_ave,
                    promo=pr,
                    production_mult=1.0,
                    marketing_mult=1.0,
                ),
            )
        )

    mkt_max = scenario_from_product(
        focal,
        primary_firm,
        1,
        f"{primary_firm}_Marketing_Max_P1",
        adj_pri,
        marketing_mult=1.25,
    )
    cap = adj_pri * MARKET_CONFIG["constraints"]["marketing_max_pct"]
    mkt_max = mkt_max.model_copy(update={"marketing_budget": round(cap, 2)})

    grid.append((f"{primary_firm}_Marketing_Max_P1", primary_firm, mkt_max))

    grid.append(
        (
            f"{primary_firm}_RD_5pct_P1",
            primary_firm,
            scenario_from_product(
                focal,
                primary_firm,
                1,
                f"{primary_firm}_RD_5pct_P1",
                adj_pri,
                rd_pct=0.05,
            ),
        )
    )

    grid.append(
        (
            f"{primary_firm}_Durabilite_2_tranches",
            primary_firm,
            scenario_from_product(
                focal,
                primary_firm,
                1,
                f"{primary_firm}_Durabilite_2_tranches",
                adj_pri,
                sustainability_tranches=2,
            ),
        )
    )

    # Variante production plus basse (sous-production volontaire)
    grid.append(
        (
            f"{primary_firm}_SousProduction_P1",
            primary_firm,
            scenario_from_product(
                focal,
                primary_firm,
                1,
                f"{primary_firm}_SousProduction_P1",
                adj_pri,
                production_mult=0.72,
            ),
        )
    )

    return grid


def fmt_money(x: float) -> str:
    return f"{int(round(x)):,}".replace(",", " ")


def fmt_pct(x: float, dec: int = 1) -> str:
    return f"{100.0 * x:.{dec}f} %"


def run_grid(grid: list[tuple[str, str, ScenarioInput]]) -> list[tuple[str, str, ScenarioInput, Any]]:
    out = []
    for sid, owner, scen in grid:
        out.append((sid, owner, scen, simulate(scen)))
    out.sort(key=lambda x: x[3].profit, reverse=True)
    return out


def segment_label_from_idx(wb: openpyxl.Workbook, idx: int) -> str:
    ws = wb["SEGMENTS"]
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value == idx:
            return str(ws.cell(r, 2).value or f"Segment {idx}")
    return f"Segment {idx}"


def growth_rows() -> list[list[str]]:
    rows = []
    p1_tot = total_market_size(1)
    s3_p1 = segment_size(1, "endurants_performants")
    for p in range(1, 9):
        tot = total_market_size(p)
        s3 = segment_size(p, "endurants_performants")
        growth = "" if p == 1 else f"+{(tot / p1_tot - 1) * 100:.0f} %"
        rows.append(
            [
                str(p),
                str(period_to_year(p)),
                f"{tot:,.0f}".replace(",", " "),
                f"{s3:,.0f}".replace(",", " "),
                growth,
            ]
        )
    return rows


def section_titles_2_to_8(firm: str) -> list[str]:
    return [
        "Contexte concurrentiel — Structure du marché VAE",
        f"Portefeuille produits {firm} — Analyse par segment",
        "Analyse des leviers stratégiques",
        f"Analyse du scénario {firm} — Résultat de référence",
        "Structure des coûts et marge",
        "Projection temporelle — Risque d'une stratégie statique",
        "Recommandations stratégiques",
    ]


def load_mm_rows(wb: openpyxl.Workbook) -> list[list[str]]:
    ws_m = wb["MARKETING_MATRIX"]
    rows: list[list[str]] = []
    for r in range(2, ws_m.max_row + 1):
        if ws_m.cell(r, 1).value is None:
            continue
        rows.append(
            [
                str(ws_m.cell(r, 1).value),
                str(ws_m.cell(r, 2).value),
                str(ws_m.cell(r, 3).value),
                str(ws_m.cell(r, 4).value),
                str(ws_m.cell(r, 5).value),
                str(ws_m.cell(r, 6).value),
            ]
        )
    return rows


def scenario_prefix(firm: str, prod: ProdRow) -> str:
    raw = "".join(c if (str(c).isalnum() or c in "_-") else "_" for c in str(prod.product_key))
    return f"{firm}_{raw}"[:40]


def build_product_bundle(prod: ProdRow, firm: str, adj: float) -> dict[str, Any]:
    pref = scenario_prefix(firm, prod)
    s_p1 = scenario_from_product(prod, firm, 1, f"{pref}_P1", adj, production_mult=1.05)
    s_p2 = scenario_from_product(
        prod,
        firm,
        2,
        f"{pref}_P2ref",
        adj,
        production_mult=1.08,
        sustainability_tranches=2,
    )

    def freeze(sp: ScenarioInput, per: int, name: str) -> ScenarioInput:
        return sp.model_copy(update={"period": per, "scenario_name": name})

    s_p4 = freeze(s_p1, 4, f"{pref}_FigP4")
    s_p8 = freeze(s_p1, 8, f"{pref}_FigP8")
    cap = adj * MARKET_CONFIG["constraints"]["marketing_max_pct"]
    s_mkt = scenario_from_product(
        prod, firm, 1, f"{pref}_MktMax", adj, production_mult=1.05, marketing_mult=1.25
    )
    s_mkt = s_mkt.model_copy(update={"marketing_budget": round(cap, 2)})
    s_promo = s_p1.model_copy(update={"promotion_rate": -0.05, "scenario_name": f"{pref}_Promo5"})
    s_under = scenario_from_product(prod, firm, 1, f"{pref}_SousProd", adj, production_mult=0.72)
    lever_specs = [
        ("Référence P1", s_p1),
        ("Marketing plafond", s_mkt),
        ("Promo −5 %", s_promo),
        ("Sous-production (−28 %)", s_under),
    ]
    levers: list[tuple[str, SimulationResult]] = [(lab, simulate(sc)) for lab, sc in lever_specs]
    ref_res = simulate(s_p2)
    return {
        "ref_scen": s_p2,
        "ref_res": ref_res,
        "levers": levers,
        "r_p1": levers[0][1],
        "r_p4": simulate(s_p4),
        "r_p8": simulate(s_p8),
    }


def append_toc_multi_scope(story: list, firm: str, legend: str, prods: list[ProdRow]) -> None:
    titles = section_titles_2_to_8(firm)
    sub_style = ParagraphStyle(
        "TOC_PART",
        parent=P_INS,
        fontName="Helvetica-Bold",
        fontSize=9.5,
        textColor=NAVY,
        spaceBefore=8,
        spaceAfter=2,
    )
    story.append(Paragraph("<b>Table des matières</b>", P_INS))
    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>1.</b> Tableau de bord global — scénarios simulés", P_TOC))
    story.append(Paragraph(pdf_escape(f"Vue firme — {legend}"), sub_style))
    for i, t in enumerate(titles, start=2):
        story.append(Paragraph(f"<b>{i}.</b> {pdf_escape(t)}", P_TOC))
    for p in prods:
        story.append(
            Paragraph(
                pdf_escape(f"Vue modèle — {p.product_key} — {p.model_name[:52]}"),
                sub_style,
            )
        )
        for i, t in enumerate(titles, start=2):
            story.append(Paragraph(f"<b>{i}.</b> {pdf_escape(t)}", P_TOC))
    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>9.</b> Synthèse décisionnelle et conclusion", P_TOC))
    story.append(PageBreak())


def append_section_2_contexte_firm(story: list, wb: openpyxl.Workbook, firm: str, w: float) -> None:
    H1(story, "2. Contexte concurrentiel — Structure du marché VAE")
    intro_mkt = (
        f"La simulation s’appuie sur <b>9 firmes</b> et <b>6 segments</b>. Les parts relatives ci-dessous "
        f"sont lues dans la feuille <b>FIRMS</b> du classeur (Share_RefYear). Le marché total de référence "
        f"est de <b>110 000</b> unités (PARAM / configuration), avec croissance <b>12 %</b> par an."
    )
    story.append(Paragraph(intro_mkt, P_JUST))
    story.append(Spacer(1, 8))

    ws_f = wb["FIRMS"]
    firm_rows = []
    for r in range(2, ws_f.max_row + 1):
        code = ws_f.cell(r, 1).value
        if not code:
            continue
        u = ws_f.cell(r, 3).value
        sh = ws_f.cell(r, 4).value
        firm_rows.append([str(code), f"{float(u or 0):,.0f}".replace(",", " "), fmt_pct(float(sh or 0))])
    firm_rows.sort(
        key=lambda x: float(x[2].replace(" %", "").replace(",", ".").replace(" ", "")),
        reverse=True,
    )
    story.append(Paragraph("<b>2.1 Parts de marché relatives — année de référence</b>", P_INS))
    story.append(Spacer(1, 4))
    story.append(
        table_standard(
            ["Firme", "Unités (réf.)", "PDM"],
            firm_rows,
            [w * 0.28, w * 0.36, w * 0.36],
        )
    )

    ws_s = wb["SEGMENTS"]
    seg_rows = []
    for r in range(2, ws_s.max_row + 1):
        idx = ws_s.cell(r, 1).value
        if idx is None:
            continue
        seg_rows.append(
            [
                str(idx),
                str(ws_s.cell(r, 2).value or ""),
                fmt_pct(float(ws_s.cell(r, 3).value or 0)),
                f"{float(ws_s.cell(r, 5).value or 0):,.0f}".replace(",", " "),
                f"{float(ws_s.cell(r, 4).value or 0):,.0f}".replace(",", " ") + " $",
                fmt_pct(float(ws_s.cell(r, 6).value or 0)),
            ]
        )
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>2.2 Structure du marché par segment</b>", P_INS))
    story.append(Spacer(1, 4))
    story.append(
        table_standard(
            ["Seg.", "Description", "Part", "Unités réf.", "Prix préf.", "Online"],
            seg_rows,
            [w * 0.06, w * 0.30, w * 0.10, w * 0.14, w * 0.14, w * 0.10],
        )
    )

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>2.3 Croissance du marché — projection P1–P8</b>", P_INS))
    story.append(Spacer(1, 4))
    gr = growth_rows()
    story.append(
        table_standard(
            ["Période", "Année", "Marché total", "Seg. 3 (Endurants)", "Croiss. vs P1"],
            gr,
            [w * 0.12, w * 0.12, w * 0.22, w * 0.22, w * 0.22],
        )
    )
    story.append(PageBreak())


def append_section_2_contexte_model(
    story: list, wb: openpyxl.Workbook, firm: str, w: float, prod: ProdRow, legend: str
) -> None:
    H1(story, "2. Contexte concurrentiel — Structure du marché VAE")
    seg_lab = segment_label_from_idx(wb, prod.segment_idx)
    story.append(
        Paragraph(
            f"<b>Vue modèle ({pdf_xml_fragment(prod.product_key)}).</b> Le cadre concurrentiel est identique à la partie firme ; "
            f"ici on met l’accent sur le <b>segment {prod.segment_idx}</b> ({pdf_xml_fragment(seg_lab)}), où est positionné ce produit.",
            P_JUST,
        )
    )
    story.append(Spacer(1, 8))
    ws_s = wb["SEGMENTS"]
    focus_row = None
    for r in range(2, ws_s.max_row + 1):
        if ws_s.cell(r, 1).value == prod.segment_idx:
            focus_row = [
                str(ws_s.cell(r, 1).value),
                str(ws_s.cell(r, 2).value or ""),
                fmt_pct(float(ws_s.cell(r, 3).value or 0)),
                f"{float(ws_s.cell(r, 5).value or 0):,.0f}".replace(",", " "),
                f"{float(ws_s.cell(r, 4).value or 0):,.0f}".replace(",", " ") + " $",
                fmt_pct(float(ws_s.cell(r, 6).value or 0)),
            ]
            break
    if focus_row:
        story.append(Paragraph("<b>2.1 Segment cible du modèle</b>", P_INS))
        story.append(Spacer(1, 4))
        story.append(
            table_standard(
                ["Seg.", "Description", "Part", "Unités réf.", "Prix préf.", "Online"],
                [focus_row],
                [w * 0.06, w * 0.30, w * 0.10, w * 0.14, w * 0.14, w * 0.10],
            )
        )
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>2.2 Rappel — croissance globale P1–P8</b>", P_INS))
    story.append(Spacer(1, 4))
    story.append(
        table_standard(
            ["Période", "Année", "Marché total", "Seg. 3 (Endurants)", "Croiss. vs P1"],
            growth_rows(),
            [w * 0.12, w * 0.12, w * 0.22, w * 0.22, w * 0.22],
        )
    )
    story.append(
        Paragraph(
            pdf_escape(
                f"Les tableaux détaillés FIRMS / SEGMENTS complets figurent dans la vue firme ({legend})."
            ),
            P_SMALL,
        )
    )
    story.append(PageBreak())


def append_section_3_portefeuille_firm(
    story: list, wb: openpyxl.Workbook, firm: str, w: float, prods: list[ProdRow], focal_prod: ProdRow
) -> None:
    H1(story, f"3. Portefeuille produits {firm} — Analyse par segment")
    port_rows = []
    for p in prods:
        port_rows.append(
            [
                p.product_key,
                p.model_name[:32],
                f"{p.segment_idx} — {segment_label_from_idx(wb, p.segment_idx)[:22]}",
                p.range_raw,
                f"{p.base_price:,.0f}".replace(",", " ") + " $",
                f"{p.units:,.0f}".replace(",", " "),
            ]
        )
    story.append(
        table_standard(
            ["Code", "Nom produit", "Segment", "Gamme", "Prix réf.", "Unités réf."],
            port_rows,
            [w * 0.10, w * 0.28, w * 0.26, w * 0.12, w * 0.12, w * 0.12],
        )
    )
    story.append(
        Paragraph(
            pdf_escape(
                f"Ligne stratégique mise en avant dans les scénarios agrégés : {focal_prod.product_key} — "
                f"{focal_prod.model_name} (segment {focal_prod.segment_idx}, gamme {focal_prod.range_raw})."
            ),
            P_SMALL,
        )
    )
    story.append(PageBreak())


def append_section_3_portefeuille_model(story: list, wb: openpyxl.Workbook, firm: str, w: float, prod: ProdRow) -> None:
    H1(story, f"3. Portefeuille produits {firm} — Analyse par segment")
    story.append(
        Paragraph(
            f"<b>Focus modèle.</b> Analyse restreinte à la référence <b>{pdf_xml_fragment(prod.product_key)}</b> ; "
            f"le portefeuille complet est présenté dans la partie firme.",
            P_JUST,
        )
    )
    story.append(Spacer(1, 8))
    row = [
        prod.product_key,
        prod.model_name[:36],
        f"{prod.segment_idx} — {segment_label_from_idx(wb, prod.segment_idx)[:24]}",
        prod.range_raw,
        f"{prod.base_price:,.0f}".replace(",", " ") + " $",
        f"{prod.units:,.0f}".replace(",", " "),
    ]
    story.append(
        table_standard(
            ["Code", "Nom produit", "Segment", "Gamme", "Prix réf.", "Unités réf."],
            [row],
            [w * 0.10, w * 0.28, w * 0.26, w * 0.12, w * 0.12, w * 0.12],
        )
    )
    story.append(PageBreak())


def append_section_4_leviers_firm(
    story: list, results: list[tuple[str, str, ScenarioInput, Any]], firm: str, w: float, mm_rows: list[list[str]]
) -> None:
    H1(story, "4. Analyse des leviers stratégiques")

    sweep_rows = []
    for sid, owner, scen, res in results:
        if sid.startswith("Sweep_promo") and owner == "AVE":
            sweep_rows.append(
                [
                    sid.replace("Sweep_promo_", "").replace("_AVE", ""),
                    f"{scen.price * (1 + scen.promotion_rate):,.0f}".replace(",", " ") + " $",
                    fmt_money(res.revenue),
                    fmt_money(res.profit),
                    fmt_pct(res.margin),
                    fmt_pct(res.service_rate, 0),
                    f"{max(0, res.demand - res.sales):,.0f}".replace(",", " "),
                ]
            )
    if sweep_rows:
        story.append(
            Paragraph(
                "<b>4.1 Impact de la promotion (sweep, firme AVE, produit urbain milieu de gamme, P1)</b>",
                P_INS,
            )
        )
        story.append(Spacer(1, 4))
        story.append(
            table_standard(
                ["Promo", "Prix net", "CA ($)", "Profit ($)", "Marge", "Service", "Écart demande"],
                sweep_rows,
                [w * 0.12, w * 0.14, w * 0.14, w * 0.14, w * 0.10, w * 0.09, w * 0.13],
            )
        )

    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            "<b>4.2 Marketing — coefficients par canal (feuille MARKETING_MATRIX)</b>",
            P_INS,
        )
    )
    story.append(Spacer(1, 4))
    story.append(
        table_standard(
            ["Segment", "Digital", "Social", "Influenceur", "Affichage", "Événements"],
            mm_rows,
            [w * 0.14, w * 0.14, w * 0.14, w * 0.16, w * 0.14, w * 0.14],
        )
    )

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>4.3 Sous-production — indicateurs sur scénarios représentatifs</b>", P_INS))
    story.append(Spacer(1, 4))
    sub_prod_rows = []
    for sid, owner, scen, res in results:
        if owner != firm:
            continue
        if sid in (f"{firm}_SousProduction_P1", f"{firm}_Figee_P4", f"{firm}_Figee_P8", f"{firm}_FocalPremium_P1"):
            lost = max(0.0, res.demand - res.sales)
            sub_prod_rows.append(
                [
                    sid.replace("_", " ")[:30],
                    str(scen.production),
                    f"{lost:,.0f}".replace(",", " "),
                    fmt_pct(res.service_rate, 0),
                ]
            )
    story.append(
        table_standard(
            ["Scénario", "Production", "Écart demande", "Service"],
            sub_prod_rows,
            [w * 0.38, w * 0.18, w * 0.22, w * 0.22],
        )
    )
    story.append(PageBreak())


def append_section_4_leviers_model(
    story: list, firm: str, w: float, prod: ProdRow, bundle: dict[str, Any], mm_rows: list[list[str]]
) -> None:
    H1(story, "4. Analyse des leviers stratégiques")
    story.append(
        Paragraph(
            f"<b>Vue modèle {pdf_xml_fragment(prod.product_key)}.</b> Quatre tirages sur la même base calée Excel "
            f"(P1), pour isoler marketing, prix et capacité.",
            P_JUST,
        )
    )
    story.append(Spacer(1, 8))
    rows = []
    for lab, res in bundle["levers"]:
        rows.append(
            [
                lab,
                str(res.sales),
                fmt_money(res.revenue),
                fmt_money(res.profit),
                fmt_pct(res.margin),
                fmt_pct(res.service_rate, 0),
                f"{max(0, res.demand - res.sales):,.0f}".replace(",", " "),
            ]
        )
    story.append(Paragraph("<b>4.1 Leviers simulés — même produit, décisions distinctes (P1)</b>", P_INS))
    story.append(Spacer(1, 4))
    story.append(
        table_standard(
            ["Levier", "Ventes", "CA ($)", "Profit ($)", "Marge", "Service", "Écart demande"],
            rows,
            [w * 0.22, w * 0.08, w * 0.13, w * 0.13, w * 0.10, w * 0.09, w * 0.12],
        )
    )
    seg_focus = str(prod.segment_idx)
    mm_line = next((r for r in mm_rows if r[0] == seg_focus), None)
    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            "<b>4.2 Marketing — coefficients du segment du modèle (MARKETING_MATRIX)</b>",
            P_INS,
        )
    )
    story.append(Spacer(1, 4))
    if mm_line:
        story.append(
            table_standard(
                ["Segment", "Digital", "Social", "Influenceur", "Affichage", "Événements"],
                [mm_line],
                [w * 0.14, w * 0.14, w * 0.14, w * 0.16, w * 0.14, w * 0.14],
            )
        )
    else:
        story.append(Paragraph("Ligne segment introuvable dans MARKETING_MATRIX.", P_SMALL))
    story.append(PageBreak())


def append_section_5_reference(
    story: list,
    w: float,
    *,
    firm: str,
    legend: str,
    prod: ProdRow,
    ref_scen: ScenarioInput,
    ref_res: SimulationResult,
    ref_label: str,
) -> None:
    H1(story, f"5. Analyse du scénario {firm} — Résultat de référence")
    story.append(
        Paragraph(
            f"Calibrage analysé : <b>{pdf_xml_fragment(ref_label)}</b> — produit <b>{pdf_xml_fragment(prod.product_key)}</b> "
            f"({pdf_xml_fragment(prod.model_name)}), période moteur <b>{ref_scen.period}</b> ({period_to_year(ref_scen.period)}).",
            P_JUST,
        )
    )
    story.append(Spacer(1, 8))
    param_pairs = [
        ("Firme", legend),
        ("Produit", f"{prod.product_key} — {prod.model_name}"),
        ("Segment", SEG_IDX_TO_KEY[prod.segment_idx]),
        ("Gamme", prod.range_raw),
        ("Période", f"{ref_scen.period} ({period_to_year(ref_scen.period)})"),
        ("Prix catalogue", f"{fmt_money(ref_scen.price)} $"),
        ("Promotion", fmt_pct(ref_scen.promotion_rate)),
        ("Production", f"{ref_scen.production} unités"),
        ("Marketing", f"{fmt_money(ref_scen.marketing_budget)} $"),
        ("Recherche et développement", f"{fmt_money(ref_scen.rd_budget)} $"),
    ]
    story.append(
        table_standard(
            ["Paramètre", "Valeur"],
            [[pdf_escape(a), pdf_escape(b)] for a, b in param_pairs],
            [w * 0.38, w * 0.62],
        )
    )
    story.append(Spacer(1, 8))
    kpi_ref = [
        ("Ventes", f"{ref_res.sales} u."),
        ("CA", f"{fmt_money(ref_res.revenue)} $"),
        ("Profit", f"{fmt_money(ref_res.profit)} $"),
        ("Marge", fmt_pct(ref_res.margin)),
        ("PDM segment", fmt_pct(ref_res.market_share_segment)),
        ("PDM globale", fmt_pct(ref_res.market_share)),
        ("Taux de service", fmt_pct(ref_res.service_rate, 0)),
        ("Stock final (est.)", f"{ref_res.forecast_ending_stock_units} u."),
        ("Coût stockage (est.)", f"{fmt_money(ref_res.inventory_carrying_cost)} $"),
    ]
    story.append(
        table_standard(
            ["KPI", "Résultat"],
            [[pdf_escape(a), pdf_escape(b)] for a, b in kpi_ref],
            [w * 0.42, w * 0.58],
        )
    )
    story.append(PageBreak())


def append_section_6_costs(story: list, w: float, prod: ProdRow) -> None:
    H1(story, "6. Structure des coûts et marge")
    rng_key = RANGE_MAP.get(prod.range_raw, "mid")
    rc = MARKET_CONFIG["ranges"][rng_key]
    cog = MARKET_CONFIG["cogs_ratios"][rng_key]
    story.append(
        Paragraph(
            pdf_escape(
                f"Gamme moteur « {prod.range_raw} » (modèle {prod.product_key}) : COGS ~ {cog*100:.0f} % du prix net, "
                f"distribution magasin {rc['distribution_rate']*100:.0f} % du CA (principalement). "
                f"SAV et frais généraux sont indexés sur le budget ajusté (proxy CA ref.)."
            ),
            P_JUST,
        )
    )
    cost_rows = [
        ["COGS (production)", f"{cog*100:.0f} % du prix net", f"{cog*100:.1f} %"],
        ["Distribution", f"{rc['distribution_rate']*100:.0f} % du CA hors prime", f"{rc['distribution_rate']*100:.1f} %"],
        ["Marketing et recherche et développement", "Budgets déclarés", "—"],
        ["Stockage (est.)", "Règle diagnostics stock", "voir KPI"],
    ]
    story.append(Spacer(1, 8))
    story.append(
        table_standard(
            ["Poste", "Règle", "% indicatif"],
            cost_rows,
            [w * 0.28, w * 0.52, w * 0.20],
        )
    )
    story.append(PageBreak())


def append_section_7_projection(
    story: list, w: float, r_p1: SimulationResult, r_p4: SimulationResult, r_p8: SimulationResult, scope_note: str
) -> None:
    H1(story, "7. Projection temporelle — Risque d'une stratégie statique")
    story.append(Paragraph(pdf_escape(scope_note), P_JUST))
    story.append(Spacer(1, 8))
    proj_rows = [
        ["Profit ($)", fmt_money(r_p1.profit), fmt_money(r_p4.profit), fmt_money(r_p8.profit)],
        ["Marge", fmt_pct(r_p1.margin), fmt_pct(r_p4.margin), fmt_pct(r_p8.margin)],
        ["PDM globale", fmt_pct(r_p1.market_share), fmt_pct(r_p4.market_share), fmt_pct(r_p8.market_share)],
        ["Service", fmt_pct(r_p1.service_rate, 0), fmt_pct(r_p4.service_rate, 0), fmt_pct(r_p8.service_rate, 0)],
    ]
    story.append(
        table_standard(
            ["Indicateur", "P1", "P4", "P8"],
            proj_rows,
            [w * 0.28, w * 0.24, w * 0.24, w * 0.24],
        )
    )
    story.append(PageBreak())


def append_section_8_recommandations_firm(
    story: list,
    legend: str,
    ref_res: SimulationResult,
    focal_prod: ProdRow,
    mm_rows: list[list[str]],
    results: list[tuple[str, str, ScenarioInput, Any]],
) -> None:
    H1(story, "8. Recommandations stratégiques")
    story.append(
        Paragraph(
            f"<b>Vue firme.</b> Synthèse pour <b>{pdf_xml_fragment(legend)}</b> à partir du scénario vedette et du maillage multi-scénarios ; "
            f"chaque fiche modèle qui suit renouvelle les sections 2 à 8 au niveau de la référence produit.",
            P_JUST,
        )
    )
    story.append(Spacer(1, 8))
    recs: list[str] = []
    if ref_res.service_rate < 0.95:
        recs.append(
            "<b>1. Monter en capacité.</b> Le scénario de référence n’atteint pas 100 % de service : "
            "augmenter la production ou le stock de départ pour limiter les ventes perdues."
        )
    else:
        recs.append(
            "<b>1. Capacité.</b> Bon taux de service sur le scénario vedette ; sécuriser une marge sur "
            "stock final pour absorber les oscillations de demande."
        )

    seg_focus = focal_prod.segment_idx
    mm_line = next((r for r in mm_rows if r[0] == str(seg_focus)), None)
    if mm_line:
        recs.append(
            f"<b>2. Marketing.</b> Sur le segment {seg_focus}, les coefficients MARKETING_MATRIX suggèrent "
            f"d’allouer prioritairement les postes aux meilleurs coefficients relatifs "
            f"(Digital {mm_line[1]}, Influenceur {mm_line[3]}, …)."
        )

    best_promo_row = next((x for x in results if x[0] == "Sweep_promo_0pct_AVE"), None)
    worst_promo_row = next((x for x in results if x[0] == "Sweep_promo_-10pct_AVE"), None)
    if best_promo_row and worst_promo_row:
        delta_p = best_promo_row[3].profit - worst_promo_row[3].profit
        recs.append(
            f"<b>3. Prix / promotion.</b> Sur le produit AVE de sweep, l’écart de profit entre 0 % et −10 % "
            f"de promo est d’environ <b>{fmt_money(delta_p)} $</b> — toute remise doit être assortie "
            f"d’une hausse de volume utile (production)."
        )

    recs.append(
        "<b>4. Adaptation périodique.</b> Les scénarios « Figée » montrent la dérive possible si les décisions "
        "ne sont pas révisées alors que le marché grossit (+12 % / an)."
    )

    recs.append(
        "<b>5. Cohérence prix / gamme.</b> Vérifier dans Excel les planchers par gamme (CONTROLE_DECISIONS / "
        "règles prix) pour éviter les pénalités PriceFit."
    )

    for r in recs:
        story.append(Paragraph(r, P_JUST))
        story.append(Spacer(1, 6))


def append_section_8_recommandations_model(
    story: list, prod: ProdRow, bundle: dict[str, Any], mm_rows: list[list[str]]
) -> None:
    H1(story, "8. Recommandations stratégiques")
    ref_res: SimulationResult = bundle["ref_res"]
    levers: list[tuple[str, SimulationResult]] = bundle["levers"]
    best_lab, best_r = max(levers, key=lambda x: x[1].profit)
    story.append(
        Paragraph(
            f"<b>Vue modèle {pdf_xml_fragment(prod.product_key)}.</b> Levier le plus rentable sur les quatre tirages : "
            f"<b>{pdf_xml_fragment(best_lab)}</b> (profit {fmt_money(best_r.profit)} $).",
            P_JUST,
        )
    )
    story.append(Spacer(1, 8))
    recs: list[str] = []
    if ref_res.service_rate < 0.95:
        recs.append(
            "<b>1. Capacité.</b> Sur la référence P2 de ce modèle, le service est sous le plafond : "
            "prioriser production ou stock pour ce segment avant d’accentuer les remises."
        )
    else:
        recs.append(
            "<b>1. Capacité.</b> Service élevé sur la référence ; surveiller le stock final pour limiter les coûts de stockage."
        )
    mm_line = next((r for r in mm_rows if r[0] == str(prod.segment_idx)), None)
    if mm_line:
        recs.append(
            f"<b>2. Marketing.</b> Segment {prod.segment_idx} : adapter le mix aux coefficients "
            f"(Digital {mm_line[1]}, Influenceurs {mm_line[3]}, …)."
        )
    ref_p1 = levers[0][1]
    promo_r = levers[2][1]
    if promo_r.profit > ref_p1.profit:
        recs.append(
            "<b>3. Prix.</b> La promo −5 % améliore le profit vs référence P1 sur ce modèle : "
            "la demande réagit favorablement à ce niveau de remise."
        )
    elif promo_r.profit < ref_p1.profit:
        recs.append(
            "<b>3. Prix.</b> La promo −5 % dégrade le profit vs référence : protéger la marge ou compenser par volume/cross-sell."
        )
    recs.append(
        "<b>4. Horizon.</b> Réviser prix et capacité à chaque période : la projection P4/P8 montre la sensibilité "
        "à une stratégie figée."
    )
    for r in recs:
        story.append(Paragraph(r, P_JUST))
        story.append(Spacer(1, 6))


def main():
    ap = argparse.ArgumentParser(description="Rapport analyse stratégique style rapport_vae.pdf")
    ap.add_argument(
        "--firm",
        default="TRE",
        help="Code firme (AVE, CAN, …). « VAE » est accepté comme alias de AVE.",
    )
    ap.add_argument("--workbook", type=Path, default=DEFAULT_XLSX)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    firm = resolve_firm_code(args.firm)
    if firm not in MARKET_CONFIG["firms"]:
        raise SystemExit(
            f"Firme inconnue : {args.firm!r}. Codes valides : {', '.join(sorted(MARKET_CONFIG['firms']))} (VAE → AVE)."
        )
    xlsx = args.workbook.expanduser()
    if not xlsx.exists():
        raise SystemExit(f"Classeur introuvable : {xlsx}")

    wb = openpyxl.load_workbook(xlsx, data_only=True)
    grid = build_scenario_grid(wb, firm)
    results = run_grid(grid)

    prods = load_products(wb, firm)
    focal_prod = pick_focal_product(prods)
    adj_pri = firm_ref_revenue(prods)
    mm_rows = load_mm_rows(wb)
    product_bundles = {p.product_key: build_product_bundle(p, firm, adj_pri) for p in prods}
    legend = FIRM_LEGEND.get(firm, f"{firm} ({firm})")
    footer = f"Rapport de Simulation VAE — {legend} — Usage interne"

    best_sid, best_owner, best_scen, best_res = results[0]
    worst_sid, worst_owner, worst_scen, worst_res = results[-1]
    max_margin = max(r[3].margin for r in results)

    primary_rows = [x for x in results if x[1] == firm]
    primary_rows.sort(key=lambda x: x[3].profit, reverse=True)
    best_primary = primary_rows[0] if primary_rows else results[0]

    # Résumé exécutif (style narratif)
    n_scen = len(results)
    n_models = len(prods)
    exec_txt = (
        f"<b>Résumé exécutif.</b> Rapport VAE pour <b>{pdf_escape(legend)}</b>. "
        f"<b>{n_scen} scénarios</b> agrégés (grille multi-scénarios, produit vedette) ; puis, pour chaque référence "
        f"catalogue (<b>{n_models} modèle(s)</b>), les sections <b>2 à 8</b> sont rejouées : "
        f"contexte marché, portefeuille, leviers, résultat de référence, structure des coûts, projection « figée » "
        f"et recommandations. Meilleur profit global : <b>{pdf_escape(best_sid)}</b> "
        f"({fmt_money(best_res.profit)} $). "
        f"Meilleur scénario primaire {firm} : <b>{pdf_escape(best_primary[0])}</b> "
        f"({fmt_money(best_primary[3].profit)} $). Croissance marché <b>12 %</b> / an (PARAM)."
    )

    story: list = []

    hero_style = ParagraphStyle(
        "RAPPORT_HERO",
        parent=P_INS,
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=NAVY,
        alignment=TA_CENTER,
        spaceAfter=8,
    )
    sub_style = ParagraphStyle(
        "RAPPORT_SUB",
        parent=P_INS,
        fontSize=10,
        leading=14,
        alignment=TA_CENTER,
        spaceAfter=14,
        textColor=NAVY,
    )

    story.append(Spacer(1, 6))
    story.append(Paragraph("RAPPORT D'ANALYSE STRATÉGIQUE", hero_style))
    story.append(
        Paragraph(
            pdf_escape(f"Simulation de marché VAE — Résultats, lecture concurrentielle et recommandations — {legend}"),
            sub_style,
        )
    )
    story.append(Paragraph(exec_txt, P_JUST))
    story.append(Spacer(1, 12))

    append_toc_multi_scope(story, firm, legend, prods)

    w = CONTENT_WIDTH
    ref_sid, _ref_own, ref_scen, ref_res = next(x for x in results if x[0] == f"{firm}_FocalPremium_P2")

    # ─── 1. Tableau de bord ─────────────────────────────────────────────────
    H1(story, f"1. Tableau de bord — vue d'ensemble ({n_scen} scénarios)")
    kpi_items = [
        ("Meilleur profit (toutes firmes)", f"{fmt_money(best_res.profit)} $", NAVY),
        ("Meilleur scénario (firme suivie)", f"{fmt_money(best_primary[3].profit)} $ — {best_primary[0][:28]}", NAVY),
        ("Pire cas (tri global)", f"{fmt_money(worst_res.profit)} $ — {worst_sid[:24]}", NAVY),
        ("Marge max. (tous scénarios)", fmt_pct(max_margin), NAVY),
    ]
    story.append(kpi_block(kpi_items))
    story.append(Spacer(1, 10))

    cmp_rows = []
    fills = []
    for sid, owner, scen, res in results:
        cmp_rows.append(
            [
                sid.replace("_", " ")[:34],
                owner,
                str(scen.period),
                str(res.sales),
                fmt_money(res.revenue),
                fmt_money(res.profit),
                fmt_pct(res.margin),
                fmt_pct(res.market_share),
                fmt_pct(res.service_rate, 0),
            ]
        )
        fills.append(GREEN_LT if owner == firm else None)

    cw = [w * 0.26, w * 0.06, w * 0.05, w * 0.07, w * 0.11, w * 0.11, w * 0.08, w * 0.09, w * 0.09]
    story.append(
        Paragraph("<b>1.1 Comparatif — scénarios classés par profit</b>", P_INS)
    )
    story.append(Spacer(1, 4))
    story.append(
        table_standard(
            ["Scénario", "Fir.", "P.", "Ventes", "CA ($)", "Profit ($)", "Marge", "PDM", "Serv."],
            cmp_rows,
            cw,
            row_fills=fills,
        )
    )
    story.append(
        Paragraph(
            pdf_escape(
                "Lignes triées par profit décroissant. Surbrillance verte = scénarios de la firme suivie. "
                "P. = période moteur. PDM = part de marché globale (ventes / marché total)."
            ),
            P_SMALL,
        )
    )
    story.append(PageBreak())

    part_hdr = ParagraphStyle(
        "RAPPORT_PART",
        parent=P_INS,
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=NAVY,
        alignment=TA_CENTER,
        spaceAfter=6,
    )
    story.append(Paragraph("<b>PARTIE — VUE FIRME</b>", part_hdr))
    story.append(Spacer(1, 4))

    append_section_2_contexte_firm(story, wb, firm, w)
    append_section_3_portefeuille_firm(story, wb, firm, w, prods, focal_prod)
    append_section_4_leviers_firm(story, results, firm, w, mm_rows)
    append_section_5_reference(
        story,
        w,
        firm=firm,
        legend=legend,
        prod=focal_prod,
        ref_scen=ref_scen,
        ref_res=ref_res,
        ref_label=ref_sid,
    )
    append_section_6_costs(story, w, focal_prod)
    try:
        r_p1_f = next(x[3] for x in results if x[0] == f"{firm}_FocalPremium_P1")
        r_p4_f = next(x[3] for x in results if x[0] == f"{firm}_Figee_P4")
        r_p8_f = next(x[3] for x in results if x[0] == f"{firm}_Figee_P8")
        append_section_7_projection(
            story,
            w,
            r_p1_f,
            r_p4_f,
            r_p8_f,
            "Les scénarios « Figée » répliquent les mêmes prix, production et budgets marketing et recherche et développement que la référence P1 du produit vedette, aux périodes 4 et 8 : le marché et les coûts évoluent malgré tout.",
        )
    except StopIteration:
        story.append(PageBreak())
        H1(story, "7. Projection temporelle — Risque d'une stratégie statique")
        story.append(Paragraph("Projection indisponible (scénarios figés absents).", P_SMALL))
        story.append(PageBreak())

    append_section_8_recommandations_firm(story, legend, ref_res, focal_prod, mm_rows, results)

    for prod in prods:
        story.append(PageBreak())
        story.append(
            Paragraph(
                pdf_escape(f"PARTIE — VUE MODÈLE — {prod.product_key}"),
                part_hdr,
            )
        )
        story.append(Spacer(1, 4))
        b = product_bundles[prod.product_key]
        append_section_2_contexte_model(story, wb, firm, w, prod, legend)
        append_section_3_portefeuille_model(story, wb, firm, w, prod)
        append_section_4_leviers_model(story, firm, w, prod, b, mm_rows)
        append_section_5_reference(
            story,
            w,
            firm=firm,
            legend=legend,
            prod=prod,
            ref_scen=b["ref_scen"],
            ref_res=b["ref_res"],
            ref_label=b["ref_scen"].scenario_name,
        )
        append_section_6_costs(story, w, prod)
        append_section_7_projection(
            story,
            w,
            b["r_p1"],
            b["r_p4"],
            b["r_p8"],
            "Décisions figées comme en P1 pour ce modèle ; passage aux périodes 4 et 8 pour mesurer la dérive du marché.",
        )
        append_section_8_recommandations_model(story, prod, b, mm_rows)

    story.append(PageBreak())

    # ─── 9. Synthèse ──────────────────────────────────────────────────────────
    H1(story, "9. Synthèse décisionnelle et conclusion")
    syn_rows = [
        ["Priorité capacité / service", "Réduit ventes perdues", "P3", "Haute"],
        ["Pilotage marketing par canal", "Alignement coefficients segment", "P3–P4", "Moyenne"],
        ["Maîtrise des promotions", "Eviter erosion marge sans volume", "P3", "Haute"],
        ["Révision décisionnelle chaque période", "Évite dérive « stratégie figée »", "P3–P8", "Critique"],
    ]
    story.append(
        table_standard(
            ["Action", "Impact attendu", "Horizon", "Priorité"],
            syn_rows,
            [w * 0.34, w * 0.30, w * 0.14, w * 0.22],
        )
    )
    story.append(Spacer(1, 12))

    conclusion = (
        f"<b>Conclusion.</b> {pdf_escape(legend)} dispose d’un portefeuille structuré et d’un scénario vedette "
        f"({pdf_escape(ref_sid)}) dans la grille agrégée ; chaque modèle du catalogue dispose en outre d’un bloc "
        f"sections 2–8 pour comparer leviers et projection à l’échelle de la référence produit. "
        f"La dynamique de marché (+12 % / an) impose de réaligner prix, capacité et mix marketing à chaque période. "
        f"Les données structurelles (parts, segments, matrice marketing) proviennent du classeur "
        f"<b>{pdf_escape(xlsx.name)}</b> ; les résultats chiffrés du <b>moteur Python simulate()</b>. "
        f"Document généré le <b>{date.today().isoformat()}</b>."
    )
    story.append(Paragraph(conclusion, P_JUST))
    story.append(Spacer(1, 10))
    story.append(
        Paragraph(
            pdf_escape(
                "Sources : feuilles FIRMS, SEGMENTS, MARKETING_MATRIX, BASE_REFERENCE_MODEL du classeur VAE ; "
                "moteur open-source du dépôt BotMarketing (engine.simulation)."
            ),
            P_SMALL,
        )
    )

    wb.close()

    out = args.out or Path(str(OUT_PDF).format(firm=firm))
    if not out.is_absolute():
        out = Path.cwd() / out
    out.parent.mkdir(parents=True, exist_ok=True)
    build_doc(out, story, firm_code=firm, left_text=footer)

    dl = DOWNLOADS / out.name
    try:
        shutil.copy2(out, dl)
        print(f"PDF : {out}")
        print(f"Copie : {dl}")
    except OSError:
        print(f"PDF : {out}")


if __name__ == "__main__":
    main()
