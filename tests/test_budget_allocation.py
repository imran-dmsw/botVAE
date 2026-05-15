import unittest

from engine.budget_allocation import (
  allocate_firm_budgets,
  compute_product_weights,
  firm_marketing_and_rd_totals,
  snap_rd_firm_pct,
  verify_allocation_totals,
)
from engine.firm_simulation import simulate_firm_portfolio
from engine.models import ScenarioInput
from engine.simulation import simulate


class _Prod:
  def __init__(self, key: str, segment_idx: int, base_price: float, units: float):
    self.product_key = key
    self.segment_idx = segment_idx
    self.base_price = base_price
    self.units = units


class TestBudgetAllocation(unittest.TestCase):
  def test_weights_sum_to_one(self):
    products = [
      _Prod("P001", 1, 5000, 1000),
      _Prod("P002", 2, 4000, 500),
    ]
    weights = compute_product_weights(products, "forecast_sales")
    self.assertAlmostEqual(sum(weights.values()), 1.0, places=6)

  def test_allocated_budgets_match_firm_totals(self):
    products = [
      _Prod("P001", 1, 5000, 1000),
      _Prod("P002", 2, 4000, 500),
    ]
    firm_adj = 2_000_000.0
    allocations = allocate_firm_budgets(products, firm_adj)
    firm_mkt = firm_adj * 0.08
    firm_rd = firm_adj * 0.02
    ok, issues = verify_allocation_totals(allocations, firm_mkt, firm_rd)
    self.assertTrue(ok, issues)

  def test_snap_rd_firm_pct_to_discrete_levels(self):
    self.assertEqual(snap_rd_firm_pct(None), 0.02)
    self.assertEqual(snap_rd_firm_pct(0.02), 0.02)
    self.assertEqual(snap_rd_firm_pct(0.05), 0.05)
    self.assertEqual(snap_rd_firm_pct(0.08), 0.08)
    self.assertEqual(snap_rd_firm_pct(0.044), 0.05)
    self.assertEqual(snap_rd_firm_pct(0.069), 0.08)

  def test_firm_rd_totals_use_snapped_pct(self):
    _mkt, rd = firm_marketing_and_rd_totals(1_000_000.0, rd_pct=0.046)
    self.assertAlmostEqual(rd, 1_000_000.0 * 0.05, places=1)

  def test_single_product_simulation_not_multiplied(self):
    products = [_Prod("P040", 3, 6000, 2000)]
    firm_adj = 1_500_000.0

    def build_scenario(prod, alloc):
      return ScenarioInput(
        firm_name="TRE",
        period=1,
        scenario_name="test",
        model_name="Model",
        product_type="route_connecte",
        segment="endurants_performants",
        model_range="premium",
        product_status="active",
        marketing_budget=alloc.marketing,
        rd_budget=alloc.rd,
        price=6500,
        production=2000,
        adjusted_budget=alloc.adjusted_budget,
        competitor_attractiveness=14,
      )

    portfolio = simulate_firm_portfolio(products, build_scenario, firm_adjusted_budget=firm_adj)
    self.assertTrue(portfolio.allocation_ok)
    self.assertGreater(portfolio.products[0]["result"].profit, -5_000_000)

  def test_allocated_product_profit_less_negative_than_full_firm_budget(self):
    scenario_full = ScenarioInput(
      firm_name="TRE",
      period=1,
      scenario_name="full",
      model_name="Model",
      product_type="ville_quotidien",
      segment="urbains_presses",
      model_range="mid",
      product_status="active",
      marketing_budget=120_000,
      rd_budget=30_000,
      price=3200,
      production=1500,
      adjusted_budget=1_200_000,
      competitor_attractiveness=18,
    )
    scenario_alloc = scenario_full.model_copy(
      update={
        "marketing_budget": 20_000,
        "rd_budget": 5_000,
        "adjusted_budget": 200_000,
        "allocation_weight": 0.17,
        "firm_marketing_budget_total": 120_000,
        "firm_rd_budget_total": 30_000,
      }
    )
    full = simulate(scenario_full)
    alloc = simulate(scenario_alloc)
    self.assertGreater(alloc.profit, full.profit)


if __name__ == "__main__":
  unittest.main()
