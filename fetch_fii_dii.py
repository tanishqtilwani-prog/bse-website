#!/usr/bin/env python3
"""
fetch_fii_dii.py
Fetches FII/DII cash market data from NSE and updates Supabase.
Runs twice daily via pm2 cron (6 PM and 8 PM IST, weekdays):
  - If NSE has today's number, writes it under today's date.
  - If not yet published, carries forward yesterday's number as
    today's displayed value (overwritten automatically once the
    8 PM run finds the real number).
The weekly-total table (fii_dii_daily) is always keyed to NSE's
actual reported date, so nothing gets double-counted.
"""
import os, requests
from datetime import datetime, timedelta

SUPABASE_URL = "https://kbklmidusxqkbjgpsdlg.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

def fmt(val):
    sign = "+" if val >= 0 else ""
    return f"{sign}₹{abs(int(val)):,} Cr"

def fetch_nse_fii_dii():
    """Returns (data_date_iso, fii_net, dii_net) or (None, None, None) on failure."""
    try:
        s = requests.Session()
        s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        s.get("https://www.nseindia.com", timeout=10)
        r = s.get("https://www.nseindia.com/api/fiidiiTradeReact", timeout=10)
        if r.status_code != 200:
            print(f"NSE API error: {r.status_code}")
            return None, None, None
        rows = r.json()
        fii_net = dii_net = data_date = None
        for row in rows:
            cat = row.get("category", "")
            net = float(row.get("netValue", 0))
            d = row.get("date")
            if "FII" in cat:
                fii_net = net
                data_date = d
            elif cat == "DII":
                dii_net = net
                data_date = data_date or d
        if fii_net is None or dii_net is None or not data_date:
            print(f"Unexpected response shape: {rows}")
            return None, None, None
        return datetime.strptime(data_date, "%d-%b-%Y").date().isoformat(), fii_net, dii_net
    except Exception as e:
        print(f"NSE fetch error: {e}")
        return None, None, None

def main():
    data_date, fii_net, dii_net = fetch_nse_fii_dii()
    if data_date is None:
        print("✗ Could not fetch FII/DII data — leaving existing values untouched")
        return

    today_ist = (datetime.utcnow() + timedelta(hours=5, minutes=30)).date().isoformat()
    is_fresh = (data_date == today_ist)
    print(f"NSE data is for {data_date} ({'fresh — today' if is_fresh else 'carried forward'}): "
          f"FII {fmt(fii_net)}, DII {fmt(dii_net)}")

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    # 1. Always display under TODAY's date, whether fresh or carried forward
    next_day = (datetime.strptime(today_ist, "%Y-%m-%d").date() + timedelta(days=1)).isoformat()
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/market_pulse?date=gte.{today_ist}T00:00:00Z&date=lt.{next_day}T00:00:00Z",
        headers=headers,
        json={
            "fii_flow":    fmt(fii_net),
            "fii_verdict": "green" if fii_net > 0 else "red",
            "fii_label":   "Buying" if fii_net > 0 else "Selling",
            "dii_flow":    fmt(dii_net),
            "dii_verdict": "green" if dii_net > 0 else "red",
            "dii_label":   "Buying" if dii_net > 0 else "Selling",
        },
        timeout=15
    )

    # 2. Weekly-total table keyed to the REAL reported date - no double counting
    requests.post(
        f"{SUPABASE_URL}/rest/v1/fii_dii_daily",
        headers={**headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
        json={"date": data_date, "fii_net": fii_net, "dii_net": dii_net},
        timeout=15
    )

    print("✓ Saved to Supabase")

if __name__ == "__main__":
    main()
