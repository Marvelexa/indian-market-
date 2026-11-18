import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from scratch.test_adaptive_regime import AdaptiveDualRegimeEngine
from backend.replay_engine import TOTAL_DAY_SECONDS

class TrendOnlyAdaptiveEngine(AdaptiveDualRegimeEngine):
    def evaluate_seat_signals(self):
        # Simply override: if not trend regime, don't execute chop ping-pong!
        if self.realized_pnl_inr <= -2500.0:
            return
        if self.second_of_day < 2700:
            return
        if len(self.active_positions) >= 4:
            return

        bar_idx = min(74, self.second_of_day // 300)
        day_bars = self.by_date_5m.get(self.current_date, {})
        cur_time_str = self.get_formatted_time()

        bull_count = 0
        bear_count = 0
        total_syms = 0
        vwaps = {}
        for s in self.whitelist if hasattr(self, 'whitelist') else [p for p in day_bars.keys()]:
            pass

eng_adapt = AdaptiveDualRegimeEngine()
# Let's inspect each day of October in eng_adapt: trend PnL vs chop PnL
oct_dates = [d for d in eng_adapt.sorted_dates if d.startswith("2026-10")]
print(f"{'Date':<12} | {'Trend PnL':<12} | {'Chop PnL':<12} | {'Total PnL':<12}")
print("=" * 55)
for d in oct_dates:
    eng_adapt.set_date(d, auto_play=True)
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng_adapt.advance_seconds(5)
    t_pnl = sum(t.get('netPnlInr', t.get('pnlInr',0)) for t in eng_adapt.closed_ledger if t.get('seatBucket') != "CHOP_PING_PONG_SEAT")
    c_pnl = sum(t.get('netPnlInr', t.get('pnlInr',0)) for t in eng_adapt.closed_ledger if t.get('seatBucket') == "CHOP_PING_PONG_SEAT")
    tot = t_pnl + c_pnl
    print(f"{d:<12} | INR {t_pnl:>8,.2f} | INR {c_pnl:>8,.2f} | INR {tot:>8,.2f}")
