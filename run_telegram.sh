#!/bin/zsh
set -euo pipefail

cd /Users/imran/BotMarketing

if [[ ! -f ".env" ]]; then
  echo "Erreur: fichier .env introuvable."
  echo "Crée-le depuis le modèle: cp .env.example .env"
  exit 1
fi

# Export all variables defined in .env
set -a
source ./.env
set +a

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  echo "Erreur: TELEGRAM_BOT_TOKEN est vide dans .env"
  exit 1
fi

echo "Lancement du bot Telegram..."
python3 telegram_bot.py
