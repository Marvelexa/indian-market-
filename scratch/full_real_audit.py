import re

log_path = r"C:\Users\Rajesh\.gemini\antigravity\brain\ad428b8d-94bd-4900-ba0c-e90e8694fd02\.system_generated\tasks\task-643.log"
lines = open(log_path, encoding='utf-8', errors='ignore').readlines()

broker_orders = []
for line in lines:
    if '[BROKER ORDER]' in line:
        broker_orders.append(line.strip())

# Parse into structured trades
all_orders = []
for bo in broker_orders:
    m = re.search(r'(BUY|SELL)\s+(\d+)x\s+(\S+)\s+@\s+₹([\d.]+)\s+\|\s+Seat:\s+(\S+)\s+\|\s+Tag:\s+(\S+)', bo)
    if m:
        all_orders.append({
            'side': m.group(1),
            'qty': int(m.group(2)),
            'symbol': m.group(3),
            'price': float(m.group(4)),
            'seat': m.group(5),
            'tag': m.group(6),
        })

# Match BUY-SELL pairs to calculate real P&L
# Track open positions, match FIFO
open_positions = {}  # symbol -> list of {qty, price, seat}
completed_trades = []

for o in all_orders:
    sym = o['symbol']
    if o['side'] == 'BUY':
        if sym not in open_positions:
            open_positions[sym] = []
        open_positions[sym].append({'qty': o['qty'], 'price': o['price'], 'seat': o['seat'], 'tag': o['tag']})
    else:  # SELL
        if sym in open_positions and len(open_positions[sym]) > 0:
            entry = open_positions[sym].pop(0)
            qty = min(entry['qty'], o['qty'])
            entry_val = entry['price'] * qty
            exit_val = o['price'] * qty
            
            # Charges: ~₹9 per round trip for small, ~₹16 for large
            turnover = entry_val + exit_val
            brokerage = min(20, turnover * 0.0003) * 2
            stt = exit_val * 0.000625
            exchange = turnover * 0.0000345
            stamp = entry_val * 0.00015
            gst = brokerage * 0.18
            total_charges = round(brokerage + stt + exchange + stamp + gst, 2)
            
            gross_pnl = round(exit_val - entry_val, 2)
            net_pnl = round(gross_pnl - total_charges, 2)
            
            completed_trades.append({
                'symbol': sym,
                'qty': qty,
                'entry_price': entry['price'],
                'exit_price': o['price'],
                'entry_tag': entry['tag'],
                'exit_tag': o['tag'],
                'seat': entry['seat'],
                'gross_pnl': gross_pnl,
                'charges': total_charges,
                'net_pnl': net_pnl,
            })

# Clean up symbol for display
def clean_sym(s):
    return s.replace('.NS', '').replace('_MIS', '')

# Print results
print("=" * 100)
print(f"REAL SYSTEM TRADE LOG — 17 NOV 2026 (09:15 AM to 03:18 PM IST)")
print(f"Total Completed Round-Trip Trades: {len(completed_trades)}")
print("=" * 100)

total_gross = 0
total_charges = 0
total_net = 0
wins = 0
losses = 0
maruti_loop_count = 0
maruti_loop_charges = 0

for i, t in enumerate(completed_trades):
    is_maruti_loop = 'MARUTI' in t['symbol'] and t['exit_tag'] == 'AUTO_SQUARE_OFF_318PM' and abs(t['gross_pnl']) < 10
    is_loop = ('AUTO_SQUARE_OFF_318PM' in t['exit_tag'] and abs(t['gross_pnl']) < 50 and 
               (t['entry_tag'] in ['ATM_CE_ENTRY', 'ATM_PE_ENTRY']))
    
    tag = ""
    if is_maruti_loop or (is_loop and i > 70):
        tag = " ⚠️ LOOP BUG"
        maruti_loop_count += 1
        maruti_loop_charges += t['charges']
    elif t['net_pnl'] > 0:
        tag = " ✅"
        wins += 1
    else:
        tag = " ❌"
        losses += 1
    
    total_gross += t['gross_pnl']
    total_charges += t['charges']
    total_net += t['net_pnl']
    
    print(f"#{i+1:>3} | {clean_sym(t['symbol']):<30} | {t['qty']:>5} Qty | Entry ₹{t['entry_price']:>8.2f} -> Exit ₹{t['exit_price']:>8.2f} | Gross: ₹{t['gross_pnl']:>+9.2f} | Charges: ₹{t['charges']:>7.2f} | Net: ₹{t['net_pnl']:>+9.2f} | {t['exit_tag']}{tag}")

print("\n" + "=" * 100)
print(f"FINAL SUMMARY")
print(f"=" * 100)
print(f"Total Round-Trip Trades:    {len(completed_trades)}")
print(f"  Legitimate Trades:        {wins + losses}")
print(f"    Winners:                {wins}")
print(f"    Losers:                 {losses}")
print(f"  Bug Loop Trades:          {maruti_loop_count} (Wasted ₹{maruti_loop_charges:.2f} in charges)")
print(f"")
print(f"Gross P&L (Before Charges): ₹{total_gross:>+10,.2f}")
print(f"Total Charges/Brokerage:    ₹{total_charges:>10,.2f}")
print(f"NET REAL P&L:               ₹{total_net:>+10,.2f}")
print(f"=" * 100)
