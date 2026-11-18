import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS

eng = IndianPastDateReplayEngine()

bn_trades = []
for d in eng.sorted_dates:
    eng.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng.advance_seconds(5)
    for t in eng.closed_ledger:
        if t['symbol'] == 'BANKNIFTY':
            bn_trades.append((d, t))

print(f"Total BankNifty trades: {len(bn_trades)}")
wins = [t for _, t in bn_trades if t['netPnlInr'] > 0]
losses = [t for _, t in bn_trades if t['netPnlInr'] < 0]
print(f"Wins: {len(wins)} (+INR {sum(t['netPnlInr'] for t in wins):,.2f})")
print(f"Losses: {len(losses)} (-INR {abs(sum(t['netPnlInr'] for t in losses)):,.2f})")
print(f"Net PnL: INR {sum(t['netPnlInr'] for _, t in bn_trades):,.2f}")

print("\nMonthly breakdown for BankNifty:")
for m in ['2026-08', '2026-09', '2026-10', '2026-11']:
    m_trades = [t for d, t in bn_trades if d[:7] == m]
    m_pnl = sum(t['netPnlInr'] for t in m_trades)
    m_w = sum(1 for t in m_trades if t['netPnlInr'] > 0)
    print(f"  {m}: {len(m_trades)} trades | {m_w}W / {len(m_trades)-m_w}L | Net: INR {m_pnl:,.2f}")

print("\nSample Losing Trades in BankNifty:")
for d, t in losses[:10]:
    print(f"  {d} | {t['entryTimeFormatted']} -> {t['exitTimeFormatted']} | {t['side']} | Entry: {t['entryPrice']} | Exit: {t['exitPrice']} | Net: INR {t['netPnlInr']:,.2f} | Reason: {t['exitReason']}")
