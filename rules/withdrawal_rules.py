from __future__ import annotations

from typing import Dict, Tuple


def check_withdrawal_limits(
    firm: str,
    current_period: int,
    withdrawal_history: Dict[str, list[int]],
    *,
    max_per_year: int = 1,
    max_total: int = 4,
) -> Tuple[bool, str]:
    periods = sorted(withdrawal_history.get(firm, []))
    if len(periods) >= max_total:
        return False, f"{firm}: limite totale de retraits atteinte ({max_total})."

    same_year_count = sum(1 for p in periods if p == current_period)
    if same_year_count >= max_per_year:
        return False, f"{firm}: limite annuelle de retraits atteinte ({max_per_year})."

    return True, f"{firm}: retrait autorise ({len(periods)}/{max_total} retraits utilises)."
