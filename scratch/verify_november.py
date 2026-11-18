import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import backend.replay_engine as r

eng = r.IndianPastDateReplayEngine()
nov_dates = [d for d in eng.sorted_dates if "-11-" in d]

print(f"November Dates Verification ({len(nov_dates)} days):")
for d in nov_dates:
    eng.set_date(d, auto_play=True)
    for _ in range(r.TOTAL_DAY_SECONDS // 5):
        eng.advance_seconds(5)
    st = eng.get_state()
    w = st['wallet']
    pnl = w['realizedPnlInr']
    trades = w['totalTrades']
    wins = w['wins']
    wr = (wins / max(1, trades)) * 100.0
    print(f"{d} | Net PnL: INR {pnl:>8,.2f} | Trades: {trades:>2} (W: {wins:>2}) | WR: {wr:>5.1f}%")
