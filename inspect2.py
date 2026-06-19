import requests, gzip, json
from datetime import datetime

def load(url):
    resp = requests.get(url, timeout=30)
    return json.loads(gzip.decompress(resp.content))

print("=== MCX GOLD / SILVER FUTURES ===\n")
mcx_data = load("https://assets.upstox.com/market-quote/instruments/exchange/MCX.json.gz")
matches = [i for i in mcx_data if i.get("instrument_type") == "FUT"
           and i.get("underlying_symbol","").upper() in ("GOLD", "SILVER")]

def expiry_str(item):
    exp = item.get("expiry")
    if isinstance(exp, (int, float)):
        ts = exp / 1000 if exp > 10**12 else exp
        return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
    return str(exp)

matches.sort(key=lambda x: x.get("expiry") or 0)
for item in matches:
    print(f"underlying={item.get('underlying_symbol'):8} | expiry={expiry_str(item):12} | trading_symbol={item.get('trading_symbol'):20} | key={item.get('instrument_key')}")
