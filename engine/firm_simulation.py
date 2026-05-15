"""Simulation portefeuille firme avec budgets alloués par produit."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from engine.budget_allocation import (
    DEFAULT_ALLOCATION_METHOD,
    allocate_firm_budgets,
    firm_marketing_and_rd_totals,
    verify_allocation_totals,
)
from engine.models import ScenarioInput, SimulationResult
from engine.simulation import default_competitor_attractiveness, simulate


@dataclass
class FirmPortfolioResult:
  firm_name: str
  allocation_method: str
  firm_marketing_total: float
  firm_rd_total: float
  firm_adjusted_budget: float
  products: list[dict[str, Any]]
  firm_profit: float
  firm_revenue: float
  firm_margin: float
  allocation_ok: bool
  allocation_issues: list[str]
  stability_score: float


def simulate_firm_portfolio(
  products: Sequence[Any],
  build_scenario,
  *,
  firm_adjusted_budget: float,
  allocation_method: str = DEFAULT_ALLOCATION_METHOD,
  debug: bool = False,
) -> FirmPortfolioResult:
  allocations = allocate_firm_budgets(
    products,
    firm_adjusted_budget,
    allocation_method=allocation_method,
  )
  firm_mkt, firm_rd = firm_marketing_and_rd_totals(firm_adjusted_budget)
  ok, issues = verify_allocation_totals(allocations, firm_mkt, firm_rd)

  rows: list[dict[str, Any]] = []
  total_profit = 0.0
  total_revenue = 0.0
  peer_mkt = [a.marketing for a in allocations.values()]

  for prod in products:
    key = prod.product_key if hasattr(prod, "product_key") else prod["product_key"]
    alloc = allocations[key]
    scenario: ScenarioInput = build_scenario(prod, alloc)
    scenario = scenario.model_copy(
      update={
        "allocation_method": allocation_method,
        "allocation_weight": alloc.weight,
        "firm_marketing_budget_total": firm_mkt,
        "firm_rd_budget_total": firm_rd,
        "marketing_budget": alloc.marketing,
        "rd_budget": alloc.rd,
        "adjusted_budget": alloc.adjusted_budget,
        "competitor_attractiveness": default_competitor_attractiveness(scenario.segment),
      }
    )
    result = simulate(scenario)
    from engine.stability_checks import run_financial_controls

    controls = run_financial_controls(scenario, result, peer_marketing=peer_mkt)
    row = {
      "product_key": key,
      "scenario": scenario,
      "result": result,
      "allocation": alloc,
      "controls": controls,
    }
    if debug:
      row["debug"] = {
        "ca": result.revenue,
        "variable_costs": result.production_cost + result.distribution_cost,
        "marketing_allocated": result.marketing_cost,
        "rd_allocated": result.rd_cost,
        "profit": result.profit,
        "margin": result.margin,
        "allocation_weight": alloc.weight,
      }
    rows.append(row)
    total_profit += result.profit
    total_revenue += result.revenue

  stability = sum(r["result"].simulation_stability_score for r in rows) / max(len(rows), 1)
  firm_name = rows[0]["scenario"].firm_name if rows else ""
  return FirmPortfolioResult(
    firm_name=firm_name,
    allocation_method=allocation_method,
    firm_marketing_total=firm_mkt,
    firm_rd_total=firm_rd,
    firm_adjusted_budget=firm_adjusted_budget,
    products=rows,
    firm_profit=total_profit,
    firm_revenue=total_revenue,
    firm_margin=total_profit / max(total_revenue, 1.0),
    allocation_ok=ok,
    allocation_issues=issues,
    stability_score=stability,
  )
