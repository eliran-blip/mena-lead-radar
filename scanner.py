"""
MENA Lead Radar — Daily Scanner v4
Uses SerpAPI Google News (real-time, reliable)
"""

import os
import re
import time
import requests
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SHEET_ID     = os.environ.get("GOOGLE_SHEET_ID", "")
GOOGLE_CREDS = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
SERP_API_KEY = os.environ.get("SERP_API_KEY", "")
TODAY        = datetime.utcnow().strftime("%Y-%m-%d")

# ── Search queries ─────────────────────────────────────────────
QUERIES = [
    "GCC market entry business expansion",
    "Saudi Arabia business expansion new company",
    "UAE market entry new company launch",
    "MENA business development expansion",
    "Middle East market entry strategy company",
    "Gulf distributor partnership agreement",
    "Saudi Arabia joint venture company",
    "UAE partnership business signed",
    "MENA director appointed business",
    "GCC sales director new role",
    "Saudi Arabia regulatory approval company",
    "NEOM contract company awarded",
    "GITEX 2025 company exhibitor",
    "Arab Health 2025 company",
    "Egypt business foreign company expansion",
    "Jordan market entry company",
    "Kuwait business expansion new",
    "Qatar business development company",
    "Oman business new company",
    "Bahrain company launch expansion",
]

NEGATIVE_KEYWORDS = [
    "trump", "biden", "sanctions", "nuclear", "military", "war",
    "iran", "missile", "weapon", "hamas", "hezbollah", "terror",
    "attack", "killed", "died", "crisis", "protest", "conflict",
]

MARKET_WEIGHTS = {
    "saudi arabia": 15, "riyadh": 13, "uae": 14, "dubai": 13,
    "abu dhabi": 13, "egypt": 12, "jordan": 11, "kuwait": 12,
    "qatar": 12, "bahrain": 11, "oman": 10, "gcc": 13,
    "gulf": 11, "mena": 12, "middle east": 11,
    "vision 2030": 15, "neom": 15,
}

SIGNAL_WEIGHTS = {
    "market entry": 25, "expansion": 18, "launch": 16,
    "opens": 15, "new office": 22, "partnership": 15,
    "distributor": 20, "contract": 14, "agreement": 15,
    "deal": 12, "investment": 12, "funding": 12,
    "joint venture": 20, "appointed": 16, "director": 10,
    "regulatory": 18, "license": 16, "approval": 15,
    "exhibition": 12, "tender": 14, "award": 15, "first": 12,
    "signed": 14, "new": 8,
}

def fetch_serp_news():
    articles = []
    seen = set()

    for query in QUERIES:
        try:
            params = {
                "engine": "google_news",
                "q": query,
                "api_key": SERP_API_KEY,
                "hl": "en",
                "gl": "us",
            }
            r = requests.get("https://serpapi.com/search", params=params, timeout=15)
            if r.status_code != 200:
                print(f"[WARN] SerpAPI error {r.status_code} for: {query}")
                continue

            data = r.json()
            news_results = data.get("news_results", [])

            for item in news_results[:5]:
                title = item.get("title", "")
                if not title or title in seen:
                    continue
                seen.add(title)

                articles.append({
                    "title":       title,
                    "description": item.get("snippet", ""),
                    "url":         item.get("link", ""),
                    "source":      item.get("source", {}).get("name", "Google News") if isinstance(item.get("source"), dict) else str(item.get("source", "Google News")),
                    "published":   item.get("date", TODAY),
                })

            time.sleep(0.5)

        except Exception as e:
            print(f"[WARN] Query failed: {query[:30]} — {e}")

    print(f"[INFO] Fetched {len(articles)} articles from SerpAPI")
    return articles

