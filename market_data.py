#!/usr/bin/env python3
"""
market_data.py v3
Uses Upstox API for all price/index data instead of NSE scraping.
Runs twice: 10 AM (morning) and 4:30 PM (evening) IST on weekdays.
"""

import os, json, time, csv, re, requests
from datetime import datetime, date, timedelta
from bse import BSE

# ── CONFIG ────────────────────────────────────────────────────────────
SUPABASE_URL   = "https://kbklmidusxqkbjgpsdlg.supabase.co"
SUPABASE_KEY   = os.environ.get("SUPABASE_SERVICE_KEY", "")
UPSTOX_TOKEN   = os.environ.get("UPSTOX_TOKEN", "")
CSV_CLASSIFIED = "/home/ubuntu/bse-website/ind_nifty750_classified.csv"
BSE_DL         = "/tmp/bse_data"
RUN_MODE       = os.environ.get("RUN_MODE", "evening")

UPSTOX_HEADERS = {
    "Authorization": f"Bearer {UPSTOX_TOKEN}",
    "Accept": "application/json"
}

# ── SUPABASE ──────────────────────────────────────────────────────────
def supabase_upsert(table, record):
    try:
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal"
            },
            json=record, timeout=15
        )
        return resp.status_code in (200, 201)
    except Exception as e:
        print(f"✗ Supabase upsert error {table}: {e}")
        return False

def supabase_select(table, params=""):
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}?{params}",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
            timeout=15
        )
        return resp.json() if resp.status_code == 200 else []
    except Exception as e:
        print(f"✗ Supabase select error: {e}")
        return []

