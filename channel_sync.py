import re
import time
import csv
import requests
from telethon.sync import TelegramClient, events
from telethon.tl.types import MessageEntityUrl, MessageEntityTextUrl

API_ID       = 21598306
API_HASH     = "3620b1fbc6c9559c410cf44d596a263b"
SESSION_FILE = "/home/ubuntu/bse-website/tg_session"
CHANNEL_IDS  = [-1003806349868, -1003975218278]
SUPABASE_URL = "https://kbklmidusxqkbjgpsdlg.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtia2xtaWR1c3hxa2JqZ3BzZGxnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MDExNTcxNywiZXhwIjoyMDk1NjkxNzE3fQ.v-gWV939rbNfNSXxzSbzaGduDXvxFhB8f_MHEp0wlFY"
CSV_100      = "/home/ubuntu/bse-website/ind_nifty100list.csv"
CSV_TOTAL    = "/home/ubuntu/bse-website/ind_niftytotalmarket_list.csv"

def load_names(csv_file):
    names = set()
    try:
        with open(csv_file, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Company Name", "").strip().lower()
                if name:
                    names.add(name)
        print(f"Loaded {len(names)} names from {csv_file}")
    except Exception as e:
        print(f"CSV load failed {csv_file}: {e}")
    return names

NIFTY100_NAMES = load_names(CSV_100)
NIFTYTOTAL_NAMES = load_names(CSV_TOTAL)

def check_index(company_name, names_set):
    import re as _re
    def clean(s):
        return _re.sub(r'[^a-z0-9\s]', '', s.lower()).strip()
    name = clean(company_name or "")
    for n in names_set:
        nc = clean(n)
        if nc == name or nc in name or name in nc:
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

def clean_body(text, scrip):
    text = re.sub(r'\*+', '', text)
    if scrip:
        lines = text.strip().splitlines()
        if lines and scrip in lines[0]:
            lines = lines[1:]
            text = '\n'.join(lines).strip()
    return text.strip()

def extract_company(text):
    match = re.search(r'^(.+?)\s*\(\d{6}\)', text.strip(), re.MULTILINE)
    if match:
        name = match.group(1).strip()
    else:
        lines = text.strip().splitlines()
        name = lines[0].strip() if lines else None
    if name:
        name = re.sub(r'\*+', '', name).strip()
    return name

def extract_scrip(text):
    match = re.search(r'\((\d{6})\)', text)
    return match.group(1) if match else None

def extract_price(text):
    match = re.search(r'Price[:\s]+[^\d]*([\d,.]+)\s*([+-][\d.]+%)', text, re.IGNORECASE)
    if match:
        return match.group(1).replace(',', ''), match.group(2)
    return None, None

def extract_filing_url(msg):
    try:
        if msg.reply_markup:
            for row in msg.reply_markup.rows:
                for btn in row.buttons:
                    if hasattr(btn, 'url') and btn.url:
                        return btn.url
    except:
        pass
    try:
        if msg.entities:
            for ent in msg.entities:
                if isinstance(ent, MessageEntityTextUrl):
                    return ent.url
                if isinstance(ent, MessageEntityUrl) and msg.text:
                    return msg.text[ent.offset:ent.offset+ent.length]
    except:
        pass
    return None

def save_to_supabase(message_id, text, company, scrip, category, is_nifty100, is_niftytotal, price, price_change, filing_url, msg_date=None):
    record = {
        "message_id": message_id,
        "text": text,
        "date": msg_date or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "company_name": company,
        "scrip_code": scrip,
        "category": category,
        "is_nifty100": is_nifty100,
        "is_niftytotal": is_niftytotal,
        "price": price,
        "price_change": price_change,
        "filing_url": filing_url,
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
            print(f"Saved: {company} | {category} | n100={is_nifty100} | ntotal={is_niftytotal}")
    except Exception as e:
        print(f"Supabase failed: {e}")

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
            if any(skip in clean.lower() for skip in ['is now running', 'bot started', 'monitoring top']):
                return
            company = extract_company(clean)
            scrip = extract_scrip(clean)
            clean = clean_body(clean, scrip)
            category = detect_category(clean)
            is_nifty100 = check_index(company, NIFTY100_NAMES) if company else False
            is_niftytotal = check_index(company, NIFTYTOTAL_NAMES) if company else False
            price, price_change = extract_price(clean)
            filing_url = extract_filing_url(msg)
            msg_date = msg.date.strftime("%Y-%m-%dT%H:%M:%SZ") if msg.date else None
            save_to_supabase(
                message_id=msg.id,
                text=clean,
                company=company,
                scrip=scrip,
                category=category,
                is_nifty100=is_nifty100,
                is_niftytotal=is_niftytotal,
                price=price,
                price_change=price_change,
                filing_url=filing_url,
                msg_date=msg_date
            )
        except Exception as e:
            print(f"Handler error: {e}")

    print("Logged in! Listening for messages...")
    client.run_until_disconnected()
