import csv

with open('october_2026_all_trades.csv') as f:
    reader = csv.DictReader(f)
    trades = list(reader)

def print_day_trades(date_str):
    day_trades = [t for t in trades if t['date'] == date_str]
    print(f"\n================ TRADES FOR {date_str} (Total: {len(day_trades)}) ================")
    for t in day_trades:
        print(f"Time: {t['time']} | {t['symbol']:<10} | {t['side']:<4} | Option: {t['isOption']} {t['optionType']} | PnL: INR {float(t['netPnlInr']):>+8.2f} | Reason: {t['exitReason']}")

print_day_trades("2026-10-15")
print_day_trades("2026-10-12")
print_day_trades("2026-10-05")
print_day_trades("2026-10-26")
