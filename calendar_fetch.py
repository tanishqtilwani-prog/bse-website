"""
calendar_fetch.py - Builds the corporate calendar in Supabase.

Sources (all via the BSE library):
  * resultCalendar()            -> upcoming result / board-meeting dates
  * actions(by_date="record")   -> dividend / bonus / split / rights record dates
  * announcements("New Listing")-> new listings
  * circulars()                 -> OFS, buyback, IPO  (exchange notices)

Note: BSE ignores the date-range params on actions(); it always returns
"all forthcoming" actions. That's fine - we upsert daily and let the
table accumulate.

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
}

DAYS_AHEAD = 60
CIRCULAR_LOOKBACK = 15     # how far back to scan exchange notices
RETAIN_DAYS = 45           # keep this much history before purging


# -- helpers ---------------------------------------------

def parse_date(s):
    """BSE gives '26 Aug 2026' or '2026-08-25T00:00:00'. -> 'YYYY-MM-DD'."""
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%d %b %Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(s[:11], fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def classify_action(purpose):
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


def classify_circular(subject):
    """Return event_type for an exchange notice, or None to ignore it."""
    s = subject.lower()
    if "offer for sale" in s:
        return "ofs"
    if "buyback" in s or "buy back" in s or "acquisition window" in s:
        return "buyback"
    if "tender offer" in s:
        return "buyback"
    if "public issue" in s:
        return "ipo"
    return None


# strip these leading phrases before pulling the company name out
CIRC_PREFIXES = [
    r"^opening of offer to buy\s*[\u2013-]?\s*acquisition window\s*\(buyback\)\s*for\s*",
    r"^opening of offer for sale\s+offer for sale\s+for\s*",
    r"^opening of offer for sale\s+for\s*",
    r"^opening of offer for sale\s*",
    r"^tender offer\s*\(buyback\)\s*of equity shares\s*(of)?\s*",
    r"^buyback of the equity shares of\s*",
    r"^buyback of the shares of\s*",
    r"^buyback of\s*",
    r"^public issue of\s*",
    r"^offer for sale\s*(for|of)?\s*",
]

# cut the company name off at any of these
CIRC_TAILS = [
    r"\s+from open market.*$",
    r"\s+through stock exchange.*$",
    r"\s*\(.*$",
    r"\s*[\u2013-]\s+.*$",
    r"\s*,\s*the\s+.*$",
    r"\s*\.\s*$",
]


def company_from_subject(subject):
    s = " ".join(str(subject).split())
    low = s.lower()
    for pat in CIRC_PREFIXES:
        m = re.match(pat, low)
        if m:
            s = s[m.end():]
            break
    for pat in CIRC_TAILS:
        s = re.sub(pat, "", s, flags=re.IGNORECASE)
    s = s.strip(" .,-\u2013")
    return s if 3 <= len(s) <= 90 else ""


def name_key(name):
    """Normalise so 'Hindustan Copper Limited' == 'HINDUSTAN COPPER LTD'."""
    k = name.upper()
    k = re.sub(r"[^A-Z0-9 ]", " ", k)
    k = re.sub(r"\b(LIMITED|LTD|THE)\b", "", k)
    return re.sub(r"\s+", "", k)


def titlecase(name):
    """'HINDUSTAN COPPER LTD' -> 'Hindustan Copper Ltd'; leave mixed case alone."""
    if name.isupper():
        return " ".join(w.capitalize() for w in name.split())
    return name


# -- collection ------------------------------------------

def collect():
    today = datetime.now()
    start = today - timedelta(days=RETAIN_DAYS)
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
            r = b.resultCalendar(from_date=start, to_date=end)
            for x in r:
                add(parse_date(x.get("meeting_date")), "result",
                    x.get("Long_Name"), x.get("scrip_Code"),
                    "Board meeting for financial results", x.get("URL", ""))
            print(f"  results   ok ({len(r)})")
        except Exception as e:
            print(f"  results   FAILED: {e}")

        # 2. CORPORATE ACTIONS (record date)
        try:
            acts = b.actions(by_date="record", from_date=start, to_date=end)
            for a in acts:
                purpose = str(a.get("Purpose", ""))
                details = clean_purpose(purpose)
                if a.get("Ex_date"):
                    details += f" | Ex-date {a.get('Ex_date')}"
                add(parse_date(a.get("RD_Date")), classify_action(purpose),
                    a.get("long_name"), a.get("scrip_code"), details)
            print(f"  actions   ok ({len(acts)})")
        except Exception as e:
            print(f"  actions   FAILED: {e}")

        # 3. NEW LISTINGS
        try:
            nl = b.announcements(category="New Listing")
            if isinstance(nl, dict):
                nl = nl.get("Table", [])
            for n in nl:
                add(parse_date(n.get("NEWS_DT")), "listing",
                    n.get("SLONGNAME"), n.get("SCRIP_CD"), "New listing")
            print(f"  listings  ok ({len(nl)})")
        except Exception as e:
            print(f"  listings  FAILED: {e}")

        # 4. CIRCULARS -> OFS / BUYBACK / IPO
        try:
            cfrom = today - timedelta(days=CIRCULAR_LOOKBACK)
            circ = b.circulars(from_date=cfrom, to_date=today)
            if isinstance(circ, dict):
                circ = circ.get("Table", [])

            # one company gets several notices for the same event -
            # keep only the earliest notice per (company, type)
            best = {}
            for c in circ:
                subject = str(c.get("Subject", "")).strip()
                etype = classify_circular(subject)
                if not etype:
                    continue
                company = company_from_subject(subject)
                if not company:
                    continue
                date = parse_date(c.get("Notice_Date"))
                if not date:
                    continue
                k = (name_key(company), etype)
                if k not in best or date < best[k]["date"]:
                    best[k] = {
                        "date": date,
                        "company": titlecase(company),
                        "url": str(c.get("FileName", "")),
                    }

            label = {"ofs": "Offer for Sale",
                     "buyback": "Buyback offer",
                     "ipo": "IPO / public issue"}

            for (nkey, etype), v in best.items():
                add(v["date"], etype, v["company"], "C" + nkey[:20],
                    label.get(etype, "Exchange notice"), v["url"])

            print(f"  circulars ok ({len(circ)} scanned -> {len(best)} events)")
        except Exception as e:
            print(f"  circulars FAILED: {e}")

    return list(rows.values())


# -- write -----------------------------------------------

def push(records):
    saved = 0
    for i in range(0, len(records), 200):
        batch = records[i:i + 200]
        try:
            r = requests.post(
                SUPABASE_URL + "/rest/v1/calendar_events",
                headers={**HEADERS,
                         "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=batch, timeout=30)
            if r.status_code in (200, 201, 204):
                saved += len(batch)
            else:
                print(f"  supabase {r.status_code}: {r.text[:150]}")
        except Exception as e:
            print(f"  push error: {e}")
    return saved


def purge():
    cutoff = (datetime.now() - timedelta(days=RETAIN_DAYS)).strftime("%Y-%m-%d")
    try:
        requests.delete(
            SUPABASE_URL + "/rest/v1/calendar_events",
            headers={**HEADERS, "Prefer": "return=minimal"},
            params={"event_date": "lt." + cutoff}, timeout=15)
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

    # show notice-derived ones so you can eyeball the name parsing
    special = [e for e in events if e["event_type"] in ("ofs", "buyback", "ipo")]
    if special:
        print("\n  From exchange notices:")
        for e in sorted(special, key=lambda x: x["event_date"]):
            print(f"    {e['event_date']}  {e['event_type']:8} {e['company_name']}")

    n = push(events)
    purge()
    print(f"\nSaved {n} events")
