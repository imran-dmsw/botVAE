"""
Report generator: produces Markdown text, Word (.docx) and PDF (.pdf) reports
from a ScenarioInput + SimulationResult pair.
"""
import io
import json
from datetime import datetime
from typing import Optional

from engine.models import ScenarioInput, SimulationResult
from config.market_config import MARKET_CONFIG


# ─── Markdown / text report ───────────────────────────────────────────────────

def generate_markdown_report(scenario: ScenarioInput, result: SimulationResult) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    seg_label = MARKET_CONFIG["segments"][scenario.segment]["label"]
    range_label = MARKET_CONFIG["ranges"][scenario.model_range]["label"]
    mkt_max = scenario.adjusted_budget * MARKET_CONFIG["constraints"]["marketing_max_pct"]
    rd_max = scenario.adjusted_budget * MARKET_CONFIG["constraints"]["rd_max_pct"]

    status_icon = "✅" if result.is_valid else "❌"

    lines = [
        f"# Rapport de simulation VAE",
        f"**Généré le :** {now}  |  **Statut :** {status_icon} {'Valide' if result.is_valid else 'Non valide'}",
        "",
        "---",
        "",
        "## 1. Résumé exécutif",
        "",
        f"| Indicateur | Valeur |",
        f"|---|---|",
        f"| Firme | {result.firm_name} |",
        f"| Période | {result.period} |",
        f"| Scénario | {result.scenario_name} |",
        f"| Ventes | {result.sales:,} unités |",
        f"| Chiffre d'affaires | {result.revenue:,.0f} $ |",
        f"| Profit | {result.profit:,.0f} $ |",
        f"| Marge | {result.margin*100:.1f}% |",
        f"| Part de marché totale | {result.market_share*100:.2f}% |",
        f"| Part de marché segment ({seg_label}) | {result.market_share_segment*100:.2f}% |",
        f"| Taux de service | {result.service_rate*100:.1f}% |",
        f"| Score innovation | {result.innovation_score:.1f}/10 |",
        f"| Score durabilité | {result.sustainability_score:.1f}/10 |",
        "",
        "---",
        "",
        "## 2. Hypothèses du scénario",
        "",
        f"- **Modèle :** {scenario.model_name} ({range_label}, segment {seg_label})",
        f"- **Statut produit :** {scenario.product_status}",
        f"- **Prix :** {scenario.price:,.0f} $ (promotion : {scenario.promotion_rate*100:.1f}%)",
        f"- **Production :** {scenario.production:,} unités",
        f"- **Budget marketing :** {scenario.marketing_budget:,.0f} $ "
        f"({scenario.marketing_budget/mkt_max*100:.1f}% du plafond)",
        f"  - Digital : {scenario.marketing_channels.digital:,.0f} $",
        f"  - Réseaux sociaux : {scenario.marketing_channels.social_media:,.0f} $",
        f"  - Influenceurs : {scenario.marketing_channels.influencers:,.0f} $",
        f"  - Affichage : {scenario.marketing_channels.display:,.0f} $",
        f"  - Événements : {scenario.marketing_channels.events:,.0f} $",
        f"- **Budget R&D :** {scenario.rd_budget:,.0f} $ "
        f"({scenario.rd_budget/rd_max*100:.1f}% du plafond) | Projets : {scenario.rd_projects}",
        f"- **Investissement durabilité :** {scenario.sustainability_investment:,.0f} $",
        f"- **Budget ajusté de référence :** {scenario.adjusted_budget:,.0f} $",
        "",
        "---",
        "",
        "## 3. Résultats financiers détaillés",
        "",
        f"| Poste | Montant (CAD) | % du CA |",
        f"|---|---|---|",
        f"| Chiffre d'affaires | {result.revenue:,.0f} $ | 100.0% |",
        f"| Coûts de production | -{result.production_cost:,.0f} $ | {result.production_cost/max(result.revenue,1)*100:.1f}% |",
        f"| Coûts de distribution | -{result.distribution_cost:,.0f} $ | {result.distribution_cost/max(result.revenue,1)*100:.1f}% |",
        f"| Coûts marketing | -{result.marketing_cost:,.0f} $ | {result.marketing_cost/max(result.revenue,1)*100:.1f}% |",
        f"| Coûts R&D | -{result.rd_cost:,.0f} $ | {result.rd_cost/max(result.revenue,1)*100:.1f}% |",
        f"| Coûts d'exploitation | -{result.operating_cost:,.0f} $ | {result.operating_cost/max(result.revenue,1)*100:.1f}% |",
        f"| SAV / Garantie | -{result.aftersales_cost:,.0f} $ | {result.aftersales_cost/max(result.revenue,1)*100:.1f}% |",
        f"| Durabilité | -{result.sustainability_cost:,.0f} $ | {result.sustainability_cost/max(result.revenue,1)*100:.1f}% |",
        f"| **Total coûts** | **-{result.total_cost:,.0f} $** | **{result.total_cost/max(result.revenue,1)*100:.1f}%** |",
        f"| **Profit** | **{result.profit:,.0f} $** | **{result.margin*100:.1f}%** |",
        "",
        "---",
        "",
        "## 4. Alertes",
        "",
    ]

    if result.alerts:
        for alert in result.alerts:
            lines.append(f"- ⚠️ {alert}")
    else:
        lines.append("Aucune alerte — scénario conforme aux règles métier.")

    lines += [
        "",
        "---",
        "",
        "## 5. Analyse et interprétation",
        "",
    ]

    for interp in result.interpretations:
        lines.append(f"- {interp}")

    lines += [
        "",
        "---",
        "",
        "## 6. Recommandations",
        "",
    ]
    lines += _generate_recommendations(scenario, result)

    lines += [
        "",
        "---",
        f"*Rapport généré automatiquement par le Bot de Simulation VAE — {now}*",
    ]

    return "\n".join(lines)


