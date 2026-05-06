import unittest

from engine.models import ScenarioInput
from engine.simulation import (
    build_next_period_scenario,
    period_inflation_factor,
    simulate,
    simulate_full_market,
)
from rules.marketing_rules import profit_rate_status
from rules.price_rules import check_price_range_consistency
from rules.product_lifecycle_rules import apply_new_product_first_year_sales_cap
from rules.promo_rules import validate_promo_rate
from rules.withdrawal_rules import check_withdrawal_limits
from simulation.full_market_runner import run_full_market_simulation
from simulation.multi_scenario_runner import run_marketing_short_term_test, run_promo_sales_test


def _base_scenario() -> ScenarioInput:
    return ScenarioInput(
        firm_name="TRE",
        period=1,
        scenario_name="Test",
        model_name="Model",
        product_type="ville_quotidien",
        segment="urbains_presses",
        model_range="mid",
        product_status="active",
        marketing_budget=80000,
        rd_budget=15000,
        price=3200,
        production=1500,
        adjusted_budget=1_200_000,
        competitor_attractiveness=18,
    )


class TestBusinessRulesAndSimulation(unittest.TestCase):
    def test_price_range_consistency(self):
        status, _ = check_price_range_consistency(2500, "mid")
        self.assertEqual(status, "error")

    def test_validate_promo_rate(self):
        self.assertTrue(validate_promo_rate(-0.05)[0])
        self.assertFalse(validate_promo_rate(-0.07)[0])
        self.assertTrue(validate_promo_rate(-0.20, liquidation=True)[0])
        self.assertFalse(validate_promo_rate(-0.21, liquidation=True)[0])

    def test_liquidation_next_period_production_zero(self):
        sc = _base_scenario().model_copy(update={"liquidation": True})
        res = simulate(sc)
        self.assertEqual(res.next_period_recommended_production, 0)

    def test_withdrawal_over_limit(self):
        allowed, _ = check_withdrawal_limits("TRE", 4, {"TRE": [1, 2, 3, 4]}, max_total=4)
        self.assertFalse(allowed)

    def test_withdrawal_min_gap(self):
        allowed_ok, _ = check_withdrawal_limits(
            "TRE", 5, {"TRE": [3]}, min_period_gap=2, max_total=4
        )
        self.assertTrue(allowed_ok)
        allowed_bad, _ = check_withdrawal_limits(
            "TRE", 4, {"TRE": [3]}, min_period_gap=2, max_total=4
        )
        self.assertFalse(allowed_bad)

    def test_sustainability_revenue_premium_not_in_base_price(self):
        """Prime CA sur tranches 2-4 ; attractivité inchangée (même prix saisi)."""
        from engine.financials import sustainability_revenue_premium_rate

        self.assertEqual(sustainability_revenue_premium_rate(4), 0.005)
        self.assertEqual(sustainability_revenue_premium_rate(1), 0.0)
        base = _base_scenario()
        r0 = simulate(base.model_copy(update={"sustainability_tranches": 0}))
        r4 = simulate(base.model_copy(update={"sustainability_tranches": 4}))
        self.assertGreater(r4.revenue, r0.revenue)
        self.assertEqual(r4.demand, r0.demand)

    def test_new_product_first_year_sales_cap(self):
        capped, was_capped, _ = apply_new_product_first_year_sales_cap(3500, is_new_product_first_year=True)
        self.assertTrue(was_capped)
        self.assertEqual(capped, 2000)

    def test_profit_rate_classification(self):
        self.assertEqual(profit_rate_status(0.03), "faible")
        self.assertEqual(profit_rate_status(0.07), "optimal")
        self.assertEqual(profit_rate_status(0.12), "tres_bon")

    def test_marketing_simulation_0_10(self):
        rows = run_marketing_short_term_test(_base_scenario())
        self.assertEqual(len(rows), 6)

    def test_promo_sales_simulation(self):
        rows = run_promo_sales_test(_base_scenario())
        self.assertEqual(len(rows), 4)

    def test_full_market_global_simulation(self):
        all_periods = run_full_market_simulation()
        self.assertEqual(len(all_periods), 8)
        self.assertIn("firms", all_periods[0])

    def test_full_market_runs_all_companies_same_time(self):
        market = simulate_full_market(period=2, user_firm=None, user_scenario=None)
        self.assertEqual(len(market["firms"]), 9)
        self.assertEqual(set(market["firms"].keys()), {"AVE", "CAN", "EBI", "GIA", "PED", "RID", "SUR", "TRE", "VEL"})

    def test_opening_stock_increases_available_units(self):
        base = _base_scenario()
        low = simulate(base.model_copy(update={"opening_stock": 0, "production": 800}))
        high = simulate(base.model_copy(update={"opening_stock": 300, "production": 800}))
        self.assertGreaterEqual(high.stock_available_units, low.stock_available_units)
        self.assertGreaterEqual(high.sales, low.sales)

    def test_stock_coverage_alert_when_underproduced(self):
        sc = _base_scenario().model_copy(update={"production": 200, "opening_stock": 0})
        res = simulate(sc)
        self.assertEqual(res.stock_coverage_level, "red_under")
        self.assertTrue(any("[Stock]" in a for a in res.alerts))

    def test_next_period_opens_with_ending_stock(self):
        base = _base_scenario()
        res = simulate(base)
        nxt = build_next_period_scenario(base, res)
        self.assertEqual(nxt.opening_stock, res.forecast_ending_stock_units)

    def test_costs_increase_with_period_inflation(self):
        base = _base_scenario()
        p1 = simulate(base.model_copy(update={"period": 1, "price": 3200}))
        p4 = simulate(base.model_copy(update={"period": 4, "price": 3200}))
        self.assertGreater(period_inflation_factor(4), period_inflation_factor(1))
        self.assertGreater(p4.production_cost, p1.production_cost)

    def test_reference_model_prices_increase_by_period(self):
        market_p1 = simulate_full_market(period=1, user_firm=None, user_scenario=None)
        market_p4 = simulate_full_market(period=4, user_firm=None, user_scenario=None)
        self.assertGreater(
            market_p4["firms"]["TRE"]["total_revenue_before_premium"],
            market_p1["firms"]["TRE"]["total_revenue_before_premium"],
        )

    def test_full_market_financial_formulas_consistent(self):
        base = _base_scenario()
        market = simulate_full_market(period=1, user_firm="TRE", user_scenario=base)
        tre = market["firms"]["TRE"]
        self.assertIn("total_cost_estimate", tre)
        self.assertGreaterEqual(tre["total_revenue"], 0.0)
        self.assertGreaterEqual(tre["total_cost_estimate"], 0.0)
        self.assertAlmostEqual(
            tre["profit_estimate"],
            tre["total_revenue"] - tre["total_cost_estimate"],
            places=4,
        )
        self.assertGreaterEqual(tre["capacity_ratio"], 0.0)
        self.assertLessEqual(tre["capacity_ratio"], 1.0)


if __name__ == "__main__":
    unittest.main()
