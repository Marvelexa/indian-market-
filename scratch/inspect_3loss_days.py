import csv

with open('october_2026_all_trades.csv') as f:
    trades = list(csv.DictReader(f))

def print_days(date_list):
    for d in date_list:
        d_trades = [t for t in trades if t['date'] == d]
        print(f"\n==================== {d} (Total: {len(d_trades)}) ====================")
        for t in d_trades:
            print(f"Time: {t['time']} | Sym: {t['symbol']:<10} | Side: {t['side']:<4} | Opt: {t['isOption']} {t['optionType']} | PnL: INR {float(t['netPnlInr']):>+8.2f} | Reason: {t['exitReason']}")

print_days(['2026-10-26', '2026-10-27', '2026-10-28'])
