import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS

class NoForcedLiquidationEngine(IndianPastDateReplayEngine):
    def advance_seconds(self, delta_sec: int):
        """Advances replay clock without prematurely murdering open winner positions"""
        old_sec = self.second_of_day
        self.second_of_day = min(TOTAL_DAY_SECONDS, self.second_of_day + delta_sec)

        self.update_live_prices_for_second()
        self.evaluate_active_positions_tick()

        # Halt NEW entries if realized_pnl <= -2500, but let open positions finish
        self.evaluate_seat_signals()

        # Auto square off at 03:18 PM
        if old_sec < 21780 and self.second_of_day >= 21780:
            self.trigger_intraday_auto_square_off()

eng = NoForcedLiquidationEngine()
monthly_stats = {}
total_pnl = 0.0

for d in eng.sorted_dates:
    m = d[:7]
    if m not in monthly_stats:
        monthly_stats[m] = {"days": 0, "trades": 0, "wins": 0, "losses": 0, "pnl": 0.0, "green": 0, "red": 0}
    eng.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng.advance_seconds(5)
    st = eng.get_state()
    w = st['wallet']
    p = round(w['realizedPnlInr'], 2)
    t = w['totalTrades']
    wn = w['wins']
    ls = t - wn
    monthly_stats[m]["days"] += 1
    monthly_stats[m]["trades"] += t
    monthly_stats[m]["wins"] += wn
    monthly_stats[m]["losses"] += ls
    monthly_stats[m]["pnl"] += p
    if p > 0: monthly_stats[m]["green"] += 1
    else: monthly_stats[m]["red"] += 1
    total_pnl += p

print("=" * 85)
print("NO FORCED LIQUIDATION AUDIT (REAL TICKS):")
print("=" * 85)
for m, v in sorted(monthly_stats.items()):
    wr = round((v['wins'] / v['trades']) * 100, 1) if v['trades'] > 0 else 0
    pnl_str = f"+INR {v['pnl']:,.2f}" if v['pnl'] >= 0 else f"-INR {abs(v['pnl']):,.2f}"
    margin_roe = f"+{v['pnl'] / 25000.0 * 100:.1f}%" if v['pnl'] >= 0 else f"-{abs(v['pnl']) / 25000.0 * 100:.1f}%"
    print(f"{m:<10} | {v['days']:^5} | {v['green']}G / {v['red']}R    | {v['trades']:^7} | {v['wins']:^5} | {wr:>5.1f}% | {pnl_str:>14} | {margin_roe:>12}")

print("=" * 85)
print(f"60-DAY CUMULATIVE NET P&L: INR {total_pnl:,.2f}")
print(f"Base Return (1L Capital): +{total_pnl / 100000.0 * 100:.2f}%")
print(f"Margin ROE (25k Capital): +{total_pnl / 25000.0 * 100:.2f}%")
