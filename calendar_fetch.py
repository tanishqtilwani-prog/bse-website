"""
calendar_fetch.py - Builds the corporate calendar in Supabase.

Sources (all via the BSE library):
  * resultCalendar()            -> upcoming result/board-meeting dates
  * actions(by_date="record")   -> dividend / bonus / split / rights / buyback record dates
  * announcements("New Listing")-> new listings

Run daily via pm2 cron.
"""

import re
import requests
from datetime import datetime, timedelta
from bse import BSE

SUPABASE_URL = "https://kbklmidusxqkbjgpsdlg.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtia2xtaWR1c3hxa2JqZ3BzZGxnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MDExNTcxNywiZXhwIjoyMDk1NjkxNzE3fQ.v-gWV939rbNfNSXxzSbzaGduDXvxFhB8f_MHEp0wlFY"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",
}

DAYS_AHEAD = 60
DAYS_BEHIND = 3


def parse_date(s):
    """BSE gives '26 Aug 2026' or '2026-08-26T...'. Return 'YYYY-MM-DD' or None."""
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%d %b %Y", "%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:11], fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def classify(purpose):
    """Map a BSE purpose string to our event_type."""
    p = purpose.lower()
    if "bonus" in p:
        return "bonus"
    if "right" in p:
        return "rights"
    if "split" in p or "sub-division" in p or "subdivision" in p:
        return "split"
    if "buyback" in p or "buy back" in p:
        return "buyback"
    if "dividend" in p:
        return "dividend"
    return "corp_action"


def clean_purpose(purpose):
    """'Final Dividend - Rs. - 1.2500' -> 'Final Dividend Rs 1.25'"""
    p = re.sub(r"\s*-\s*", " ", str(purpose)).strip()
    p = re.sub(r"\s+", " ", p)
    p = re.sub(r"(\d+\.\d*?)0+\b", r"\1", p)
    p = re.sub(r"(\d+)\.\b", r"\1", p)
    return p.strip()


def collect():
    today = datetime.now()
    start = today - timedelta(days=DAYS_BEHIND)
    end = today + timedelta(days=DAYS_AHEAD)
    rows = {}

    def add(date, etype, company, scrip, details, url=""):
        if not date or not company:
            return
        key = (date, str(scrip), etype)
        rows[key] = {
            "event_date": date,
            "event_type": etype,
            "company_name": str(company).strip(),
            "scrip_code": str(scrip),
            "details": details,
            "url": url,
        }

    with BSE(download_folder="/tmp/") as b:

        # 1. RESULTS
        try:
            for r in b.resultCalendar(from_date=start, to_date=end):
                add(
                    parse_date(r.get("meeting_date")),
                    "result",
                    r.get("Long_Name"),
                    r.get("scrip_Code"),
                    "Board meeting for financial results",
                    r.get("URL", ""),
                )
            print(f"  results ok")
        except Exception as e:
            print(f"  results FAILED: {e}")

        # 2. CORPORATE ACTIONS (by record date)
        try:
            acts = b.actions(by_date="record", from_date=start, to_date=end)
            for a in acts:
                purpose = str(a.get("Purpose", ""))
                details = clean_purpose(purpose)
                ex = parse_date(a.get("Ex_date"))
                if ex:
                    details += f" | Ex-date {a.get('Ex_date')}"
                add(
                    parse_date(a.get("RD_Date")),
                    classify(purpose),
                    a.get("long_name"),
                    a.get("scrip_code"),
                    details,
                )
            print(f"  actions ok ({len(acts)})")
        except Exception as e:
            print(f"  actions FAILED: {e}")

        # 3. NEW LISTINGS
        try:
            nl = b.announcements(category="New Listing")
            if isinstance(nl, dict):
                nl = nl.get("Table", [])
            for n in nl:
                add(
                    parse_date(n.get("NEWS_DT")),
                    "listing",
                    n.get("SLONGNAME"),
                    n.get("SCRIP_CD"),
                    "New listing",
                )
            print(f"  listings ok ({len(nl)})")
        except Exception as e:
            print(f"  listings FAILED: {e}")

    return list(rows.values())


def push(records):
    """Upsert in batches of 200."""
    saved = 0
    for i in range(0, len(records), 200):
        batch = records[i:i + 200]
        try:
            r = requests.post(
                SUPABASE_URL + "/rest/v1/calendar_events",
                headers={**HEADERS, "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=batch,
                timeout=30,
            )
            if r.status_code in (200, 201, 204):
                saved += len(batch)
            else:
                print(f"  supabase {r.status_code}: {r.text[:150]}")
        except Exception as e:
            print(f"  push error: {e}")
    return saved


def purge():
    """Drop events older than DAYS_BEHIND days."""
    cutoff = (datetime.now() - timedelta(days=DAYS_BEHIND)).strftime("%Y-%m-%d")
    try:
        requests.delete(
            SUPABASE_URL + "/rest/v1/calendar_events",
            headers={**HEADERS, "Prefer": "return=minimal"},
            params={"event_date": "lt." + cutoff},
            timeout=15,
        )
    except Exception as e:
        print(f"  purge error: {e}")


if __name__ == "__main__":
    print(f"Calendar fetch {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    events = collect()
    print(f"Collected {len(events)} events")

    counts = {}
    for e in events:
        counts[e["event_type"]] = counts.get(e["event_type"], 0) + 1
    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {v:5d}  {k}")

    n = push(events)
    purge()
    print(f"Saved {n} events")
