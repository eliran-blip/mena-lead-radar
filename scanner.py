"""
MENA Lead Radar — Daily Scanner
Scans news sources for companies with MENA/GCC market entry signals
Outputs to Google Sheets automatically every day
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ── Configuration ──────────────────────────────────────────────
NEWS_API_KEY    = os.environ.get("NEWS_API_KEY", "")
SHEET_ID        = os.environ.get("GOOGLE_SHEET_ID", "")
GOOGLE_CREDS    = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")

TODAY           = datetime.utcnow().strftime("%Y-%m-%d")
YESTERDAY       = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

# ── Target countries ───────────────────────────────────────────
TARGET_MARKETS = [
    "Saudi Arabia", "UAE", "United Arab Emirates",
    "Jordan", "Egypt", "Kuwait", "Qatar", "Bahrain", "Oman"
]

# ── Search queries — early-signal focused ──────────────────────
QUERIES = [
    # Market entry intent
    "expand market Saudi Arabia business",
    "expand market UAE business development",
    "expand market Egypt Jordan business",
    "GCC market entry strategy",
    "Gulf market expansion 2025",
    "MENA market entry first",
    "Middle East business development new",
    # Job signals
    "hiring MENA director business development",
    "GCC sales director job appointed",
    "Middle East regional director new role",
    # Regulatory / first steps
    "Saudi Arabia regulatory approval new",
    "UAE market launch first",
    "Egypt business license foreign company",
    # Partnerships / distributors
    "Gulf distributor partner agreement signed",
    "MENA distribution partnership announced",
    "Saudi Arabia joint venture new",
    # Exhibitions / events
    "GITEX 2025 exhibitor new",
    "Arab Health 2025 participant",
    "Big 5 Dubai 2025 company",
    # Funding with MENA intent
    "funding round MENA expansion",
    "investment Middle East expansion plan",
    # Sectors
    "technology company Saudi Arabia launch",
    "healthcare company UAE expansion",
    "food company Egypt market",
    "cybersecurity GCC new contract",
    "renewable energy Saudi Arabia project",
    "construction company NEOM contract",
]

# ── Scoring weights ────────────────────────────────────────────
SIGNAL_WEIGHTS = {
    "market entry":      25,
    "first":             20,
    "expansion":         18,
    "new office":        22,
    "distributor":       20,
    "partner":           15,
    "regulatory":        18,
    "launch":            16,
    "hiring":            14,
    "director":          12,
    "agreement":         15,
    "contract":          14,
    "exhibition":        12,
    "gitex":             15,
    "arab health":       15,
    "big 5":             12,
    "funding":           10,
    "investment":        10,
    "vision 2030":       18,
    "neom":              20,
}

MARKET_WEIGHTS = {
    "saudi arabia": 15, "uae": 14, "united arab emirates": 14,
    "egypt": 12, "jordan": 11, "kuwait": 12,
    "qatar": 12, "bahrain": 11, "oman": 10,
}

# Entry route logic — based on company origin
ENTRY_ROUTES = {
    "Israel": "IL", "Germany": "EU", "France": "EU",
    "Netherlands": "EU", "Sweden": "EU", "Finland": "EU",
    "Switzerland": "EU", "UK": "EU", "Italy": "EU",
    "Spain": "EU", "Belgium": "EU", "Austria": "EU",
    "USA": "AR", "China": "AR", "Japan": "AR",
    "India": "AR", "South Korea": "AR",
}

KNOWN_COUNTRIES = {
    ".il": "Israel", ".de": "Germany", ".fr": "France",
    ".nl": "Netherlands", ".se": "Sweden", ".fi": "Finland",
    ".ch": "Switzerland", ".co.uk": "UK", ".it": "Italy",
    ".es": "Spain", ".be": "Belgium", ".at": "Austria",
    ".com": "USA", ".cn": "China", ".jp": "Japan",
}

# ── Fetch news ─────────────────────────────────────────────────
def fetch_news():
    articles = []
    seen_urls = set()

    for query in QUERIES:
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                "q":          query,
                "from":       YESTERDAY,
                "to":         TODAY,
                "language":   "en",
                "sortBy":     "relevancy",
                "pageSize":   10,
                "apiKey":     NEWS_API_KEY,
            }
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                for a in data.get("articles", []):
                    u = a.get("url", "")
                    if u and u not in seen_urls:
                        seen_urls.add(u)
                        articles.append({
                            "title":       a.get("title", ""),
                            "description": a.get("description", "") or "",
                            "url":         u,
                            "source":      a.get("source", {}).get("name", ""),
                            "published":   a.get("publishedAt", "")[:10],
                            "query":       query,
                        })
            time.sleep(0.3)  # rate limit respect
        except Exception as e:
            print(f"[WARN] Query failed: {query} — {e}")

    print(f"[INFO] Fetched {len(articles)} raw articles")
    return articles

# ── Also fetch via free RSS feeds ─────────────────────────────
def fetch_rss_feeds():
    feeds = [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://rss.ft.com/rss/time/business",
        "https://www.arabianbusiness.com/rss",
        "https://gulfnews.com/rss",
    ]
    articles = []
    for feed in feeds:
        try:
            r = requests.get(feed, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                import re
                titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', r.text)
                links  = re.findall(r'<link>(https?://[^<]+)</link>', r.text)
                for i, title in enumerate(titles[:15]):
                    articles.append({
                        "title":       title,
                        "description": "",
                        "url":         links[i] if i < len(links) else "",
                        "source":      feed.split("/")[2],
                        "published":   TODAY,
                        "query":       "rss",
                    })
        except Exception as e:
            print(f"[WARN] RSS failed: {feed} — {e}")
    print(f"[INFO] RSS fetched {len(articles)} items")
    return articles

# ── Score an article ───────────────────────────────────────────
def score_article(article):
    text = (article["title"] + " " + article["description"]).lower()

    # Must mention at least one target market
    market_hit = None
    market_score = 0
    for market, country in [
        ("saudi arabia", "Saudi Arabia"), ("uae", "UAE"),
        ("united arab emirates", "UAE"), ("jordan", "Jordan"),
        ("egypt", "Egypt"), ("kuwait", "Kuwait"),
        ("qatar", "Qatar"), ("bahrain", "Bahrain"), ("oman", "Oman"),
        ("gcc", "GCC"), ("gulf", "Gulf"), ("mena", "MENA"),
        ("middle east", "Middle East"),
    ]:
        if market in text:
            market_hit = country
            market_score += MARKET_WEIGHTS.get(market, 8)
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

    if signal_score < 10:
        return None

    total = min(99, market_score + signal_score)

    # Heat classification
    if total >= 75:
        heat = "hot"
    elif total >= 55:
        heat = "warm"
    else:
        heat = "cold"

    # Extract company name (first capitalized phrase before verb)
    import re
    companies = re.findall(r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})\b', article["title"])
    company = companies[0] if companies else "Unknown"

    # Guess entry route from URL
    url = article.get("url", "")
    entry = "EU"
    for ext, country_name in KNOWN_COUNTRIES.items():
        if ext in url:
            entry = ENTRY_ROUTES.get(country_name, "AR")
            break

    return {
        "date":         TODAY,
        "company":      company,
        "signal":       article["title"][:120],
        "market":       market_hit,
        "source":       article["source"],
        "url":          article["url"],
        "score":        total,
        "heat":         heat,
        "entry":        entry,
        "signals":      ", ".join(signals_found[:3]),
        "status":       "new",
        "approved":     "",
        "contact_name": "",
        "contact_role": "",
        "contact_email":"",
        "notes":        "",
    }

# ── Deduplicate leads ──────────────────────────────────────────
def deduplicate(leads):
    seen = set()
    unique = []
    for l in leads:
        key = l["company"].lower()[:15] + l["market"].lower()[:10]
        if key not in seen:
            seen.add(key)
            unique.append(l)
    return unique

# ── Write to Google Sheets ─────────────────────────────────────
def write_to_sheets(leads):
    if not GOOGLE_CREDS or not SHEET_ID:
        print("[WARN] Google Sheets not configured — printing to console instead")
        for l in leads[:5]:
            print(f"  {l['heat'].upper():4} | {l['score']:3} | {l['company'][:30]:30} | {l['market']:15} | {l['signal'][:60]}")
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

        # Header row
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

        # Write to sheet named by today's date
        tab_name = f"סריקה {TODAY}"
        try:
            sheet.values().update(
                spreadsheetId=SHEET_ID,
                range=f"'{tab_name}'!A1",
                valueInputOption="RAW",
                body={"values": rows}
            ).execute()
        except Exception:
            sheet.values().update(
                spreadsheetId=SHEET_ID,
                range="Sheet1!A1",
                valueInputOption="RAW",
                body={"values": rows}
            ).execute()

        print(f"[OK] Written {len(leads)} leads to Google Sheet")

    except Exception as e:
        print(f"[ERROR] Google Sheets write failed: {e}")
        for l in leads[:10]:
            print(f"  {l['heat']:4} | {l['score']:3} | {l['company'][:30]:30} | {l['signal'][:60]}")

# ── Main ───────────────────────────────────────────────────────
def main():
    print(f"\n{'='*60}")
    print(f"  MENA Lead Radar — {TODAY}")
    print(f"{'='*60}\n")

    # Fetch
    news_articles = fetch_news() if NEWS_API_KEY else []
    rss_articles  = fetch_rss_feeds()
    all_articles  = news_articles + rss_articles

    print(f"[INFO] Total raw articles: {len(all_articles)}")

    # Score
    leads = []
    for article in all_articles:
        scored = score_article(article)
        if scored:
            leads.append(scored)

    print(f"[INFO] Leads after scoring: {len(leads)}")

    # Sort by score descending
    leads.sort(key=lambda x: x["score"], reverse=True)

    # Deduplicate
    leads = deduplicate(leads)
    print(f"[INFO] Leads after dedup: {len(leads)}")

    # Stats
    hot  = sum(1 for l in leads if l["heat"] == "hot")
    warm = sum(1 for l in leads if l["heat"] == "warm")
    cold = sum(1 for l in leads if l["heat"] == "cold")
    print(f"\n[RESULTS] Hot: {hot} | Warm: {warm} | Cold: {cold}")
    print(f"[RESULTS] Top lead: {leads[0]['company']} — score {leads[0]['score']}\n")

    # Write
    write_to_sheets(leads)
    print("\n[DONE] Scan complete.\n")

if __name__ == "__main__":
    main()
