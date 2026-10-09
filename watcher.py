#!/usr/bin/env python3
"""MarketSpy - scant Marktplaats en 2dehands.be op Meta Quest 3 aanbiedingen.

Gebruik:
    python3 watcher.py scan [--photos]   # scan draaien
    python3 watcher.py report            # verloop-rapport t.o.v. vorige snapshot
"""

import argparse
import json
import re
import sys
import hashlib
from datetime import date, datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SNAPSHOTS = DATA / "snapshots"
REPORTS = DATA / "reports"
PHOTOS = DATA / "photos"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

MARKTPLAATS_API = "https://www.marktplaats.nl/lrp/api/search"
TWEEDEHANDS_API = "https://www.2dehands.be/lrp/api/search"


def load_config():
    with open(ROOT / "config.json") as f:
        return json.load(f)


def fetch_via_api(base_url, query, limit=100):
    """Probeer de JSON-zoek-API van Marktplaats/2dehands (zelfde Adevinta-stack)."""
    out = []
    for offset in range(0, limit, 30):
        try:
            r = requests.get(
                base_url,
                params={"query": query, "limit": 30, "offset": offset},
                headers={"User-Agent": UA},
                timeout=20,
            )
            if r.status_code != 200:
                break
            data = r.json()
        except (requests.RequestException, ValueError):
            break
        listings = data.get("listings", [])
        if not listings:
            break
        out.extend(listings)
    return out


def api_listing_to_item(l):
    price = l.get("price", 0) / 100 if isinstance(l.get("price"), int) else l.get("price")
    return {
        "id": str(l.get("itemId") or l.get("id") or ""),
        "title": l.get("title", "").strip(),
        "price": price,
        "currency": l.get("priceInfo", {}).get("priceType", ""),
        "condition": l.get("attributes", {}).get("condition", ""),
        "description": (l.get("description") or "")[:400],
        "city": l.get("location", {}).get("cityName", ""),
        "date": l.get("date", ""),
        "url": l.get("vipUrl") or l.get("url") or "",
        "images": [i.get("url") for i in (l.get("images") or []) if i.get("url")],
        "seller": l.get("seller", {}).get("name", ""),
    }


def fetch_via_html(url, query, max_pages=5):
    """Fallback: HTML ophalen en advertenties uit de pagina parsen."""
    items = []
    for page in range(1, max_pages + 1):
        try:
            r = requests.get(url, params={"query": query, "pageNumber": page},
                             headers={"User-Agent": UA}, timeout=20)
            if r.status_code != 200:
                break
        except requests.RequestException:
            break
        soup = BeautifulSoup(r.text, "html.parser")
        found = 0
        for a in soup.select("a[href*='/a/'], a[href*='/lp/']"):
            title_tag = a.select_one("h3, .hz-Listing-title")
            price_tag = a.select_one(".hz-Listing-price, [data-testid='listing-price']")
            if not title_tag:
                continue
            items.append({
                "id": hashlib.md5((title_tag.get_text(strip=True) + (r.url or "")).encode()).hexdigest()[:12],
                "title": title_tag.get_text(strip=True),
                "price": price_tag.get_text(strip=True) if price_tag else "onbekend",
                "description": "",
                "city": "",
                "date": "",
                "url": str(a.get("href", "")),
                "images": [],
                "seller": "",
                "_source_note": "html-fallback",
            })
            found += 1
        if found == 0:
            break
    return items


def is_quest_3(title, description=""):
    text = f"{title} {description}".lower()
    if "quest 3s" in text or "quest3s" in text or "3 s " in text:
        return False
    if "quest 2" in text or "quest 1" in text or "oculus quest 1" in text:
        return False
    return "quest 3" in text or "quest3" in text


def storage_gb(text):
    m = re.search(r"(\d{2,3})\s?(gb)", text.lower())
    return int(m.group(1)) if m else None


ACCESSOIRE_WOORDEN = [
    "elite strap", "head strap", "hoofdband", "hoofdtelefoon", "case", "tas",
    "draagtas", "kabel", "link cable", "dock", "oplaadstation", "batterij",
    "controller", "gezichtspad", "face pad", "cover", "lens",
]


