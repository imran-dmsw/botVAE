from __future__ import annotations

from typing import Tuple


ALLOWED_PROMO_RATES = {0.0, -0.02, -0.03, -0.04, -0.05, -0.10}


def validate_promo_rate(rate: float) -> Tuple[bool, str]:
    normalized = round(float(rate), 2)
    if normalized in ALLOWED_PROMO_RATES:
        return True, "Taux promotion valide."
    return False, (
        f"Taux promotion invalide ({normalized*100:.0f}%). "
        "Valeurs autorisees: 0%, -2%, -3%, -4%, -5%, -10%."
    )
