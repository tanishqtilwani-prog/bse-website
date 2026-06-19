import requests, gzip, json, os
from datetime import datetime

UPSTOX_TOKEN = os.environ.get("UPSTOX_TOKEN", "")
HEADERS = {"Authorization": f"Bearer {UPSTOX_TOKEN}", "Accept": "application/json"}

GLOBAL_KEYS = {
    "gift_nifty": "GLOBAL_INDEX|SGX NIFTY",
    "dow_jones":  "GLOBAL_INDEX|^DJI",
    "us30":       "GLOBAL_INDEX|DOW FUTURES",
    "sp500":      "GLOBAL_INDEX|^GSPC",
    "nasdaq":     "GLOBAL_INDEX|IXIX",
    "dax":        "GLOBAL_INDEX|^GDAXI",
    "cac40":      "GLOBAL_INDEX|^FCHI",
    "ftse100":    "GLOBAL_INDEX|^FTSE",
    "hangseng":   "GLOBAL_INDEX|^HSI",
    "nikkei225":  "GLOBAL_INDEX|^N225",
    "usdinr":     "GLOBAL_INDICATOR|USDINR",
    "brent":      "GLOBAL_INDICATOR|BZUSD",
    "wti":        "GLOBAL_INDICATOR|CLUSD",
}

def get_mcx_gold_silver_keys():
    r = requests.get("https://assets.upstox.com/market-quote/instruments/exchange/MCX.json.gz", timeout=30)
    data = json.loads(gzip.decompress(r.content))
    out = {}
    for metal in ("GOLD", "SILVER"):
        items = [i for i in data if i.get("instrument_type") == "FUT" and i.get("underlying_symbol","").upper() == metal]
        items.sort(key=lambda x: x.get("expiry") or 0)
        if items:
            out[metal.lower()] = items[0]["instrument_key"]
    return out

print("Resolving current MCX gold/silver contracts...")
mcx_keys = get_mcx_gold_silver_keys()
print(mcx_keys, "\n")

all_keys = {**GLOBAL_KEYS, **mcx_keys}
joined = ",".join(all_keys.values())
url = f"https://api.upstox.com/v3/market-quote/ltp?instrument_key={joined}"
r = requests.get(url, headers=HEADERS, timeout=20)
print("HTTP status:", r.status_code)
payload = r.json()
print("\n=== RAW UPSTOX RESPONSE ===")
print(json.dumps(payload, indent=2))

print("\n=== KOSPI + USD INDEX (Yahoo) ===")
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
for label, ticker in [("kospi", "^KS11"), ("usd_index", "DX-Y.NYB")]:
    try:
        yr = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}", headers=YAHOO_HEADERS, timeout=15)
        meta = yr.json()["chart"]["result"][0]["meta"]
        print(label, "->", {"price": meta.get("regularMarketPrice"), "prev_close": meta.get("previousClose") or meta.get("chartPreviousClose")})
    except Exception as e:
        print(label, "-> ERROR", e, yr.status_code if 'yr' in dir() else '')
