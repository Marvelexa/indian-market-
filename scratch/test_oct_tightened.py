import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scratch.test_tightened_cap import EquityTightenedEngine, TOTAL_DAY_SECONDS

eng = EquityTightenedEngine()
oct_dates = [d for d in eng.sorted_dates if "-10-" in d]

tot_pnl = 0.0
tot_trades = 0
tot_wins = 0
win_days = 0

for d in oct_dates:
    eng.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng.advance_seconds(5)
    st = eng.get_state()
    w = st['wallet']
    pnl = w['realizedPnlInr']
    trades = w['totalTrades']
    wins = w['wins']
    tot_pnl += pnl
    tot_trades += trades
    tot_wins += wins
    if pnl > 0: win_days += 1

wr = tot_wins / max(1, tot_trades) * 100.0
print(f"Whole October with Equity Loss Cap -INR 750:")
print(f"Total Net PnL: INR {tot_pnl:>10,.2f} ({tot_pnl/1000:>+5.2f}% on 1 Lakh)")
print(f"Win Rate:      {wr:>5.1f}% ({tot_wins}W / {tot_trades-tot_wins}L)")
print(f"Win Days:      {win_days} / 20 ({win_days/20*100:.1f}%)")
