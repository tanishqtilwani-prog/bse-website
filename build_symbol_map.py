"""
build_symbol_map.py — Run ONCE on VM to generate bse_to_nse_symbol.csv

Uses BSE's lookup() API with each company's ISIN code to get both the
BSE scrip code and NSE symbol in one call — the most reliable approach
since ISIN is a globally unique identifier that works across exchanges.

Usage:
    cd /home/ubuntu/bse-website
    python3 build_symbol_map.py

Output:
    bse_to_nse_symbol.csv  (columns: bse_code, nse_symbol)

Then commit and push this file to the bse-website GitHub repo.
"""

import csv
import time
from bse import BSE

INPUT_CSV  = "ind_niftytotalmarket_list.csv"   # symbol, company_name, isin
OUTPUT_CSV = "bse_to_nse_symbol.csv"
RESUME_CSV = "bse_to_nse_symbol.csv"  # if exists, resumes from where it left off

def main():
    # Load master_companies.csv
    companies = []
    try:
        with open(INPUT_CSV, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                isin   = row.get('ISIN Code', '').strip()
                symbol = row.get('Symbol', '').strip()
                if isin and symbol:
                    companies.append({'isin': isin, 'nse_symbol': symbol})
    except Exception as e:
        print(f"Error reading {INPUT_CSV}: {e}")
        return

    print(f"Loaded {len(companies)} companies from {INPUT_CSV}")

    # Check if we can resume from a previous partial run
    existing = {}
    try:
        with open(RESUME_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('bse_code') and row.get('nse_symbol'):
                    existing[row['nse_symbol']] = row['bse_code']
        if existing:
            print(f"Resuming — {len(existing)} already mapped, skipping those")
    except FileNotFoundError:
        pass

    results = list(existing.items())  # (nse_symbol, bse_code) pairs already done
    errors  = []
    to_process = [c for c in companies if c['nse_symbol'] not in existing]
    print(f"Need to process: {len(to_process)} companies")
    print(f"Estimated time: ~{len(to_process) * 1.3 / 60:.0f} minutes\n")

    with BSE(download_folder="/tmp/") as bse:
        for i, company in enumerate(to_process):
            isin       = company['isin']
            nse_symbol = company['nse_symbol']
            try:
                result = bse.lookup(isin)
                if result and result.get('bse_code'):
                    bse_code = str(result['bse_code']).strip()
                    results.append((nse_symbol, bse_code))
                else:
                    errors.append({'symbol': nse_symbol, 'isin': isin, 'error': 'lookup returned None or no bse_code'})

                if (i + 1) % 100 == 0:
                    print(f"  {i+1}/{len(to_process)} done ({len(errors)} errors)...")
                    # Save progress every 100 to allow safe resume
                    _save(results, OUTPUT_CSV)

                time.sleep(1.0)  # stay within BSE rate limits

            except Exception as e:
                errors.append({'symbol': nse_symbol, 'isin': isin, 'error': str(e)})
                if (i + 1) % 10 == 0:
                    print(f"  Error for {nse_symbol}: {e}")
                time.sleep(2)

    _save(results, OUTPUT_CSV)

    print(f"\n✅ Done!")
    print(f"   Mapped:  {len(results)} → {OUTPUT_CSV}")
    print(f"   Errors:  {len(errors)} (BSE-only or delisted companies)")
    if errors:
        print(f"\nFirst 10 failures:")
        for e in errors[:10]:
            print(f"  {e['symbol']} ({e['isin']}): {e['error']}")

def _save(results, path):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['bse_code', 'nse_symbol'])
        for nse_symbol, bse_code in results:
            writer.writerow([bse_code, nse_symbol])

if __name__ == "__main__":
    main()
