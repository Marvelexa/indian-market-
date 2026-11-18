import re

log_path = r"C:\Users\Rajesh\.gemini\antigravity\brain\ad428b8d-94bd-4900-ba0c-e90e8694fd02\.system_generated\tasks\task-643.log"

lines = open(log_path, encoding='utf-8', errors='ignore').readlines()

# Extract every BROKER ORDER line
broker_orders = []
for line in lines:
    if '[BROKER ORDER]' in line:
        broker_orders.append(line.strip())

# Also extract FO OPTION SNIPER EXIT lines
exits = []
for line in lines:
    if 'FO OPTION SNIPER EXIT' in line:
        exits.append(line.strip())

print(f"=== TOTAL BROKER ORDERS FIRED: {len(broker_orders)} ===\n")

# Parse each broker order
buy_count = 0
sell_count = 0
symbols_traded = set()

for i, bo in enumerate(broker_orders):
    # Extract: BUY/SELL, qty, symbol, price, seat, tag
    m = re.search(r'(BUY|SELL)\s+(\d+)x\s+(\S+)\s+@\s+₹([\d.]+)\s+\|\s+Seat:\s+(\S+)\s+\|\s+Tag:\s+(\S+)', bo)
    if m:
        side = m.group(1)
        qty = m.group(2)
        sym = m.group(3)
        price = m.group(4)
        seat = m.group(5)
        tag = m.group(6)
        if side == 'BUY':
            buy_count += 1
        else:
            sell_count += 1
        symbols_traded.add(sym.replace('.NS', '').split('26NOV')[0] if '26NOV' in sym else sym)
        print(f"#{i+1:>3} | {side:>4} {qty:>5}x {sym:<30} @ ₹{price:>8} | Seat: {seat:<10} | Tag: {tag}")

print(f"\n{'='*80}")
print(f"TOTAL BROKER ORDERS: {len(broker_orders)}")
print(f"  BUY Orders:  {buy_count}")
print(f"  SELL Orders: {sell_count}")
print(f"  Unique Round-Trip Trades: {sell_count}")  # Each SELL = 1 completed trade
print(f"  Unique Symbols Traded: {len(symbols_traded)} -> {sorted(symbols_traded)}")
print(f"{'='*80}")
