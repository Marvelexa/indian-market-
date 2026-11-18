import sys
sys.path.append('scratch')
from test_scaled_performance import res_df

print("\n--- WHAT IF COPPER IS EXCLUDED? ---")
no_copper = res_df[res_df['symbol'] != 'COPPER']
for d, sub in no_copper.groupby('date'):
    wins = sub[sub['pnl'] > 0]
    losses = sub[sub['pnl'] < 0]
    gp = wins['pnl'].sum()
    gl = losses['pnl'].sum()
    net = sub['pnl'].sum()
    wr = len(wins) / len(sub) * 100 if len(sub) else 0
    print(f"{d:<12} | Trades: {len(sub):<3} | Wins: {len(wins):<2} | Losses: {len(losses):<2} | WinRate: {wr:>5.1f}% | Net P&L: ₹{net:>+11,.2f}")

days = no_copper['date'].nunique()
tot = no_copper['pnl'].sum()
print("="*65)
print(f"TOTAL NET PROFIT WITHOUT COPPER: ₹{tot:+,.2f}")
print(f"AVERAGE PROFIT PER DAY: ₹{tot/days:+,.2f} / day")
print("="*65)
