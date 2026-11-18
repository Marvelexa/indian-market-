import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scratch.test_30_percent_roadmap import Target30PctReplayEngine, TOTAL_DAY_SECONDS

def run_test(lots, open_runner, label):
    eng = Target30PctReplayEngine(index_lots=lots, daily_circuit_limit=-2500.0, allow_open_runner=open_runner)
    oct_dates = [d for d in eng.sorted_dates if "-10-" in d]

    total_pnl = 0.0
    total_trades = 0
    total_wins = 0

    for d in oct_dates:
        eng.set_date(d, auto_play=True)
        eng.is_running = True
        for _ in range(TOTAL_DAY_SECONDS // 5):
            eng.advance_seconds(5)
        st = eng.get_state()
        w = st['wallet']
        total_pnl += w['realizedPnlInr']
        total_trades += w['totalTrades']
        total_wins += w['wins']

    wr = total_wins / max(1, total_trades) * 100.0
    ret_pct = total_pnl / 100000.0 * 100.0
    print(f"{label:<40} | Net PnL: ₹{total_pnl:>10,.2f} ({ret_pct:>+5.1f}%) | Trades: {total_trades:>3} | WR: {wr:>5.1f}%")

print("October 20-Day Simulations for 30% Return Target:")
run_test(1, False, "Option A: 1-Lot Standard Ladder")
run_test(2, False, "Option B: 2-Lot Standard Ladder (Fixed 3K)")
run_test(2, True,  "Option C: 2-Lot Scaled + Open Super Runner")
