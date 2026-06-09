#!/usr/bin/env python3
"""
update_fii_dii.py
Manually update FII/DII cash market data in Supabase.
Run daily after 6 PM when NSE publishes the data.

Usage: python3 update_fii_dii.py <fii_net> <dii_net>
Example: python3 update_fii_dii.py -4566 6159
"""
import sys, os, requests
from datetime import date

SUPABASE_URL = "https://kbklmidusxqkbjgpsdlg.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

if len(sys.argv) < 3:
    print("Usage: python3 update_fii_dii.py <fii_net_cr> <dii_net_cr>")
    sys.exit(1)

try:
    fii_net = float(sys.argv[1])
    dii_net = float(sys.argv[2])
except ValueError:
    print("Error: Please provide numbers"); sys.exit(1)

def fmt(val):
    sign = "+" if val >= 0 else ""
    return f"{sign}₹{abs(int(val)):,} Cr"

today = date.today().isoformat()
headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

# 1. Update market_pulse for Pulse tab display
requests.patch(
    f"{SUPABASE_URL}/rest/v1/market_pulse?date=gte.{today}T00:00:00Z",
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

# 2. Upsert into fii_dii_daily for weekly total calculation
requests.post(
    f"{SUPABASE_URL}/rest/v1/fii_dii_daily",
    headers={**headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
    json={"date": today, "fii_net": fii_net, "dii_net": dii_net},
    timeout=15
)

print(f"✓ Updated!")
print(f"  FII: {fmt(fii_net)} ({'Buying' if fii_net > 0 else 'Selling'})")
print(f"  DII: {fmt(dii_net)} ({'Buying' if dii_net > 0 else 'Selling'})")