def score_article(article):
    text = (article["title"] + " " + article["description"]).lower()

    for neg in NEGATIVE_KEYWORDS:
        if neg in text:
            return None

    market_hit = None
    market_score = 0
    for market, weight in MARKET_WEIGHTS.items():
        if market in text:
            market_hit = market.title()
            market_score = weight
            break

    if not market_hit:
        return None

    signal_score = 0
    signals_found = []
    for signal, weight in SIGNAL_WEIGHTS.items():
        if signal in text:
            signal_score += weight
            signals_found.append(signal)

    if signal_score < 8:
        return None

    total = min(99, market_score + signal_score)
    heat = "hot" if total >= 55 else "warm" if total >= 35 else "cold"

    companies = re.findall(r'\b([A-Z][a-zA-Z&]+(?:\s+[A-Z][a-zA-Z&]+){0,3})\b', article["title"])
    company = companies[0] if companies else "Unknown"

    url = article.get("url", "")
    entry = "AR"
    for ext, route in {".il": "IL", ".de": "EU", ".fr": "EU",
                       ".nl": "EU", ".se": "EU", ".ch": "EU",
                       ".co.uk": "EU", ".it": "EU"}.items():
        if ext in url:
            entry = route
            break

    return {
        "date": TODAY, "company": company,
        "signal": article["title"][:120],
        "market": market_hit,
        "source": article["source"],
        "url": article["url"],
        "score": total, "heat": heat, "entry": entry,
        "signals": ", ".join(signals_found[:3]),
        "status": "new", "approved": "",
        "contact_name": "", "contact_role": "",
        "contact_email": "", "notes": "",
    }

def write_to_sheets(leads):
    if not GOOGLE_CREDS or not SHEET_ID:
        for l in leads[:10]:
            print(f"  {l['heat']:4} | {l['score']:3} | {l['company'][:25]:25} | {l['signal'][:55]}")
        return

    try:
        import json as jm
        creds = Credentials.from_service_account_info(
            jm.loads(GOOGLE_CREDS),
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        svc = build("sheets", "v4", credentials=creds).spreadsheets()
        rows = [[
            "תאריך", "חברה", "סיגנל", "שוק יעד", "מקור", "קישור",
            "דירוג", "חום", "זרוע", "סיגנלים", "סטטוס",
            "אושר?", "איש קשר", "תפקיד", "אימייל", "הערות"
        ]]
        for l in leads:
            rows.append([
                l["date"], l["company"], l["signal"], l["market"],
                l["source"], l["url"], l["score"], l["heat"],
                l["entry"], l["signals"], l["status"],
                l["approved"], l["contact_name"], l["contact_role"],
                l["contact_email"], l["notes"]
            ])

        for rng in ["A1", "Sheet1!A1", "גיליון1!A1"]:
            try:
                svc.values().update(
                    spreadsheetId=SHEET_ID, range=rng,
                    valueInputOption="RAW", body={"values": rows}
                ).execute()
                print(f"[OK] Written {len(leads)} leads to Google Sheet")
                return
            except Exception:
                continue
        print("[ERROR] Could not write to sheet")

    except Exception as e:
        print(f"[ERROR] Sheets failed: {e}")

def main():
    print(f"\n{'='*60}")
    print(f"  MENA Lead Radar v4 — {TODAY}")
    print(f"  Source: SerpAPI Google News")
    print(f"{'='*60}\n")

    if not SERP_API_KEY:
        print("[ERROR] SERP_API_KEY not set")
        return

    articles = fetch_serp_news()
    print(f"[INFO] Total articles: {len(articles)}")

    leads = []
    for a in articles:
        scored = score_article(a)
        if scored:
            leads.append(scored)

    leads.sort(key=lambda x: x["score"], reverse=True)

    seen = set()
    unique = []
    for l in leads:
        k = l["company"].lower()[:12] + l["market"].lower()[:8]
        if k not in seen:
            seen.add(k)
            unique.append(l)
    leads = unique

    print(f"[INFO] Leads after scoring+dedup: {len(leads)}")
    hot  = sum(1 for l in leads if l["heat"] == "hot")
    warm = sum(1 for l in leads if l["heat"] == "warm")
    cold = sum(1 for l in leads if l["heat"] == "cold")
    print(f"[RESULTS] Hot: {hot} | Warm: {warm} | Cold: {cold}")
    for l in leads[:5]:
        print(f"  {l['heat']:4} | {l['score']:3} | {l['company'][:25]:25} | {l['signal'][:55]}")

    write_to_sheets(leads)
    print("\n[DONE] Scan complete.\n")

if __name__ == "__main__":
    main()
