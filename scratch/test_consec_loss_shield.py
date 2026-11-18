import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scratch.test_super_accuracy_strategy import SuperStrategyReplayEngine, TOTAL_DAY_SECONDS

class SuperShieldedReplayEngine(SuperStrategyReplayEngine):
    def __init__(self, max_consec_loss=2, daily_loss_limit=-2000.0, **kwargs):
        super().__init__(**kwargs)
        self.max_consec_loss = max_consec_loss
        self.daily_loss_limit = daily_loss_limit
        self.consec_loss_count = 0

    def reset_day_state(self):
        super().reset_day_state()
        self.consec_loss_count = 0

    def close_position(self, pos, exit_price, exit_reason, exit_time_str):
        super().close_position(pos, exit_price, exit_reason, exit_time_str)
        # Check last trade pnl
        if self.closed_ledger:
            last_pnl = self.closed_ledger[0]["netPnlInr"]
            if last_pnl < 0:
                self.consec_loss_count += 1
            else:
                self.consec_loss_count = 0

    def evaluate_seat_signals(self):
        # Halt if max consecutive losses hit (protects against sustained chop)
        if self.consec_loss_count >= self.max_consec_loss:
            return
        if self.realized_pnl_inr <= self.daily_loss_limit:
            return
        super().evaluate_seat_signals()

for consec in [1, 2, 3]:
    for dlimit in [-1500.0, -2000.0, -2500.0]:
        eng = SuperShieldedReplayEngine(
            min_start_sec=2700,
            min_breadth_pct=70.0,
            index_lots=1,
            max_consec_loss=consec,
            daily_loss_limit=dlimit
        )
        oct_dates = [d for d in eng.sorted_dates if "-10-" in d]
        total_pnl = 0.0
        total_trades = 0
        total_wins = 0
        win_days = 0
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
            if pnl > 0: win_days += 1
        wr = (total_wins / max(1, total_trades)) * 100.0
        print(f"ConsecLoss={consec} | DayLimit=INR {dlimit:>7.0f} | Net PnL: INR {total_pnl:>9,.2f} ({total_pnl/1000:>+5.1f}%) | WR: {wr:>5.1f}% | Win Days: {win_days:>2}/20 | Trades: {total_trades:>3}")
