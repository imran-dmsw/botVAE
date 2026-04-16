from __future__ import annotations

from typing import Tuple


def apply_new_product_first_year_sales_cap(
    sales: int,
    *,
    is_new_product_first_year: bool,
    min_units: int = 1000,
    max_units: int = 2000,
) -> Tuple[int, bool, str]:
    """
    Enforce first-year diffusion cap for new products.
    Returns (capped_sales, was_capped, message).
    """
    if not is_new_product_first_year:
        return sales, False, "Aucun plafond applique."

    capped = min(max(sales, min_units), max_units)
    was_capped = capped != sales
    message = (
        f"Nouveau produit (annee 1): ventes encadrees dans [{min_units}, {max_units}] -> {capped:,}."
    )
    return capped, was_capped, message


def liquidation_next_period_production_flag(product_status: str, liquidation: bool) -> bool:
    return liquidation or product_status == "withdrawal"
