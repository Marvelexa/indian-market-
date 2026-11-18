import re

log_path = r"C:\Users\Rajesh\.gemini\antigravity\brain\ad428b8d-94bd-4900-ba0c-e90e8694fd02\.system_generated\tasks\task-1081.log"
content = open(log_path, encoding='utf-8', errors='ignore').read()

lines = content.splitlines()
trades = []
for line in lines:
    # Match pattern: e.g. 1   | GOLDM        | SELL | ₹109676.4 | ₹109674.4 | 09:00 -> 10:15 | +2 pts | +₹       20 | 1:1.6 | TRAILED_SL_HIT
    m = re.match(r"^\s*(\d+)\s+\|\s+(\S+)\s+\|\s+(BUY|SELL)\s+\|\s+₹\s*([\d.]+)\s+\|\s+₹\s*([\d.]+)\s+\|\s+(\d{2}:\d{2})\s+->\s+(\d{2}:\d{2})\s+\|\s+([+-]?[\d.]+)\s+pts\s+\|\s+([+-]?₹?\s*[\d,.-]+)\s+\|\s+1:([\d.]+)\s+\|\s+(.*)", line)
    if m:
        pnl_str = m.group(9).replace('₹', '').replace(' ', '').replace(',', '')
        pnl = float(pnl_str)
        trades.append({
            'num': int(m.group(1)),
            'symbol': m.group(2),
            'action': m.group(3),
            'entry': float(m.group(4)),
            'exit': float(m.group(5)),
            'in_time': m.group(6),
            'out_time': m.group(7),
            'points': float(m.group(8)),
            'pnl': pnl,
            'rr': float(m.group(10)),
            'reason': m.group(11).strip()
        })

print(f"Parsed {len(trades)} trades from backtest log.")

# Breakdown by symbol
by_symbol = {}
for t in trades:
    s = t['symbol']
    if s not in by_symbol:
        by_symbol[s] = []
    by_symbol[s].append(t)

print("\n" + "="*85)
print(f"{'Symbol':<12} | {'Trades':<7} | {'Wins':<5} | {'Losses':<7} | {'WinRate':<8} | {'Gross Win':<12} | {'Gross Loss':<12} | {'Net P&L':<12}")
print("="*85)
for s, trs in sorted(by_symbol.items()):
    wins = [t for t in trs if t['pnl'] > 0]
    losses = [t for t in trs if t['pnl'] < 0]
    gwin = sum(t['pnl'] for t in wins)
    gloss = sum(t['pnl'] for t in losses)
    net = sum(t['pnl'] for t in trs)
    wr = len(wins) / len(trs) * 100 if trs else 0
    print(f"{s:<12} | {len(trs):<7} | {len(wins):<5} | {len(losses):<7} | {wr:>6.1f}% | +₹{gwin:>10,.2f} | ₹{gloss:>10,.2f} | ₹{net:>+10,.2f}")

print("="*85)
