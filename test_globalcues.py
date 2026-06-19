import requests, os, json

UPSTOX_TOKEN = os.environ.get("UPSTOX_TOKEN", "")
HEADERS = {"Authorization": f"Bearer {UPSTOX_TOKEN}", "Accept": "application/json"}

test_keys = {
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
    "gold":       "MCX_FO|466583",
    "silver":     "MCX_FO|464150",
}

url = "https://api.upstox.com/v3/market-quote/ltp"

print("=== ONE AT A TIME (using proper encoding) ===\n")
for label, key in test_keys.items():
    r = requests.get(url, headers=HEADERS, params={"instrument_key": key}, timeout=15)
    print(f"{label:12} | {key:28} | status={r.status_code} | {r.text[:200]}")

print("\n=== ALL TOGETHER IN ONE BATCH ===\n")
joined = ",".join(test_keys.values())
r = requests.get(url, headers=HEADERS, params={"instrument_key": joined}, timeout=20)
print("status:", r.status_code)
print(json.dumps(r.json(), indent=2))
