import requests, os, json

UPSTOX_TOKEN = os.environ.get("UPSTOX_TOKEN", "")
HEADERS = {"Authorization": f"Bearer {UPSTOX_TOKEN}", "Accept": "application/json"}

indicator_keys = {
    "usdinr": "GLOBAL_INDICATOR|USDINR",
    "brent":  "GLOBAL_INDICATOR|BZUSD",
    "wti":    "GLOBAL_INDICATOR|CLUSD",
}

print("=== v2 LTP ===\n")
for label, key in indicator_keys.items():
    r = requests.get("https://api.upstox.com/v2/market-quote/ltp", headers=HEADERS, params={"instrument_key": key}, timeout=15)
    print(f"{label:8} | status={r.status_code} | {r.text[:200]}")

print("\n=== v2 FULL QUOTE ===\n")
for label, key in indicator_keys.items():
    r = requests.get("https://api.upstox.com/v2/market-quote/quotes", headers=HEADERS, params={"instrument_key": key}, timeout=15)
    print(f"{label:8} | status={r.status_code} | {r.text[:200]}")

print("\n=== CONFIRM CLEAN BATCH (10 indices + gold + silver, no indicators) ===\n")
clean_keys = ["GLOBAL_INDEX|SGX NIFTY","GLOBAL_INDEX|^DJI","GLOBAL_INDEX|DOW FUTURES",
              "GLOBAL_INDEX|^GSPC","GLOBAL_INDEX|IXIX","GLOBAL_INDEX|^GDAXI",
              "GLOBAL_INDEX|^FCHI","GLOBAL_INDEX|^FTSE","GLOBAL_INDEX|^HSI",
              "GLOBAL_INDEX|^N225","MCX_FO|466583","MCX_FO|464150"]
r = requests.get("https://api.upstox.com/v3/market-quote/ltp", headers=HEADERS,
                  params={"instrument_key": ",".join(clean_keys)}, timeout=20)
print("status:", r.status_code)
print(json.dumps(r.json(), indent=2)[:1500])
