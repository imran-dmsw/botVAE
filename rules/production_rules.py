from __future__ import annotations

from typing import Tuple


def recommend_next_period_production(
    sales_n: int,
    stock_final_n: int,
    market_trend: float,
    product_status: str,
    adjustment_factor: float = 1.10,
) -> Tuple[int, str]:
    """
    Compute recommended production for N+1 with a transparent explanation.
    """
    if product_status == "withdrawal":
        return 0, "Produit en retrait: production N+1 forcee a 0."

    base = max(sales_n - max(stock_final_n, 0), 0)
    trend_factor = max(0.85, min(1.20, 1.0 + market_trend))
    final_factor = max(1.05, min(1.15, adjustment_factor))
    recommended = int(base * trend_factor * final_factor)
    explanation = (
        f"Production N+1 = max(ventes N - stock final, 0) x tendance ({trend_factor:.2f}) "
        f"x ajustement ({final_factor:.2f}) = {recommended:,}."
    )
    return max(recommended, 0), explanation


def production_efficiency(sales: int, production: int) -> float:
    if production <= 0:
        return 0.0
    return sales / production
