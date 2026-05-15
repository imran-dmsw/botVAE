"""Calcul pédagogique « production 2 250 u. » partagé Excel / PDF (sans openpyxl)."""
from __future__ import annotations

import math
from typing import Any

MARKET_UNITS_RATIO = 123_200 / 110_000
PRODUCTION_FIXED = 2250

COGS_BY_GAMME = {"Basic": 0.60, "Medium": 0.57, "Premium": 0.55}
DIST_BY_GAMME = {"Basic": 0.08, "Medium": 0.09, "Premium": 0.10}

# Ordre colonnes : Scénario | Ventes | Profit | Service | CA | Marge | Stock
REFERENCE_2250_HEADERS: tuple[str, ...] = (
    "Scénario",
    "Ventes (u.)",
    "Profit ($)",
    "Taux de service (%)",
    "CA ($)",
    "Marge (%)",
    "Stock restant (u.)",
)


def gamme_bucket_for_ratios(range_raw: Any) -> str:
    key = str(range_raw or "").strip()
    if key.lower() == "standard":
        return "Medium"
    low = key.lower()
    if low in ("basic", "bas"):
        return "Basic"
    if low in ("medium", "moyen"):
        return "Medium"
    if low in ("premium", "haut"):
        return "Premium"
    return "Medium"


def compute_reference_2250_row(
    *,
    units_ref: float,
    price_p2: float,
    marketing_alloc: float,
    rd_alloc: float,
    range_raw: str,
) -> dict[str, float | int]:
    """Ventes = floor(min(2250, unités_ref × 123200/110000)), puis CA, profit, marge, service, stock."""
    u_ref = float(units_ref)
    price = float(price_p2)
    mkt = float(marketing_alloc)
    rd = float(rd_alloc)
    demande = u_ref * MARKET_UNITS_RATIO
    ventes = int(math.floor(min(float(PRODUCTION_FIXED), demande)))
    ca = ventes * price
    bucket = gamme_bucket_for_ratios(range_raw)
    cogs_r = COGS_BY_GAMME[bucket]
    dist_r = DIST_BY_GAMME[bucket]
    profit = ca - ca * cogs_r - ca * dist_r - mkt - rd
    marge = (profit / ca) if ca else 0.0
    service = min(1.0, ventes / float(PRODUCTION_FIXED)) if PRODUCTION_FIXED else 0.0
    stock = max(0, PRODUCTION_FIXED - ventes)
    return {
        "ventes": ventes,
        "profit": profit,
        "service": service,
        "ca": ca,
        "marge": marge,
        "stock": stock,
    }