def _generate_recommendations(scenario: ScenarioInput, result: SimulationResult):
    recs = []
    cfg = MARKET_CONFIG["constraints"]
    mkt_max = scenario.adjusted_budget * cfg["marketing_max_pct"]
    rd_max = scenario.adjusted_budget * cfg["rd_max_pct"]

    if result.margin < cfg["min_profit_rate"]:
        recs.append(
            "**Améliorer la rentabilité** : augmenter le prix, réduire les coûts variables "
            "ou diminuer les dépenses marketing/R&D pour atteindre le seuil minimal de 2 %."
        )
    if result.service_rate < 0.85:
        recs.append(
            f"**Augmenter la production** : le taux de service est de {result.service_rate*100:.0f}%. "
            f"Envisager une production de {int(result.demand * 1.05):,} unités."
        )
    if scenario.marketing_budget < mkt_max * 0.3 and result.market_share_segment < 0.10:
        recs.append(
            "**Investir davantage en marketing** : la part de marché est faible et le budget marketing "
            "est bien en dessous du plafond autorisé."
        )
    if scenario.rd_budget == 0:
        recs.append(
            "**Allouer un budget R&D** : sans investissement R&D, le score innovation diminue chaque période, "
            "réduisant l'attractivité future du produit."
        )
    if result.market_share_segment > 0.30:
        recs.append(
            "**Position dominante** : surveiller la réaction des concurrents et consolider l'avantage "
            "par l'innovation et la durabilité."
        )
    if not recs:
        recs.append("Le scénario est globalement satisfaisant. Maintenir la stratégie actuelle.")

    return [f"- {r}" for r in recs]


# ─── JSON export ──────────────────────────────────────────────────────────────

def generate_json_report(scenario: ScenarioInput, result: SimulationResult) -> str:
    data = {
        "generated_at": datetime.now().isoformat(),
        "scenario": scenario.model_dump(),
        "result": result.model_dump(),
    }
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


# ─── Word (.docx) report ──────────────────────────────────────────────────────