def tel_accessoires(item):
    text = f"{item['title']} {item.get('description', '')}".lower()
    return sum(1 for w in ACCESSOIRE_WOORDEN if w in text)


def flag_item(item, config):
    flags = []
    text = f"{item['title']} {item['description']}".lower()
    price = item.get("price")

    if isinstance(price, (int, float)):
        if price < config.get("min_price_eur", 0):
            flags.append("PRIJS_OPMERKELIJK_LAAG")
        if price > config.get("max_price_eur", 10**9):
            flags.append("PRIJS_BOVEN_MAX")
    elif price in ("onbekend", None, ""):
        flags.append("GEEN_PRIJS")

    if "bieden" in text or "bied naar waarde" in text:
        flags.append("BIEDING")
    if not item.get("description"):
        flags.append("GEEN_BESCHRIJVING")
    if not item.get("images"):
        flags.append("GEEN_FOTOS")
    if storage_gb(text) is None:
        flags.append("OPSLAG_ONBEKEND")
    return flags


def filter_items(items, config):
    places = {p.lower() for p in config["places_within_reach"]}
    required = set(config.get("storage_required_gb", []))
    optional = set(config.get("storage_optional_gb", []))
    condities = {c.lower() for c in config.get("conditions", []) if c}
    alleen_vaste = config.get("alleen_vaste_prijs", False)
    min_acc = config.get("min_accessoires", 0)
    kept, rejected = [], []
    for it in items:
        if not is_quest_3(it["title"], it.get("description", "")):
            rejected.append((it, "geen quest 3 / 3s"))
            continue
        gb = storage_gb(f"{it['title']} {it.get('description','')}")
        if gb is not None and gb not in required | optional:
            rejected.append((it, f"opslag {gb}gb niet gewenst"))
            continue
        if condities:
            cond = (it.get("condition") or "").lower()
            if cond and not any(c in cond for c in condities):
                rejected.append((it, f"condite '{it.get('condition')}' niet gewenst"))
                continue
        if alleen_vaste and "bieden" in f"{it['title']} {it.get('description','')}".lower():
            rejected.append((it, "bieding i.p.v. vaste prijs"))
            continue
        if min_acc and tel_accessoires(it) < min_acc:
            rejected.append((it, f"minder dan {min_acc} accessoires"))
            continue
        city = (it.get("city") or "").lower()
        if places and city and city not in places:
            rejected.append((it, f"plaats {it.get('city')} buiten bereik"))
            continue
        it["flags"] = flag_item(it, config)
        kept.append(it)
    return kept, rejected


def download_photos(items):
    ok = 0
    for it in items:
        if not it.get("images"):
            continue
        folder = PHOTOS / it["id"]
        folder.mkdir(parents=True, exist_ok=True)
        for n, url in enumerate(it["images"][:6]):
            dest = folder / f"{n}.jpg"
            if dest.exists():
                continue
            try:
                r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
                if r.status_code == 200:
                    dest.write_bytes(r.content)
                    ok += 1
            except requests.RequestException:
                continue
    return ok


def save_snapshot(items, rejected):
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    snap = {
        "date": date.today().isoformat(),
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "items": items,
        "rejected_count": len(rejected),
    }
    path = SNAPSHOTS / f"{snap['date']}.json"
    if path.exists():
        path = SNAPSHOTS / f"{snap['date']}-{snap['fetched_at'].replace(':','')}.json"
    with open(path, "w") as f:
        json.dump(snap, f, indent=2, ensure_ascii=False)
    return path


def load_latest_snapshot(exclude=None):
    files = sorted(SNAPSHOTS.glob("*.json"), reverse=True)
    for p in files:
        if exclude and p.name == exclude.name:
            continue
        with open(p) as f:
            return json.load(f)
    return None


