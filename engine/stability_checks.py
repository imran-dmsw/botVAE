"""Contrôles de cohérence financière et score de stabilité."""
from __future__ import annotations

from typing import Iterable

from config.market_config import MARKET_CONFIG
from engine.models import ScenarioInput, SimulationResult


def marketing_roi(result: SimulationResult) -> float:
  if result.marketing_cost <= 0:
    return 0.0
  return result.profit / result.marketing_cost


def rd_roi(result: SimulationResult) -> float:
  if result.rd_cost <= 0:
    return 0.0
  return result.profit / result.rd_cost


def compute_simulation_stability_score(
  scenario: ScenarioInput,
  result: SimulationResult,
) -> float:
  score = 100.0
  if result.profit_rate < 0:
    score -= 35.0
  elif result.profit_rate < MARKET_CONFIG["constraints"]["profit_target_min"]:
    score -= 15.0
  if result.margin < -0.5:
    score -= 25.0
  elif result.margin < 0:
    score -= 10.0
  if result.marketing_cost > max(result.revenue, 1.0) * 0.35:
    score -= 15.0
  if result.rd_cost > max(result.revenue, 1.0) * 0.20:
    score -= 10.0
  if result.service_rate < 0.35:
    score -= 10.0
  if scenario.allocation_weight > 0 and scenario.allocation_weight > 0.65:
    score -= 5.0
  return max(0.0, min(100.0, score))


MARKET_MIN_PROFIT_TARGET = 0.02


def run_financial_controls(
  scenario: ScenarioInput,
  result: SimulationResult,
  *,
  peer_marketing: list[float] | None = None,
) -> list[str]:
  messages: list[str] = []
  if result.profit_rate < 0:
    messages.append(
      f"Profit négatif ({result.profit_rate * 100:.1f} % du CA) — revoir prix, production ou budgets."
    )
  if scenario.firm_marketing_budget_total > 0:
    if abs(result.marketing_cost - scenario.marketing_budget) > 1.0:
      messages.append("Incohérence marketing alloué vs coût comptabilisé.")
  if scenario.firm_rd_budget_total > 0 and abs(result.rd_cost - scenario.rd_budget) > 1.0:
    messages.append("Incohérence R&D alloué vs coût comptabilisé.")

  if peer_marketing:
    avg_mkt = sum(peer_marketing) / len(peer_marketing)
    if result.marketing_cost > avg_mkt * 2.5 and scenario.allocation_weight > 0.45:
      messages.append(
        f"Le modèle {scenario.model_name} absorbe une part excessive du budget marketing."
      )
    if result.rd_cost > max(result.revenue, 1.0) * 0.25 and result.marketing_cost > avg_mkt * 1.5:
      messages.append("Les budgets R&D sont disproportionnés par rapport aux ventes.")
    if len(peer_marketing) >= 2 and all(abs(m - result.marketing_cost) / max(m, 1.0) < 0.2 for m in peer_marketing):
      messages.append("La répartition budgétaire est cohérente avec les ventes prévues.")

  if result.margin < -1.0:
    messages.append("Marge irréaliste (< −100 %) — vérifier la double comptabilisation des budgets firme.")
  if result.total_cost > result.revenue * 3:
    messages.append("Coûts totaux très supérieurs au CA — simulation potentiellement instable.")

  return messages
