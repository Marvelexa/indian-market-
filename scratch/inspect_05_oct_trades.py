import csv

with open('october_2026_all_trades.csv') as f:
    reader = csv.DictReader(f)
    trades = [t for t in reader if t['date'] == '2026-10-05']

print(f"Total trades on 2026-10-05: {len(trades)}")
for i, t in enumerate(trades, 1):
    pnl = float(t['netPnlInr'])
    print(f"#{i:02d} | Time: {t['time']} | Sym: {t['symbol']:<10} | Side: {t['side']:<4} | Opt: {t['isOption']} {t['optionType']} | PnL: INR {pnl:>+8.2f} | Reason: {t['exitReason']} | Badge: {t['exitBadge']}")
