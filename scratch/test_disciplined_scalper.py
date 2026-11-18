# Let's see what happens if we only take high-conviction trades with a 20-min cooldown
import re

log_path = r"C:\Users\Rajesh\.gemini\antigravity\brain\ad428b8d-94bd-4900-ba0c-e90e8694fd02\.system_generated\tasks\task-1081.log"
lines = open(log_path, encoding='utf-8', errors='ignore').readlines()

trades = []
for line in lines:
    m = re.match(r"^\s*(\d+)\s+\|\s+(\S+)\s+\|\s+(BUY|SELL)\s+\|\s+₹\s*([\d.]+)\s+\|\s+₹\s*([\d.]+)\s+\|\s+(\d{2}:\d{2})\s+->\s+(\d{2}:\d{2})\s+\|\s+([+-]?[\d.]+)\s+pts\s+\|\s+([+-]?₹?\s*[\d,.-]+)\s+\|\s+1:([\d.]+)\s+\|\s+(.*)", line)
    if m:
        pnl = float(m.group(9).replace('₹', '').replace(' ', '').replace(',', ''))
        trades.append({
            'symbol': m.group(2),
            'action': m.group(3),
            'in_time': m.group(6),
            'out_time': m.group(7),
            'pnl': pnl,
            'reason': m.group(11).strip()
        })

# Let's filter for Mini contracts: NATGASMINI, GOLDM, SILVERM, and NATURALGAS
mini_trades = [t for t in trades if t['symbol'] in ['NATGASMINI', 'GOLDM', 'SILVERM', 'NATURALGAS']]

# Apply cooldown: if a trade in symbol was closed, wait at least 15 mins before next trade
filtered = []
last_exit_mins = {}

def to_mins(t_str):
    h, m = map(int, t_str.split(':'))
    return h * 60 + m

for t in trades:
    sym = t['symbol']
    in_m = to_mins(t['in_time'])
    last_ex = last_exit_mins.get(sym, -999)
    if in_m - last_ex >= 15:
        filtered.append(t)
        last_exit_mins[sym] = to_mins(t['out_time'])

print(f"Total Raw Trades: {len(trades)} | Total Net: ₹{sum(t['pnl'] for t in trades):+,.2f}")
print(f"Mini Contracts Only ({len(mini_trades)} trades): Net: +₹{sum(t['pnl'] for t in mini_trades):+,.2f}")

wins_mini = [t for t in mini_trades if t['pnl'] > 0]
print(f"  Mini Winners: {len(wins_mini)}/{len(mini_trades)} ({len(wins_mini)/len(mini_trades)*100:.1f}%)")
for s in ['NATGASMINI', 'NATURALGAS', 'GOLDM', 'SILVERM']:
    st = [t for t in mini_trades if t['symbol'] == s]
    s_wins = [t for t in st if t['pnl'] > 0]
    print(f"  -> {s:<10}: {len(st)} trades | {len(s_wins)} wins | Net: ₹{sum(t['pnl'] for t in st):+,.2f}")

print(f"\nCooldown Filtered (All symbols, {len(filtered)} trades): Net: ₹{sum(t['pnl'] for t in filtered):+,.2f}")
