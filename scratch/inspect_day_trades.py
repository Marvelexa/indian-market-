import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.replay_engine import IndianPastDateReplayEngine

engine = IndianPastDateReplayEngine()
print(f"Loaded {len(engine.sorted_dates)} dates.")

# Test on 2026-11-04 (user's screenshot date)
engine.set_date("2026-11-04", auto_play=False)

# Step through whole day
for sec in range(0, 22500, 5):
    engine.second_of_day = sec
    engine.update_session_gate()
    engine.compute_intra_second_prices()
    engine.evaluate_active_positions_tick()
    if sec % 300 == 0:
        engine.evaluate_seat_signals()

print(f"\nResults for 2026-11-13:")
print(f"Total Trades: {len(engine.closed_ledger)}")
print(f"Realized PnL: ₹{engine.realized_pnl_inr}")
for t in engine.closed_ledger:
    print(f"  {t['symbol']} {t['side']} Entry: ₹{t['entryPrice']} -> Exit: ₹{t['exitPrice']} | PnL: ₹{t['netPnlInr']} ({t['exitReason']})")
