from __future__ import annotations

from typing import Optional

from engine.models import ScenarioInput
from engine.simulation import simulate_full_market_all_periods


def run_full_market_simulation(
    user_firm: Optional[str] = None,
    user_scenario_template: Optional[ScenarioInput] = None,
) -> list:
    """
    Global stability run: all firms, all segments, all periods.
    """
    return simulate_full_market_all_periods(user_firm, user_scenario_template)
