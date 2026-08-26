"""Check whether OFS notices live in BSE circulars."""
import inspect
from bse import BSE
from datetime import datetime, timedelta

print("=" * 64)
print("circulars() signature")
print("=" * 64)
print(inspect.getsource(BSE.circulars)[:1800])

today = datetime.now()
past = today - timedelta(days=20)

with BSE(download_folder="/tmp/") as b:
    print()
    print("=" * 64)
    print("CIRCULARS (last 20 days)")
    print("=" * 64)
    try:
        c = b.circulars(from_date=past, to_date=today)
        if isinstance(c, dict):
            for k in c.keys():
                print("  dict key:", k, "->", type(c[k]),
                      len(c[k]) if isinstance(c[k], list) else "")
            c = c.get("Table", c.get("Table1", []))
        print(f"  rows: {len(c)}")

        if c:
            print("\n  FIELDS AVAILABLE:")
            for k, v in c[0].items():
                print(f"    {k:22} = {str(v)[:60]}")

            print("\n  OFS / BUYBACK MATCHES:")
            n = 0
            for r in c:
                blob = " ".join(str(v) for v in r.values()).lower()
                if "offer for sale" in blob or "ofs" in blob or "buyback" in blob or "buy back" in blob:
                    n += 1
                    head = r.get("HEADLINE") or r.get("Subject") or r.get("CIRCULARNAME") or ""
                    dt = r.get("News_dt") or r.get("CIRCULARDATE") or r.get("NEWS_DT") or ""
                    print(f"    [{str(dt)[:16]}] {str(head)[:100]}")
                    if n >= 12:
                        break
            if n == 0:
                print("    none")

            print("\n  FIRST 5 CIRCULARS (any topic):")
            for r in c[:5]:
                head = r.get("HEADLINE") or r.get("Subject") or r.get("CIRCULARNAME") or "?"
                dt = r.get("News_dt") or r.get("CIRCULARDATE") or r.get("NEWS_DT") or "?"
                print(f"    [{str(dt)[:16]}] {str(head)[:100]}")
    except Exception as e:
        print("  ERROR:", e)
