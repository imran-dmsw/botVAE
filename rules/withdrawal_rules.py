from __future__ import annotations

from typing import Dict, Tuple


def check_withdrawal_limits(
    firm: str,
    current_period: int,
    withdrawal_history: Dict[str, list[int]],
    *,
    max_per_year: int = 1,
    max_total: int = 4,
    min_period_gap: int = 2,
) -> Tuple[bool, str]:
    """
    Vérifie les retraits déjà enregistrés (historique de périodes).
    - Max max_total retraits sur la simulation.
    - Max max_per_year retrait sur une même période.
    - Écart minimum min_period_gap entre la dernière période de retrait strictement
      antérieure et la période courante (règle « 1 retrait / 2 périodes »).
    """
    periods = sorted(set(withdrawal_history.get(firm, [])))
    if len(periods) >= max_total:
        return False, f"{firm}: limite totale de retraits atteinte ({max_total})."

    same_year_count = sum(1 for p in periods if p == current_period)
    if same_year_count >= max_per_year:
        return False, f"{firm}: limite annuelle de retraits atteinte ({max_per_year})."

    prior = [p for p in periods if p < current_period]
    if prior:
        last_before = max(prior)
        if current_period - last_before < min_period_gap:
            return (
                False,
                f"{firm}: delai minimum entre retraits non respecte "
                f"({min_period_gap} periodes ; dernier retrait periode {last_before}).",
            )

    return True, f"{firm}: retrait autorise ({len(periods)}/{max_total} retraits enregistres)."
