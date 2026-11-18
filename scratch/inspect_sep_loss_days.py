import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from scratch.test_adaptive_regime import AdaptiveDualRegimeEngine
from backend.replay_engine import TOTAL_DAY_SECONDS

eng = AdaptiveDualRegimeEngine()
for d in ["2026-09-01", "2026-09-03", "2026-09-16", "2026-09-17"]:
    eng.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng.advance_seconds(5)
    st = eng.get_state()
    w = st['wallet']
    print(f"\n=== {d} (PnL: INR {w['realizedPnlInr']:,.2f}) ===")
    for t in eng.closed_ledger:
        print(f"  {t['symbol']:<10} | Side: {t['side']:<4} | Type: {t.get('seatBucket',''):<25} | Reason: {t.get('exitReason',''):<20} | PnL: INR {t.get('netPnlInr', t.get('pnlInr',0)):>8,.2f}")
