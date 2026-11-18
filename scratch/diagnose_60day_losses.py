import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS

eng = IndianPastDateReplayEngine()

all_closed = []
monthly_breakdown = {}

for d in eng.sorted_dates:
    m = d[:7]
    if m not in monthly_breakdown:
        monthly_breakdown[m] = {"trades": 0, "wins": 0, "losses": 0, "win_pnl": 0.0, "loss_pnl": 0.0, "net_pnl": 0.0}
    
    eng.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng.advance_seconds(5)
    
    for t in eng.closed_ledger:
        p = t.get('netPnlInr', t.get('pnlInr', 0.0))
        monthly_breakdown[m]["trades"] += 1
        monthly_breakdown[m]["net_pnl"] += p
        if p > 0:
            monthly_breakdown[m]["wins"] += 1
            monthly_breakdown[m]["win_pnl"] += p
        else:
            monthly_breakdown[m]["losses"] += 1
            monthly_breakdown[m]["loss_pnl"] += p
        t_copy = dict(t)
        t_copy['date'] = d
        all_closed.append(t_copy)

print("=" * 85)
print(f"{'Month':<10} | {'Trades':^7} | {'Wins':^5} | {'Losses':^6} | {'Win PnL':^12} | {'Loss PnL':^12} | {'Net PnL':^14}")
print("=" * 85)
for m, v in sorted(monthly_breakdown.items()):
    pnl_str = f"+INR {v['net_pnl']:,.2f}" if v['net_pnl'] >= 0 else f"-INR {abs(v['net_pnl']):,.2f}"
    print(f"{m:<10} | {v['trades']:^7} | {v['wins']:^5} | {v['losses']:^6} | +INR {v['win_pnl']:>9,.2f} | -INR {abs(v['loss_pnl']):>9,.2f} | {pnl_str:>14}")

# Inspect what caused losses in September & November
sep_losses = [t for t in all_closed if t['date'].startswith('2026-09') and t.get('netPnlInr', 0) < 0]
nov_losses = [t for t in all_closed if t['date'].startswith('2026-11') and t.get('netPnlInr', 0) < 0]

print(f"\nTotal September Losses: {len(sep_losses)} totaling -INR {sum(abs(t.get('netPnlInr', 0)) for t in sep_losses):,.2f}")
print(f"Total November Losses: {len(nov_losses)} totaling -INR {sum(abs(t.get('netPnlInr', 0)) for t in nov_losses):,.2f}")

exit_reasons = {}
for t in sep_losses + nov_losses:
    r = t.get('exitReason', 'UNKNOWN')
    exit_reasons[r] = exit_reasons.get(r, 0) + 1

print("\nLoss Exit Reasons in Sep & Nov:")
for r, c in sorted(exit_reasons.items(), key=lambda x: x[1], reverse=True):
    print(f"  {r}: {c} trades")

# Group losses by Symbol
sym_losses = {}
for t in sep_losses + nov_losses:
    s = t.get('symbol', 'UNKNOWN')
    sym_losses[s] = sym_losses.get(s, 0) + t.get('netPnlInr', 0)

print("\nWorst Loss Contributors by Symbol in Sep & Nov:")
for s, amt in sorted(sym_losses.items(), key=lambda x: x[1])[:8]:
    print(f"  {s}: -INR {abs(amt):,.2f}")
