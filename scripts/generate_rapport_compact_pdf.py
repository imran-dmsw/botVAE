from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(__file__))

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle

from generate_rapport_vae_style_pdf import fmt_money, fmt_pct
from vae_report_style import (
    H1,
    NAVY,
    PageBreak,
    Paragraph,
    P_INS,
    P_JUST,
    P_SMALL,
    Spacer,
    alerte,
    build_doc,
    kpi_block,
    pdf_escape,
    pdf_xml_fragment,
    table_standard,
)
from vae_rapport_firme_logic import executive_priority_levers


def _section_gap(story: list, gap: float = 4) -> None:
    story.append(Spacer(1, gap))


def _append_alert_blocks(story: list, grouped: dict[str, list[Any]]) -> None:
    labels = {
        "critique": "Alertes critiques",
        "attention": "Alertes attention",
        "information": "Alertes information",
    }
    levels = {
        "critique": "critical",
        "attention": "warning",
        "information": "info",
    }
    for key in ("critique", "attention", "information"):
        items = grouped.get(key, [])
        if not items:
            continue
        H1(story, labels[key])
        for item in items[:6]:
            story.append(alerte(item.message, levels[key]))
        _section_gap(story, 2)


def _append_matrix(story: list, matrix: dict[str, Any]) -> None:
    headers = ["Firme"] + matrix["columns"]
    story.append(
        table_standard(
            headers,
            matrix["rows"],
            [42] + [52] * len(matrix["columns"]),
        )
    )
    labels = ", ".join(
        f"{col} = {label[:18]}"
        for col, label in zip(matrix["columns"], matrix["column_labels"])
    )
    story.append(Paragraph(pdf_escape(f"Légende segments : {labels}."), P_SMALL))
    _section_gap(story)


def _append_auto_scenarios(story: list, rows: list[dict[str, Any]]) -> None:
    if not rows:
        story.append(Paragraph("Aucun scénario automatique disponible.", P_JUST))
        return
    table_rows = []
    for row in rows:
        table_rows.append(
            [
                row["scenario"],
                str(row["sales"]),
                fmt_money(row["revenue"]),
                fmt_money(row["profit"]),
                fmt_pct(row["margin"]),
                fmt_pct(row["market_share"]),
                fmt_pct(row["service_rate"]),
                str(row["ending_stock"]),
            ]
        )
    story.append(
        table_standard(
            [
                "Scénario",
                "Ventes",
                "CA",
                "Profit",
                "Marge",
                "PDM",
                "Service",
                "Stock fin.",
            ],
            table_rows,
            [88, 34, 48, 48, 34, 34, 38, 34],
        )
    )
    _section_gap(story)


def _append_debug(story: list, audit: Any, *, limit: int = 10) -> None:
    probes = list(audit.probes)[:limit]
    if not probes:
        story.append(Paragraph("Aucune trace Excel disponible.", P_JUST))
        return
    rows = []
    for probe in probes:
        rows.append(
            [
                probe.sheet,
                probe.cell,
                probe.field,
                str(probe.raw_value),
                str(probe.validated_value),
                str(probe.used_value),
            ]
        )
    story.append(
        table_standard(
            ["Feuille", "Cellule", "Champ", "Brut", "Validé", "Utilisé"],
            rows,
            [58, 34, 52, 70, 54, 54],
        )
    )
    _section_gap(story)


def generer_pdf_rapport_compact(
    chemin_sortie: str | Path,
    *,
    code_firme: str,
    donnees: dict[str, Any],
    recommandations: list[Any],
) -> None:
    legend = donnees["nom_firme"]
    footer = donnees["footer"]
    vue_firme = donnees["vue_firme"]
    ref_sid = vue_firme["ref_sid"]
    ref_res = vue_firme["ref_res"]
    firm_pdm = donnees.get("firm_pdm")
    if firm_pdm is None:
        from generate_rapport_vae_style_pdf import load_firm_share

        firm_pdm = load_firm_share(donnees["wb"], code_firme)

    hero_style = ParagraphStyle(
        "COMPACT_HERO",
        parent=P_INS,
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=NAVY,
        alignment=TA_CENTER,
        spaceAfter=6,
    )
    sub_style = ParagraphStyle(
        "COMPACT_SUB",
        parent=P_INS,
        fontSize=9,
        leading=12,
        alignment=TA_CENTER,
        spaceAfter=8,
        textColor=NAVY,
    )

    story: list = []
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"RAPPORT COMPACT — {pdf_xml_fragment(legend)}", hero_style))
    story.append(
        Paragraph(
            pdf_escape("Synthèse stratégique VAE — KPI, PDM, alertes et scénarios testés"),
            sub_style,
        )
    )
    story.append(Paragraph(vue_firme["exec_txt"], P_JUST))
    story.append(Paragraph(pdf_escape(donnees["data_source_label"]), P_SMALL))
    _section_gap(story)

    H1(story, "KPI principaux")
    story.append(
        kpi_block(
            [
                ("Meilleur scénario", ref_sid, None),
                ("Profit", f"{fmt_money(ref_res.profit)} $", None),
                ("Marge", fmt_pct(ref_res.margin), None),
                ("PDM FIRMS", fmt_pct(firm_pdm), None),
            ]
        )
    )
    story.append(
        kpi_block(
            [
                ("Service", fmt_pct(ref_res.service_rate), None),
                ("Stock final", str(ref_res.forecast_ending_stock_units), None),
                ("Ventes", str(ref_res.sales), None),
                ("CA", f"{fmt_money(ref_res.revenue)} $", None),
            ]
        )
    )
    _section_gap(story)

    H1(story, "Tableau compagnie × segment (PDM segment)")
    _append_matrix(story, donnees["company_segment_matrix"])

    H1(story, "Alertes principales")
    _append_alert_blocks(story, donnees["prioritized_alerts"])

    H1(story, "Scénarios testés")
    _append_auto_scenarios(story, donnees["auto_scenario_rows"])

    H1(story, "Recommandations prioritaires")
    priority = executive_priority_levers(recommandations, 5)
    if priority:
        for idx, line in enumerate(priority, 1):
            story.append(Paragraph(f"{idx}. {pdf_escape(line)}", P_JUST))
    else:
        story.append(Paragraph("Aucune recommandation prioritaire.", P_JUST))
    _section_gap(story)

    story.append(PageBreak())
    H1(story, "Debug — traçabilité Excel")
    story.append(Paragraph(pdf_escape(donnees["data_source_label"]), P_JUST))
    _append_debug(story, donnees["excel_audit"])

    build_doc(
        str(chemin_sortie),
        story,
        firm_code=code_firme,
        left_text=footer,
    )
