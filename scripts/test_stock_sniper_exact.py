# Let's run the 7 stock trades through the exact FoOptionSniperEngine ladder
trades = [
    {'time': '09:45 AM', 'sym': 'HDFCBANK', 'side': 'BUY', 'opt': 'CE', 'lot': 550, 'entry': 809.80, 'exit': 813.80, 'peak_spot': 817.50, 'exit_time': '02:00 PM'},
    {'time': '10:00 AM', 'sym': 'LT', 'side': 'SELL', 'opt': 'PE', 'lot': 150, 'entry': 4147.30, 'exit': 4125.97, 'peak_spot': 4118.00, 'exit_time': '11:00 AM'},
    {'time': '10:00 AM', 'sym': 'ICICIBANK', 'side': 'BUY', 'opt': 'CE', 'lot': 700, 'entry': 1592.30, 'exit': 1581.92, 'peak_spot': 1594.00, 'exit_time': '01:45 PM'},
    {'time': '11:00 AM', 'sym': 'RELIANCE', 'side': 'SELL', 'opt': 'PE', 'lot': 250, 'entry': 1336.50, 'exit': 1335.23, 'peak_spot': 1334.00, 'exit_time': '11:30 AM'},
    {'time': '11:30 AM', 'sym': 'TCS', 'side': 'SELL', 'opt': 'PE', 'lot': 175, 'entry': 2396.00, 'exit': 2393.56, 'peak_spot': 2391.00, 'exit_time': '02:00 PM'},
    {'time': '01:45 PM', 'sym': 'BAJFINANCE', 'side': 'SELL', 'opt': 'PE', 'lot': 125, 'entry': 1105.65, 'exit': 1104.57, 'peak_spot': 1102.00, 'exit_time': '03:00 PM'},
    {'time': '02:00 PM', 'sym': 'LT', 'side': 'SELL', 'opt': 'PE', 'lot': 150, 'entry': 4121.80, 'exit': 4127.10, 'peak_spot': 4118.60, 'exit_time': '03:18 PM'}
]

DELTA = 0.55
OPT_COMM = 62.0

print("=" * 105)
print("  EXACT STOCK OPTIONS UNDER NEW FO OPTION SNIPER LADDER (16-NOV-2026)")
print("=" * 105)

stock_closed = []
for t in trades:
    mult = t['lot'] * DELTA
    if t['side'] == 'BUY':
        peak_gain = (t['peak_spot'] - t['entry']) * mult
        cur_gain = (t['exit'] - t['entry']) * mult
    else:
        peak_gain = (t['entry'] - t['peak_spot']) * mult
        cur_gain = (t['entry'] - t['exit']) * mult
    
    # Ladder check
    locked = 0.0
    stage_name = "Base"
    if peak_gain >= 8000.0:
        locked = max(6500.0, peak_gain - 1000.0)
        stage_name = f"Runner Locked +₹{int(locked)}"
    elif peak_gain >= 4000.0:
        locked = 3000.0
        stage_name = "Stage 4 Locked +₹3,000"
    elif peak_gain >= 2000.0:
        locked = 1400.0
        stage_name = "Stage 3 Locked +₹1,400"
    elif peak_gain >= 1000.0:
        locked = 600.0
        stage_name = "TP2 Locked +₹600"
    elif peak_gain >= 500.0:
        locked = 150.0
        stage_name = "TP1 Locked +₹150 (Risk-Free)"
    
    if locked > 0.0:
        gross = locked
        reason = f"Trailed SL ({stage_name})"
    else:
        # Check if SL hit
        if cur_gain <= -2500.0:
            gross = -2500.0
            reason = "Hard SL Hit (-₹2,500 Cap)"
        else:
            gross = cur_gain
            reason = "03:18 PM Auto Square-Off"
            
    net = round(gross - OPT_COMM, 2)
    t['net_pnl'] = net
    t['reason'] = reason
    stock_closed.append(t)
    print(f"{t['time']:<10} {t['sym']} ATM {t['opt']} ({t['side']}) | Lot: {t['lot']} | Peak Gain: ₹{peak_gain:7.1f} | Gross: ₹{gross:7.1f} | Net: {net:+9.2f} INR | {reason}")

total_stock_net = sum(t['net_pnl'] for t in stock_closed)
print("-" * 105)
print(f"Total Top 50 Stock Options Net P&L: {total_stock_net:+9.2f} INR")
