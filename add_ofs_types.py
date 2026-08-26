"""
add_ofs_types.py - teaches the calendar UI about OFS / IPO / buyback.

Run on VM1:
    cd /home/ubuntu/bse-website
    python3 add_ofs_types.py
"""

import shutil
import sys

PATH = "index.html"
with open(PATH, "r", encoding="utf-8") as f:
    html = f.read()

shutil.copy(PATH, PATH + ".bak2")
print("Backup: index.html.bak2")

OLD_TYPES = """var CAL_TYPES = {
  result:   { label: 'Results',      color: '#d97706' },
  dividend: { label: 'Dividend',     color: '#16a34a' },
  bonus:    { label: 'Bonus',        color: '#3b82f6' },
  rights:   { label: 'Rights',       color: '#a855f7' },
  split:    { label: 'Split',        color: '#14b8a6' },
  buyback:  { label: 'Buyback',      color: '#ec4899' },
  listing:  { label: 'New listing',  color: '#f97316' },
  corp_action: { label: 'Other',     color: '#64748b' }
};
var CAL_ORDER = ['result','listing','bonus','rights','split','buyback','dividend','corp_action'];"""

NEW_TYPES = """var CAL_TYPES = {
  ofs:      { label: 'OFS',          color: '#dc2626' },
  ipo:      { label: 'IPO',          color: '#f59e0b' },
  buyback:  { label: 'Buyback',      color: '#ec4899' },
  result:   { label: 'Results',      color: '#d97706' },
  listing:  { label: 'New listing',  color: '#f97316' },
  bonus:    { label: 'Bonus',        color: '#3b82f6' },
  rights:   { label: 'Rights',       color: '#a855f7' },
  split:    { label: 'Split',        color: '#14b8a6' },
  dividend: { label: 'Dividend',     color: '#16a34a' },
  corp_action: { label: 'Other',     color: '#64748b' }
};
var CAL_ORDER = ['ofs','ipo','buyback','listing','bonus','rights','split','result','dividend','corp_action'];"""

if OLD_TYPES not in html:
    print("\nFAILED: could not find CAL_TYPES block.")
    print("Did add_calendar.py run successfully? Nothing written.")
    sys.exit(1)

html = html.replace(OLD_TYPES, NEW_TYPES, 1)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(html)

print("Done - OFS, IPO added; ordering updated so rare events sort first.")
