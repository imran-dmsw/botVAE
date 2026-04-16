import unittest

from engine.models import ScenarioInput
from engine.simulation import simulate
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

    def test_liquidation_next_period_production_zero(self):
        sc = _base_scenario().model_copy(update={"liquidation": True})
        res = simulate(sc)
        self.assertEqual(res.next_period_recommended_production, 0)

    def test_withdrawal_over_limit(self):
        allowed, _ = check_withdrawal_limits("TRE", 4, {"TRE": [1, 2, 3, 4]}, max_total=4)
        self.assertFalse(allowed)

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


if __name__ == "__main__":
    unittest.main()
