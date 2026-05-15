from __future__ import annotations

from typing import Any

from config.market_config import MARKET_CONFIG
from engine.models import ScenarioInput
from engine.simulation import simulate_full_market, total_market_size


def build_cross_matrix_pct_total_market(
    *,
    period: int = 1,
    user_firm: str | None = None,
    user_scenario: ScenarioInput | None = None,
) -> dict[str, Any]:
    """
    Ventes firme × segment en % du marché total (taille marché = total_market_size(period)).
    Ligne TOTAL = somme colonnes ; colonne TOTAL = somme lignes ; coin = total ventes / T.
    """
    mkt = simulate_full_market(period, user_firm, user_scenario)
    seg_keys = list(MARKET_CONFIG["segments"].keys())
    firm_keys = sorted(MARKET_CONFIG["firms"].keys())
    T = float(total_market_size(period))
    if T <= 0:
        T = 1.0

    sales: dict[tuple[str, str], float] = {}
    for seg in seg_keys:
        for fk in firm_keys:
            cell = mkt["segment_breakdown"][seg].get(fk, {})
            sales[(fk, seg)] = float(cell.get("sales", 0.0))

    grid = [[100.0 * sales[(f, s)] / T for s in seg_keys] for f in firm_keys]
    row_totals = [sum(grid[i][j] for j in range(len(seg_keys))) for i in range(len(firm_keys))]
    col_totals = [sum(grid[i][j] for i in range(len(firm_keys))) for j in range(len(seg_keys))]
    grand = sum(row_totals)
    total_sales_units = grand * T / 100.0

    raw_grand = grand
    footnote_explain = None
    if abs(grand - 100.0) >= 0.005 and grand > 0:
        scale = 100.0 / grand
        grid = [[grid[i][j] * scale for j in range(len(seg_keys))] for i in range(len(firm_keys))]
        row_totals = [sum(grid[i][j] for j in range(len(seg_keys))) for i in range(len(firm_keys))]
        col_totals = [sum(grid[i][j] for i in range(len(firm_keys))) for j in range(len(seg_keys))]
        grand = sum(row_totals)
        footnote_explain = (
            f"Les pourcentages sont normalisés pour totaliser 100,00 % (2 déc.) ; "
            f"total brut moteur {raw_grand:.2f} % (ventes {total_sales_units:,.0f} u. / marché {T:,.0f} u.)."
        )

    footnote = footnote_explain or (
        None
        if abs(raw_grand - 100.0) < 0.05
        else f"Total ventes simulées ({total_sales_units:,.0f} u.) < taille marché ({T:,.0f} u.) : somme des cellules < 100 %."
    )

    return {
        "period": period,
        "denominator_units": T,
        "total_sales_units": total_sales_units,
        "firms": firm_keys,
        "segments": seg_keys,
        "segment_labels": [MARKET_CONFIG["segments"][k]["label"] for k in seg_keys],
        "pct_grid": grid,
        "row_totals_pct": row_totals,
        "col_totals_pct": col_totals,
        "grand_total_pct": grand,
        "footnote": footnote,
    }


def matrix_from_full_market(mkt: dict[str, Any], *, value_mode: str = "pdm") -> dict[str, Any]:
    seg_keys = list(mkt["segment_breakdown"].keys())
    firm_keys = sorted(mkt["firms"].keys())
    columns = [f"S{i}" for i in range(1, len(seg_keys) + 1)]
    column_labels = [MARKET_CONFIG["segments"][key]["label"] for key in seg_keys]
    rows: list[list[str]] = []
    numeric: list[list[float]] = []

    for firm in firm_keys:
        row = [firm]
        values: list[float] = []
        for seg_key in seg_keys:
            cell = mkt["segment_breakdown"][seg_key].get(firm, {})
            if value_mode == "sales":
                value = float(cell.get("sales", 0.0))
                row.append(f"{int(value):,}".replace(",", " "))
            else:
                value = float(cell.get("segment_share", 0.0)) * 100.0
                row.append(f"{value:.1f} %")
            values.append(value)
        rows.append(row)
        numeric.append(values)

    return {
        "period": mkt.get("period"),
        "columns": columns,
        "column_labels": column_labels,
        "rows": rows,
        "numeric": numeric,
        "firms": firm_keys,
        "segments": seg_keys,
        "value_mode": value_mode,
    }


def build_firm_segment_matrix(
    *,
    period: int = 1,
    user_firm: str | None = None,
    user_scenario: ScenarioInput | None = None,
    value_mode: str = "pdm",
) -> dict[str, Any]:
    market = simulate_full_market(period, user_firm, user_scenario)
    seg_keys = list(MARKET_CONFIG["segments"].keys())
    firm_keys = sorted(MARKET_CONFIG["firms"].keys())
    columns = [f"S{i}" for i in range(1, len(seg_keys) + 1)]
    column_labels = [MARKET_CONFIG["segments"][key]["label"] for key in seg_keys]
    rows: list[list[str]] = []
    numeric: list[list[float]] = []

    for firm in firm_keys:
        row = [firm]
        values: list[float] = []
        for seg_key in seg_keys:
            cell = market["segment_breakdown"][seg_key].get(firm, {})
            if value_mode == "sales":
                value = float(cell.get("sales", 0.0))
                row.append(f"{int(value):,}".replace(",", " "))
            else:
                value = float(cell.get("segment_share", 0.0)) * 100.0
                row.append(f"{value:.1f} %")
            values.append(value)
        rows.append(row)
        numeric.append(values)

    return {
        "period": period,
        "columns": columns,
        "column_labels": column_labels,
        "rows": rows,
        "numeric": numeric,
        "firms": firm_keys,
        "segments": seg_keys,
        "value_mode": value_mode,
        "market": market,
    }
