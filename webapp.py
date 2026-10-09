#!/usr/bin/env python3
"""Lokale webinterface voor MarketSpy.

Start:
    python3 webapp.py
Open daarna: http://127.0.0.1:5001

Je kunt hier zoekqueries aanmaken met jouw kwalificaties, ze bewaren,
aanpassen (scherpen) en direct een scan mee draaien.
"""

import json
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for

import watcher

ROOT = Path(__file__).resolve().parent
QUERIES = ROOT / "data" / "queries.json"
INBOX = ROOT / "data" / "inbox"

app = Flask(__name__)


def load_queries():
    if QUERIES.exists():
        return json.loads(QUERIES.read_text())
    return []


def save_queries(queries):
    QUERIES.parent.mkdir(parents=True, exist_ok=True)
    QUERIES.write_text(json.dumps(queries, indent=2, ensure_ascii=False))


def form_to_query(form):
    places = [p.strip() for p in form.get("places", "").split(",") if p.strip()]
    return {
        "id": form.get("id") or datetime.now().strftime("%Y%m%d%H%M%S"),
        "naam": form.get("naam", "").strip() or "naamloos",
        "zoekterm": form.get("zoekterm", "meta quest 3").strip(),
        "opslag_voorkeur": [int(g) for g in form.getlist("opslag_voorkeur")],
        "opslag_optioneel": [int(g) for g in form.getlist("opslag_optioneel")],
        "condities": form.getlist("condities"),
        "min_prijs": int(form.get("min_prijs") or 0),
        "max_prijs": int(form.get("max_prijs") or 0),
        "alleen_vaste_prijs": "alleen_vaste_prijs" in form,
        "min_accessoires": int(form.get("min_accessoires") or 0),
        "plaatsen": places,
        "fotos_downloaden": "fotos_downloaden" in form,
        "aangemaakt": datetime.now().isoformat(timespec="seconds"),
        "laatst_gescand": None,
    }


@app.post("/inbox")
def inbox():
    payload = request.get_json(silent=True)
    if not payload:
        return {"ok": False, "error": "geen json"}, 400
    INBOX.mkdir(parents=True, exist_ok=True)
    ad_id = payload.get("ad_number") or datetime.now().strftime("%Y%m%d%H%M%S")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = INBOX / f"{ad_id}-{ts}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return {"ok": True, "opgeslagen": str(path)}


@app.get("/inbox")
def inbox_overzicht():
    items = []
    if INBOX.exists():
        for p in sorted(INBOX.glob("*.json"), reverse=True):
            d = json.loads(p.read_text())
            items.append({
                "bestand": p.name,
                "ad_nummer": d.get("ad_number"),
                "titel": d.get("title"),
                "prijs": d.get("price"),
                "conditie": d.get("condition"),
                "plaats": d.get("place"),
                "verkoper": (d.get("seller") or {}).get("name"),
                "reviews": (d.get("seller") or {}).get("reviews"),
                "fotos": len(d.get("photos") or []),
                "url": d.get("url"),
                "verzonden": d.get("captured_at"),
            })
    return render_template("inbox.html", items=items)


@app.get("/")
def index():
    queries = load_queries()
    bewerk = None
    qid = request.args.get("bewerk")
    if qid:
        bewerk = next((q for q in queries if q["id"] == qid), None)
    report = None
    report_path = watcher.REPORTS / "latest.md"
    if report_path.exists():
        report = report_path.read_text()
    return render_template("index.html", queries=queries, report=report, bewerk=bewerk)


@app.post("/opslaan")
def opslaan():
    queries = load_queries()
    q = form_to_query(request.form)
    if not request.form.get("id"):
        bestaat = next((x for x in queries if x["naam"] == q["naam"]), None)
        if bestaat:
            q["id"] = bestaat["id"]
    existing = next((i for i, x in enumerate(queries) if x["id"] == q["id"]), None)
    if existing is not None:
        q["aangemaakt"] = queries[existing]["aangemaakt"]
        q["laatst_gescand"] = queries[existing].get("laatst_gescand")
        queries[existing] = q
    else:
        queries.append(q)
    save_queries(queries)
    return redirect(url_for("index"))


@app.post("/verwijder/<qid>")
def verwijder(qid):
    queries = [q for q in load_queries() if q["id"] != qid]
    save_queries(queries)
    return redirect(url_for("index"))


@app.post("/scan/<qid>")
def scan(qid):
    queries = load_queries()
    q = next((x for x in queries if x["id"] == qid), None)
    if not q:
        return redirect(url_for("index"))

    config = {
        "search_query": q["zoekterm"],
        "places_within_reach": q["plaatsen"],
        "storage_required_gb": q["opslag_voorkeur"],
        "storage_optional_gb": q["opslag_optioneel"],
        "conditions": q["condities"],
        "min_price_eur": q["min_prijs"],
        "max_price_eur": q["max_prijs"],
        "photo_download": q["fotos_downloaden"],
        "alleen_vaste_prijs": q["alleen_vaste_prijs"],
        "min_accessoires": q["min_accessoires"],
    }
    watcher.cmd_scan(config, with_photos=q["fotos_downloaden"])

    q["laatst_gescand"] = datetime.now().isoformat(timespec="seconds")
    save_queries(queries)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)
