"""
MENA Lead Radar — Daily Scanner v2
Uses Google News RSS (free, real-time) instead of NewsAPI
Outputs to Google Sheets automatically every day
"""

import os
import re
import time
import requests
from datetime import datetime, timedelta
from urllib.parse import quote
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ── Configuration ──────────────────────────────────────────────
SHEET_ID     = os.environ.get("GOOGLE_SHEET_ID", "")
GOOGLE_CREDS = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
TODAY        = datetime.utcnow().strftime("%Y-%m-%d")

# ── Google News RSS queries ────────────────────────────────────
QUERIES = [
    # Market entry
    "GCC market entry business",
    "Saudi Arabia business expansion new",
    "UAE market entry company",
    "MENA business development expansion",
    "Middle East market entry strategy",
    "Gulf business new company launch",
    # Jobs signals
    "MENA director business development hired",
    "GCC sales director appointed",
    "Middle East regional director new",
    "Saudi Arabia country manager appointed",
    # Partnerships
    "Gulf distributor partnership agreement",
    "MENA distribution agreement signed",
    "Saudi Arabia joint venture announced",
    "UAE partnership business signed",
    # Regulatory
    "Saudi Arabia regulatory approval company",
    "UAE business license foreign company",
    "SFDA approval new company",
    # Exhibitions
    "GITEX 2025 company exhibitor",
    "Arab Health 2025 participant",
    "Big 5 Dubai 2025 company",
    # Sectors
    "technology company Saudi Arabia launch",
    "healthcare UAE expansion new",
    "cybersecurity GCC contract",
    "renewable energy Saudi Arabia project",
    "NEOM contract company",
    "Egypt business foreign company",
    "Jordan market entry company",
    "Kuwait business expansion",
    "Qatar business development new",
    "Bahrain company launch",
    "Oman business new",
]

# ── Negative keywords — filter out political noise ─────────────
NEGATIVE_KEYWORDS = [
    "trump", "biden", "sanctions", "nuclear", "military",
    "war", "iran", "missile", "weapon", "army", "political",
    "election", "vote", "congress", "senate", "parliament",
    "hamas", "hezbollah", "terror", "attack", "killed",
]

# ── Signal weights ─────────────────────────────────────────────
SIGNAL_WEIGHTS = {
    "market entry": 25, "first": 15, "expansion": 18,
    "new office": 22, "distributor": 20, "partner": 12,
    "regulatory": 18, "launch": 16, "hiring": 14,
    "director": 10, "agreement": 15, "contract": 14,
    "exhibition": 12, "gitex": 15, "arab health": 15,
    "big 5": 12, "funding": 10, "investment": 10,
    "vision 2030": 18, "neom": 20, "appointed": 16,
    "signed": 14, "awarded": 16, "opens": 15,
}

MARKET_WEIGHTS = {
    "saudi arabia": 15, "uae": 14, "united arab emirates": 14,
    "egypt": 12, "jordan": 11, "kuwait": 12,
    "qatar": 12, "bahrain": 11, "oman": 10,
    "gcc": 13, "gulf": 11, "mena": 12,
}

ENTRY_ROUTES = {
    ".il": "IL", ".de": "EU", ".fr": "EU", ".nl": "EU",
    ".se": "EU", ".fi": "EU", ".ch": "EU", ".co.uk": "EU",
    ".it": "EU", ".es": "EU", ".be": "EU", ".at": "EU",
    ".com": "AR", ".cn": "AR", ".jp": "AR",
}

# ── Fetch Google News RSS ──────────────────────────────────────
def fetch_google_news():
    articles = []
    seen = set()

    for query in QUERIES:
        try:
            encoded = quote(query)
            url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
            r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                continue

            # Parse titles and links
            titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', r.text)
            links  = re.findall(r'<link>(https?://[^<]+)</link>', r.text)
            dates  = re.findall(r'<pubDate>(.*?)</pubDate>', r.text)

            for i, title in enumerate(titles[1:16]):  # skip first (feed title)
                if title in seen:
                    continue
                seen.add(title)
                articles.append({
                    "title":       title,
                    "description": title,
                    "url":         links[i+1] if i+1 < len(links) else "",
                    "source":      "Google News",
                    "published":   dates[i][:16] if i < len(dates) else TODAY,
                    "query":       query,
                })

            time.sleep(0.5)

        except Exception as e:
            print(f"[WARN] Query failed: {query} — {e}")

    print(f"[INFO] Fetched {len(articles)} articles from Google News RSS")
    return articles

