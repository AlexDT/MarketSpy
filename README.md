# MarketSpy

Lokale watcher voor Marktplaats, 2dehands.be en Funda: doorzoek dagelijks het aanbod op jouw criteria, houd verloop bij (prijs, tekst, van de markt) en vang detailpagina's via een Safari-extensie.

## Wat het doet

- **Zoekt** op Marktplaats + 2dehands.be (`q=meta quest 3`) en op Funda (woningen) met alle vindbare advertenties per run
- **Filtert** op jouw kwalificaties: opslag, conditie, prijsrange, plaatsen binnen bereik, vaste prijs, min. accessoires
- **Logt** elke run als snapshot (`data/snapshots/`, `data/funda-snapshots/`) — nooit overschreven, dus verloop-analyse is altijd mogelijk
- **Detecteert** verschillen met de vorige snapshot: nieuwe advertenties, verwijderde (waarschijnlijk verkocht), prijs- en tekstwijzigingen
- **Downloadt** foto's per advertentie-id voor uniciteitscontrole
- **Genereert** rapporten: `data/reports/latest.md`, `data/funda-reports/latest.md`
- **Vangt detailpagina's** via de Safari-extensie (advertenties én Funda-woningen) in `data/inbox/` — inclusief foto-URL's, verkopersinfo en reviews

## Installatie (macOS)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Webinterface (aanbevolen)

```bash
python3 webapp.py
# open http://127.0.0.1:5001
```

In de interface:
- **Zoekopdracht aanmaken**: zoekterm, opslag-voorkeur (512 GB) + optioneel (128 GB), condities (nieuw / zo goed als nieuw / gebruikt), prijsrange, min. aantal accessoires, plaatsen binnen bereik, alleen vaste prijs, foto's downloaden.
- **Scherpen**: klik op een bestaande query → formulier wordt voorgevuld → aanpassen en opslaan (zelfde naam = bijwerken).
- **Scan nu**: draait de scan met de kwalificaties van die query en toont daarna het rapport op de pagina.
- **Inbox**: alles wat je via de Safari-extensie hebt doorgestuurd, in een overzichtstabel.

## Safari-extensie (pagina's doorsturen met één klik)

In `safari-extension/` zit een Web Extension die in Safari 16.4+ werkt (en ook in Chrome):

1. Zorg dat de webapp draait: `python3 webapp.py`
2. Safari → Instellingen → Geavanceerd → vink "Toon functies voor webontwikkelaars" aan
3. Safari → Ontwikkelen → Toon Extensies-ontwikkelaar → laad de map als niet-gepakte extensie en zet "MarketSpy Helper" aan
4. Open een advertentie op Marktplaats/2dehands of een woning op Funda en klik op de toolbar-knop van de extensie

De extensie haalt van de pagina: titel, prijs, conditie, beschrijving, plaats, advertentienummer, bekeken/bewaard-tellers, verkoperinfo (naam, lid sinds, reviews) en alle foto-URL's — bij Funda: adres, vraagprijs, makelaar. Dat wordt als JSON naar `http://127.0.0.1:5001/inbox` gepost en opgeslagen in `data/inbox/`. Alles blijft lokaal.

## CLI-gebruik

```bash
# Marktplaats/2dehands-scan (tekst-only, snel):
python3 watcher.py scan

# Scan met foto-download (langzamer):
python3 watcher.py scan --photos

# Verloop-rapport:
python3 watcher.py report

# Funda (werkt mogelijk niet door botbescherming — zie hieronder):
python3 funda.py scan --plaats Vlaardingen --min 250000 --max 450000
python3 funda.py report
```

## Funda-kanttekening

Funda blokkeert geautomatiseerde requests (tussenpagina "Je bent bijna op de pagina die je zoekt"). `funda.py` werkt alleen als jouw machine niet geblokkeerd wordt; de Safari-extensie werkt altijd, want die gebruikt jouw eigen browsersessie.

## Dagelijkse ochtendrun (cron)

```
30 7 * * * cd /pad/naar/marketspy && .venv/bin/python3 watcher.py scan --photos >> cron.log 2>&1
```

## Datastructuur

```
data/
  snapshots/       # rauwe advertentielijst per run (JSON, nooit overschreven)
  funda-snapshots/ # idem voor Funda
  photos/          # foto's per advertentie-id
  reports/         # dagelijkse rapporten + latest.md
  funda-reports/   # idem voor Funda
  inbox/           # via de extensie doorgestuurde pagina's (JSON)
  queries.json     # bewaarde zoekopdrachten uit de webinterface
```

## Belangrijke kanttekening

`watcher.py` gebruikt gewone HTTP-requests (geen browser-automatisering). Marktplaats en 2dehands kunnen hun structuur of botbescherming wijzigen; als een scan leeg terugkomt, controleer dan eerst of de gebruikte URL-formaten nog werken. Voor Funda geldt hetzelfde, alleen strenger.
