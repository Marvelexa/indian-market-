import json

with open('october_2026_audit_summary.json', 'r') as f:
    data = json.load(f)

meta = data['meta']
days = data['dailyPerformance']

print(f"Meta: {meta}")
balance = 100000.0
for d in days:
    balance += d['netPnlInr']
    day_roe = (d['netPnlInr'] / 100000.0) * 100.0
    cum_roe = ((balance - 100000.0) / 100000.0) * 100.0
    sign = "+" if d['netPnlInr'] >= 0 else ""
    print(f"{d['date']} | {d['weekday'][:3]} | NIFTY {d['niftyChangePct']:>+5.2f}% | Trades: {d['trades']:>2} | Wins: {d['wins']:>2} | Net PnL: {sign}₹{d['netPnlInr']:>9,.2f} ({day_roe:>+5.2f}%) | Balance: ₹{balance:>10,.2f} (Cum ROE: {cum_roe:>+5.2f}%)")
