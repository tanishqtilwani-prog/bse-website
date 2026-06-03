import asyncio
import re
import time
import csv
import requests
from telethon.sync import TelegramClient, events

# ── SETTINGS ──
API_ID       = 21598306
API_HASH     = "3620b1fbc6c9559c410cf44d596a263b"
SESSION_FILE = "/home/ubuntu/bse-website/tg_session"
CHANNEL_IDS  = [-1003806349868, -1003975218278]
SUPABASE_URL = "https://kbklmidusxqkbjgpsdlg.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtia2xtaWR1c3hxa2JqZ3BzZGxnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MDExNTcxNywiZXhwIjoyMDk1NjkxNzE3fQ.v-gWV939rbNfNSXxzSbzaGduDXvxFhB8f_MHEp0wlFY"
CSV_FILE     = "/home/ubuntu/bse-website/ind_nifty500list.csv"

# ── LOAD NIFTY 500 ──
NIFTY500_NAMES = set()
try:
    with open(CSV_FILE, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Company Name", "").strip().lower()
            if name:
                NIFTY500_NAMES.add(name)
    print(f"Loaded {len(NIFTY500_NAMES)} Nifty 500 names")
except Exception as e:
    print(f"CSV load failed: {e}")

def is_nifty500(company_name):
    def clean(s):
        return ''.join(c for c in s.lower() if c.isalnum() or c.isspace()).strip()
    name = clean(company_name or "")
    for n in NIFTY500_NAMES:
        if clean(n) == name or clean(n) in name or name in clean(n):
            return True
    return False

def detect_category(text):
    t = text.lower()
    if "dividend" in t: return "dividend"
    if "bonus" in t: return "bonus"
    if "buyback" in t or "buy back" in t: return "buyback"
    if "order" in t or "contract" in t: return "order_win"
    if "auditor" in t: return "auditor"
    if "acquisition" in t or "merger" in t: return "acquisition"
    if "result" in t or "revenue" in t or "profit" in t: return "result"
    return "other"

def extract_company(text):
    match = re.search(r'^(.+?)\s*\(\d{6}\)', text.strip(), re.MULTILINE)
    if match:
        return match.group(1).strip()
    lines = text.strip().split('\n')
    return lines[0].strip() if lines else None

def extract_scrip(text):
    match = re.search(r'\((\d{6})\)', text)
    return match.group(1) if match else None

def extract_price(text):
    match = re.search(r'Price[:\s]+[₹Rs.]*\s*([\d,.]+)\s*([+-][\d.]+%)', text, re.IGNORECASE)
    if match:
        return match.group(1).replace(',', ''), match.group(2)
    return None, None

def save_to_supabase(message_id, text, company, scrip, category, is_nifty, price, price_change):
    record = {
        "message_id": message_id,
        "text": text,
        "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "company_name": company,
        "scrip_code": scrip,
        "category": category,
        "is_nifty500": is_nifty,
        "price": price,
        "price_change": price_change,
    }
    try:
        resp = requests.post(
            SUPABASE_URL + "/rest/v1/posts",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": "Bearer " + SUPABASE_KEY,
                "Content-Type": "application/json",
                "Prefer": "resolution=ignore-duplicates,return=minimal"
            },
            json=record,
            timeout=10
        )
        if resp.status_code not in (200, 201):
            print(f"Supabase error {resp.status_code}: {resp.text[:200]}")
        else:
            print(f"Saved: {company} | {category} | price={price}")
    except Exception as e:
        print(f"Supabase failed: {e}")

# ── MAIN ──
with TelegramClient(SESSION_FILE, API_ID, API_HASH) as client:
    print("BSE Channel Sync (Telethon) started!")

    @client.on(events.NewMessage(chats=CHANNEL_IDS))
    async def handler(event):
        try:
            msg = event.message
            text = msg.text or msg.message or ""
            if not text.strip():
                return
            clean = re.sub(r'<[^>]+>', '', text).strip()
            company = extract_company(clean)
            scrip = extract_scrip(clean)
            category = detect_category(clean)
            nifty = is_nifty500(company) if company else False
            price, price_change = extract_price(clean)
            save_to_supabase(
                message_id=msg.id,
                text=clean,
                company=company,
                scrip=scrip,
                category=category,
                is_nifty=nifty,
                price=price,
                price_change=price_change
            )
        except Exception as e:
            print(f"Handler error: {e}")

    print("Logged in! Listening for messages...")
    client.run_until_disconnected()
