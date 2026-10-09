# MarketSpy

Lokale watcher voor Marktplaats, 2dehands.be en Funda: doorzoek dagelijks het aanbod op jouw criteria, houd verloop bij (prijs, tekst, van de markt) en vang detailpagina's via een Safari-extensie.

## Wat het doet

- Zoekt op Marktplaats + 2dehands.be en op Funda (woningen)
- Filtert op jouw kwalificaties: opslag, conditie, prijsrange, plaatsen binnen bereik, vaste prijs, min. accessoires
- Logt elke run als snapshot — nooit overschreven, dus verloop-analyse is altijd mogelijk
- Detecteert nieuwe advertenties, verwijderde (waarschijnlijk verkocht), prijs- en tekstwijzigingen
- Downloadt foto's per advertentie-id voor uniciteitscontrole
- Genereert rapporten: data/reports/latest.md
- Vangt detailpagina's via de Safari-extensie in data/inbox/

## Installatie (macOS)

```bash
./init-repo.sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Webinterface

```bash
python3 webapp.py   # open http://127.0.0.1:5001
```

## Safari-extensie

Zie README-sectie hierboven; werkt op Marktplaats, 2dehands.be en Funda.

## CLI

```bash
python3 watcher.py scan            # Marktplaats/2dehands
python3 watcher.py scan --photos   # met foto's
python3 watcher.py report
python3 funda.py scan --plaats Vlaardingen --min 250000 --max 450000
python3 funda.py report
```

## Kanttekening

Funda blokkeert geautomatiseerde requests; gebruik voor Funda de Safari-extensie. Volledige uitleg staat in de repo-README na eerste push.
