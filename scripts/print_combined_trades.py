all_trades = [
    {'time': '09:35 AM', 'sym': 'BANKNIFTY 26NOV ATM CE', 'type': 'Index', 'act': 'BUY CE', 'exit_time': '10:02 AM', 'pnl': 3535.00, 'reason': 'TP 6 Trailed (+₹4,500 Hit / Lock 3.6K)'},
    {'time': '09:35 AM', 'sym': 'NIFTY 26NOV ATM CE', 'type': 'Index', 'act': 'BUY CE', 'exit_time': '10:01 AM', 'pnl': 634.90, 'reason': 'TP 2 Locked (+₹700 Lock)'},
    {'time': '09:45 AM', 'sym': 'HDFCBANK 26NOV 810 CE', 'type': 'Stock', 'act': 'BUY CE', 'exit_time': '02:00 PM', 'pnl': 1338.00, 'reason': 'Stage 3 Locked (+₹1,400 Lock)'},
    {'time': '10:00 AM', 'sym': 'LT 26NOV 4150 PE', 'type': 'Stock', 'act': 'BUY PE', 'exit_time': '11:00 AM', 'pnl': 1338.00, 'reason': 'Stage 3 Locked (+₹1,400 Lock)'},
    {'time': '10:00 AM', 'sym': 'ICICIBANK 26NOV 1590 CE', 'type': 'Stock', 'act': 'BUY CE', 'exit_time': '01:45 PM', 'pnl': 88.00, 'reason': 'TP 1 Locked (+₹150 Risk-Free Exit)'},
    {'time': '11:00 AM', 'sym': 'RELIANCE 26NOV 1340 PE', 'type': 'Stock', 'act': 'BUY PE', 'exit_time': '11:30 AM', 'pnl': 112.62, 'reason': 'Safe Profit Booking'},
    {'time': '11:30 AM', 'sym': 'TCS 26NOV 2400 PE', 'type': 'Stock', 'act': 'BUY PE', 'exit_time': '02:00 PM', 'pnl': 172.85, 'reason': 'Safe Profit Booking'},
    {'time': '12:05 PM', 'sym': 'BANKNIFTY 26NOV ATM CE', 'type': 'Index', 'act': 'BUY CE', 'exit_time': '12:14 PM', 'pnl': 1085.02, 'reason': 'TP 3 Locked (+₹1,150 Lock)'},
    {'time': '12:05 PM', 'sym': 'NIFTY 26NOV ATM CE', 'type': 'Index', 'act': 'BUY CE', 'exit_time': '12:14 PM', 'pnl': 235.00, 'reason': 'TP 1 Locked (+₹300 Lock)'},
    {'time': '12:45 PM', 'sym': 'BANKNIFTY 26NOV ATM CE', 'type': 'Index', 'act': 'BUY CE', 'exit_time': '12:59 PM', 'pnl': 235.06, 'reason': 'TP 1 Locked (+₹300 Lock)'},
    {'time': '12:45 PM', 'sym': 'NIFTY 26NOV ATM CE', 'type': 'Index', 'act': 'BUY CE', 'exit_time': '03:18 PM', 'pnl': -1418.00, 'reason': '03:18 PM EOD Square-Off (Dip Survived)'},
    {'time': '01:45 PM', 'sym': 'BAJFINANCE 26NOV 1100 PE', 'type': 'Stock', 'act': 'BUY PE', 'exit_time': '03:00 PM', 'pnl': 12.25, 'reason': 'Safe Profit Booking'},
    {'time': '02:00 PM', 'sym': 'LT 26NOV 4120 PE', 'type': 'Stock', 'act': 'BUY PE', 'exit_time': '03:18 PM', 'pnl': -499.25, 'reason': '03:18 PM EOD Square-Off'},
    {'time': '02:40 PM', 'sym': 'BANKNIFTY 26NOV ATM PE', 'type': 'Index', 'act': 'BUY PE', 'exit_time': '02:44 PM', 'pnl': 235.06, 'reason': 'TP 1 Locked (+₹300 Lock)'}
]

import datetime
all_trades.sort(key=lambda x: datetime.datetime.strptime(x['time'], '%I:%M %p'))

print("=" * 115)
print("  AAJ (16-NOV-2026) KA COMBINED MASTER ORDER BOOK: INDEX OPTIONS + TOP 50 STOCK OPTIONS")
print("=" * 115)
print(f"{'#':<3} {'Time':<10} {'Contract / Underlying':<26} {'Type':<8} {'Action':<8} {'Net P&L (₹)':<14} {'Running P&L':<14} {'Exit Reason'}")
print("-" * 115)

running = 0.0
for idx, t in enumerate(all_trades):
    running += t['pnl']
    print(f"{idx+1:<3} {t['time']:<10} {t['sym']:<26} {t['type']:<8} {t['act']:<8} {t['pnl']:+11.2f}   {running:+12.2f}  {t['reason']}")

print("-" * 115)
print(f"🏆 GRAND TOTAL COMBINED ORIGINAL NET PROFIT: {running:+12.2f} INR (14 Trades: 12 Wins / 2 EOD Cuts)")
print("=" * 115)
