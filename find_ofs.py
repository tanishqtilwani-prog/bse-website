"""Find where OFS and buyback live in BSE data."""
from bse import BSE
from datetime import datetime, timedelta

today = datetime.now()
wide_from = today - timedelta(days=90)
wide_to = today + timedelta(days=90)

CATS = ["Company Update", "Corp. Action", "Board Meeting", "Result",
        "New Listing", "AGM/EGM", "Insider Trading / SAST", "Amalgamation/Mergers"]

KEYWORDS = ["offer for sale", "ofs", "buyback", "buy back", "buy-back"]

with BSE(download_folder="/tmp/") as b:

    print("=" * 64)
    print("A. ANNOUNCEMENTS mentioning OFS / BUYBACK (today's feed)")
    print("=" * 64)
    hits = 0
    for cat in CATS:
        try:
            d = b.announcements(category=cat)
            if isinstance(d, dict):
                d = d.get("Table", [])
        except Exception as e:
            print(f"  {cat}: error {e}")
            continue

        for a in d:
            blob = (str(a.get("HEADLINE", "")) + " " +
                    str(a.get("NEWSSUB", "")) + " " +
                    str(a.get("SUBCATNAME", ""))).lower()
            if any(k in blob for k in KEYWORDS):
                hits += 1
                print(f"\n  CATEGORY : {cat}")
                print(f"  SUBCAT   : {a.get('SUBCATNAME','-')}")
                print(f"  COMPANY  : {str(a.get('SLONGNAME','?'))[:40]}")
                print(f"  SCRIP    : {a.get('SCRIP_CD','?')}")
                print(f"  DATE     : {str(a.get('NEWS_DT',''))[:16]}")
                print(f"  HEADLINE : {str(a.get('HEADLINE',''))[:110]}")
                if hits >= 8:
                    break
        if hits >= 8:
            break
    if hits == 0:
        print("  none found in the current announcement feed")

    print()
    print("=" * 64)
    print("B. ALL SUBCATNAME values in 'Company Update' (where OFS would sit)")
    print("=" * 64)
    try:
        d = b.announcements(category="Company Update")
        if isinstance(d, dict):
            d = d.get("Table", [])
        subs = {}
        for a in d:
            s = str(a.get("SUBCATNAME", "")).strip() or "(blank)"
            subs[s] = subs.get(s, 0) + 1
        for s, c in sorted(subs.items(), key=lambda x: -x[1]):
            print(f"  {c:4d}  {s}")
    except Exception as e:
        print("  error:", e)

    print()
    print("=" * 64)
    print("C. BUYBACK via purpose code P6 (+/- 90 days)")
    print("=" * 64)
    try:
        bb = b.actions(by_date="record", from_date=wide_from,
                       to_date=wide_to, purpose_code="P6")
        print(f"  found {len(bb)}")
        for a in bb[:6]:
            print(f"    {str(a.get('long_name','?'))[:35]:36} RD {a.get('RD_Date','?')}  {str(a.get('Purpose',''))[:40]}")
    except Exception as e:
        print("  error:", e)

    print()
    print("=" * 64)
    print("D. ALL corp-action purposes (+/- 90 days, non-dividend)")
    print("=" * 64)
    try:
        acts = b.actions(by_date="record", from_date=wide_from, to_date=wide_to)
        print(f"  total actions: {len(acts)}")
        kinds = {}
        for a in acts:
            p = str(a.get("Purpose", ""))
            if "dividend" in p.lower():
                continue
            key = p.split("-")[0].strip()[:45]
            kinds[key] = kinds.get(key, 0) + 1
        for k, c in sorted(kinds.items(), key=lambda x: -x[1]):
            print(f"    {c:4d}  {k}")
        if not kinds:
            print("    (only dividends in this window)")
    except Exception as e:
        print("  error:", e)
