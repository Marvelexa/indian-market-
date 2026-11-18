import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from scratch.test_adaptive_regime import AdaptiveDualRegimeEngine
from scratch.test_true_breakout import TrueBreakoutAntiChopEngine
from backend.replay_engine import TOTAL_DAY_SECONDS

def inspect_day(engine_cls, name, date_str):
    eng = engine_cls()
    eng.set_date(date_str, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng.advance_seconds(5)
    st = eng.get_state()
    print(f"=== {name} on {date_str} (PnL: {st['wallet']['realizedPnlInr']}) ===")
    for t in eng.closed_ledger:
        print(f"  {t['symbol']:<10} {t['side']:<4} | Entry: {t['entryPrice']} | Exit: {t['exitPrice']} | PnL: {t['netPnlInr']:>8.2f} | Reason: {t['exitReason']}")

inspect_day(AdaptiveDualRegimeEngine, "ADAPT", "2026-10-07")
inspect_day(TrueBreakoutAntiChopEngine, "TRUE_BREAKOUT", "2026-10-07")
