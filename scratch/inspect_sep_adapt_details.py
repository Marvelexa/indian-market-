import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from scratch.test_adaptive_regime import AdaptiveDualRegimeEngine
from backend.replay_engine import TOTAL_DAY_SECONDS

def inspect_day(date_str):
    eng = AdaptiveDualRegimeEngine()
    eng.set_date(date_str, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng.advance_seconds(5)
    st = eng.get_state()
    print(f"\n=== ADAPT on {date_str} (PnL: {st['wallet']['realizedPnlInr']}) ===")
    for t in eng.closed_ledger:
        print(f"  {t['symbol']:<10} {t['side']:<4} | Type: {t['seatBucket'][:12]} | Entry: {t['entryPrice']} | Exit: {t['exitPrice']} | PnL: {t['netPnlInr']:>8.2f} | Reason: {t['exitReason']}")

for d in ["2026-09-01", "2026-09-03", "2026-09-16", "2026-09-17", "2026-09-22"]:
    inspect_day(d)
