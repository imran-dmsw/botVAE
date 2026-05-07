from __future__ import annotations

from typing import Any, Dict, List

from config.market_config import MARKET_CONFIG
from engine.models import ScenarioInput, SimulationResult


def build_2026_market_reference_state() -> dict:
    """
    Build a compact 2026 reference snapshot from MARKET_CONFIG only.

    This is intentionally "structure-only": the bot does not import the Excel workbook,
    so this state serves as a stable reference frame for reports and validation.
    """
    market_2026 = float(MARKET_CONFIG["base_market_size"])
    avg_price_2026 = float(MARKET_CONFIG["base_average_price"])

    segments: List[Dict[str, Any]] = []
    for seg_key, seg in MARKET_CONFIG["segments"].items():
        segments.append(
            {
                "segment_key": seg_key,
                "label": seg.get("label", seg_key),
                "share": float(seg["share"]),
                "market_units_2026": float(market_2026 * float(seg["share"])),
                "reference_price_2026": float(seg["reference_price"]),
                "description": seg.get("description", ""),
            }
        )

    firms: List[Dict[str, Any]] = []
    total_units_ref = sum(float(f.get("units_ref", 0.0)) for f in MARKET_CONFIG["firms"].values()) or 1.0
    for firm_key, firm in MARKET_CONFIG["firms"].items():
        units_ref = float(firm.get("units_ref", 0.0))
        firms.append(
            {
                "firm_key": firm_key,
                "label": firm.get("label", firm_key),
                "units_ref_2026": units_ref,
                "market_share_estimate_2026": units_ref / market_2026 if market_2026 > 0 else 0.0,
                "units_ref_share_of_config_total": units_ref / total_units_ref,
                "default_segment": firm.get("default_segment"),
                "default_range": firm.get("default_range"),
                "base_rep": float(firm.get("base_rep", 0.0)),
            }
        )

    return {
        "market_size_2026": market_2026,
        "avg_price_2026": avg_price_2026,
        "baseline_market_revenue_2026": market_2026 * avg_price_2026,
        "segments": sorted(segments, key=lambda x: -x["share"]),
        "firms": sorted(firms, key=lambda x: -x["units_ref_2026"]),
        "notes": [
            "Référence structurelle 2026 issue de MARKET_CONFIG (pas d'import Excel).",
            "units_ref_2026 par firme sert d'ordre de grandeur; la reconciliation Excel est un choix de design.",
        ],
    }


def build_2026_baseline_summary(scenario: ScenarioInput, result: SimulationResult) -> dict:
    market_2026 = MARKET_CONFIG["base_market_size"]
    avg_price_2026 = MARKET_CONFIG["base_average_price"]
    baseline_revenue = market_2026 * avg_price_2026
    baseline_share = result.sales / max(market_2026, 1)
    baseline_profitability = result.profit / max(result.revenue, 1)
    return {
        "market_size_2026": market_2026,
        "firm_baseline_revenue_2026": baseline_revenue,
        "segment_baseline_share_2026": MARKET_CONFIG["segments"][scenario.segment]["share"],
        "baseline_price_2026": avg_price_2026,
        "baseline_market_share_2026": baseline_share,
        "baseline_profitability_2026": baseline_profitability,
        "scenario_vs_baseline_revenue_delta": result.revenue - baseline_revenue,
        "scenario_vs_baseline_share_delta": result.market_share - baseline_share,
        "market_reference_state_2026": build_2026_market_reference_state(),
    }
