#!/usr/bin/env python3
"""
Générateur de rapport stratégique VAE — point d'entrée.
Usage : python3 scripts/generate_rapport_firme.py --firme AVE
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

from generate_rapport_compact_pdf import generer_pdf_rapport_compact  # noqa: E402
from generate_rapport_vae_style_pdf import generer_pdf_rapport  # noqa: E402
from vae_rapport_firme_logic import (  # noqa: E402
    FIRMES_VALIDES,
    calculer_vue_firme,
    calculer_vue_modele,
    charger_donnees_firme,
    default_excel_path,
    generer_recommandations_firme,
    resolve_firm_code,
)

OUTPUT_DIR = Path("/Users/imran/BotMarketing/reports")
DOWNLOAD_DIR = Path("/Users/imran/Downloads")


def main() -> None:
    parser = argparse.ArgumentParser(description="Générateur rapport stratégique VAE")
    parser.add_argument(
        "--firme",
        "--firm",
        dest="firme",
        required=True,
        help=f"Code firme parmi : {', '.join(FIRMES_VALIDES)}",
    )
    parser.add_argument("--workbook", type=Path, default=None, help="Classeur Excel VAE")
    parser.add_argument("--out", type=Path, default=None, help="Chemin PDF de sortie")
    parser.add_argument(
        "--complet",
        action="store_true",
        help="Générer le rapport stratégique long (sinon rapport compact 3–5 pages)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Exécuter la checklist Excel ↔ rapport avant génération PDF",
    )
    args = parser.parse_args()

    code_firme = resolve_firm_code(args.firme)
    if code_firme not in FIRMES_VALIDES:
        print(f"[ERREUR] Firme '{args.firme}' inconnue. Valeurs acceptées : {FIRMES_VALIDES}")
        sys.exit(1)

    excel_path = args.workbook.expanduser() if args.workbook else default_excel_path()
    if not excel_path.exists():
        print(f"[ERREUR] Classeur introuvable : {excel_path}")
        sys.exit(1)

    if args.verify:
        from verify_rapport_workbook_parity import verify_workbook_parity

        print(f"[INFO] Vérification concordance Excel ↔ rapport ({excel_path})...")
        checks = verify_workbook_parity(excel_path, code_firme)
        failed = sum(1 for c in checks if not c.ok)
        for item in checks:
            tag = "OK" if item.ok else "ECHEC"
            print(f"[{tag}] {item.name} — {item.detail}")
        if failed:
            print(f"[ERREUR] {failed} contrôle(s) en échec — génération PDF annulée.")
            sys.exit(1)
        print("[OK] Checklist validée.")

    print(f"[INFO] Chargement données pour {code_firme}...")
    donnees = charger_donnees_firme(excel_path, code_firme)

    print("[INFO] Calcul vue firme...")
    vue_firme = calculer_vue_firme(donnees)

    produits = donnees["produits"]
    print(f"[INFO] Calcul {len(produits)} fiches modèle...")
    fiches_modeles = {p.product_key: calculer_vue_modele(donnees, p) for p in produits}

    print("[INFO] Génération recommandations firme...")
    recommandations = generer_recommandations_firme(vue_firme, donnees)

    date_str = date.today().strftime("%Y-%m-%d")
    prefix = "Rapport" if args.complet else "Rapport_compact"
    nom_fichier = f"{prefix}_{code_firme}_VAE_{date_str}.pdf"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    chemin_sortie = args.out or (OUTPUT_DIR / nom_fichier)
    if not chemin_sortie.is_absolute():
        chemin_sortie = Path.cwd() / chemin_sortie

    print(f"[INFO] Génération PDF → {chemin_sortie}")
    if args.complet:
        generer_pdf_rapport(
            chemin_sortie=str(chemin_sortie),
            code_firme=code_firme,
            vue_firme=vue_firme,
            fiches_modeles=fiches_modeles,
            recommandations=recommandations,
            donnees=donnees,
        )
    else:
        generer_pdf_rapport_compact(
            chemin_sortie=str(chemin_sortie),
            code_firme=code_firme,
            donnees=donnees,
            recommandations=recommandations,
        )

    chemin_dl = DOWNLOAD_DIR / chemin_sortie.name
    try:
        shutil.copy2(chemin_sortie, chemin_dl)
        print(f"[OK] Rapport généré : {chemin_sortie}")
        print(f"[OK] Copie Downloads : {chemin_dl}")
    except OSError as exc:
        print(f"[OK] Rapport généré : {chemin_sortie}")
        print(f"[AVERTISSEMENT] Copie Downloads impossible : {exc}")


if __name__ == "__main__":
    main()
