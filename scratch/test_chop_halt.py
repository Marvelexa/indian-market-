import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scratch.test_anti_chop import AntiChopReplayEngine, TOTAL_DAY_SECONDS

class ConservativeChopProtectionEngine(AntiChopReplayEngine):
    def evaluate_seat_signals(self):
        # Strict Chop Stop: If today's realized loss touches -₹2,500, HALT!
        # Do not allow chopping market to bleed the account beyond -₹2,500!
        if self.realized_pnl_inr <= -2500.0:
            return
        
        # Also check consecutive losses: if first 2 trades both lost, pause new breakouts
        losses_so_far = [t for t in self.closed_ledger if t.get('netPnlInr', 0) < 0]
        wins_so_far = [t for t in self.closed_ledger if t.get('netPnlInr', 0) > 0]
        if len(losses_so_far) >= 2 and len(wins_so_far) == 0:
            # 2 out of 2 morning trades failed -> Market is in CHOP TRAP!
            return

        super().evaluate_seat_signals()

eng = ConservativeChopProtectionEngine()
oct_dates = [d for d in eng.sorted_dates if "-10-" in d]

total_pnl = 0.0
total_trades = 0
total_wins = 0

print("Testing 2-Loss Morning Chop Halt + -₹2,500 Daily Shield on October:")
for d in oct_dates:
    eng.set_date(d, auto_play=True)
    eng.is_running = True
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng.advance_seconds(5)
    st = eng.get_state()
    w = st['wallet']
    pnl = w['realizedPnlInr']
    total_pnl += pnl
    total_trades += w['totalTrades']
    total_wins += w['wins']
    sign = "+" if pnl >= 0 else ""
    print(f"  {d}: {sign}₹{pnl:>9,.2f} | Trades: {w['totalTrades']:>2} | Wins: {w['wins']:>2} | WR: {w['winRatePct']:>5.1f}%")

print("=" * 60)
print(f"Original October Net PnL:     ₹11,467.08 (186 trades)")
print(f"Chop Shielded October PnL:   ₹{total_pnl:,.2f} ({total_trades} trades, {total_wins} wins, {total_wins/max(1,total_trades)*100:.1f}% WR)")
print("=" * 60)
