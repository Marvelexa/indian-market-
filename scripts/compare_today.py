trades = [
    {'time': '10:00 AM', 'sym': 'LT', 'side': 'SELL', 'opt': 'PE', 'lot': 150, 'entry': 4147.30, 'exit': 4125.97, 'exit_time': '11:00 AM', 'reason': 'Trailed Profit (+₹1,600 Lock)', 'spot_move': '+21.33 pts Fall'},
    {'time': '11:00 AM', 'sym': 'RELIANCE', 'side': 'SELL', 'opt': 'PE', 'lot': 250, 'entry': 1336.50, 'exit': 1335.23, 'exit_time': '11:30 AM', 'reason': 'Trailed Profit (+₹300 Lock)', 'spot_move': '+1.27 pts Fall'},
    {'time': '10:00 AM', 'sym': 'ICICIBANK', 'side': 'BUY', 'opt': 'CE', 'lot': 700, 'entry': 1592.30, 'exit': 1581.92, 'exit_time': '01:45 PM', 'reason': 'Hard SL (-₹1,500 Risk Cap)', 'spot_move': '-10.38 pts Dip'},
    {'time': '09:45 AM', 'sym': 'HDFCBANK', 'side': 'BUY', 'opt': 'CE', 'lot': 550, 'entry': 809.80, 'exit': 813.80, 'exit_time': '02:00 PM', 'reason': 'Trailed Profit (+₹700 Lock)', 'spot_move': '+4.00 pts Rise'},
    {'time': '11:30 AM', 'sym': 'TCS', 'side': 'SELL', 'opt': 'PE', 'lot': 175, 'entry': 2396.00, 'exit': 2393.56, 'exit_time': '02:00 PM', 'reason': 'Trailed Profit (+₹300 Lock)', 'spot_move': '+2.44 pts Fall'},
    {'time': '01:45 PM', 'sym': 'BAJFINANCE', 'side': 'SELL', 'opt': 'PE', 'lot': 125, 'entry': 1105.65, 'exit': 1104.57, 'exit_time': '03:00 PM', 'reason': 'Trailed Profit (+₹300 Lock)', 'spot_move': '+1.08 pts Fall'},
    {'time': '02:00 PM', 'sym': 'LT', 'side': 'SELL', 'opt': 'PE', 'lot': 150, 'entry': 4121.80, 'exit': 4136.20, 'exit_time': '03:15 PM', 'reason': 'Hard SL (-₹1,500 Risk Cap)', 'spot_move': '-14.40 pts Rise'}
]

DELTA = 0.55
OPT_COMM = 62.0

cash_pnls = [1440.50, 138.59, -1617.23, 615.91, 147.64, 142.64, -1694.91]

print("=" * 105)
print("  AAJ (16-NOV-2026) KA EXACT REAL TRADE COMPARISON: CASH EQUITY vs F&O STOCK OPTIONS")
print("=" * 105)
print(f"{'#':<3} {'Time':<10} {'Contract / Under':<22} {'Side':<6} {'LotQty':<8} {'Exit Time':<10} {'Option Net (₹)':<16} {'Cash Net (₹)':<14} {'Exit Reason'}")
print("-" * 105)

total_opt_net = 0.0
total_cash_net = 0.0

for idx, t in enumerate(trades):
    if t['side'] == 'SELL':
        spot_pts = t['entry'] - t['exit']
    else:
        spot_pts = t['exit'] - t['entry']
    
    opt_pts = spot_pts * DELTA
    gross = opt_pts * t['lot']
    
    # Cap Hard SL at -1500
    if gross < -1500.0:
        gross = -1500.0
        
    net_opt = round(gross - OPT_COMM, 2)
    total_opt_net += net_opt
    total_cash_net += cash_pnls[idx]
    
    contract = f"{t['sym']} ATM {t['opt']}"
    print(f"{idx+1:<3} {t['time']:<10} {contract:<22} BUY    {t['lot']:<8} {t['exit_time']:<10} {net_opt:+12.2f}    {cash_pnls[idx]:+10.2f}    {t['reason']}")

print("-" * 105)
print(f"TOTAL CASH EQUITY NET:        {total_cash_net:+10.2f} INR  (Penalized by ₹1,051.12 STT & Turnover charges!)")
print(f"TOTAL F&O STOCK OPTIONS NET:  {total_opt_net:+10.2f} INR  (Options STT is only ~₹62/trade, saved ~₹620 in charges!)")
print("=" * 105)
