import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS

eng = IndianPastDateReplayEngine()

max_losses = []
for d in eng.sorted_dates:
    eng.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng.advance_seconds(5)
    for t in eng.closed_ledger:
        if t['exitReason'] == 'MAX_LOSS_CAP_HIT':
            max_losses.append((d, t))

print(f"Total MAX_LOSS_CAP_HIT trades: {len(max_losses)}")
for d, t in max_losses:
    print(f"{d} | {t['symbol']:<10} | {t['side']:<4} | {t['entryTimeFormatted']} -> {t['exitTimeFormatted']} | PnL: INR {t['netPnlInr']:,.2f}")
