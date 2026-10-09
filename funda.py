#!/usr/bin/env python3
"""Funda Watcher - scant Funda koopwoningen op plaats + prijsrange.

Gebruik:
    python3 funda.py scan --plaats Vlaardingen --min 250000 --max 450000
    python3 funda.py report

Snapshots en rapporten komen in data/funda-snapshots/ en data/funda-reports/.
"""

import argparse
import json
import re
from datetime import date, datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
SNAPSHOTS = ROOT / "data" / "funda-snapshots"
REPORTS = ROOT / "data" / "funda-reports"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def funda_url(plaats, min_prijs=None, max_prijs=None):
    path = f"https://www.funda.nl/koop/{plaats.lower().replace(' ', '-')}/"
    if min_prijs or max_prijs:
        path += f"{min_prijs or 0}-{max_prijs or ''}/"
    return path


def fetch_listings(plaats, min_prijs, max_prijs, max_pages=3):
    """Haalt woninglijsten op van Funda en parseert de zoekresultatenpagina's."""
    items = []
    for page in range(1, max_pages + 1):
        url = funda_url(plaats, min_prijs, max_prijs)
        try:
            r = requests.get(url, params={"page": page} if page > 1 else None,
                             headers={"User-Agent": UA}, timeout=20)
            if r.status_code != 200:
                print(f"Funda gaf status {r.status_code} op pagina {page} — "
                      "mogelijk botbescherming; verlaag de frequentie of check de URL in je browser.")
                break
        except requests.RequestException as e:
            print(f"Fout bij ophalen: {e}")
            break

        soup = BeautifulSoup(r.text, "html.parser")
        page_items = []
        for block in soup.select("div[data-test-id='search-result-item'], li[class*='search-result']"):
            text = block.get_text(" ", strip=True)
            prijs = re.search(r"€\s?([\d\.]+)\s?(k\.k\.|v\.o\.n\.)", text)
            adres = block.select_one("h2, [data-test-id='street-name']")
            postcode = re.search(r"(\d{4}\s?[A-Z]{2})", text)
            m2 = re.search(r"(\d+)\s?m²", text)
            kamers = re.search(r"(\d+)\s?kamers?", text, re.I)
            label = re.search(r"\b(A\+\+|A\+|A|B|C|D|E|F|G)\b", text)
            link = block.select_one("a[href*='/koop/']")
            item_id = None
            if link:
                m = re.search(r"(\d{8,})", link.get("href", ""))
                item_id = m.group(1) if m else None
            if not adres:
                continue
            page_items.append({
                "id": item_id or re.sub(r"\W", "", adres.get_text(strip=True))[:20],
                "adres": adres.get_text(" ", strip=True),
                "prijs": int(prijs.group(1).replace(".", "")) if prijs else None,
                "prijs_type": prijs.group(2) if prijs else None,
                "postcode": postcode.group(1) if postcode else "",
                "m2": int(m2.group(1)) if m2 else None,
                "kamers": int(kamers.group(1)) if kamers else None,
                "energielabel": label.group(1) if label else "",
                "makelaar": "",
                "url": "https://www.funda.nl" + link.get("href", "") if link else url,
                "omschrijving": "",
            })
        if not page_items:
            break
        items.extend(page_items)
    return items


def save_snapshot(items):
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    snap = {
        "date": date.today().isoformat(),
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "items": items,
    }
    path = SNAPSHOTS / f"{snap['date']}.json"
    if path.exists():
        path = SNAPSHOTS / f"{snap['date']}-{snap['fetched_at'].replace(':','')}.json"
    path.write_text(json.dumps(snap, indent=2, ensure_ascii=False))
    return path


def make_report(current_path):
    current = json.loads(current_path.read_text())
    files = sorted(SNAPSHOTS.glob("*.json"), reverse=True)
    prev = next((json.loads(p.read_text()) for p in files if p != current_path), None)
    cur = {i["id"]: i for i in current["items"]}

    lines = [f"# Funda-scan {current['fetched_at']}", ""]
    if prev:
        old = {i["id"]: i for i in prev["items"]}
        nieuw = [i for i in cur if i not in old]
        weg = [i for i in old if i not in cur]
        prijs_wijziging = [(cur[i], old[i]["prijs"], cur[i]["prijs"])
                           for i in old if i in cur and old[i]["prijs"] != cur[i]["prijs"]]
        lines.append(f"## Verloop t.o.v. {prev['fetched_at']}")
        lines.append("")
        if nieuw:
            lines.append(f"### Nieuw ({len(nieuw)})")
            for i in nieuw:
                it = cur[i]
                lines.append(f"- **{it['adres']}** — €{it['prijs']} ({it['prijs_type']}) — "
                             f"{it['kamers']} kamers — {it['m2']}m² — {it['url']}")
            lines.append("")
        if weg:
            lines.append(f"### Van de markt / verkocht ({len(weg)})")
            for i in weg:
                it = old[i]
                lines.append(f"- {it['adres']} — was €{it['prijs']}")
            lines.append("")
        if prijs_wijziging:
            lines.append(f"### Prijs gewijzigd ({len(prijs_wijziging)})")
            for it, oud, nieuw2 in prijs_wijziging:
                lines.append(f"- {it['adres']}: €{oud} -> €{nieuw2} ({it['url']})")
            lines.append("")
        if not (nieuw or weg or prijs_wijziging):
            lines.append("Geen wijzigingen.")
            lines.append("")

    lines.append(f"## Alle woningen ({len(cur)})")
    lines.append("")
    lines.append("| Adres | Prijs | Kamers | m² | Label | URL |")
    lines.append("|---|---|---|---|---|---|")
    for it in current["items"]:
        lines.append(f"| {it['adres'][:50]} | €{it['prijs']} {it['prijs_type'] or ''} "
                     f"| {it['kamers'] or '?'} | {it['m2'] or '?'} | {it['energielabel'] or '?'} | {it['url']} |")

    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "latest.md").write_text("\n".join(lines), encoding="utf-8")
    (REPORTS / f"{current['date']}.md").write_text("\n".join(lines), encoding="utf-8")
    return REPORTS / "latest.md"


def main():
    p = argparse.ArgumentParser(description="Funda Watcher")
    p.add_argument("command", choices=["scan", "report"])
    p.add_argument("--plaats", default="Vlaardingen")
    p.add_argument("--min", type=int, default=None)
    p.add_argument("--max", type=int, default=None)
    args = p.parse_args()

    if args.command == "scan":
        items = fetch_listings(args.plaats, args.min, args.max)
        print(f"{len(items)} woningen opgehaald in {args.plaats}")
        snap = save_snapshot(items)
        print(f"Snapshot: {snap}")
        print(f"Rapport:  {make_report(snap)}")
    else:
        files = sorted(SNAPSHOTS.glob("*.json"), reverse=True)
        if not files:
            print("Nog geen snapshots. Draai eerst: python3 funda.py scan")
            return
        print(make_report(files[0]))


if __name__ == "__main__":
    main()
