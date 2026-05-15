import unittest
from pathlib import Path

from engine.excel_sources import audit_workbook_fields
from engine.market_matrix import build_firm_segment_matrix
from engine.rapport_alertes import build_prioritized_alerts
from engine.models import ScenarioInput
from engine.simulation import simulate
from scripts.generate_rapport_vae_style_pdf import AUTO_SCENARIO_TAGS, build_scenario_grid, run_grid
from scripts.vae_rapport_firme_logic import default_excel_path

import openpyxl


class TestRapportCompact(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workbook = default_excel_path()
        if not cls.workbook.exists():
            raise unittest.SkipTest(f"Classeur absent : {cls.workbook}")

    def test_auto_scenarios_present_for_tre(self):
        wb = openpyxl.load_workbook(self.workbook, data_only=True)
        grid = build_scenario_grid(wb, "TRE")
        ids = {sid for sid, owner, _ in grid if owner == "TRE"}
        for tag in AUTO_SCENARIO_TAGS:
            self.assertTrue(any(tag in sid for sid in ids), msg=tag)

    def test_auto_scenario_metrics(self):
        wb = openpyxl.load_workbook(self.workbook, data_only=True)
        grid = build_scenario_grid(wb, "TRE")
        results = run_grid(grid)
        auto = [row for row in results if row[1] == "TRE" and any(tag in row[0] for tag in AUTO_SCENARIO_TAGS)]
        self.assertGreaterEqual(len(auto), 4)
        for _sid, _owner, _scen, res in auto:
            self.assertGreaterEqual(res.sales, 0)
            self.assertIsNotNone(res.margin)

    def test_company_segment_matrix_shape(self):
        matrix = build_firm_segment_matrix(period=1)
        self.assertEqual(len(matrix["rows"]), 9)
        self.assertEqual(len(matrix["columns"]), 6)

    def test_excel_audit_label(self):
        audit = audit_workbook_fields(self.workbook, "TRE")
        self.assertIn("Source des données", audit.source_label)
        self.assertGreater(len(audit.probes), 0)

    def test_prioritized_alerts_grouping(self):
        scenario = ScenarioInput(
            firm_name="TRE",
            period=1,
            scenario_name="Test",
            model_name="Model",
            product_type="ville_quotidien",
            segment="urbains_presses",
            model_range="mid",
            product_status="active",
            marketing_budget=80_000,
            rd_budget=10_000,
            price=2400,
            production=1500,
            adjusted_budget=1_200_000,
            competitor_attractiveness=18,
            promotion_rate=-0.11,
        )
        result = simulate(scenario)
        result = result.model_copy(
            update={
                "margin": 0.03,
                "service_rate": 0.75,
                "forecast_ending_stock_units": 400,
                "forecast_coverage_rate": 1.2,
            }
        )
        grouped = build_prioritized_alerts(scenario=scenario, result=result)
        self.assertTrue(grouped["critique"] or grouped["attention"])


if __name__ == "__main__":
    unittest.main()
