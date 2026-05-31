import time
import json
import os
import csv
import requests

# ── SETTINGS ──
BOT_TOKEN    = "8795975670:AAHMXeEMBIhtDJ6Yu1i6IQe6N_R4rQ7QLp8"
CHANNEL_ID   = "-1003806349868"
SUPABASE_URL = "https://kbklmidusxqkbjgpsdlg.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtia2xtaWR1c3hxa2JqZ3BzZGxnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MDExNTcxNywiZXhwIjoyMDk1NjkxNzE3fQ.v-gWV939rbNfNSXxzSbzaGduDXvxFhB8f_MHEp0wlFY"
CSV_FILE     = "ind_nifty500list.csv"
POLL_EVERY   = 300
OFFSET_FILE  = "/tmp/tg_offset.json"

# ── LOAD NIFTY 500 ──
def load_nifty500():
    names = set()
    try:
        with open(CSV_FILE, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Company Name", "").strip().lower()
                if name:
                    names.add(name)
        print(f"Loaded {len(names)} Nifty 500 names")
    except Exception as e:
        print(f"CSV load failed: {e}")
    return names

NIFTY500_NAMES = load_nifty500()

def is_nifty500(company_name):
    def clean(s):
        return ''.join(c for c in s.lower() if c.isalnum() or c.isspace()).strip()
    name = clean(company_name)
    for n in NIFTY500_NAMES:
        if clean(n) == name or clean(n) in name or name in clean(n):
            return True
    return False

# ── DETECT CATEGORY ──
def detect_category(text):
    t = text.lower()
    if "dividend" in t: return "dividend"
    if "bonus" in t: return "bonus"
    if "rights" in t: return "rights"
    if "buyback" in t or "buy back" in t: return "buyback"
    if "order" in t or "contract" in t: return "order_win"
    if "auditor" in t: return "auditor"
    if "agm" in t or "annual general" in t: return "agm"
    if "board meeting" in t: return "board_meeting"
    if "result" in t or "revenue" in t or "profit" in t: return "result"
    return "other"

# ── EXTRACT COMPANY ──
def extract_company(text):
    import re
    match = re.search(r'<b>(.+?)\s*\(', text)
    if match:
        return match.group(1).strip()
    lines = text.strip().split('\n')
    return lines[0].replace('<b>', '').replace('</b>', '').strip() if lines else None

def extract_symbol(text):
    import re
    match = re.search(r'\((\d{6})\)', text)
    return match.group(1) if match else None

def clean_text(text):
    import re
    return re.sub(r'<[^>]+>', '', text).strip()

# ── LOAD/SAVE OFFSET ──
def load_offset():
    if os.path.exists(OFFSET_FILE):
        try:
            return json.load(open(OFFSET_FILE)).get("offset", 0)
        except:
            return 0
    return 0

def save_offset(offset):
    json.dump({"offset": offset}, open(OFFSET_FILE, "w"))

# ── SUPABASE INSERT ──
def supabase_upsert(record):
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
    except Exception as e:
        print(f"Supabase insert failed: {e}")

# ── FETCH TELEGRAM UPDATES ──
def fetch_updates(offset):
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
            params={
                "offset": offset,
                "limit": 100,
                "timeout": 30,
                "allowed_updates": json.dumps(["channel_post"])
            },
            timeout=40
        )
        data = resp.json()
        if not data.get("ok"):
            print(f"Telegram error: {data}")
            return [], offset
        updates = data.get("result", [])
        new_offset = updates[-1]["update_id"] + 1 if updates else offset
        return updates, new_offset
    except Exception as e:
        print(f"Fetch error: {e}")
        return [], offset

# ── PROCESS UPDATE ──
def process_update(update):
    msg = update.get("channel_post")
    if not msg:
        return

    chat_id = msg.get("chat", {}).get("id")
    if str(chat_id) != CHANNEL_ID:
        return

    message_id = msg.get("message_id")
    text = msg.get("text") or msg.get("caption") or ""
    date = msg.get("date")
    posted_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(date)) if date else None

    company = extract_company(text)
    symbol = extract_symbol(text)
    category = detect_category(text)
    nifty = is_nifty500(company) if company else False

    files = []
    if msg.get("document"):
        files.append({"type": "document", "file_id": msg["document"]["file_id"]})
    if msg.get("photo"):
        files.append({"type": "photo", "file_id": msg["photo"][-1]["file_id"]})

    record = {
        "channel": "results",
        "telegram_chat_id": chat_id,
        "telegram_message_id": message_id,
        "category": category,
        "symbol": symbol,
        "company_name": company,
        "title": company,
        "body": clean_text(text),
        "files": files,
        "raw": msg,
        "posted_at": posted_at,
        "is_nifty500": nifty,
    }

    supabase_upsert(record)
    print(f"Synced: {company or 'unknown'} | {category} | nifty={nifty}")

# ── MAIN LOOP ──
print("BSE Channel Sync started!")
offset = load_offset()

while True:
    updates, offset = fetch_updates(offset)
    for update in updates:
        process_update(update)
    if updates:
        save_offset(offset)
        print(f"Processed {len(updates)} updates. New offset: {offset}")
    else:
        print(f"No new updates at {time.strftime('%H:%M:%S')}")
    time.sleep(POLL_EVERY)
