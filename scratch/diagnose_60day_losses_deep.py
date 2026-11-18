import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS

eng = IndianPastDateReplayEngine()

total_pnl = 0.0
loss_trades = []
win_trades = []

for d in eng.sorted_dates:
    eng.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng.advance_seconds(5)
    for t in eng.closed_ledger:
        if t['netPnlInr'] < 0:
            loss_trades.append((d, t))
        else:
            win_trades.append((d, t))

print(f"Total Trades: {len(win_trades) + len(loss_trades)}")
print(f"Wins: {len(win_trades)} (+INR {sum(t['netPnlInr'] for _, t in win_trades):,.2f})")
print(f"Losses: {len(loss_trades)} (-INR {abs(sum(t['netPnlInr'] for _, t in loss_trades)):,.2f})")
print(f"Net P&L: INR {sum(t['netPnlInr'] for _, t in win_trades) + sum(t['netPnlInr'] for _, t in loss_trades):,.2f}")

# Loss by exit reason
loss_by_reason = {}
for _, t in loss_trades:
    r = t['exitReason']
    loss_by_reason[r] = loss_by_reason.get(r, 0.0) + abs(t['netPnlInr'])

print("\nLosses by Exit Reason:")
for r, amt in sorted(loss_by_reason.items(), key=lambda x: x[1], reverse=True):
    count = sum(1 for _, t in loss_trades if t['exitReason'] == r)
    print(f"  {r:<28}: {count:>3} trades | INR {amt:>10,.2f} (Avg: INR {amt/count:,.2f})")

# Loss by symbol
loss_by_sym = {}
win_by_sym = {}
for _, t in loss_trades:
    s = t['symbol']
    loss_by_sym[s] = loss_by_sym.get(s, 0.0) + abs(t['netPnlInr'])
for _, t in win_trades:
    s = t['symbol']
    win_by_sym[s] = win_by_sym.get(s, 0.0) + t['netPnlInr']

print("\nPerformance by Symbol:")
print(f"{'Symbol':<12} | {'Trades':^7} | {'Win PnL':^12} | {'Loss PnL':^12} | {'Net PnL':^14}")
all_syms = sorted(list(set(list(loss_by_sym.keys()) + list(win_by_sym.keys()))))
for s in all_syms:
    w = win_by_sym.get(s, 0.0)
    l = loss_by_sym.get(s, 0.0)
    net = w - l
    n_trades = sum(1 for _, t in win_trades if t['symbol'] == s) + sum(1 for _, t in loss_trades if t['symbol'] == s)
    print(f"{s:<12} | {n_trades:^7} | +INR {w:>8,.2f} | -INR {l:>8,.2f} | {'+INR ' if net>=0 else '-INR '}{abs(net):>9,.2f}")
