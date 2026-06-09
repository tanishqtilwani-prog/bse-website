#!/usr/bin/env python3
"""
update_fii_dii.py
Manually update FII/DII cash market data in Supabase.
Run daily after 6 PM when NSE publishes the data.

Usage: python3 update_fii_dii.py <fii_net> <dii_net>
Example: python3 update_fii_dii.py -1500 2200
         python3 update_fii_dii.py +3200 -800

Get data from: https://www.nseindia.com/market-data/securities-available-for-trading
Or: moneycontrol.com / investing.com FII DII section
"""
import sys, os, requests
from datetime import datetime, date

SUPABASE_URL = "https://kbklmidusxqkbjgpsdlg.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

if len(sys.argv) < 3:
    print("Usage: python3 update_fii_dii.py <fii_net_cr> <dii_net_cr>")
    print("Example: python3 update_fii_dii.py -1500 2200")
    sys.exit(1)

try:
    fii_net = float(sys.argv[1])
    dii_net = float(sys.argv[2])
except ValueError:
    print("Error: Please provide numbers for FII and DII net values in Crores")
    sys.exit(1)

def fmt(val):
    sign = "+" if val >= 0 else ""
    return f"{sign}₹{abs(int(val)):,} Cr"

fii_str     = fmt(fii_net)
dii_str     = fmt(dii_net)
fii_verdict = "green" if fii_net > 0 else "red"
dii_verdict = "green" if dii_net > 0 else "red"
fii_label   = "Buying" if fii_net > 0 else "Selling"
dii_label   = "Buying" if dii_net > 0 else "Selling"

today = date.today().isoformat()

resp = requests.patch(
    f"{SUPABASE_URL}/rest/v1/market_pulse?date=gte.{today}T00:00:00Z",
    headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    },
    json={
        "fii_flow":    fii_str,
        "fii_verdict": fii_verdict,
        "fii_label":   fii_label,
        "dii_flow":    dii_str,
        "dii_verdict": dii_verdict,
        "dii_label":   dii_label,
    },
    timeout=15
)

if resp.status_code in (200, 204):
    print(f"✓ Updated successfully!")
    print(f"  FII: {fii_str} ({fii_label})")
    print(f"  DII: {dii_str} ({dii_label})")
else:
    print(f"✗ Failed: {resp.status_code} {resp.text}")
