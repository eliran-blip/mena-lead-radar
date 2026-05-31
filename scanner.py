"""
MENA Lead Radar — Daily Scanner v3
Uses multiple RSS feeds that work from GitHub Actions
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
TODAY        = datetime.utcnow().strftime("%Y-%m-%d")

# ── RSS feeds that work from GitHub servers ────────────────────
RSS_FEEDS = [
    # Arabian Business
    "https://www.arabianbusiness.com/rss",
    "https://www.arabianbusiness.com/rss/industries",
    # Gulf News
    "https://gulfnews.com/rss/business",
    "https://gulfnews.com/rss",
    # Zawya
    "https://www.zawya.com/rss/allstories",
    # Al Monitor Business
    "https://www.al-monitor.com/rss",
    # Middle East Eye
    "https://www.middleeasteye.net/rss",
    # BBC Business
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    # Financial Times
    "https://www.ft.com/rss/home",
    # Reuters
    "https://feeds.reuters.com/reuters/businessNews",
    # Bloomberg Middle East
    "https://www.bloomberg.com/feeds/bbiz/sitemap_news.xml",
    # MEED
    "https://www.meed.com/rss",
    # Trade Arabia
    "https://www.tradearabia.com/rss/NEWS.xml",
    # Saudi Gazette
    "https://saudigazette.com.sa/rss",
    # Khaleej Times
    "https://www.khaleejtimes.com/rss",
    # The National UAE
    "https://www.thenationalnews.com/rss",
]

MENA_KEYWORDS = [
    "saudi arabia", "uae", "united arab emirates", "dubai", "riyadh",
    "abu dhabi", "egypt", "jordan", "kuwait", "qatar", "bahrain",
    "oman", "gcc", "gulf", "mena", "middle east", "vision 2030",
    "neom", "expo", "gitex", "arab health",
]

BUSINESS_KEYWORDS = [
    "market entry", "expansion", "launch", "opens", "new office",
    "partnership", "distributor", "contract", "agreement", "deal",
    "investment", "funding", "joint venture", "appointed", "director",
    "ceo", "manager", "regulatory", "license", "approval",
    "exhibition", "expo", "conference", "award", "tender", "bid",
]

NEGATIVE_KEYWORDS = [
    "trump", "biden", "sanctions", "nuclear", "military", "war",
    "iran", "missile", "weapon", "army", "hamas", "hezbollah",
    "terror", "attack", "killed", "died", "death", "crisis",
    "protest", "riot", "conflict",
]

MARKET_WEIGHTS = {
    "saudi arabia": 15, "riyadh": 14, "uae": 14, "dubai": 13,
    "abu dhabi": 13, "united arab emirates": 14, "egypt": 12,
    "jordan": 11, "kuwait": 12, "qatar": 12, "bahrain": 11,
    "oman": 10, "gcc": 13, "gulf": 11, "mena": 12,
    "middle east": 11, "vision 2030": 15, "neom": 15,
}

SIGNAL_WEIGHTS = {
    "market entry": 25, "expansion": 18, "launch": 16,
    "opens": 15, "new office": 22, "partnership": 15,
    "distributor": 20, "contract": 14, "agreement": 15,
    "deal": 12, "investment": 12, "funding": 12,
    "joint venture": 20, "appointed": 16, "director": 10,
    "ceo": 12, "regulatory": 18, "license": 16,
    "approval": 15, "exhibition": 12, "tender": 14,
    "bid": 12, "award": 15, "first": 12,
}

def fetch_rss(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/rss+xml, application/xml, text/xml",
        }
        r = requests.get(url, timeout=12, headers=headers)
        if r.status_code != 200:
            return []

        text = r.text
        articles = []

        # Try CDATA format
        titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', text, re.DOTALL)
        links  = re.findall(r'<link><!\[CDATA\[(.*?)\]\]></link>', text, re.DOTALL)

        # Try plain format if CDATA empty
        if not titles:
            titles = re.findall(r'<title>(.*?)</title>', text, re.DOTALL)
            titles = [t for t in titles if len(t) > 10 and '<' not in t]

        if not links:
            links = re.findall(r'<link>(https?://[^<\s]+)</link>', text)

        descriptions = re.findall(r'<description><!\[CDATA\[(.*?)\]\]></description>', text, re.DOTALL)
        if not descriptions:
            descriptions = re.findall(r'<description>(.*?)</description>', text, re.DOTALL)

        source_name = url.split("/")[2].replace("www.", "").replace("feeds.", "")

        for i, title in enumerate(titles[1:20]):
            title = title.strip()
            if len(title) < 10:
                continue
            articles.append({
                "title":       title[:200],
                "description": descriptions[i].strip()[:300] if i < len(descriptions) else "",
                "url":         links[i] if i < len(links) else url,
                "source":      source_name,
                "published":   TODAY,
            })

        return articles

    except Exception as e:
        print(f"[WARN] RSS failed: {url.split('/')[2]} — {type(e).__name__}")
        return []

def score_article(article):
    text = (article["title"] + " " + article["description"]).lower()

    # Filter negative
    for neg in NEGATIVE_KEYWORDS:
        if neg in text:
            return None

    # Must mention MENA
    market_hit = None
    market_score = 0
    for market, weight in MARKET_WEIGHTS.items():
        if market in text:
            market_hit = market.title()
            market_score = weight
            break

    if not market_hit:
        return None

    # Must have business signal
    signal_score = 0
    signals_found = []
    for signal, weight in SIGNAL_WEIGHTS.items():
        if signal in text:
            signal_score += weight
            signals_found.append(signal)

    if signal_score < 10:
        return None

    total = min(99, market_score + signal_score)
    heat = "hot" if total >= 70 else "warm" if total >= 50 else "cold"

    companies = re.findall(r'\b([A-Z][a-zA-Z&]+(?:\s+[A-Z][a-zA-Z&]+){0,3})\b', article["title"])
    company = companies[0] if companies else "Unknown"

    url = article.get("url", "")
    entry = "AR"
    for ext, route in {".il": "IL", ".de": "EU", ".fr": "EU", ".nl": "EU",
                       ".se": "EU", ".ch": "EU", ".co.uk": "EU", ".it": "EU"}.items():
        if ext in url:
            entry = route
            break

    return {
        "date": TODAY, "company": company,
        "signal": article["title"][:120], "market": market_hit,
        "source": article["source"], "url": article["url"],
        "score": total, "heat": heat, "entry": entry,
        "signals": ", ".join(signals_found[:3]),
        "status": "new", "approved": "",
        "contact_name": "", "contact_role": "",
        "contact_email": "", "notes": "",
    }

def write_to_sheets(leads):
    if not GOOGLE_CREDS or not SHEET_ID:
        for l in leads[:10]:
            print(f"  {l['heat']:4} | {l['score']:3} | {l['company'][:25]:25} | {l['signal'][:60]}")
        return

    try:
        import json as jm
        creds = Credentials.from_service_account_info(
            jm.loads(GOOGLE_CREDS),
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        svc   = build("sheets", "v4", credentials=creds).spreadsheets()
        rows  = [[
            "תאריך","חברה","סיגנל","שוק יעד","מקור","קישור",
            "דירוג","חום","זרוע","סיגנלים","סטטוס",
            "אושר?","איש קשר","תפקיד","אימייל","הערות"
        ]]
        for l in leads:
            rows.append([
                l["date"],l["company"],l["signal"],l["market"],
                l["source"],l["url"],l["score"],l["heat"],
                l["entry"],l["signals"],l["status"],
                l["approved"],l["contact_name"],l["contact_role"],
                l["contact_email"],l["notes"]
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
    print(f"  MENA Lead Radar v3 — {TODAY}")
    print(f"  Sources: {len(RSS_FEEDS)} RSS feeds")
    print(f"{'='*60}\n")

    all_articles = []
    seen = set()

    for feed_url in RSS_FEEDS:
        articles = fetch_rss(feed_url)
        for a in articles:
            key = a["title"][:50]
            if key not in seen:
                seen.add(key)
                all_articles.append(a)
        time.sleep(0.3)

    print(f"[INFO] Total articles: {len(all_articles)}")

    leads = []
    for a in all_articles:
        scored = score_article(a)
        if scored:
            leads.append(scored)

    leads.sort(key=lambda x: x["score"], reverse=True)

    # Deduplicate
    seen2 = set()
    unique = []
    for l in leads:
        k = l["company"].lower()[:12] + l["market"].lower()[:8]
        if k not in seen2:
            seen2.add(k)
            unique.append(l)
    leads = unique

    print(f"[INFO] Leads after scoring+dedup: {len(leads)}")
    hot  = sum(1 for l in leads if l["heat"]=="hot")
    warm = sum(1 for l in leads if l["heat"]=="warm")
    cold = sum(1 for l in leads if l["heat"]=="cold")
    print(f"[RESULTS] Hot: {hot} | Warm: {warm} | Cold: {cold}")
    if leads:
        print(f"[RESULTS] Top: {leads[0]['company']} — {leads[0]['score']}")
        for l in leads[:5]:
            print(f"  {l['heat']:4} | {l['score']:3} | {l['company'][:25]:25} | {l['signal'][:55]}")

    write_to_sheets(leads)
    print("\n[DONE] Scan complete.\n")

if __name__ == "__main__":
    main()
