from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from typing import Any, Dict, Iterator

from config.market_config import MARKET_CONFIG


def _deep_update(d: Dict[str, Any], patch: Dict[str, Any]) -> None:
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(d.get(k), dict):
            _deep_update(d[k], v)  # type: ignore[index]
        else:
            d[k] = v


@contextmanager
def temporary_market_config(overrides: Dict[str, Any]) -> Iterator[None]:
    """
    Contexte de calibration: applique des overrides à MARKET_CONFIG puis restaure.
    Utile pour exécuter des tests de sensibilité sans modifier durablement la config.
    """
    snapshot = deepcopy(MARKET_CONFIG)
    try:
        _deep_update(MARKET_CONFIG, overrides)
        yield
    finally:
        MARKET_CONFIG.clear()
        MARKET_CONFIG.update(snapshot)

