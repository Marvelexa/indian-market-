import sys, os
sys.path.insert(0, os.path.abspath("."))
import json
from backend.replay_engine import IndianPastDateReplayEngine

for test_date in ["2026-11-13", "2026-11-06", "2026-11-02"]:
    engine = IndianPastDateReplayEngine()
    engine.set_date(test_date)

    for sec in range(0, 22500, 5):
        engine.advance_seconds(5)

    print(f"=== {test_date} RESULT ===")
    print(f"Trades: {len(engine.closed_ledger)}")
    print(f"Balance: {engine.balance_inr}")
    print(f"Realized PnL: {engine.realized_pnl_inr}")
    for t in engine.closed_ledger:
        sym = t['symbol']
        side = t['side']
        en = t['entryPrice']
        ex = t['exitPrice']
        pnl = t['netPnlInr']
        reason = t['exitReason']
        badge = t.get('exitBadgeLabel', '')
        print(f"  {sym:12} {side:4} En: {en:8.2f} Ex: {ex:8.2f} PnL: {pnl:+8.1f} | Reason: {reason} | Badge: {badge}")
    print()
