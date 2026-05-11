#!/usr/bin/env python3
"""Point d’entrée court : génère le PDF d’analyse VAE (styles dans vae_report_style.py)."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_SCRIPTS))

from generate_rapport_vae_style_pdf import main  # noqa: E402

if __name__ == "__main__":
    main()
