import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS

eng = IndianPastDateReplayEngine()

loss_by_time = {}
loss_by_sym = {}
loss_by_reason = {}

for d in eng.sorted_dates:
    eng.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng.advance_seconds(5)
    for t in eng.closed_ledger:
        if t['netPnlInr'] < 0:
            sym = t['symbol']
            entry_time = t['entryTimeFormatted'].split(':')[0] # hour e.g. "10", "11", "12", "01", "02"
            reason = t['exitReason']

            loss_by_time[entry_time] = loss_by_time.get(entry_time, 0.0) + abs(t['netPnlInr'])
            loss_by_sym[sym] = loss_by_sym.get(sym, 0.0) + abs(t['netPnlInr'])
            loss_by_reason[reason] = loss_by_reason.get(reason, 0.0) + abs(t['netPnlInr'])

print("=== LOSS BY ENTRY HOUR ===")
for h, l in sorted(loss_by_time.items()):
    print(f"  Hour {h}: INR {l:,.2f}")

print("\n=== LOSS BY SYMBOL ===")
for s, l in sorted(loss_by_sym.items(), key=lambda x: x[1], reverse=True):
    print(f"  {s:<12}: INR {l:,.2f}")

print("\n=== LOSS BY EXIT REASON ===")
for r, l in sorted(loss_by_reason.items(), key=lambda x: x[1], reverse=True):
    print(f"  {r:<25}: INR {l:,.2f}")
