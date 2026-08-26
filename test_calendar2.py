"""Check non-dividend corp actions + new listings"""
from bse import BSE
from datetime import datetime, timedelta

today = datetime.now()
future = today + timedelta(days=60)

with BSE(download_folder="/tmp/") as b:

    print("=" * 60)
    print("NON-DIVIDEND CORPORATE ACTIONS (next 60 days)")
    print("=" * 60)
    acts = b.actions(by_date="record", from_date=today, to_date=future)
    print(f"Total actions: {len(acts)}")

    nondiv = [a for a in acts if "dividend" not in str(a.get("Purpose", "")).lower()]
    print(f"Non-dividend: {len(nondiv)}\n")

    seen = set()
    for a in nondiv:
        p = str(a.get("Purpose", ""))
        key = p.split("-")[0].strip()
        if key not in seen:
            seen.add(key)
            print(f"  [{key}]")
            print(f"     {a.get('long_name','?')[:35]} | RD: {a.get('RD_Date','?')} | {p[:50]}")

    print()
    print("=" * 60)
    print("NEW LISTINGS (announcements)")
    print("=" * 60)
    try:
        nl = b.announcements(category="New Listing")
        if isinstance(nl, dict):
            nl = nl.get("Table", [])
        print(f"Total: {len(nl)}")
        for n in nl[:5]:
            print(" ", str(n.get("SLONGNAME", "?"))[:35], "|", n.get("NEWS_DT", "?")[:10])
            print("     ", str(n.get("HEADLINE", ""))[:80])
    except Exception as e:
        print("ERROR:", e)
