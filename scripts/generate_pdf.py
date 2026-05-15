#!/usr/bin/env python3
"""
Génère le rapport PDF VAE révisé (ReportLab), même logique que generate_rapport_vae_style_pdf.
Usage : python3 scripts/generate_pdf.py --firme TRE [--workbook PATH] [--out PATH]
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.market_config import MARKET_CONFIG  # noqa: E402
from generate_rapport_vae_style_pdf import (  # noqa: E402
    OUT_PDF,
    generer_pdf_rapport,
)
from vae_rapport_firme_logic import (  # noqa: E402
    calculer_vue_firme,
    calculer_vue_modele,
    charger_donnees_firme,
    default_excel_path,
    generer_recommandations_firme,
    resolve_firm_code,
)

DOWNLOAD_DIR = Path("/Users/imran/Downloads")


def main() -> None:
    ap = argparse.ArgumentParser(description="Rapport PDF VAE (vue longue révisée)")
    ap.add_argument("--all-firms", action="store_true", help="Générer un PDF par firme (codes MARKET_CONFIG)")
    ap.add_argument("--firme", "--firm", default="TRE")
    ap.add_argument("--workbook", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    xlsx = args.workbook.expanduser() if args.workbook else default_excel_path()
    if not xlsx.exists():
        raise SystemExit(f"Classeur introuvable : {xlsx}")

    if args.all_firms:
        firms = sorted(MARKET_CONFIG["firms"].keys())
        for code in firms:
            firm = resolve_firm_code(code)
            donnees = charger_donnees_firme(xlsx, firm)
            vue_firme = calculer_vue_firme(donnees)
            produits = donnees["produits"]
            fiches_modeles = {p.product_key: calculer_vue_modele(donnees, p) for p in produits}
            recommandations = generer_recommandations_firme(vue_firme, donnees)
            out_f = Path(str(OUT_PDF).format(firm=firm, date=date.today().isoformat()))
            out_f = out_f.expanduser()
            if not out_f.is_absolute():
                out_f = Path.cwd() / out_f
            generer_pdf_rapport(out_f, firm, vue_firme, fiches_modeles, recommandations, donnees)
            try:
                shutil.copy2(out_f, DOWNLOAD_DIR / out_f.name)
            except OSError:
                pass
            print(f"[OK] PDF : {out_f}")
        return

    firm = resolve_firm_code(args.firme)
    if firm not in MARKET_CONFIG["firms"]:
        raise SystemExit(f"Firme inconnue : {firm!r}")

    donnees = charger_donnees_firme(xlsx, firm)
    vue_firme = calculer_vue_firme(donnees)
    produits = donnees["produits"]
    fiches_modeles = {p.product_key: calculer_vue_modele(donnees, p) for p in produits}
    recommandations = generer_recommandations_firme(vue_firme, donnees)

    out = args.out or Path(str(OUT_PDF).format(firm=firm, date=date.today().isoformat()))
    out = out.expanduser()
    if not out.is_absolute():
        out = Path.cwd() / out

    generer_pdf_rapport(out, firm, vue_firme, fiches_modeles, recommandations, donnees)
    try:
        shutil.copy2(out, DOWNLOAD_DIR / out.name)
        print(f"[OK] PDF : {out}")
        print(f"[OK] Copie : {DOWNLOAD_DIR / out.name}")
    except OSError as e:
        print(f"[OK] PDF : {out}")
        print(f"[AVERTISSEMENT] Copie Downloads : {e}")


if __name__ == "__main__":
    main()
