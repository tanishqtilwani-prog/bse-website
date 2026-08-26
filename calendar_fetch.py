"""
calendar_fetch.py - Builds the corporate calendar in Supabase.

Sources (all via the BSE library):
  * resultCalendar()            -> upcoming result / board-meeting dates
  * actions(by_date="record")   -> dividend / bonus / split / rights record dates
  * announcements("New Listing")-> new listings
  * circulars()                 -> OFS, buyback, IPO  (exchange notices)

Note: BSE ignores the date-range params on actions(); it always returns
"all forthcoming" actions. We upsert daily and let the table accumulate.

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

# must match the unique index on calendar_events
CONFLICT_COLS = "event_date,scrip_code,event_type"

DAYS_AHEAD = 60
CIRCULAR_LOOKBACK = 15

# BSE notices carry the NOTICE date, not the event date. These offsets
# convert notice date -> event window, in trading days.
#   OFS  : notice is T-1, offer runs 2 days   (verified: Hindustan Copper
#          notice 24 Aug -> OFS 25 & 26 Aug)
#   IPO  : anchor allocation is T-1, issue runs 3 days
#   Buyback / delisting : tender window is ~5 trading days from open
WINDOWS = {
    "ofs":       (1, 2),
    "ipo":       (1, 3),
    "buyback":   (1, 5),
    "delisting": (1, 5),
}
RETAIN_DAYS = 45

DEBUG_SUBJECTS = True      # print raw notice subject next to parsed name


# -- date --------------------------------------------------

def parse_date(s):
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


# -- corporate actions -------------------------------------

MONTHS_RE = ("january|february|march|april|may|june|july|august|"
             "september|october|november|december")


def date_in_text(text):
    m = re.search(r"(" + MONTHS_RE + r")\s+(\d{1,2}),?\s+(\d{4})", str(text), re.IGNORECASE)
    if m:
        try:
            return datetime.strptime(f"{m.group(1)[:3]} {m.group(2)} {m.group(3)}", "%b %d %Y").strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = re.search(r"(\d{1,2})\s+(" + MONTHS_RE + r")\s+(\d{4})", str(text), re.IGNORECASE)
    if m:
        try:
            return datetime.strptime(f"{m.group(2)[:3]} {m.group(1)} {m.group(3)}", "%b %d %Y").strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def is_new_listing_circular(subject):
    s = subject.lower()
    if "new securities" in s or "further securities" in s:
        return False
    if "esop" in s or "esos" in s or "warrant" in s:
        return False
    return "listing of equity shares" in s


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
    p = re.sub(r"\s*-\s*", " ", str(purpose)).strip()
    p = re.sub(r"\s+", " ", p)
    p = re.sub(r"(\d+\.\d*?)0+\b", r"\1", p)
    p = re.sub(r"(\d+)\.\b", r"\1", p)
    return p.strip()


# -- exchange notices --------------------------------------

def business_days(start, lo, hi):
    """Trading days start+lo .. start+hi, skipping weekends."""
    out, n, off = [], 0, 0
    while len(out) < hi:
        off += 1
        d = start + timedelta(days=off)
        if d.weekday() >= 5:          # Sat / Sun
            continue
        n += 1
        if n >= lo:
            out.append(d)
    return out


def is_anchor(subject, etype):
    """Only the OPENING notice sets the window. Follow-ups (settlement
    schedule, oversubscription) would otherwise anchor us weeks late."""
    s = subject.lower()
    if "settlement schedule" in s:
        return False
    if etype == "ipo":
        return "public issue" in s
    return "opening of" in s


def classify_circular(subject):
    s = subject.lower()
    if "delisting" in s:
        return "delisting"
    if "offer for sale" in s:
        return "ofs"
    if any(k in s for k in ("buyback", "buy back", "acquisition window",
                            "offer to buy", "tender offer")):
        return "buyback"
    if "public issue" in s:
        return "ipo"
    return None


# every bit of notice boilerplate, stripped wherever it appears
JARGON = [
    r"voluntary delisting",
    r"delisting",
    r"revised settlement schedule",
    r"settlement schedule",
    r"live activities schedule",
    r"oversubscription notice",
    r"acquisition window",
    r"opening of",
    r"offer to buy",
    r"offer for sale",
    r"tender offer",
    r"public issue",
    r"buyback of the equity shares",
    r"buyback of the shares",
    r"buyback",
    r"buy back",
    r"of equity shares",
    r"equity shares",
    r"from open market",
    r"through stock exchange",
    r"through the stock exchange",
    r"stock exchange mechanism",
    r"allocation to anchor investors",
    r"anchor investors",
    r"bidding period",
    r"non retail",
    r"non-retail",
    r"retail investors",
    r"scrip code\s*:?\s*\d+",
    r"reverse book building",
    r"\bshares?\b",
    r"\bequity\b",
]

# if any of these survive, the parse failed
POISON = ["offer", "schedule", "window", "notice", "issue", "buyback",
          "tender", "bidding", "investors"]


def company_from_subject(subject):
    s = " ".join(str(subject).split())

    s = re.sub(r"\(.*?\)", " ", s)          # drop bracketed asides
    s = re.sub(r"\(.*$", " ", s)            # and any unclosed bracket
    for pat in JARGON:
        s = re.sub(pat, " ", s, flags=re.IGNORECASE)

    s = re.sub(r"[\u2013\u2014]", "-", s)
    s = re.sub(r"\s+", " ", s).strip(" -")  # clear dangling dashes first
    parts = [p.strip() for p in s.split(" - ") if p.strip()]
    s = parts[0] if parts else ""            # keep the head, drop trailing detail
    s = re.sub(r"[\"\u201c\u201d'.,:;]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    # trim dangling joiners left behind by the strips
    s = re.sub(r"^(for|of|the|and|to|in|by)\b\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*\b(for|of|the|and|to|in|by)$", "", s, flags=re.IGNORECASE)
    s = s.strip(" -")
    s = re.sub(r"\s+[a-z]$", "", s)          # trailing 's' etc left by strips
    s = re.sub(r"'s\b", "", s, flags=re.IGNORECASE)
    s = s.strip(" -")

    if not (3 <= len(s) <= 90):
        return ""
    low = s.lower()
    if any(w in low for w in POISON):
        return ""
    if not re.search(r"[A-Za-z]{3}", s):
        return ""
    return s


def name_key(name):
    """Hindustan Copper Limited == HINDUSTAN COPPER LTD; & == And."""
    k = name.upper().replace("&", " AND ")
    k = re.sub(r"[^A-Z0-9 ]", " ", k)
    k = re.sub(r"\b(LIMITED|LTD|THE|PVT|PRIVATE)\b", " ", k)
    return re.sub(r"\s+", "", k)


def titlecase(name):
    if name.isupper():
        return " ".join(w.capitalize() for w in name.split())
    return name


# -- collection --------------------------------------------

def collect():
    today = datetime.now()
    start = today - timedelta(days=RETAIN_DAYS)
    end = today + timedelta(days=DAYS_AHEAD)
    rows = {}
    skipped = []
    listed_names = set()

    def add(date, etype, company, scrip, details, url=""):
        if not date or not company:
            return
        rows[(date, str(scrip), etype)] = {
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

        # 2. CORPORATE ACTIONS
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
                d = date_in_text(str(n.get("HEADLINE", ""))) or parse_date(n.get("NEWS_DT"))
                nm = n.get("SLONGNAME")
                if nm:
                    listed_names.add(name_key(str(nm)))
                add(d, "listing", nm, n.get("SCRIP_CD"), "Listed and admitted to dealings")
            print(f"  listings  ok ({len(nl)})")
        except Exception as e:
            print(f"  listings  FAILED: {e}")

        # 4. CIRCULARS -> OFS / BUYBACK / IPO
        try:
            cfrom = today - timedelta(days=CIRCULAR_LOOKBACK)
            circ = b.circulars(from_date=cfrom, to_date=today)
            if isinstance(circ, dict):
                circ = circ.get("Table", [])

            best = {}
            upcoming = {}
            for c in circ:
                subject = str(c.get("Subject", "")).strip()
                if is_new_listing_circular(subject):
                    nm = re.sub(r"^listing of equity shares of\s*", "", subject, flags=re.IGNORECASE).strip(" .")
                    nm = re.sub(r"\s*\(.*$", "", nm).strip()
                    d = parse_date(c.get("Notice_Date"))
                    if nm and d and 3 <= len(nm) <= 90:
                        k = name_key(nm)
                        if k not in listed_names and (k not in upcoming or d < upcoming[k]["date"]):
                            upcoming[k] = {"date": d, "company": titlecase(nm)}
                    continue
                etype = classify_circular(subject)
                if not etype:
                    continue
                if not is_anchor(subject, etype):
                    continue
                company = company_from_subject(subject)
                date = parse_date(c.get("Notice_Date"))
                if not company:
                    skipped.append(subject)
                    continue
                if not date:
                    continue
                k = (name_key(company), etype)
                if k not in best or date < best[k]["date"]:
                    best[k] = {"date": date,
                               "company": titlecase(company),
                               "subject": subject,
                               "url": str(c.get("FileName", ""))}

            label = {"ofs": "Offer for Sale",
                     "delisting": "Delisting offer",
                     "buyback": "Buyback offer",
                     "ipo": "IPO / public issue"}

            for (nkey, etype), v in best.items():
                lo, hi = WINDOWS.get(etype, (1, 1))
                d0 = datetime.strptime(v["date"], "%Y-%m-%d")
                days = business_days(d0, lo, hi)
                total = len(days)
                base = label.get(etype, "Exchange notice")
                for i, d in enumerate(days, 1):
                    if etype == "ofs" and total == 2:
                        leg = "non-retail / HNI day" if i == 1 else "retail day"
                    elif total > 1:
                        leg = f"day {i} of {total}"
                    else:
                        leg = ""
                    det = f"{base} \u00b7 {leg}" if leg else base
                    add(d.strftime("%Y-%m-%d"), etype, v["company"],
                        "C" + nkey[:20], det, v["url"])

            for k, v in upcoming.items():
                d0 = datetime.strptime(v["date"], "%Y-%m-%d")
                nxt = business_days(d0, 1, 1)[0]
                add(nxt.strftime("%Y-%m-%d"), "listing", v["company"], "L" + k[:20], "Listing expected")

            projected = 0
            for (nkey, etype), v in best.items():
                if etype != "ipo" or nkey in listed_names:
                    continue
                d0 = datetime.strptime(v["date"], "%Y-%m-%d")
                lo, hi = WINDOWS["ipo"]
                close = business_days(d0, lo, hi)[-1]
                listing = business_days(close, 3, 3)[0]
                add(listing.strftime("%Y-%m-%d"), "listing", v["company"],
                    "P" + nkey[:20], "Listing expected (from IPO close)")
                projected += 1

            print(f"  circulars ok ({len(circ)} scanned -> {len(best)} events, "
                  f"{len(upcoming)} upcoming listings, "
                  f"{projected} projected, {len(skipped)} unparsed)")
        except Exception as e:
            print(f"  circulars FAILED: {e}")

    return list(rows.values()), best if 'best' in dir() else {}, skipped


# -- write -------------------------------------------------

def push(records):
    url = (SUPABASE_URL + "/rest/v1/calendar_events?on_conflict=" + CONFLICT_COLS)
    saved = 0
    for i in range(0, len(records), 200):
        batch = records[i:i + 200]
        try:
            r = requests.post(
                url,
                headers={**HEADERS,
                         "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=batch, timeout=30)
            if r.status_code in (200, 201, 204):
                saved += len(batch)
            else:
                print(f"  supabase {r.status_code}: {r.text[:180]}")
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
    events, best, skipped = collect()
    print(f"Collected {len(events)} events")

    counts = {}
    for e in events:
        counts[e["event_type"]] = counts.get(e["event_type"], 0) + 1
    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {v:5d}  {k}")

    special = [e for e in events
               if e["event_type"] in ("ofs", "buyback", "ipo", "delisting")]
    if special:
        print("\n  From exchange notices:")
        for e in sorted(special, key=lambda x: x["event_date"]):
            print(f"    {e['event_date']}  {e['event_type']:8} {e['company_name']}")

    if DEBUG_SUBJECTS and skipped:
        print(f"\n  Unparsed subjects ({len(skipped)}) - first 10:")
        for s in skipped[:10]:
            print(f"    {s[:105]}")

    n = push(events)
    purge()
    print(f"\nSaved {n} events")
 
