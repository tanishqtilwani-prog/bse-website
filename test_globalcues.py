#!/usr/bin/env python3
"""
global_cues.py
Fetches the global markets watchlist (indices, currency, commodities)
and stores it in Supabase. Runs 3x daily via pm2 cron: 8AM/17:00/00:00 IST.

Sources:
- Upstox (one batched LTP call): GIFT Nifty, Dow Jones, S&P 500, DAX,
  Nikkei 225, Gold (MCX), Silver (MCX)
- Yahoo Finance: USD/INR, Brent Crude, WTI Crude, Kospi, USD Index
"""

import os, json, gzip, requests
from datetime import datetime

SUPABASE_URL = "https://kbklmidusxqkbjgpsdlg.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
UPSTOX_TOKEN = os.environ.get("UPSTOX_TOKEN", "")

UPSTOX_HEADERS = {"Authorization": f"Bearer {UPSTOX_TOKEN}", "Accept": "application/json"}
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

UPSTOX_KEYS = {
    "gift_nifty": "GLOBAL_INDEX|SGX NIFTY",
    "dow_jones":  "GLOBAL_INDEX|^DJI",
    "sp500":      "GLOBAL_INDEX|^GSPC",
    "dax":        "GLOBAL_INDEX|^GDAXI",
    "nikkei225":  "GLOBAL_INDEX|^N225",
}

YAHOO_TICKERS = {
    "usdinr":    "INR=X",
    "brent":     "BZ=F",
    "wti":       "CL=F",
    "kospi":     "^KS11",
    "usd_index": "DX-Y.NYB",
}

def get_mcx_gold_silver_keys():
    """Gold/Silver MCX futures roll over monthly - always resolve nearest expiry."""
    try:
        r = requests.get("https://assets.upstox.com/market-quote/instruments/exchange/MCX.json.gz", timeout=30)
        data = json.loads(gzip.decompress(r.content))
        out = {}
        for metal in ("GOLD", "SILVER"):
            items = [i for i in data if i.get("instrument_type") == "FUT"
                     and i.get("underlying_symbol", "").upper() == metal]
            items.sort(key=lambda x: x.get("expiry") or 0)
            if items:
                out[metal.lower()] = items[0]["instrument_key"]
        return out
    except Exception as e:
        print(f"MCX key resolution error: {e}")
        return {}

def fetch_upstox_batch(keys):
    if not keys:
        return {}
    joined = ",".join(keys.values())
    try:
        r = requests.get("https://api.upstox.com/v3/market-quote/ltp",
                          headers=UPSTOX_HEADERS, params={"instrument_key": joined}, timeout=20)
        if r.status_code != 200:
            print(f"Upstox batch error {r.status_code}: {r.text[:300]}")
            return {}
        payload = r.json().get("data", {})
    except Exception as e:
        print(f"Upstox batch exception: {e}")
        return {}

    out = {}
    for label, key in keys.items():
        item = next((v for v in payload.values() if v.get("instrument_token") == key), None)
        if item:
            price, prev = item.get("last_price"), item.get("cp")
            pct = round((price - prev) / prev * 100, 2) if price and prev else None
            out[label] = {"price": price, "pct_change": pct}
        else:
            out[label] = {"price": None, "pct_change": None}
    return out

def fetch_yahoo(ticker):
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
                          headers=YAHOO_HEADERS, timeout=15)
        meta = r.json()["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice")
        prev = meta.get("previousClose") or meta.get("chartPreviousClose")
        pct = round((price - prev) / prev * 100, 2) if price and prev else None
        return {"price": price, "pct_change": pct}
    except Exception as e:
        print(f"Yahoo error ({ticker}): {e}")
        return {"price": None, "pct_change": None}

def supabase_upsert(table, record):
    try:
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                     "Content-Type": "application/json", "Prefer": "return=minimal"},
            json=record, timeout=15
        )
        print(f"{'✓ Saved' if resp.status_code in (200,201) else '✗ Error ' + str(resp.status_code)}: {resp.text[:200]}")
    except Exception as e:
        print(f"✗ Supabase exception: {e}")

def main():
    print(f"\n── Global cues collection — {datetime.utcnow().isoformat()} ──")

    mcx_keys = get_mcx_gold_silver_keys()
    upstox_data = fetch_upstox_batch({**UPSTOX_KEYS, **mcx_keys})
    yahoo_data = {label: fetch_yahoo(ticker) for label, ticker in YAHOO_TICKERS.items()}

    record = {"date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}
    for label, d in {**upstox_data, **yahoo_data}.items():
        record[label] = d.get("price")
        record[f"{label}_pct"] = d.get("pct_change")

    for k, v in record.items():
        print(f"  {k}: {v}")

    supabase_upsert("global_cues", record)

if __name__ == "__main__":
    main()