# ── Score article ──────────────────────────────────────────────
def score_article(article):
    text = (article["title"] + " " + article["description"]).lower()

    # Filter negative keywords
    for neg in NEGATIVE_KEYWORDS:
        if neg in text:
            return None

    # Must mention target market
    market_hit = None
    market_score = 0
    for market, weight in MARKET_WEIGHTS.items():
        if market in text:
            market_hit = market.title()
            market_score = weight
            break

    if not market_hit:
        return None

    # Signal score
    signal_score = 0
    signals_found = []
    for signal, weight in SIGNAL_WEIGHTS.items():
        if signal in text:
            signal_score += weight
            signals_found.append(signal)

    if signal_score < 8:
        return None

    total = min(99, market_score + signal_score)

    heat = "hot" if total >= 70 else "warm" if total >= 50 else "cold"

    # Extract company name
    companies = re.findall(r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})\b', article["title"])
    company = companies[0] if companies else "Unknown"

    # Entry route
    url = article.get("url", "")
    entry = "AR"
    for ext, route in ENTRY_ROUTES.items():
        if ext in url:
            entry = route
            break

    return {
        "date":          TODAY,
        "company":       company,
        "signal":        article["title"][:120],
        "market":        market_hit,
        "source":        article["source"],
        "url":           article["url"],
        "score":         total,
        "heat":          heat,
        "entry":         entry,
        "signals":       ", ".join(signals_found[:3]),
        "status":        "new",
        "approved":      "",
        "contact_name":  "",
        "contact_role":  "",
        "contact_email": "",
        "notes":         "",
    }

# ── Deduplicate ────────────────────────────────────────────────
def deduplicate(leads):
    seen = set()
    unique = []
    for l in leads:
        key = l["company"].lower()[:15] + l["market"].lower()[:8]
        if key not in seen:
            seen.add(key)
            unique.append(l)
    return unique

# ── Write to Google Sheets ─────────────────────────────────────
def write_to_sheets(leads):
    if not GOOGLE_CREDS or not SHEET_ID:
        print("[WARN] Google Sheets not configured")
        for l in leads[:10]:
            print(f"  {l['heat']:4} | {l['score']:3} | {l['company'][:30]:30} | {l['signal'][:60]}")
        return

    try:
        import json as json_mod
        creds_dict = json_mod.loads(GOOGLE_CREDS)
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build("sheets", "v4", credentials=creds)
        sheet   = service.spreadsheets()

        headers = [
            "תאריך", "חברה", "סיגנל", "שוק יעד", "מקור", "קישור",
            "דירוג", "חום", "זרוע", "סיגנלים", "סטטוס",
            "אושר?", "איש קשר", "תפקיד", "אימייל", "הערות"
        ]

        rows = [headers]
        for l in leads:
            rows.append([
                l["date"], l["company"], l["signal"], l["market"],
                l["source"], l["url"], l["score"], l["heat"],
                l["entry"], l["signals"], l["status"],
                l["approved"], l["contact_name"], l["contact_role"],
                l["contact_email"], l["notes"]
            ])

        # Try different sheet name formats
        for range_name in ["A1", "Sheet1!A1", "גיליון1!A1"]:
            try:
                sheet.values().update(
                    spreadsheetId=SHEET_ID,
                    range=range_name,
                    valueInputOption="RAW",
                    body={"values": rows}
                ).execute()
                print(f"[OK] Written {len(leads)} leads to Google Sheet")
                return
            except Exception:
                continue

        print("[ERROR] Could not write to any sheet range")

    except Exception as e:
        print(f"[ERROR] Google Sheets write failed: {e}")
        for l in leads[:10]:
            print(f"  {l['heat']:4} | {l['score']:3} | {l['company'][:30]:30} | {l['signal'][:60]}")

# ── Main ───────────────────────────────────────────────────────
def main():
    print(f"\n{'='*60}")
    print(f"  MENA Lead Radar v2 — {TODAY}")
    print(f"  Source: Google News RSS (free, real-time)")
    print(f"{'='*60}\n")

    articles = fetch_google_news()
    print(f"[INFO] Total articles: {len(articles)}")

    leads = []
    for article in articles:
        scored = score_article(article)
        if scored:
            leads.append(scored)

    print(f"[INFO] Leads after scoring: {len(leads)}")
    leads.sort(key=lambda x: x["score"], reverse=True)
    leads = deduplicate(leads)
    print(f"[INFO] Leads after dedup: {len(leads)}")

    hot  = sum(1 for l in leads if l["heat"] == "hot")
    warm = sum(1 for l in leads if l["heat"] == "warm")
    cold = sum(1 for l in leads if l["heat"] == "cold")
    print(f"\n[RESULTS] Hot: {hot} | Warm: {warm} | Cold: {cold}")
    if leads:
        print(f"[RESULTS] Top lead: {leads[0]['company']} — score {leads[0]['score']}\n")

    write_to_sheets(leads)
    print("\n[DONE] Scan complete.\n")

if __name__ == "__main__":
    main()
