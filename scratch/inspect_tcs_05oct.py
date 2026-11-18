import csv
import json

with open('october_2026_all_trades.csv') as f:
    trades = [t for t in csv.DictReader(f) if t['date'] == '2026-10-05']

print(f"Total 05 Oct Trades: {len(trades)}\n")
for t in trades:
    print(f"Sym: {t['symbol']:<10} | Side: {t['side']:<4} | Entry: {t['entryPrice']:<8} | Exit: {t['exitPrice']:<8} | Time: {t['time']} | PnL: INR {float(t['netPnlInr']):>+8.2f} | Reason: {t['exitReason']}")
