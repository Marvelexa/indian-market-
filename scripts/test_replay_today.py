import sys
import os
sys.path.insert(0, r"d:\new start")

from backend.replay_engine import IndianPastDateReplayEngine

engine = IndianPastDateReplayEngine.get_instance()
print(f"Total indexed days: {len(engine.sorted_dates)}")
print(f"Last 5 days: {engine.sorted_dates[-5:]}")

# Test setting date to 2026-11-16
target = "2026-11-16"
if target in engine.sorted_dates:
    print(f"\nSetting date to {target}...")
    engine.set_date(target, auto_play=True, speed=300)
    print(f"Current Date: {engine.current_date}")
    print(f"Day Open Prices: {engine.day_open_prices}")
    print(f"Opening Ranges: {engine.opening_ranges.get('NIFTY')}, {engine.opening_ranges.get('BANKNIFTY')}")

    # Advance through the whole day (22500 seconds)
    print("\nSimulating full day advance...")
    while engine.second_of_day < 22500 and engine.is_running:
        engine.advance_seconds(300) # 5 min step

    print("\n=== REPLAY COMPLETED ===")
    print(f"Final Session Gate: {engine.session_gate}")
    print(f"Realized PnL: ₹{engine.realized_pnl_inr:,.2f}")
    print(f"Total Closed Trades: {len(engine.closed_ledger)}")
    print(f"Active Positions: {len(engine.active_positions)}")

    print("\nClosed Trades Ledger:")
    print("-" * 105)
    print(f"{'Time':<9} {'Symbol':<12} {'Side':<6} {'Seat':<28} {'Entry':<9} {'Exit':<9} {'Net PnL (₹)':<12} {'Exit Reason'}")
    print("-" * 105)
    for t in reversed(engine.closed_ledger):
        print(f"{t['entryTimeFormatted']:<9} {t['symbol']:<12} {t['side']:<6} {t['seatBucket']:<28} ₹{t['entryPrice']:<8.2f} ₹{t['exitPrice']:<8.2f} {t['netPnlInr']:<12.2f} {t['exitReason']}")
    print("-" * 105)
else:
    print(f"Target {target} NOT in sorted dates!")
