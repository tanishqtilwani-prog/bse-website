"""
Measure the gap between first notice and the event window.

BSE issues several notices per event. The first is the announcement
(before the event); later ones like 'Oversubscription Notice' or
'Live Activities Schedule' are published DURING it. So the spread of
notice dates per company approximates the real window - no PDF needed.
"""

import re
from collections import defaultdict
from datetime import datetime, timedelta
from bse import BSE

LOOKBACK = 45

JARGON = [r"voluntary delisting", r"delisting", r"revised settlement schedule",
          r"settlement schedule", r"live activities schedule",
          r"oversubscription notice", r"acquisition window", r"opening of",
          r"offer to buy", r"offer for sale", r"tender offer", r"public issue",
          r"buyback of the equity shares", r"buyback of the shares", r"buyback",
          r"buy back", r"of equity shares", r"equity shares", r"from open market",
          r"through stock exchange", r"through the stock exchange",
          r"allocation to anchor investors", r"anchor investors",
          r"bidding period", r"non retail", r"non-retail", r"retail investors",
          r"scrip code\s*:?\s*\d+", r"reverse book building",
          r"\bshares?\b", r"\bequity\b"]
POISON = ["offer", "schedule", "window", "notice", "issue", "buyback",
          "tender", "bidding", "investors"]


def etype(s):
    s = s.lower()
    if "delisting" in s: return "delisting"
    if "offer for sale" in s: return "ofs"
    if any(k in s for k in ("buyback", "buy back", "acquisition window",
                            "offer to buy", "tender offer")): return "buyback"
    if "public issue" in s: return "ipo"
    return None


def company(subject):
    s = " ".join(str(subject).split())
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"\(.*$", " ", s)
    for p in JARGON:
        s = re.sub(p, " ", s, flags=re.IGNORECASE)
    s = re.sub(r"[\u2013\u2014]", "-", s)
    s = re.sub(r"\s+", " ", s).strip(" -")
    parts = [p.strip() for p in s.split(" - ") if p.strip()]
    s = parts[0] if parts else ""
    s = re.sub(r"[\"\u201c\u201d'.,:;]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^(for|of|the|and|to|in|by)\b\s*", "", s, flags=re.I)
    s = re.sub(r"\s*\b(for|of|the|and|to|in|by)$", "", s, flags=re.I)
    s = s.strip(" -")
    s = re.sub(r"\s+[a-z]$", "", s)
    s = s.strip(" -")
    if not (3 <= len(s) <= 90): return ""
    if any(w in s.lower() for w in POISON): return ""
    return s


def key(n):
    k = n.upper().replace("&", " AND ")
    k = re.sub(r"[^A-Z0-9 ]", " ", k)
    k = re.sub(r"\b(LIMITED|LTD|THE|PVT|PRIVATE)\b", " ", k)
    return re.sub(r"\s+", "", k)


t = datetime.now()
with BSE(download_folder="/tmp/") as b:
    c = b.circulars(from_date=t - timedelta(days=LOOKBACK), to_date=t)
    c = c.get("Table", []) if isinstance(c, dict) else c

print(f"Scanned {len(c)} circulars over {LOOKBACK} days\n")

groups = defaultdict(list)
for r in c:
    sub = str(r.get("Subject", "")).strip()
    et = etype(sub)
    if not et:
        continue
    co = company(sub)
    if not co:
        continue
    d = str(r.get("Notice_Date", ""))[:10]
    if len(d) == 10:
        groups[(key(co), et)].append((d, co, sub))

spans = defaultdict(list)

for et_want in ("ofs", "ipo", "buyback", "delisting"):
    rows = {k: v for k, v in groups.items() if k[1] == et_want}
    multi = {k: v for k, v in rows.items() if len(v) > 1}
    print("=" * 74)
    print(f"{et_want.upper()}   {len(rows)} companies, {len(multi)} with multiple notices")
    print("=" * 74)
    for k, v in sorted(multi.items(), key=lambda x: min(d for d, _, _ in x[1]))[:8]:
        v.sort()
        first, last = v[0][0], v[-1][0]
        span = (datetime.strptime(last, "%Y-%m-%d")
                - datetime.strptime(first, "%Y-%m-%d")).days
        spans[et_want].append(span)
        print(f"\n  {v[0][1][:45]}")
        print(f"    notices {first} -> {last}   span {span}d   ({len(v)} notices)")
        for d, _, s in v:
            print(f"      {d}  {s[:80]}")

print()
print("=" * 74)
print("SUMMARY - notice span per type (proxy for event window)")
print("=" * 74)
for et_want in ("ofs", "ipo", "buyback", "delisting"):
    s = spans.get(et_want, [])
    if s:
        print(f"  {et_want:10} spans: {sorted(s)}   median {sorted(s)[len(s)//2]}d")
    else:
        print(f"  {et_want:10} not enough multi-notice samples")
