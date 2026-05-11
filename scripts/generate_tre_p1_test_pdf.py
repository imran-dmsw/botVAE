"""
Genere un rapport PDF pour le test bout en bout TRE P1 (simulation VAE).
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from vae_report_style import *  # noqa: F403

import openpyxl
from reportlab.lib.units import mm

from run_tre_p1_e2e_test import (
    MARKETING_TRE,
    PRODUCTIONS,
    OUT as TEST_XLSX,
    WORKBOOK_DEFAULT,
    budget_base_adjusted_tre_p1,
    evaluate_controles_tre_p1_python,
    inject_valid_decisions,
    price_list_p040_est,
    seuils_marketing,
    tre_revenue_ref_year,
)

PDF_DOWNLOADS = Path("/Users/imran/Downloads/Rapport_test_TRE_P1_VAE.pdf")
PDF_REL = Path("reports/Rapport_test_TRE_P1_VAE.pdf")


def format_money(x: float | int | None) -> str:
    if x is None:
        return "n/a"
    return f"{int(round(float(x))):,}".replace(",", " ") + " $"


def row_fill_for_controle(statut: str):
    s = str(statut)
    if "✗" in s:
        return RED_LT
    if "⚠" in s or "Attention" in s:
        return AMBER_LT
    return GREEN_LT


def main():
    wb_path = TEST_XLSX if TEST_XLSX.exists() else WORKBOOK_DEFAULT
    wb = openpyxl.load_workbook(wb_path)
    inject_valid_decisions(wb)
    rev_ref = tre_revenue_ref_year(wb)
    budget_base = budget_base_adjusted_tre_p1(wb)
    rd_budget = int(round(0.02 * budget_base))
    prix_p040 = price_list_p040_est(wb)
    mkt_min, mkt_max = seuils_marketing(wb, "TRE", 1)
    report, n_blocked = evaluate_controles_tre_p1_python(wb)

    story = []
    story.append(
        cover_banner(
            "RAPPORT — TEST BOUT EN BOUT TRE (PÉRIODE 1)",
            f"Fichier classeur : {wb_path.name}",
        )
    )
    story.append(Spacer(1, 14))

    meta_text = (
        f"<b>Revenu de référence TRE (somme P×U) :</b> {format_money(rev_ref)}<br/>"
        f"<b>BudgetBase ajusté P1 (×1,12 ×1,07) :</b> {format_money(budget_base)}<br/>"
        f"<b>Seuils marketing TRE P1 (PARAM) :</b> min {format_money(mkt_min)} / max {format_money(mkt_max)}<br/>"
        f"<b>Budget R&D injecté (2 %) :</b> {format_money(rd_budget)}<br/>"
        f"<b>Prix liste estimé P040 (base × inflation P1) :</b> {format_money(prix_p040)}"
    )
    story.append(box_info(Paragraph(meta_text, P_INS)))
    story.append(Spacer(1, 14))

    H1(story, "1.  Décisions injectées — INPUT_FIRM (TRE P1)")
    rows_firm: list[list[str]] = []
    for k, v in MARKETING_TRE.items():
        rows_firm.append([k, format_money(v)])
    rows_firm.append(["Total marketing", format_money(sum(MARKETING_TRE.values()))])
    rows_firm.append(["BudgetRD", format_money(rd_budget)])
    rows_firm.append(["SustainabilityInvestPct", "0,005"])
    rows_firm.append(["LancementPrevu", "0"])
    story.append(
        table_standard(
            ["Champ", "Valeur"],
            rows_firm,
            [78 * mm, CONTENT_WIDTH - 78 * mm],
        )
    )
    story.append(Spacer(1, 12))

    H1(story, "2.  INPUT_MODEL — Productions TRE P1")
    rows_prod = [[pk, f"{PRODUCTIONS[pk]:,}".replace(",", " ")] for pk in sorted(PRODUCTIONS.keys())]
    story.append(
        table_standard(
            ["Produit", "Production (unités)"],
            rows_prod,
            [36 * mm, CONTENT_WIDTH - 36 * mm],
        )
    )
    story.append(Spacer(1, 12))

    H1(story, "3.  CONTROLE_DECISIONS — Synthèse Python")
    rows_cd: list[list[str]] = []
    fills_cd = []
    for row in report:
        msg = (row.get("msg") or "")[:140]
        rows_cd.append([str(row["type"]), str(row["statut"]), msg])
        fills_cd.append(row_fill_for_controle(str(row["statut"])))
    story.append(
        table_standard(
            ["Type", "Statut", "Message"],
            rows_cd,
            [58 * mm, 28 * mm, CONTENT_WIDTH - 86 * mm],
            row_fills=fills_cd,
        )
    )
    story.append(Spacer(1, 12))

    H1(story, "4.  Bandeau et interprétation")
    interp = (
        "Cellule A1 de CONTROLE_DECISIONS : formule COUNTIF sur la colonne Statut (bloqués X). "
        "Les alertes ! (marketing sous plancher) ne déclenchent pas le bandeau rouge ; "
        "dépassement du plafond marketing → X Bloqué."
    )
    story.append(Paragraph(interp, P_JUST))
    story.append(Spacer(1, 10))
    if n_blocked == 0:
        story.append(alerte("TOUTES LES DÉCISIONS VALIDÉES — 0 blocage", "ok"))
    else:
        story.append(
            alerte(
                f"DÉCISIONS BLOQUÉES — {n_blocked} ligne(s) en X Bloqué",
                "critical",
            )
        )
    story.append(Spacer(1, 12))

    H1(story, "5.  Test invalide (documentation)")
    story.append(
        Paragraph(
            "Scénario avec BudgetInfluencer élevé (dépassement plafond ~132 k$ TRE P1), promotion P040 = -15 %, "
            "LancementPrevu = 1. Le portefeuille plein (NbActifs >= NbInit+2) dépend du moteur Excel. "
            "Feuille TEST_TRE_P1_INVALIDE dans le classeur *_TEST.xlsx.",
            P_JUST,
        )
    )

    build_doc(
        PDF_REL,
        story,
        firm_code="TRE",
        left_text="Simulation marché VAE — Test TRE période 1",
    )

    out_abs = Path.cwd() / PDF_REL
    out_abs.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out_abs, PDF_DOWNLOADS)
    print(f"PDF genere : {out_abs}")
    print(f"Copie : {PDF_DOWNLOADS}")


if __name__ == "__main__":
    main()
