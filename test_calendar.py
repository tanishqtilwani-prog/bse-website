"""Test what calendar data BSE gives us"""
from bse import BSE
from datetime import datetime, timedelta
import json

today = datetime.now()
future = today + timedelta(days=30)

with BSE(download_folder="/tmp/") as b:

    print("=" * 60)
    print("1. RESULT CALENDAR (next 30 days)")
    print("=" * 60)
    try:
        res = b.resultCalendar(from_date=today, to_date=future)
        print(f"Total: {len(res)}")
        if res:
            print("\nSample record (all fields):")
            print(json.dumps(res[0], indent=2)[:800])
            print("\nFirst 5:")
            for r in res[:5]:
                print(" ", r.get("Long_Name", "?")[:35], "|", r.get("meeting_date", "?"))
    except Exception as e:
        print("ERROR:", e)

    print()
    print("=" * 60)
    print("2. CORPORATE ACTIONS by RECORD DATE (next 30 days)")
    print("=" * 60)
    try:
        acts = b.actions(by_date="record", from_date=today, to_date=future)
        print(f"Total: {len(acts)}")
        if acts:
            print("\nSample record (all fields):")
            print(json.dumps(acts[0], indent=2)[:800])
            print("\nUnique purposes found:")
            purposes = {}
            for a in acts:
                p = a.get("Purpose", "?")
                purposes[p] = purposes.get(p, 0) + 1
            for p, c in sorted(purposes.items(), key=lambda x: -x[1])[:15]:
                print(f"  {c:4d}  {p[:60]}")
    except Exception as e:
        print("ERROR:", e)
