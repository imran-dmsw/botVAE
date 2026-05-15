#!/usr/bin/env python3
"""
Rapport Word (.docx) — même contenu que le PDF VAE (vue firme + fiches modèles).

Usage:
  python3 scripts/generate_rapport_vae_style_docx.py --firm TRE
  python3 scripts/generate_rapport_vae_style_docx.py --firm TRE --out reports/Rapport_TRE_VAE.docx
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.market_config import MARKET_CONFIG  # noqa: E402
from generate_rapport_vae_style_pdf import (  # noqa: E402
    DEFAULT_XLSX,
    DOWNLOADS,
    build_report_payload,
    firm_adjusted_budget_from_scenario,
    fmt_money,
    fmt_pct,
    fmt_pct_and_money,
    growth_rows,
    load_firms_market_rows,
    scenario_display_title,
    segment_label_from_idx,
)
from vae_rapport_firme_logic import resolve_firm_code  # noqa: E402
from vae_report_sink import DocxSink  # noqa: E402
from vae_report_tables import (  # noqa: E402
    canonical_gamme_label,
    competitor_reaction_blurb,
    portfolio_anomaly_note,
    production_band_note,
    top3_channels_cell,
)

OUT_DOCX = Path("reports/Rapport_{firm}_VAE_{date}.docx")


def _note(sink: DocxSink, text: str) -> None:
    sink.paragraph(f"Note de lecture : {text}", style="small")


def _render_rapport_docx(
    sink: DocxSink,
    code_firme: str,
    vue_firme: dict,
    fiches_modeles: dict,
    recommandations: list,
    donnees: dict,
) -> None:
    wb = donnees["wb"]
    produits = donnees["produits"]
    mm_rows = donnees["mm_rows"]
    product_bundles = donnees["product_bundles"]
    firm_results = vue_firme["firm_results"]
    legend = vue_firme["legend"]

    best = max(firm_results, key=lambda row: row[3].profit)
    sink.center_heading(
        "RAPPORT VAE — ANALYSE STRATÉGIQUE",
        subtitle=f"Firme {code_firme} — {legend}",
    )
    sink.paragraph(
        f"Résumé exécutif. {legend} — {len(firm_results)} scénarios firme simulés. "
        f"Meilleur profit : {scenario_display_title(best[0])} ({fmt_money(best[3].profit)} $). "
        f"Vue firme (sections 1.1 à 1.10) puis {len(fiches_modeles)} fiches modèle.",
        style="justify",
    )
    sink.page_break()

    sink.h1("Table des matières")
    for item in [
        "PARTIE — VUE FIRME",
        "1.1 Tableau de bord scénarios",
        "1.2 Parts de marché firmes",
        "1.3 Segments de marché",
        "1.4 Croissance du marché",
        "Tableau croisé firme × segment",
        "1.5 Portefeuille et performance",
        "1.6 Leviers stratégiques",
        "1.7 Référence + projections 1500 / 2250 / 3000",
        "1.10 Recommandations",
        "PARTIE — VUE MODÈLE",
        *[f"Modèle {k}" for k in fiches_modeles],
    ]:
        sink.paragraph(f"• {item}", style="toc")
    sink.page_break()

    sink.part_banner("PARTIE — VUE FIRME")

    sink.h1("1.1 Tableau de bord scénarios — vue firme")
    sink.kpi_block(
        [
            ("Scénarios", str(len(firm_results)), None),
            ("Meilleur profit", f"{fmt_money(max(r[3].profit for r in firm_results))} $", None),
            ("Marge max.", fmt_pct(max(r[3].margin for r in firm_results)), None),
            ("Service max.", fmt_pct(max(r[3].service_rate for r in firm_results), 0), None),
        ]
    )
    rows_11_main = []
    rows_11_notes = []
    for sid, _owner, scen, res in sorted(firm_results, key=lambda row: row[3].profit, reverse=True):
        title = scenario_display_title(sid)
        rows_11_main.append(
            [
                title,
                str(scen.period),
                str(res.sales),
                fmt_money(res.revenue),
                fmt_money(res.profit),
                fmt_pct(res.margin),
                fmt_pct(res.market_share),
                fmt_pct(res.service_rate, 0),
            ]
        )
        rows_11_notes.append([title, competitor_reaction_blurb(sid, code_firme, max_len=200)])
    sink.table(
        [
            "Scénario",
            "P.",
            "Ventes",
            "CA ($)",
            "Profit ($)",
            "Marge",
            "PDM",
            "Service",
        ],
        rows_11_main,
        compact=True,
    )
    sink.paragraph("Notes — réactions concurrentielles plausibles (indicatif) :", style="small")
    sink.table(
        ["Scénario", "Note concurrentielle"],
        rows_11_notes,
    )

    sink.h1("1.2 Parts de marché firmes")
    sink.table(
        ["Firme", "Unités réf.", "PDM"],
        [[code, f"{units:,.0f}".replace(",", " "), fmt_pct(share)] for code, units, share in load_firms_market_rows(wb)],
    )
    _note(sink, "PDM lue depuis la feuille FIRMS (année de référence).")

    sink.h1("1.3 Structure des segments")
    rows_s = []
    ws = wb["SEGMENTS"]
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value is None:
            continue
        rows_s.append(
            [
                str(ws.cell(r, 1).value),
                str(ws.cell(r, 2).value or ""),
                fmt_pct(float(ws.cell(r, 3).value or 0)),
                f"{float(ws.cell(r, 5).value or 0):,.0f}".replace(",", " "),
                fmt_pct(float(ws.cell(r, 6).value or 0)),
            ]
        )
    sink.table(["Segment", "Description", "Part", "Unités réf.", "Online"], rows_s, compact=True)

    sink.h1("1.4 Croissance du marché")
    gr, seg_col = growth_rows(code_firme)
    sink.table(["Période", "Année", "Marché total", seg_col, "Croiss. vs P1"], gr)
    _note(sink, "Projection 8 périodes ; croissance globale +12 % / an.")

    cross = vue_firme["cross_matrix_pct"]
    sink.h1("Tableau croisé firme × segment")
    firms = cross["firms"]
    segs = cross["segments"]
    grid = cross["pct_grid"]
    headers = ["Firme"] + [f"S{i}" for i in range(1, len(segs) + 1)] + ["TOTAL"]
    rows_c = []
    for i, f in enumerate(firms):
        rows_c.append(
            [f]
            + [fmt_pct(grid[i][j] / 100.0, 2) for j in range(len(segs))]
            + [fmt_pct(cross["row_totals_pct"][i] / 100.0, 2)]
        )
    rows_c.append(
        ["TOTAL"]
        + [fmt_pct(cross["col_totals_pct"][j] / 100.0, 2) for j in range(len(segs))]
        + [fmt_pct(cross["grand_total_pct"] / 100.0, 2)]
    )
    sink.table(headers, rows_c, compact=True)
    if cross.get("footnote"):
        _note(sink, str(cross["footnote"]))

    sink.h1("1.5 Portefeuille produits et grille performance")
    rows_p = []
    for p in produits:
        note = portfolio_anomaly_note(p.product_key) or production_band_note(p.units)
        rows_p.append(
            [
                p.product_key,
                p.model_name[:34],
                f"{p.segment_idx} — {segment_label_from_idx(wb, p.segment_idx)[:20]}",
                canonical_gamme_label(p.range_raw),
                fmt_money(p.base_price),
                fmt_money(p.units),
                note or "",
            ]
        )
    sink.table(
        ["Code", "Modèle", "Segment", "Gamme", "Prix réf.", "Unités réf.", "Alerte / note"],
        rows_p,
    )
    rows_perf = []
    for p in produits:
        b = product_bundles[p.product_key]
        rs = b["ref_res"]
        rows_perf.append(
            [
                p.product_key,
                fmt_pct(rs.market_share),
                fmt_pct(rs.market_share_segment),
                fmt_pct(rs.margin),
                fmt_pct(rs.service_rate, 0),
                str(rs.forecast_ending_stock_units),
                fmt_money(rs.profit),
            ]
        )
    sink.table(
        ["Modèle", "PDM glob.", "PDM seg.", "Marge", "Service", "Stock fin.", "Profit"],
        rows_perf,
        compact=True,
    )

    sink.h1("1.6 Leviers stratégiques")
    rows_l = []
    for sid, _owner, _sc, res in sorted(firm_results, key=lambda row: row[3].profit, reverse=True):
        rows_l.append(
            [
                scenario_display_title(sid),
                fmt_money(res.revenue),
                fmt_money(res.profit),
                fmt_pct(res.margin),
                fmt_pct(res.service_rate, 0),
                fmt_money(max(0, res.demand - res.sales)),
            ]
        )
    sink.table(
        ["Levier / scénario", "CA", "Profit", "Marge", "Service", "Demande non servie"],
        rows_l,
        compact=True,
    )
    rows_m = [row + [top3_channels_cell(row)] for row in mm_rows]
    sink.table(
        [
            "Segment",
            "Digital",
            "Social",
            "Influenceur",
            "Affichage",
            "Événements",
            "Top 3 canaux",
        ],
        rows_m,
        compact=True,
    )

    ref_scen = vue_firme["ref_scen"]
    ref_res = vue_firme["ref_res"]
    sink.h1("1.7 Scénario de référence et projection 1500 / 2250 / 3000")
    adj = firm_adjusted_budget_from_scenario(ref_scen)
    sink.table(
        ["Paramètre", "Valeur"],
        [
            ["Scénario", scenario_display_title(vue_firme["ref_sid"])],
            ["Période", str(ref_scen.period)],
            ["Prix catalogue", f"{fmt_money(ref_scen.price)} $"],
            ["Promotion", fmt_pct(ref_scen.promotion_rate)],
            ["Production", str(ref_scen.production)],
            [
                "Budget marketing (firme)",
                fmt_pct_and_money(ref_scen.firm_marketing_budget_total / max(adj, 1), ref_scen.firm_marketing_budget_total),
            ],
            [
                "Budget R&D (firme)",
                fmt_pct_and_money(ref_scen.firm_rd_budget_total / max(adj, 1), ref_scen.firm_rd_budget_total),
            ],
        ],
    )
    proj_rows = []
    for units, res in vue_firme["projection_1500_2250_3000"]:
        proj_rows.append(
            [
                str(units),
                str(res.sales),
                fmt_pct(res.service_rate, 0),
                str(res.forecast_ending_stock_units),
                fmt_money(res.profit),
                "OK" if res.service_rate >= 0.85 else "Sous seuil 85 %",
            ]
        )
    sink.table(
        ["Production", "Ventes", "Service", "Stock fin.", "Profit", "Lecture"],
        proj_rows,
    )
    sink.table(
        ["Stratégie figée", "Profit", "Marge", "Service"],
        [
            ["P1", fmt_money(vue_firme["r_p1"].profit), fmt_pct(vue_firme["r_p1"].margin), fmt_pct(vue_firme["r_p1"].service_rate, 0)],
            ["P4", fmt_money(vue_firme["r_p4"].profit), fmt_pct(vue_firme["r_p4"].margin), fmt_pct(vue_firme["r_p4"].service_rate, 0)],
            ["P8", fmt_money(vue_firme["r_p8"].profit), fmt_pct(vue_firme["r_p8"].margin), fmt_pct(vue_firme["r_p8"].service_rate, 0)],
        ],
    )

    sink.h1("1.10 Exemples de recommandations stratégiques")
    sink.table(
        ["Action", "Impact attendu", "Horizon", "Priorité"],
        [[r.action, r.impact, r.horizon, r.priority] for r in recommandations],
    )

    for _key, fiche in fiches_modeles.items():
        prod = fiche["prod"]
        bundle = fiche["bundle"]
        ref_scen_m = bundle["ref_scen"]
        ref_res_m = bundle["ref_res"]
        sink.page_break()
        sink.part_banner(f"PARTIE — VUE MODÈLE — {prod.product_key}")

        sink.h1("2. Contexte concurrentiel")
        sink.paragraph(
            f"Modèle {prod.product_key} — segment {prod.segment_idx} "
            f"({segment_label_from_idx(wb, prod.segment_idx)}).",
            style="justify",
        )
        gr, seg_col = growth_rows(code_firme)
        sink.table(["Période", "Année", "Marché total", seg_col, "Croiss. vs P1"], gr)

        sink.h1("3. Portefeuille (focus modèle)")
        sink.table(
            ["Code", "Modèle", "Segment", "Gamme", "Prix réf.", "Unités réf."],
            [
                [
                    prod.product_key,
                    prod.model_name,
                    f"{prod.segment_idx} — {segment_label_from_idx(wb, prod.segment_idx)}",
                    canonical_gamme_label(prod.range_raw),
                    fmt_money(prod.base_price),
                    fmt_money(prod.units),
                ]
            ],
        )

        sink.h1("3.1 Budgets marketing et R&D (niveau firme)")
        adj_m = firm_adjusted_budget_from_scenario(ref_scen_m)
        sink.table(
            ["Indicateur", "Valeur"],
            [
                ["Budget ajusté firme", f"{fmt_money(adj_m)} $"],
                [
                    "Budget marketing (firme)",
                    fmt_pct_and_money(
                        ref_scen_m.firm_marketing_budget_total / max(adj_m, 1),
                        ref_scen_m.firm_marketing_budget_total,
                    ),
                ],
                [
                    "Budget R&D (firme)",
                    fmt_pct_and_money(
                        ref_scen_m.firm_rd_budget_total / max(adj_m, 1),
                        ref_scen_m.firm_rd_budget_total,
                    ),
                ],
                ["Poids stratégique du modèle", f"{ref_scen_m.allocation_weight * 100:.1f} %".replace(".", ",")],
                ["Contribution profit (modèle)", f"{fmt_money(ref_res_m.profit)} $"],
                ["Marge (modèle)", fmt_pct(ref_res_m.margin)],
            ],
        )
        sink.paragraph(
            "Poids stratégique : répartition proportionnelle au CA de référence (forecast_sales).",
            style="small",
        )

        sink.h1("4. Leviers stratégiques")
        rows_lev = [
            [lab, fmt_money(res.revenue), fmt_money(res.profit), fmt_pct(res.margin), fmt_pct(res.service_rate, 0)]
            for lab, res in bundle["levers"]
        ]
        sink.table(["Levier", "CA", "Profit", "Marge", "Service"], rows_lev)
        seg_mm = next((row for row in mm_rows if row[0] == str(prod.segment_idx)), None)
        if seg_mm:
            sink.table(
                [
                    "Segment",
                    "Digital",
                    "Social",
                    "Influenceur",
                    "Affichage",
                    "Événements",
                    "Top 3 canaux",
                ],
                [seg_mm + [top3_channels_cell(seg_mm)]],
            )

        sink.h1("5. Performance du modèle — dernière période simulée")
        sink.table(
            ["KPI", "Valeur"],
            [
                ["Ventes", str(ref_res_m.sales)],
                ["CA", f"{fmt_money(ref_res_m.revenue)} $"],
                ["Profit", f"{fmt_money(ref_res_m.profit)} $"],
                ["Marge", fmt_pct(ref_res_m.margin)],
                ["PDM globale", fmt_pct(ref_res_m.market_share)],
                ["PDM segment", fmt_pct(ref_res_m.market_share_segment)],
                ["Service", fmt_pct(ref_res_m.service_rate, 0)],
                ["Stock final", str(ref_res_m.forecast_ending_stock_units)],
                ["Prix catalogue", f"{fmt_money(ref_scen_m.price)} $"],
                ["Promotion", fmt_pct(ref_scen_m.promotion_rate)],
            ],
        )

        sink.h1("Alertes pour ce modèle")
        alerts = bundle.get("alerts", [])
        if alerts:
            sink.table(
                ["Niveau", "Code", "Message"],
                [[a.level.upper(), a.code, a.message] for a in alerts],
            )
        else:
            sink.paragraph("Aucune alerte priorisée pour ce modèle.", style="small")

        sink.h1("Recommandations stratégiques")
        sink.table(
            ["Action", "Impact", "Horizon", "Priorité"],
            [[r.action, r.impact, r.horizon, r.priority] for r in fiche["recommandations"]],
        )

    sink.paragraph(
        f"Sources : classeur {donnees['xlsx'].name} ; moteur BotMarketing (engine.simulation).",
        style="small",
    )


def generer_docx_rapport(
    out: Path,
    code_firme: str,
    vue_firme: dict,
    fiches_modeles: dict,
    recommandations: list,
    donnees: dict,
) -> None:
    sink = DocxSink()
    _render_rapport_docx(sink, code_firme, vue_firme, fiches_modeles, recommandations, donnees)
    footer = f"Rapport de Simulation VAE — {vue_firme['legend']} — Usage interne"
    sink.finalize(
        out,
        firm_code=code_firme,
        footer=footer,
        report_date=date.today().isoformat(),
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Rapport Word (.docx) VAE — même contenu que le PDF")
    ap.add_argument("--firm", "--firme", default="TRE")
    ap.add_argument("--workbook", type=Path, default=None)
    ap.add_argument("--all-firms", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    xlsx = args.workbook.expanduser() if args.workbook else DEFAULT_XLSX
    if not xlsx.exists():
        raise SystemExit(f"Classeur introuvable : {xlsx}")

    firm_arg = getattr(args, "firme", None) or args.firm
    firms = sorted(MARKET_CONFIG["firms"].keys()) if args.all_firms else [resolve_firm_code(firm_arg)]

    for firm in firms:
        firm = resolve_firm_code(firm)
        donnees = build_report_payload(xlsx, firm)
        out = args.out or Path(str(OUT_DOCX).format(firm=firm, date=date.today().isoformat()))
        if not out.is_absolute():
            out = Path.cwd() / out
        generer_docx_rapport(
            out,
            firm,
            donnees["vue_firme"],
            donnees["fiches_modeles"],
            donnees["recommandations_firme"],
            donnees,
        )
        try:
            shutil.copy2(out, DOWNLOADS / out.name)
        except OSError:
            pass
        finally:
            donnees["wb"].close()
        print(f"DOCX : {out}")
        if not args.all_firms:
            break


if __name__ == "__main__":
    main()
