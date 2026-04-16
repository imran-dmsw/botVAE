import unittest

from engine.models import ScenarioInput
from simulation.multi_scenario_runner import run_all_scenarios, compare_scenarios


def _base() -> ScenarioInput:
    return ScenarioInput(
        firm_name="TRE",
        period=1,
        scenario_name="Base",
        model_name="Model",
        product_type="ville_quotidien",
        segment="urbains_presses",
        model_range="mid",
        product_status="active",
        marketing_budget=80000,
        rd_budget=10000,
        price=3900,
        production=1500,
        adjusted_budget=1_200_000,
        competitor_attractiveness=18,
    )


class TestAutoScenarios(unittest.TestCase):
    def test_run_all_scenarios_has_six(self):
        rows = run_all_scenarios(_base())
        self.assertEqual(len(rows), 6)

    def test_compare_scenarios_returns_winners_columns(self):
        cmp_rows = compare_scenarios(run_all_scenarios(_base()))
        self.assertEqual(len(cmp_rows), 6)
        self.assertIn("Meilleur profit", cmp_rows[0])
        self.assertIn("Meilleur profit_rate", cmp_rows[0])


if __name__ == "__main__":
    unittest.main()
