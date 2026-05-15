"""Répartition des budgets marketing et R&D au niveau firme entre produits."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from config.market_config import MARKET_CONFIG


def firm_rd_allowed_pcts() -> tuple[float, ...]:
  """Parts R&D firme autorisées (du budget ajusté) : typiquement 2 %, 5 % et 8 %."""
  raw = MARKET_CONFIG.get("constraints", {}).get("rd_allowed_pcts", (0.02, 0.05, 0.08))
  return tuple(sorted(float(x) for x in raw))


def snap_rd_firm_pct(rd_pct: float | None) -> float:
  """Ramène le taux R&D firme à l’un des niveaux autorisés (2 %, 5 % ou 8 % du budget ajusté)."""
  allowed = firm_rd_allowed_pcts()
  if not allowed:
    return 0.02
  if rd_pct is None:
    return allowed[0]
  pct = float(rd_pct)
  return float(min(allowed, key=lambda x: abs(x - pct)))


ALLOCATION_METHODS = (
    "forecast_sales",
    "strategic_segment",
    "equal",
    "custom",
)

DEFAULT_ALLOCATION_METHOD = "forecast_sales"


@dataclass(frozen=True)
class AllocatedBudgets:
  marketing: float
  rd: float
  adjusted_budget: float
  weight: float


def product_reference_revenue(prod: Any, *, inflation: float = 1.0) -> float:
  base_price = float(getattr(prod, "base_price", prod.get("base_price", 0.0)) if isinstance(prod, dict) else prod.base_price)
  units = float(getattr(prod, "units", prod.get("units", 0.0)) if isinstance(prod, dict) else prod.units)
  return max(base_price * units * inflation, 0.0)


def product_key(prod: Any) -> str:
  if isinstance(prod, dict):
    return str(prod["product_key"])
  return str(prod.product_key)


def product_segment_idx(prod: Any) -> int:
  if isinstance(prod, dict):
    return int(prod["segment_idx"])
  return int(prod.segment_idx)


def compute_product_weights(
  products: Sequence[Any],
  method: str = DEFAULT_ALLOCATION_METHOD,
  *,
  custom_weights: Mapping[str, float] | None = None,
  segment_weights: Mapping[int, float] | None = None,
) -> dict[str, float]:
  if not products:
    return {}

  method = method if method in ALLOCATION_METHODS else DEFAULT_ALLOCATION_METHOD
  keys = [product_key(p) for p in products]

  if method == "equal":
    w = 1.0 / len(products)
    return {k: w for k in keys}

  if method == "custom":
    raw = {k: max(float((custom_weights or {}).get(k, 0.0)), 0.0) for k in keys}
    total = sum(raw.values())
    if total <= 0:
      return compute_product_weights(products, "equal")
    return {k: raw[k] / total for k in keys}

  if method == "strategic_segment":
    seg_w = segment_weights or {
      idx: float(MARKET_CONFIG["segments"][seg_key]["share"])
      for seg_key, idx in (
        ("urbains_presses", 1),
        ("prudentes_confort", 2),
        ("endurants_performants", 3),
        ("nomades_multimodaux", 4),
        ("familles_cargo", 5),
        ("aventuriers_tt", 6),
      )
    }
    raw = {product_key(p): float(seg_w.get(product_segment_idx(p), 0.1)) for p in products}
    total = sum(raw.values())
    if total <= 0:
      return compute_product_weights(products, "equal")
    return {k: raw[k] / total for k in keys}

  # forecast_sales (défaut) : poids = CA de référence produit / CA firme
  raw = {product_key(p): product_reference_revenue(p) for p in products}
  total = sum(raw.values())
  if total <= 0:
    return compute_product_weights(products, "equal")
  return {k: raw[k] / total for k in keys}


def firm_marketing_and_rd_totals(
  firm_adjusted_budget: float,
  *,
  marketing_mult: float = 1.0,
  rd_pct: float | None = None,
) -> tuple[float, float]:
  cfg = MARKET_CONFIG["constraints"]
  mkt_cap = firm_adjusted_budget * cfg["marketing_max_pct"]
  firm_mkt = min(max(firm_adjusted_budget * 0.08 * marketing_mult, 0.0), mkt_cap)
  rd_level = snap_rd_firm_pct(rd_pct)
  firm_rd = firm_adjusted_budget * rd_level
  return round(firm_mkt, 2), round(firm_rd, 2)


def allocate_firm_budgets(
  products: Sequence[Any],
  firm_adjusted_budget: float,
  *,
  allocation_method: str = DEFAULT_ALLOCATION_METHOD,
  marketing_mult: float = 1.0,
  rd_pct: float | None = None,
  custom_weights: Mapping[str, float] | None = None,
  segment_weights: Mapping[int, float] | None = None,
) -> dict[str, AllocatedBudgets]:
  weights = compute_product_weights(
    products,
    allocation_method,
    custom_weights=custom_weights,
    segment_weights=segment_weights,
  )
  firm_mkt, firm_rd = firm_marketing_and_rd_totals(
    firm_adjusted_budget,
    marketing_mult=marketing_mult,
    rd_pct=rd_pct,
  )
  keys = list(weights.keys())
  allocations: dict[str, AllocatedBudgets] = {}
  mkt_parts: list[float] = []
  rd_parts: list[float] = []
  adj_parts: list[float] = []

  for key in keys:
    w = weights[key]
    mkt_parts.append(round(firm_mkt * w, 2))
    rd_parts.append(round(firm_rd * w, 2))
    adj_parts.append(round(firm_adjusted_budget * w, 2))

  _reconcile_parts(mkt_parts, firm_mkt)
  _reconcile_parts(rd_parts, firm_rd)
  _reconcile_parts(adj_parts, firm_adjusted_budget)

  for i, key in enumerate(keys):
    allocations[key] = AllocatedBudgets(
      marketing=mkt_parts[i],
      rd=rd_parts[i],
      adjusted_budget=adj_parts[i],
      weight=weights[key],
    )
  return allocations


def _reconcile_parts(parts: list[float], target: float) -> None:
  if not parts:
    return
  delta = round(target - sum(parts), 2)
  parts[-1] = round(parts[-1] + delta, 2)


def verify_allocation_totals(
  allocations: Mapping[str, AllocatedBudgets],
  firm_marketing_total: float,
  firm_rd_total: float,
  *,
  tolerance: float = 0.05,
) -> tuple[bool, list[str]]:
  issues: list[str] = []
  mkt_sum = round(sum(a.marketing for a in allocations.values()), 2)
  rd_sum = round(sum(a.rd for a in allocations.values()), 2)
  if abs(mkt_sum - firm_marketing_total) > tolerance:
    issues.append(
      f"Marketing alloué ({mkt_sum:,.2f} $) ≠ budget firme ({firm_marketing_total:,.2f} $)."
    )
  if abs(rd_sum - firm_rd_total) > tolerance:
    issues.append(f"R&D alloué ({rd_sum:,.2f} $) ≠ budget firme ({firm_rd_total:,.2f} $).")
  return (not issues, issues)
