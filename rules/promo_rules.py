from __future__ import annotations

from typing import Tuple

from config.market_config import MARKET_CONFIG

ALLOWED_PROMO_RATES = {0.0, -0.02, -0.03, -0.04, -0.05, -0.10}


def validate_promo_rate(rate: float, liquidation: bool = False) -> Tuple[bool, str]:
    normalized = round(float(rate), 2)
    cfg = MARKET_CONFIG["constraints"]
    if liquidation:
        lo = cfg["promo_liquidation_max"]
        if normalized < lo - 1e-9 or normalized > 0:
            return False, (
                f"Taux promotion liquidation invalide ({normalized*100:.0f}%). "
                f"Plage autorisee: {lo*100:.0f}% a 0%."
            )
        return True, "Taux promotion valide (liquidation)."
    if normalized in ALLOWED_PROMO_RATES:
        return True, "Taux promotion valide."
    return False, (
        f"Taux promotion invalide ({normalized*100:.0f}%). "
        "Valeurs autorisees: 0%, -2%, -3%, -4%, -5%, -10%."
    )
