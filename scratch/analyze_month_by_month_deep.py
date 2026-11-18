import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from backend.replay_engine import IndianPastDateReplayEngine, WHITELIST_14_SYMBOLS, INDEX_SET

eng = IndianPastDateReplayEngine()
print(f"Total Dates in DB: {len(eng.sorted_dates)}")
by_month = {}
for d in eng.sorted_dates:
    m = d[:7]
    by_month.setdefault(m, []).append(d)

for m, dates in sorted(by_month.items()):
    print(f"Month {m}: {len(dates)} days ({dates[0]} to {dates[-1]})")

# Let's inspect index range vs equity range across months
for m, dates in sorted(by_month.items()):
    nifty_ranges = []
    bank_ranges = []
    for d in dates:
        bars = eng.by_date_5m.get(d, {})
        n_bars = bars.get("NIFTY", [])
        if n_bars:
            h = max(float(b["high"]) for b in n_bars)
            l = min(float(b["low"]) for b in n_bars)
            nifty_ranges.append(h - l)
        b_bars = bars.get("BANKNIFTY", [])
        if b_bars:
            h = max(float(b["high"]) for b in b_bars)
            l = min(float(b["low"]) for b in b_bars)
            bank_ranges.append(h - l)
    
    avg_n = sum(nifty_ranges)/len(nifty_ranges) if nifty_ranges else 0
    avg_b = sum(bank_ranges)/len(bank_ranges) if bank_ranges else 0
    print(f"{m} -> Avg Nifty Range: {avg_n:.1f} pts, Avg BankNifty Range: {avg_b:.1f} pts")
