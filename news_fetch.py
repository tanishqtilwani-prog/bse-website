"""
news_fetch.py — Fetches news from Upstox for Nifty 750 companies
Run via pm2 cron every 30 minutes
"""
import os
import csv
import json
import time
import requests
from datetime import datetime

UPSTOX_TOKEN = os.environ.get("UPSTOX_TOKEN", "")
SUPABASE_URL = "https://kbklmidusxqkbjgpsdlg.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtia2xtaWR1c3hxa2JqZ3BzZGxnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MDExNTcxNywiZXhwIjoyMDk1NjkxNzE3fQ.v-gWV939rbNfNSXxzSbzaGduDXvxFhB8f_MHEp0wlFY"

HEADERS_UPSTOX = {
    "Authorization": f"Bearer {UPSTOX_TOKEN}",
    "Accept": "application/json"
}

HEADERS_SUPABASE = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=ignore-duplicates"
}

def load_instrument_keys():
    """Load NSE instrument keys from CSV — format: NSE_EQ|ISIN"""
    keys = {}
    try:
        with open("/home/ubuntu/bse-website/ind_niftytotalmarket_list.csv", "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                isin = row.get("ISIN Code", "").strip()
                symbol = row.get("Symbol", "").strip()
                company = row.get("Company Name", "").strip()
                if isin and symbol:
                    keys[f"NSE_EQ|{isin}"] = company
    except Exception as e:
        print(f"Error loading CSV: {e}")
    return keys

def fetch_news(instrument_keys_batch):
    """Fetch news for a batch of up to 30 instrument keys"""
    try:
        resp = requests.get(
            "https://api.upstox.com/v2/news",
            headers=HEADERS_UPSTOX,
            params={
                "category": "instrument_keys",
                "instrument_keys": ",".join(instrument_keys_batch)
            },
            timeout=15
        )
        if resp.status_code == 200:
            return resp.json().get("data", {})
    except Exception as e:
        print(f"News fetch error: {e}")
    return {}

def save_to_supabase(articles):
    """Save news articles to Supabase, ignoring duplicates"""
    if not articles:
        return 0
    try:
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/news",
            headers=HEADERS_SUPABASE,
            json=articles,
            timeout=15
        )
        if resp.status_code in (200, 201):
            return len(articles)
    except Exception as e:
        print(f"Supabase save error: {e}")
    return 0

def main():
    print(f"News fetch started at {datetime.now().strftime('%H:%M:%S')}")
    
    instrument_map = load_instrument_keys()
    print(f"Loaded {len(instrument_map)} instrument keys")
    
    all_keys = list(instrument_map.keys())
    total_saved = 0
    
    # Process in batches of 30 (Upstox limit)
    for i in range(0, len(all_keys), 30):
        batch = all_keys[i:i+30]
        news_data = fetch_news(batch)
        
        articles = []
        for key, items in news_data.items():
            company = instrument_map.get(key, "")
            for item in items:
                articles.append({
                    "instrument_key": key,
                    "company_name": company,
                    "heading": item.get("heading", ""),
                    "summary": item.get("summary", ""),
                    "article_link": item.get("article_link", ""),
                    "thumbnail": item.get("thumbnail", ""),
                    "published_at": None
                })
        
        saved = save_to_supabase(articles)
        total_saved += saved
        time.sleep(1)  # rate limit
    
    print(f"Done — saved {total_saved} new articles")

if __name__ == "__main__":
    main()