# ── LOAD COMPANIES ────────────────────────────────────────────────────
def load_companies():
    companies = {}  # symbol -> {name, sector, isin}
    sectors   = {}  # sector -> [symbols]
    try:
        with open(CSV_CLASSIFIED, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                symbol = row.get('Symbol', '').strip()
                name   = row.get('Company Name', '').strip()
                sector = row.get('Sector', '').strip()
                isin   = row.get('ISIN Code', '').strip()
                if symbol and sector and isin and 'Dummy' not in name:
                    companies[symbol] = {'name': name, 'sector': sector, 'isin': isin}
                    sectors.setdefault(sector, []).append(symbol)
        print(f"Loaded {len(companies)} companies across {len(sectors)} sectors")
    except Exception as e:
        print(f"CSV load error: {e}")
    return companies, sectors

# ── UPSTOX API ────────────────────────────────────────────────────────
def upstox_get(url, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, headers=UPSTOX_HEADERS, timeout=15)
            if r.status_code == 200:
                return r.json()
            print(f"Upstox {r.status_code}: {url[:80]}, retry {i+1}")
            time.sleep(1)
        except Exception as e:
            print(f"Upstox error: {e}, retry {i+1}")
            time.sleep(1)
    return None

def fetch_stock_history(isin, from_date, to_date):
    """Fetch daily OHLCV history for a stock via Upstox"""
    url = f"https://api.upstox.com/v2/historical-candle/NSE_EQ|{isin}/day/{to_date}/{from_date}"
    data = upstox_get(url)
    if data and 'data' in data:
        return data['data'].get('candles', [])
    return []

def fetch_index_history(index_name, from_date, to_date):
    """Fetch daily OHLCV history for an index via Upstox"""
    url = f"https://api.upstox.com/v2/historical-candle/NSE_INDEX|{index_name}/day/{to_date}/{from_date}"
    data = upstox_get(url)
    if data and 'data' in data:
        return data['data'].get('candles', [])
    return []

def fetch_index_quote(index_name):
    """Fetch current quote for an index"""
    url = f"https://api.upstox.com/v2/market-quote/quotes?instrument_key=NSE_INDEX|{index_name}"
    data = upstox_get(url)
    if data and 'data' in data:
        key = f"NSE_INDEX:{index_name}"
        return data['data'].get(key, {})
    return {}

# ── TECHNICAL INDICATORS ──────────────────────────────────────────────
def calc_rsi(closes, period=14):
    """closes: oldest first"""
    if len(closes) < period + 1:
        return None
    gains = []; losses = []
    for i in range(1, period + 1):
        diff = closes[-(period + 1 - i + 1)] - closes[-(period + 1 - i + 2)] if len(closes) > period else 0
        diff = closes[i] - closes[i-1]
        if diff > 0: gains.append(diff)
        else: losses.append(abs(diff))
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0.0001
    return round(100 - (100 / (1 + avg_gain / avg_loss)), 1)

def calc_rsi_from_candles(candles):
    """candles: newest first [date, o, h, l, c, v, oi]"""
    closes = [c[4] for c in reversed(candles)]  # oldest first
    return calc_rsi(closes)

def calc_volume_ratio(candles):
    """Current volume vs 20-day average. candles: newest first"""
    if len(candles) < 2: return None
    current_vol = candles[0][5]
    avg_vol = sum(c[5] for c in candles[1:21]) / min(20, len(candles)-1)
    return round(current_vol / avg_vol, 2) if avg_vol > 0 else None

def calc_weekly_change(candles):
    """Weekly % change. candles: newest first"""
    if len(candles) < 6: return None
    return round(((candles[0][4] - candles[5][4]) / candles[5][4]) * 100, 2)

def calc_monthly_change(candles):
    """Monthly % change. candles: newest first"""
    if len(candles) < 22: return None
    return round(((candles[0][4] - candles[21][4]) / candles[21][4]) * 100, 2)

def calc_dist_52w_high(candles):
    """Distance from 52-week high"""
    if not candles: return None
    current = candles[0][4]
    high_52w = max(c[2] for c in candles[:252])  # high prices
    return round(((current - high_52w) / high_52w) * 100, 2)

def calc_dma_crossover(candles, short=20, long=50):
    """1 if 20DMA > 50DMA, -1 if below, 0 if insufficient"""
    closes = [c[4] for c in reversed(candles)]  # oldest first
    if len(closes) < long: return 0
    dma_short = sum(closes[-short:]) / short
    dma_long  = sum(closes[-long:]) / long
    return 1 if dma_short > dma_long else -1

# ── STORE PRICE HISTORY ───────────────────────────────────────────────
def store_price_history(symbol, sector, candles):
    """Store candles in price_history table"""
    stored = 0
    for c in candles:
        dt = c[0][:10]  # just date part
        record = {
            'date':        dt,
            'symbol':      symbol,
            'sector':      sector,
            'close_price': c[4],
            'prev_close':  None,
            'volume':      c[5],
            'high_52w':    None,
            'low_52w':     None,
            'pct_change':  None,
        }
        if supabase_upsert('price_history', record):
            stored += 1
    return stored

# ── FETCH ALL STOCK PRICES ────────────────────────────────────────────
def collect_price_history(companies):
    """Fetch last 60 days OHLCV for all 750 stocks via Upstox"""
    print("\n── Collecting Price History via Upstox ──")
    to_date   = date.today().strftime('%Y-%m-%d')
    from_date = (date.today() - timedelta(days=90)).strftime('%Y-%m-%d')
    
    total_stored = 0
    failed = 0
    
    for i, (symbol, info) in enumerate(companies.items()):
        try:
            candles = fetch_stock_history(info['isin'], from_date, to_date)
            if candles:
                stored = store_price_history(symbol, info['sector'], candles)
                total_stored += stored
            else:
                failed += 1
            
            if (i + 1) % 50 == 0:
                print(f"  Progress: {i+1}/{len(companies)} stocks, {total_stored} records stored")
            
            time.sleep(0.1)  # rate limit
        except Exception as e:
            print(f"  Error {symbol}: {e}")
            failed += 1
    
    print(f"✓ Price history: {total_stored} records stored, {failed} failed")

# ── SECTOR METRICS ────────────────────────────────────────────────────
def calculate_sector_metrics(sectors, companies):
    """Calculate sector metrics from price_history in Supabase"""
    sector_metrics = {}
    
    # Get Nifty 100 weekly change as benchmark
    nifty_candles = fetch_index_history('Nifty 100',
        (date.today() - timedelta(days=30)).strftime('%Y-%m-%d'),
        date.today().strftime('%Y-%m-%d'))
    nifty_weekly = calc_weekly_change(nifty_candles) or 0

    for sector, symbols in sectors.items():
        all_weekly=[]; all_monthly=[]; all_rsi=[]
        all_vol_ratio=[]; all_dist_52w=[]; all_dma=[]

        for symbol in symbols:
            rows = supabase_select('price_history',
                f"symbol=eq.{symbol}&order=date.desc&limit=60&select=close_price,volume")
            if len(rows) < 5: continue

            closes  = [r['close_price'] for r in rows if r['close_price']]
            volumes = [r['volume'] for r in rows if r['volume']]

            if len(closes) >= 6:
                w = ((closes[0] - closes[5]) / closes[5]) * 100
                all_weekly.append(w)
            if len(closes) >= 22:
                m = ((closes[0] - closes[21]) / closes[21]) * 100
                all_monthly.append(m)
            if len(closes) >= 15:
                rsi = calc_rsi(list(reversed(closes)))
                if rsi: all_rsi.append(rsi)
            if len(volumes) >= 5:
                avg_v = sum(volumes[1:21]) / min(20, len(volumes)-1)
                if avg_v > 0: all_vol_ratio.append(volumes[0] / avg_v)
            if len(closes) >= 52:
                h52 = max(closes[:52])
                if h52 > 0: all_dist_52w.append(((closes[0] - h52) / h52) * 100)
            if len(closes) >= 50:
                dma20 = sum(closes[:20]) / 20
                dma50 = sum(closes[:50]) / 50
                all_dma.append(1 if dma20 > dma50 else -1)

        if not all_weekly: continue

        avg_weekly  = sum(all_weekly) / len(all_weekly)
        avg_monthly = sum(all_monthly) / len(all_monthly) if all_monthly else avg_weekly * 4

        sector_metrics[sector] = {
            'weekly_change_pct':      round(avg_weekly, 2),
            'monthly_change_pct':     round(avg_monthly, 2),
            'weekly_change_vs_nifty': round(avg_weekly - nifty_weekly, 2),
            'rsi':         round(sum(all_rsi)/len(all_rsi), 1) if all_rsi else None,
            'volume_ratio':round(sum(all_vol_ratio)/len(all_vol_ratio), 2) if all_vol_ratio else None,
            'dist_52w':    round(sum(all_dist_52w)/len(all_dist_52w), 2) if all_dist_52w else None,
            'dma_crossover':round(sum(all_dma)/len(all_dma), 2) if all_dma else 0,
        }
        m = sector_metrics[sector]
        print(f"  {sector}: weekly={m['weekly_change_pct']}% vs_nifty={m['weekly_change_vs_nifty']}% rsi={m['rsi']}")

    return sector_metrics

def fetch_order_wins_by_sector(companies):
    sector_orders = {}
    try:
        month_start = date.today().replace(day=1).isoformat()
        rows = supabase_select('posts', f"category=eq.order_win&date=gte.{month_start}T00:00:00Z&select=company_name")
        name_to_sector = {info['name'].lower(): info['sector'] for info in companies.values()}
        for row in rows:
            cname = (row.get('company_name') or '').lower().strip()
            sector = name_to_sector.get(cname)
            if sector:
                sector_orders[sector] = sector_orders.get(sector, 0) + 1
        print(f"Order wins this month: {sum(sector_orders.values())}")
    except Exception as e:
        print(f"Order wins error: {e}")
    return sector_orders

def compute_sector_score(metrics, orders, bulk=0):
    scores = {}; weights = {}

    vs_nifty = metrics.get('weekly_change_vs_nifty', 0) or 0
    scores['rs']  = min(100, max(0, 50 + vs_nifty * 8));  weights['rs']  = 0.20

    weekly  = metrics.get('weekly_change_pct', 0) or 0
    monthly = metrics.get('monthly_change_pct', 0) or 0
    scores['mom'] = min(100, max(0, 50 + (weekly*0.6 + monthly*0.4)*4)); weights['mom'] = 0.15

    dist = metrics.get('dist_52w', 0) or 0
    scores['dist'] = min(100, max(0, 100 + dist*2)); weights['dist'] = 0.10

    scores['orders'] = min(100, orders * 8); weights['orders'] = 0.10
    scores['bulk']   = min(100, bulk * 15);  weights['bulk']   = 0.05

    rsi = metrics.get('rsi')
    if rsi is not None:
        scores['rsi'] = rsi; weights['rsi'] = 0.15

    vol = metrics.get('volume_ratio')
    if vol is not None:
        scores['vol'] = min(100, max(0, vol * 40)); weights['vol'] = 0.15

    dma = metrics.get('dma_crossover', 0)
    if dma != 0:
        scores['dma'] = 75 if dma > 0 else 25; weights['dma'] = 0.10

    total_w = sum(weights.values())
    return round(sum(scores[k] * weights[k] / total_w for k in scores), 1)

# ── PULSE VIA UPSTOX ──────────────────────────────────────────────────
def fetch_vix_upstox():
    q = fetch_index_quote('India VIX')
    if q and 'ohlc' in q:
        val = q['ohlc'].get('close', 0)
        val = round(float(val), 2)
        verdict = "green" if val < 15 else ("amber" if val < 20 else "red")
        label   = "Calm" if val < 15 else ("Elevated" if val < 20 else "Fearful")
        return str(val), verdict, label
    return None, "gray", "N/A"

def fetch_nifty100_vs_200dma():
    candles = fetch_index_history('Nifty 100',
        (date.today() - timedelta(days=300)).strftime('%Y-%m-%d'),
        date.today().strftime('%Y-%m-%d'))
    if len(candles) >= 200:
        closes  = [c[4] for c in reversed(candles)]
        dma200  = sum(closes[-200:]) / 200
        current = closes[-1]
        above   = current > dma200
        diff    = round(((current - dma200) / dma200) * 100, 1)
        verdict = "green" if above else "red"
        label   = f"{'Above' if above else 'Below'} by {abs(diff)}%"
        return "Above 200 DMA" if above else "Below 200 DMA", verdict, label
    elif candles:
        closes  = [c[4] for c in reversed(candles)]
        dma     = sum(closes) / len(closes)
        current = closes[-1]
        above   = current > dma
        verdict = "green" if above else "red"
        return "Above DMA" if above else "Below DMA", verdict, f"{len(candles)}-day DMA proxy"
    return None, "gray", "N/A"

def fetch_breadth_upstox(sectors, companies):
    """% of stocks above their average close using price_history"""
    try:
        # Get latest close for each stock
        rows = supabase_select('price_history',
            'order=date.desc&limit=50000&select=symbol,close_price,date')
        seen = {}
        for r in rows:
            sym = r['symbol']
            if sym not in seen:
                seen[sym] = []
            if len(seen[sym]) < 60:
                seen[sym].append(r['close_price'] or 0)
        above = 0; total = 0
        for sym, closes in seen.items():
            if len(closes) >= 10:
                dma = sum(closes[1:]) / (len(closes) - 1)
                if closes[0] > dma: above += 1
                total += 1
        if total > 0:
            pct     = round((above / total) * 100, 1)
            verdict = "green" if pct > 65 else ("red" if pct < 40 else "amber")
            label   = "Broad" if pct > 65 else ("Narrow" if pct < 40 else "Moderate")
            print(f"Breadth: {pct}% ({above}/{total} stocks above avg)")
            return pct, verdict, label
    except Exception as e:
        print(f"Breadth error: {e}")
    return None, "gray", "N/A"

def fetch_fii_dii_bse():
    """FII/DII — BSE library method unavailable, return empty for now"""
    return None, "gray", "N/A", None, "gray", "N/A"

# ── MAIN COLLECTORS ───────────────────────────────────────────────────
def collect_sectors(sectors, companies):
    print("\n── Collecting Sector data ──")
    today = date.today().isoformat()
    sector_metrics = calculate_sector_metrics(sectors, companies)
    order_wins     = fetch_order_wins_by_sector(companies)
    vix_val, _, _  = fetch_vix_upstox()
    try: vix_num = float(vix_val) if vix_val else None
    except: vix_num = None

    for sector in sectors.keys():
        metrics = sector_metrics.get(sector, {})
        orders  = order_wins.get(sector, 0)
        score   = compute_sector_score(metrics, orders) if metrics else 50.0
        supabase_upsert("sector_heatmap", {
            "date": today, "sector": sector, "score": score,
            "weekly_change_pct":      metrics.get("weekly_change_pct"),
            "monthly_change_pct":     metrics.get("monthly_change_pct"),
            "weekly_change_vs_nifty": metrics.get("weekly_change_vs_nifty"),
            "rsi":          metrics.get("rsi"),
            "breadth_pct":  metrics.get("volume_ratio"),
            "bulk_deal_count": 0,
            "fii_weekly": None, "dii_weekly": None, "vix": vix_num,
        })
        print(f"  {sector}: score={score}")

def collect_pulse(sectors, companies):
    print("\n── Collecting Pulse data ──")
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    vix_val, vix_v, vix_l     = fetch_vix_upstox();          print(f"VIX: {vix_val}")
    nt_val, nt_v, nt_l        = fetch_nifty100_vs_200dma();   print(f"Nifty 100: {nt_val}")
    br_pct, br_v, br_l        = fetch_breadth_upstox(sectors, companies); print(f"Breadth: {br_pct}%")
    ff, fv, fl, df, dv, dl    = fetch_fii_dii_bse();          print(f"FII: {ff} DII: {df}")

    # These need NSE — skip for now, show gray
    pcr_val=None; pcr_v="gray"; pcr_l="N/A"
    ad_val=None;  ad_v="gray";  ad_l="N/A"
    fii_fp=None;  fii_fv="gray"; fii_fl="N/A"

    verdicts    = [vix_v, nt_v, br_v, fv, dv]
    green_count = sum(1 for v in verdicts if v == "green")
    red_count   = sum(1 for v in verdicts if v == "red")
    mood = "Bullish" if green_count >= 4 else ("Bearish" if red_count >= 4 else "Cautious")

    supabase_upsert("market_pulse", {
        "date": now, "overall_mood": mood,
        "vix_value": vix_val, "vix_verdict": vix_v, "vix_label": vix_l,
        "pcr_nifty": pcr_val, "pcr_verdict": pcr_v, "pcr_label": pcr_l,
        "nifty_trend_value": nt_val, "nifty_trend_verdict": nt_v, "nifty_trend_label": nt_l,
        "fii_flow": ff, "fii_verdict": fv, "fii_label": fl,
        "dii_flow": df, "dii_verdict": dv, "dii_label": dl,
        "ad_ratio": ad_val, "ad_ratio_verdict": ad_v, "ad_ratio_label": ad_l,
        "fii_futures_long_pct": fii_fp, "fii_futures_verdict": fii_fv, "fii_futures_label": fii_fl,
        "breadth_pct": br_pct, "breadth_verdict": br_v, "breadth_label": br_l,
    })
    print(f"Pulse saved — Mood: {mood} ({green_count}/5 signals available)")

# ══════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"Market Pulse Data Collector v3 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {RUN_MODE}")

    if not SUPABASE_KEY: print("ERROR: SUPABASE_SERVICE_KEY not set"); exit(1)
    if not UPSTOX_TOKEN: print("ERROR: UPSTOX_TOKEN not set"); exit(1)

    companies, sectors = load_companies()

    if RUN_MODE == "evening":
        # Evening: fetch fresh prices + calculate everything
        collect_price_history(companies)
        collect_sectors(sectors, companies)
        collect_pulse(sectors, companies)
    else:
        # Morning: just recalculate from existing price history
        collect_sectors(sectors, companies)
        collect_pulse(sectors, companies)

    print("\n✓ All done!")
