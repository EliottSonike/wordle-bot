#!/bin/bash
# Script d'installation du bot Wordle sur Ubuntu/Debian
# A lancer en tant que root : sudo bash deploy.sh

set -e

INSTALL_DIR="/opt/wordle-bot"
SERVICE_USER="wordle"

echo "==> Installation des dépendances système..."
apt-get update -q
apt-get install -y python3 python3-venv python3-pip

echo "==> Création de l'utilisateur système '$SERVICE_USER'..."
id "$SERVICE_USER" &>/dev/null || useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"

echo "==> Copie des fichiers dans $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
cp bot.py database.py leaderboard.py parser.py requirements.txt "$INSTALL_DIR/"

echo "==> Création de l'environnement virtuel..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

echo "==> Configuration du fichier .env..."
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp .env.example "$INSTALL_DIR/.env"
    echo ""
    echo "  IMPORTANT : remplis $INSTALL_DIR/.env avec tes vraies valeurs avant de continuer."
    echo "  nano $INSTALL_DIR/.env"
    echo ""
fi

echo "==> Installation du service systemd..."
cp wordle-bot.service /etc/systemd/system/wordle-bot.service
chown -R "$SERVICE_USER":"$SERVICE_USER" "$INSTALL_DIR"
systemctl daemon-reload
systemctl enable wordle-bot

echo ""
echo "Installation terminée."
echo "1. Remplis le fichier /opt/wordle-bot/.env"
echo "2. Lance le bot : sudo systemctl start wordle-bot"
echo "3. Vérifie les logs : sudo journalctl -u wordle-bot -f"
