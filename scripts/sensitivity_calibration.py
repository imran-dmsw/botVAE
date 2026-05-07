from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.param_overrides import temporary_market_config
from engine.simulation import simulate
from simulation.batch_scenarios import default_base_scenario


@dataclass(frozen=True)
class SensitivityRow:
    label: str
    operating_pct: float
    growth_rate: float
    profit: float
    margin: float
    sales: int
    service_rate: float
    inventory_carrying_cost: float


def run() -> List[SensitivityRow]:
    base = default_base_scenario()
    rows: List[SensitivityRow] = []

    operating_pcts = [0.05, 0.075]
    growth_rates = [0.10, 0.11, 0.12]

    for op in operating_pcts:
        for g in growth_rates:
            overrides = {
                "growth_rate": g,
                "constraints": {"operating_ref_budget_pct": op},
            }
            with temporary_market_config(overrides):
                res = simulate(base)
            rows.append(
                SensitivityRow(
                    label=f"op{op:.3f}_g{g:.2f}",
                    operating_pct=op,
                    growth_rate=g,
                    profit=res.profit,
                    margin=res.margin,
                    sales=res.sales,
                    service_rate=res.service_rate,
                    inventory_carrying_cost=res.inventory_carrying_cost,
                )
            )
    return rows


def main() -> None:
    rows = run()
    payload: Dict[str, Any] = {
        "generated_at": datetime.now().isoformat(),
        "rows": [asdict(r) for r in rows],
    }

    out = Path("data") / "calibration_sensitivity.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Console summary (compact)
    best = max(rows, key=lambda r: r.profit)
    print(f"Wrote {out} ({len(rows)} rows). Best profit: {best.label} -> {best.profit:,.0f} $ (marge {best.margin*100:.1f}%)")


if __name__ == "__main__":
    main()

