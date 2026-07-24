"""
fundamentals_fetch.py — Fetches fundamentals from Upstox for Nifty 750 companies
Run via pm2 cron once daily at 8 PM
"""
import os
import csv
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
    "Prefer": "resolution=merge-duplicates"
}

def load_companies():
    companies = []
    try:
        with open("/home/ubuntu/bse-website/ind_niftytotalmarket_list.csv", "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                isin = row.get("ISIN Code", "").strip()
                company = row.get("Company Name", "").strip()
                if isin and company:
                    companies.append({"isin": isin, "company": company})
    except Exception as e:
        print(f"Error loading CSV: {e}")
    return companies

def fetch_fundamentals(isin):
    try:
        resp = requests.get(
            f"https://api.upstox.com/v2/fundamentals/{isin}/income-statement",
            headers=HEADERS_UPSTOX,
            params={"type": "consolidated", "time_period": "yearly"},
            timeout=15
        )
        if resp.status_code == 200:
            return resp.json().get("data", {})
        elif resp.status_code == 404:
            # Try standalone if consolidated not available
            resp2 = requests.get(
                f"https://api.upstox.com/v2/fundamentals/{isin}/income-statement",
                headers=HEADERS_UPSTOX,
                params={"type": "standalone", "time_period": "yearly"},
                timeout=15
            )
            if resp2.status_code == 200:
                return resp2.json().get("data", {})
    except Exception as e:
        print(f"Fundamentals fetch error for {isin}: {e}")
    return {}

def parse_fundamentals(isin, company, data):
    records = []
    if not data or "income_statement" not in data:
        return records

    units = data.get("units_in", "crore")
    statements = {item["category"]: item["history"] for item in data["income_statement"]}

    revenue_hist = statements.get("revenue", [])
    op_profit_hist = statements.get("operating_profit", [])
    net_profit_hist = statements.get("net_profit", [])

    for i, rev in enumerate(revenue_hist):
        period = rev.get("period", "")
        records.append({
            "isin": isin,
            "company_name": company,
            "period": period,
            "revenue": rev.get("value"),
            "operating_profit": op_profit_hist[i]["value"] if i < len(op_profit_hist) else None,
            "net_profit": net_profit_hist[i]["value"] if i < len(net_profit_hist) else None,
            "units_in": units,
            "updated_at": datetime.utcnow().isoformat()
        })
    return records

def save_to_supabase(records):
    if not records:
        return 0
    try:
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/fundamentals",
            headers=HEADERS_SUPABASE,
            json=records,
            timeout=15
        )
        if resp.status_code in (200, 201):
            return len(records)
    except Exception as e:
        print(f"Supabase save error: {e}")
    return 0

def main():
    print(f"Fundamentals fetch started at {datetime.now().strftime('%H:%M:%S')}")
    companies = load_companies()
    print(f"Processing {len(companies)} companies...")

    total = 0
    errors = 0

    for i, c in enumerate(companies):
        data = fetch_fundamentals(c["isin"])
        if data:
            records = parse_fundamentals(c["isin"], c["company"], data)
            saved = save_to_supabase(records)
            total += saved
        else:
            errors += 1

        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(companies)} done, {errors} errors...")

        time.sleep(1.2)  # stay within rate limits

    print(f"Done — saved {total} records, {errors} errors")

if __name__ == "__main__":
    main()