def generate_word_report(scenario: ScenarioInput, result: SimulationResult) -> bytes:
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    seg_label = MARKET_CONFIG["segments"][scenario.segment]["label"]
    range_label = MARKET_CONFIG["ranges"][scenario.model_range]["label"]

    # Title
    title = doc.add_heading("Rapport de Simulation VAE", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph(
        f"Firme : {result.firm_name}  |  Période : {result.period}  |  Généré le : {now}"
    ).alignment = WD_ALIGN_PARAGRAPH.CENTER

    status = "✅ Scénario valide" if result.is_valid else "❌ Scénario non valide"
    p = doc.add_paragraph(status)
    run = p.runs[0]
    run.font.bold = True
    run.font.color.rgb = RGBColor(0x00, 0x80, 0x00) if result.is_valid else RGBColor(0xCC, 0x00, 0x00)

    doc.add_heading("1. Résumé exécutif", level=1)

    kpis = [
        ("Ventes", f"{result.sales:,} unités"),
        ("Chiffre d'affaires", f"{result.revenue:,.0f} $"),
        ("Profit", f"{result.profit:,.0f} $"),
        ("Marge", f"{result.margin*100:.1f}%"),
        ("Part de marché totale", f"{result.market_share*100:.2f}%"),
        (f"Part de marché {seg_label}", f"{result.market_share_segment*100:.2f}%"),
        ("Taux de service", f"{result.service_rate*100:.1f}%"),
        ("Score innovation", f"{result.innovation_score:.1f}/10"),
        ("Score durabilité", f"{result.sustainability_score:.1f}/10"),
    ]

    table = doc.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text = "Indicateur"
    hdr[1].text = "Valeur"
    for k, v in kpis:
        row = table.add_row().cells
        row[0].text = k
        row[1].text = v

    doc.add_heading("2. Résultats financiers", level=1)

    fin_data = [
        ("Chiffre d'affaires", result.revenue),
        ("Coûts de production", -result.production_cost),
        ("Coûts de distribution", -result.distribution_cost),
        ("Coûts marketing", -result.marketing_cost),
        ("Coûts R&D", -result.rd_cost),
        ("Coûts d'exploitation", -result.operating_cost),
        ("SAV / Garantie", -result.aftersales_cost),
        ("Durabilité", -result.sustainability_cost),
        ("Profit", result.profit),
    ]

    fin_table = doc.add_table(rows=1, cols=2)
    fin_table.style = "Table Grid"
    hdr2 = fin_table.rows[0].cells
    hdr2[0].text = "Poste"
    hdr2[1].text = "Montant (CAD)"
    for label, val in fin_data:
        row = fin_table.add_row().cells
        row[0].text = label
        row[1].text = f"{val:,.0f} $"

    doc.add_heading("3. Alertes", level=1)
    if result.alerts:
        for a in result.alerts:
            doc.add_paragraph(f"• {a}")
    else:
        doc.add_paragraph("Aucune alerte — scénario conforme.")

    doc.add_heading("4. Interprétation", level=1)
    for i in result.interpretations:
        doc.add_paragraph(f"• {i}")

    doc.add_heading("5. Recommandations", level=1)
    recs = _generate_recommendations(scenario, result)
    for r in recs:
        doc.add_paragraph(r.lstrip("- "))

    doc.add_paragraph(f"\nRapport généré automatiquement par le Bot de Simulation VAE — {now}")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ─── PDF report ───────────────────────────────────────────────────────────────

def generate_pdf_report(scenario: ScenarioInput, result: SimulationResult) -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    seg_label = MARKET_CONFIG["segments"][scenario.segment]["label"]

    # Title
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Rapport de Simulation VAE", ln=True, align="C")
    pdf.set_font("Helvetica", size=9)
    pdf.cell(0, 6, f"Firme : {result.firm_name}  |  Periode : {result.period}  |  {now}", ln=True, align="C")
    status_txt = "Scenario VALIDE" if result.is_valid else "Scenario NON VALIDE"
    pdf.set_text_color(0, 128, 0) if result.is_valid else pdf.set_text_color(200, 0, 0)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 8, status_txt, ln=True, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # Section 1
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "1. Résumé exécutif", ln=True)
    pdf.set_font("Helvetica", size=10)

    kpis = [
        ("Ventes", f"{result.sales:,} unites"),
        ("Chiffre d'affaires", f"{result.revenue:,.0f} $"),
        ("Profit", f"{result.profit:,.0f} $"),
        ("Marge", f"{result.margin*100:.1f}%"),
        ("Part marche totale", f"{result.market_share*100:.2f}%"),
        (f"Part marche {seg_label}", f"{result.market_share_segment*100:.2f}%"),
        ("Taux de service", f"{result.service_rate*100:.1f}%"),
        ("Score innovation", f"{result.innovation_score:.1f}/10"),
        ("Score durabilite", f"{result.sustainability_score:.1f}/10"),
    ]
    # usable width = 210 - 2*15 = 180mm; split 60/40
    cw1, cw2 = 110, 70
    for k, v in kpis:
        pdf.cell(cw1, 7, k, border=1)
        pdf.cell(cw2, 7, v, border=1, ln=True)
    pdf.ln(4)

    # Section 2
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "2. Resultats financiers", ln=True)
    pdf.set_font("Helvetica", size=10)

    fin_rows = [
        ("Chiffre d'affaires", f"{result.revenue:,.0f} $"),
        ("Couts production", f"-{result.production_cost:,.0f} $"),
        ("Couts distribution", f"-{result.distribution_cost:,.0f} $"),
        ("Couts marketing", f"-{result.marketing_cost:,.0f} $"),
        ("Couts R&D", f"-{result.rd_cost:,.0f} $"),
        ("Couts exploitation", f"-{result.operating_cost:,.0f} $"),
        ("SAV/Garantie", f"-{result.aftersales_cost:,.0f} $"),
        ("Durabilite", f"-{result.sustainability_cost:,.0f} $"),
        ("PROFIT", f"{result.profit:,.0f} $"),
    ]
    for k, v in fin_rows:
        pdf.cell(cw1, 7, k, border=1)
        pdf.cell(cw2, 7, v, border=1, ln=True)
    pdf.ln(4)

    page_w = pdf.w - pdf.l_margin - pdf.r_margin

    # Section 3 — Alerts
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "3. Alertes", ln=True)
    pdf.set_font("Helvetica", size=10)
    if result.alerts:
        for a in result.alerts:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(page_w, 6, f"- {a}")
    else:
        pdf.set_x(pdf.l_margin)
        pdf.cell(0, 6, "Aucune alerte.", ln=True)
    pdf.ln(2)

    # Section 4 — Interpretations
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "4. Interpretation", ln=True)
    pdf.set_font("Helvetica", size=10)
    for i in result.interpretations:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(page_w, 6, f"- {i}")
    pdf.ln(2)

    # Section 5 — Recommendations
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "5. Recommandations", ln=True)
    pdf.set_font("Helvetica", size=10)
    recs = _generate_recommendations(scenario, result)
    for r in recs:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(page_w, 6, r.lstrip("- "))

    pdf.set_font("Helvetica", "I", 8)
    pdf.ln(4)
    pdf.cell(0, 6, f"Rapport genere automatiquement par le Bot de Simulation VAE - {now}", ln=True, align="C")

    return bytes(pdf.output())
