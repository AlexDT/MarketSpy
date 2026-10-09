#!/usr/bin/env bash
# Maak van deze map een git-repo en zet de eerste commit.
set -e
cd "$(dirname "$0")"
git init
git add -A
git commit -m "Init: MarketSpy"
echo
echo "Klaar. Optioneel: voeg je eigen GitHub-remote toe met:"
echo "  git remote add origin git@github.com:AlexDT/MarketSpy.git"
echo "  git push -u origin main"