def make_report(current_path):
    with open(current_path) as f:
        current = json.load(f)
    prev = load_latest_snapshot(exclude=current_path)
    cur = {i["id"]: i for i in current["items"]}

    lines = [f"# Scan {current['fetched_at']}", ""]
    if prev:
        old = {i["id"]: i for i in prev["items"]}
        new_ids = [i for i in cur if i not in old]
        gone_ids = [i for i in old if i not in cur]
        changed = []
        for i in old:
            if i in cur:
                if old[i].get("price") != cur[i].get("price"):
                    changed.append((cur[i], old[i].get("price"), cur[i].get("price")))
                elif old[i].get("description") != cur[i].get("description"):
                    changed.append((cur[i], "tekst", "tekst gewijzigd"))
        lines.append(f"## Verloop t.o.v. {prev['fetched_at']}")
        lines.append("")
        if new_ids:
            lines.append(f"### Nieuw ({len(new_ids)})")
            for i in new_ids:
                it = cur[i]
                lines.append(f"- **{it['title']}** — {it.get('price')} — {it.get('city')} "
                             f"— {it.get('url','')} {(' FLAGS: ' + ', '.join(it['flags'])) if it.get('flags') else ''}")
            lines.append("")
        if gone_ids:
            lines.append(f"### Verdwenen / waarschijnlijk verkocht ({len(gone_ids)})")
            for i in gone_ids:
                it = old[i]
                lines.append(f"- {it['title']} — was {it.get('price')} — {it.get('city')}")
            lines.append("")
        if changed:
            lines.append(f"### Gewijzigd ({len(changed)})")
            for it, oldv, newv in changed:
                lines.append(f"- {it['title']}: {oldv} -> {newv} ({it.get('url','')})")
            lines.append("")
        if not (new_ids or gone_ids or changed):
            lines.append("Geen wijzigingen t.o.v. vorige scan.")
            lines.append("")
    else:
        lines.append("(Geen eerdere snapshot gevonden — dit is de eerste meting.)")
        lines.append("")

    lines.append(f"## Alle actuele advertenties ({len(cur)})")
    lines.append("")
    lines.append("| Titel | Prijs | Plaats | Datum | Flags | URL |")
    lines.append("|---|---|---|---|---|---|")
    for it in current["items"]:
        flags = ", ".join(it.get("flags", [])) or "—"
        lines.append(f"| {it['title'][:60]} | {it.get('price')} | {it.get('city','?')} "
                     f"| {it.get('date','?')} | {flags} | {it.get('url','')} |")

    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "latest.md").write_text("\n".join(lines), encoding="utf-8")
    (REPORTS / f"{current['date']}.md").write_text("\n".join(lines), encoding="utf-8")
    return REPORTS / "latest.md"


def cmd_scan(config, with_photos):
    query = config["search_query"]
    print(f"Scannen: {query}")
    raw = []
    raw += [api_listing_to_item(l) for l in fetch_via_api(MARKTPLAATS_API, query)]
    raw += [api_listing_to_item(l) for l in fetch_via_api(TWEEDEHANDS_API, query)]
    source = "api"
    if not raw:
        print("API gaf niets, HTML-fallback wordt gebruikt...")
        raw += fetch_via_html("https://www.marktplaats.nl/q/" + query.replace(" ", "+") + "/", query)
        raw += fetch_via_html("https://www.2dehands.be/q/" + query.replace(" ", "+") + "/", query)
        source = "html-fallback"
    print(f"{len(raw)} advertenties opgehaald ({source})")

    kept, rejected = filter_items(raw, config)
    print(f"{len(kept)} relevant na filtering ({len(rejected)} afgewezen)")
    for it, why in rejected[:10]:
        print(f"  - weg: {it['title'][:50]} ({why})")

    if with_photos and config.get("photo_download", True):
        n = download_photos(kept)
        print(f"{n} foto's gedownload naar {PHOTOS}")

    snap = save_snapshot(kept, rejected)
    print(f"Snapshot: {snap}")
    report = make_report(snap)
    print(f"Rapport:  {report}")
    print("Open data/reports/latest.md voor het overzicht.")


def cmd_report(_config):
    files = sorted(SNAPSHOTS.glob("*.json"), reverse=True)
    if not files:
        print("Nog geen snapshots. Draai eerst: python3 watcher.py scan")
        sys.exit(1)
    print(make_report(files[0]))


def main():
    parser = argparse.ArgumentParser(description="MarketSpy")
    parser.add_argument("command", choices=["scan", "report"])
    parser.add_argument("--photos", action="store_true", help="foto's downloaden")
    args = parser.parse_args()

    config = load_config()
    if args.command == "scan":
        cmd_scan(config, args.photos)
    else:
        cmd_report(config)


if __name__ == "__main__":
    main()
