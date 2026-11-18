import pandas as pd
from test_scaled_performance import res_df

d16 = res_df[res_df['date'] == '2026-11-16']
print("Breakdown for 2026-11-16:")
for sym, sub in d16.groupby('symbol'):
    wins = sub[sub['pnl'] > 0]
    losses = sub[sub['pnl'] < 0]
    net = sub['pnl'].sum()
    print(f"  {sym:<12}: {len(sub)} trades | {len(wins)} wins | {len(losses)} losses | Net: ₹{net:>+10,.2f}")

print("\nAll trades on 2026-11-16:")
for idx, r in d16.iterrows():
    print(f"  [{r['entry_time']} -> {r['exit_time']}] {r['symbol']:<10} {r['action']:<4} | Entry ₹{r['entry_price']} -> Exit ₹{r['exit_price']} | PnL: ₹{r['pnl']:>+9.2f} | {r['reason']}")
