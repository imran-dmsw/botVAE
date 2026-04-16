from __future__ import annotations

from engine.models import ScenarioInput, SimulationResult
from engine.simulation import simulate


def run_scenario(scenario: ScenarioInput) -> SimulationResult:
    return simulate(scenario)
