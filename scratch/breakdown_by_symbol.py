import pandas as pd
import sys
sys.path.append('scratch')
from test_scaled_performance import res_df

print("\n" + "="*85)
print("PERFORMANCE BREAKDOWN BY COMMODITY (4-DAY TOTAL)")
print("="*85)
for sym, sub in res_df.groupby('symbol'):
    wins = sub[sub['pnl'] > 0]
    losses = sub[sub['pnl'] < 0]
    gp = wins['pnl'].sum()
    gl = losses['pnl'].sum()
    net = sub['pnl'].sum()
    wr = len(wins) / len(sub) * 100 if len(sub) else 0
    print(f"{sym:<12} | Trades: {len(sub):<3} | Wins: {len(wins):<3} | Losses: {len(losses):<3} | WinRate: {wr:>5.1f}% | Gross Win: +₹{gp:>10,.2f} | Gross Loss: ₹{gl:>10,.2f} | Net P&L: ₹{net:>+10,.2f}")

print("="*85)
