import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS

eng = IndianPastDateReplayEngine()

all_dates = eng.sorted_dates
print(f"Total available dates in database: {len(all_dates)} ({all_dates[0]} to {all_dates[-1]})\n")

monthly_stats = {}
balance = 100000.0

total_trades_all = 0
total_wins_all = 0
total_pnl_all = 0.0

for d in all_dates:
    month_key = d[:7] # YYYY-MM
    if month_key not in monthly_stats:
        monthly_stats[month_key] = {
            "tradingDays": 0,
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "netPnl": 0.0,
            "winDays": 0,
            "lossDays": 0
        }
    
    eng.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng.advance_seconds(5)
    
    st = eng.get_state()
    w = st['wallet']
    pnl = w['realizedPnlInr']
    trades = w['totalTrades']
    wins = w['wins']
    losses = trades - wins
    
    balance += pnl
    total_trades_all += trades
    total_wins_all += wins
    total_pnl_all += pnl
    
    ms = monthly_stats[month_key]
    ms["tradingDays"] += 1
    ms["trades"] += trades
    ms["wins"] += wins
    ms["losses"] += losses
    ms["netPnl"] += pnl
    if pnl > 0:
        ms["winDays"] += 1
    else:
        ms["lossDays"] += 1

print("=" * 85)
print(f"{'Month':<12} | {'Days':<5} | {'Trades':<8} | {'Wins':<6} | {'WR %':<7} | {'Win/Loss Days':<14} | {'Net PnL (INR)':<14} | {'Return %':<9}")
print("=" * 85)

for m, s in monthly_stats.items():
    wr = (s['wins'] / max(1, s['trades'])) * 100.0
    ret = (s['netPnl'] / 100000.0) * 100.0
    wl_days = f"{s['winDays']}W / {s['lossDays']}L"
    pnl_str = f"+INR {s['netPnl']:>10,.2f}" if s['netPnl'] >= 0 else f"-INR {abs(s['netPnl']):>10,.2f}"
    print(f"{m:<12} | {s['tradingDays']:<5} | {s['trades']:<8} | {s['wins']:<6} | {wr:>5.1f}% | {wl_days:<14} | {pnl_str:<14} | {ret:>+7.2f}%")

print("-" * 85)
overall_wr = (total_wins_all / max(1, total_trades_all)) * 100.0
overall_ret = (total_pnl_all / 100000.0) * 100.0
overall_roe_margin = (total_pnl_all / 25000.0) * 100.0

print(f"60-DAY TOTAL SUMMARY:")
print(f"Total Trading Days: {len(all_dates)}")
print(f"Total Trades:       {total_trades_all} ({total_wins_all} Wins / {total_trades_all - total_wins_all} Losses)")
print(f"Overall Win Rate:   {overall_wr:.1f}%")
print(f"Net Realized PnL:   INR {total_pnl_all:,.2f}")
print(f"Return on Base 1L:  {overall_ret:+.2f}%")
print(f"ROE on Margin (25k): {overall_roe_margin:+.2f}%")
print(f"Final Balance:      INR {balance:,.2f}")
