import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS

eng = IndianPastDateReplayEngine()

def run_month(month_str, month_name):
    dates = [d for d in eng.sorted_dates if f"-{month_str}-" in d]
    tot_pnl = 0.0
    tot_trades = 0
    tot_wins = 0
    win_days = 0
    for d in dates:
        eng.set_date(d, auto_play=True)
        for _ in range(TOTAL_DAY_SECONDS // 5):
            eng.advance_seconds(5)
        st = eng.get_state()
        w = st['wallet']
        pnl = w['realizedPnlInr']
        tot_pnl += pnl
        tot_trades += w['totalTrades']
        tot_wins += w['wins']
        if pnl > 0: win_days += 1
    
    wr = (tot_wins / max(1, tot_trades)) * 100.0
    ret_pct = (tot_pnl / 100000.0) * 100.0
    roe_margin = (tot_pnl / 25000.0) * 100.0
    print(f"\n==================== {month_name.upper()} 2026 ({len(dates)} TRADING DAYS) ====================")
    print(f"Net Realized PnL:        +INR {tot_pnl:>10,.2f}" if tot_pnl >= 0 else f"Net Realized PnL:        -INR {abs(tot_pnl):>10,.2f}")
    print(f"Monthly Return (1L Base): {ret_pct:>+6.2f}%")
    print(f"ROE on Deployed Margin:  {roe_margin:>+6.2f}%")
    print(f"Win Rate:                 {wr:>5.1f}% ({tot_wins} Wins / {tot_trades - tot_wins} Losses)")
    print(f"Profitable Trading Days:  {win_days} / {len(dates)} ({win_days / len(dates) * 100:.1f}%)")

run_month("09", "September")
run_month("10", "October")
run_month("11", "November (1 to 13 Nov)")
