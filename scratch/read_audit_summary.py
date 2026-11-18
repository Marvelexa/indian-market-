import json

with open('scratch/real_60day_exact_audit.json') as f:
    data = json.load(f)

months = {}
for r in data:
    m = r['date'][:7]
    if m not in months:
        months[m] = {'days': 0, 'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0.0, 'green': 0, 'red': 0}
    months[m]['days'] += 1
    months[m]['trades'] += r['trades']
    months[m]['wins'] += r['wins']
    months[m]['losses'] += r['losses']
    months[m]['pnl'] += r['pnl']
    if r['pnl'] > 0:
        months[m]['green'] += 1
    else:
        months[m]['red'] += 1

print("=" * 80)
print(f"{'Month':<10} | {'Days':^5} | {'Green/Red':^10} | {'Trades':^7} | {'Wins':^5} | {'WR %':^6} | {'Net Real PnL':^14}")
print("=" * 80)
total_pnl = 0.0
for m, v in sorted(months.items()):
    wr = round((v['wins'] / v['trades']) * 100, 1) if v['trades'] > 0 else 0
    total_pnl += v['pnl']
    pnl_str = f"+INR {v['pnl']:,.2f}" if v['pnl'] >= 0 else f"-INR {abs(v['pnl']):,.2f}"
    print(f"{m:<10} | {v['days']:^5} | {v['green']}G / {v['red']}R    | {v['trades']:^7} | {v['wins']:^5} | {wr:>5.1f}% | {pnl_str:>14}")

print("=" * 80)
print(f"TOTAL 60 DAYS TRUE REALIZED P&L: INR {total_pnl:,.2f}")
