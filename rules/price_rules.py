from __future__ import annotations

from typing import Tuple


STRICT_PRICE_BANDS = {
    "entry": (2000.0, 2800.0),
    "mid": (2800.0, 5500.0),
    "premium": (5500.0, float("inf")),
}


def check_price_range_consistency(price: float, gamme: str) -> Tuple[str, str]:
    """
    Return (status, message) where status in {"ok", "warning", "error"}.
    """
    low, high = STRICT_PRICE_BANDS[gamme]
    if price < low:
        return "error", f"Prix {price:,.0f} $ trop bas pour la gamme '{gamme}' (minimum {low:,.0f} $)."
    if high != float("inf") and price > high:
        return "warning", f"Prix {price:,.0f} $ au-dessus de la plage recommandee ({high:,.0f} $)."
    return "ok", f"Prix coherent avec la gamme '{gamme}'."


def price_range_penalty_multiplier(price: float, gamme: str) -> float:
    """
    Penalty applied to attractiveness when price/gamme is incoherent.
    """
    status, _ = check_price_range_consistency(price, gamme)
    if status == "error":
        return 0.75
    if status == "warning":
        return 0.90
    return 1.0
