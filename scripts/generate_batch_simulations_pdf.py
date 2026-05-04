#!/usr/bin/env python3
"""
Genere un PDF unique : une section par scenario (description, KPIs, conseils).
Usage :
  python scripts/generate_batch_simulations_pdf.py
  python scripts/generate_batch_simulations_pdf.py ../rapport_custom.pdf
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reports.generator import generate_multi_pdf_report
from simulation.batch_scenarios import collect_default_batch


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "rapport_lot_simulations.pdf"
    scenarios, results = collect_default_batch()
    pdf_bytes = generate_multi_pdf_report(scenarios, results)
    out.write_bytes(pdf_bytes)
    print(f"Ecrit : {out.resolve()} ({len(pdf_bytes):,} octets)")


if __name__ == "__main__":
    main()
