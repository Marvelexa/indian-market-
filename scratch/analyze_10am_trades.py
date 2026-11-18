import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS

eng = IndianPastDateReplayEngine()

wins_1000_1015 = []
losses_1000_1015 = []

for d in eng.sorted_dates:
    eng.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng.advance_seconds(5)
    for t in eng.closed_ledger:
        entry_sec = t.get('entrySecondOfDay', 0)
        # Entry between 10:00:00 (2700s) and 10:14:59 (3599s)
        # Check formatted time if entrySecondOfDay not present
        time_str = t.get('entryTimeFormatted', '')
        if time_str.startswith('10:0') or time_str.startswith('10:10') or time_str.startswith('10:11') or time_str.startswith('10:12') or time_str.startswith('10:13') or time_str.startswith('10:14'):
            pnl = t['netPnlInr']
            m = d[:7]
            trade_info = {
                'date': d,
                'month': m,
                'symbol': t['symbol'],
                'side': t['side'],
                'time': time_str,
                'pnl': pnl,
                'reason': t['exitReason']
            }
            if pnl > 0:
                wins_1000_1015.append(trade_info)
            else:
                losses_1000_1015.append(trade_info)

print(f"Total trades between 10:00-10:15 AM:")
print(f"  Wins: {len(wins_1000_1015)} | Total Win P&L: INR {sum(t['pnl'] for t in wins_1000_1015):,.2f}")
print(f"  Losses: {len(losses_1000_1015)} | Total Loss P&L: INR {sum(t['pnl'] for t in losses_1000_1015):,.2f}")
print(f"  Net P&L: INR {sum(t['pnl'] for t in wins_1000_1015) + sum(t['pnl'] for t in losses_1000_1015):,.2f}")

print("\nBreakdown by Month for 10:00-10:15 AM entries:")
for m in ['2026-08', '2026-09', '2026-10', '2026-11']:
    m_wins = [t for t in wins_1000_1015 if t['month'] == m]
    m_losses = [t for t in losses_1000_1015 if t['month'] == m]
    w_pnl = sum(t['pnl'] for t in m_wins)
    l_pnl = sum(t['pnl'] for t in m_losses)
    net = w_pnl + l_pnl
    print(f"  {m}: Wins={len(m_wins)} (+INR {w_pnl:,.2f}), Losses={len(m_losses)} (INR {l_pnl:,.2f}) -> Net: INR {net:,.2f}")
