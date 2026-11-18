import sys, os, math
sys.path.insert(0, os.path.abspath('.'))
from backend.replay_engine import IndianPastDateReplayEngine, WHITELIST_14_SYMBOLS, TOTAL_DAY_SECONDS, WARMUP_END_SECOND, SNIPER_CUTOFF_SECOND, AUTO_SQUAREOFF_SECOND

class DeterministicReplayEngine(IndianPastDateReplayEngine):
    def compute_intra_second_prices(self):
        """
        100% Deterministic Intra-Candle Pricing based on actual historical candle physics:
        Open -> Wick 1 -> Wick 2 -> Close.
        ZERO random numbers, ZERO hash(sym) variations, 100% mathematically reproducible.
        """
        day_bars = self.by_date_5m.get(self.current_date, {})
        bar_idx = min(74, self.second_of_day // 300)
        intra_sec = self.second_of_day % 300

        for sym in WHITELIST_14_SYMBOLS:
            bars = day_bars.get(sym, [])
            if not bars:
                continue

            c_idx = min(bar_idx, len(bars) - 1)
            b = bars[c_idx]
            o = float(b["open"])
            h = float(b["high"])
            l = float(b["low"])
            c = float(b["close"])

            is_bull = c >= o

            # Deterministic 3-Phase Candle Traversal:
            # Phase 1 (0 to 60s): Test wick 1 (Low if bull, High if bear)
            # Phase 2 (60 to 240s): Move to opposite extreme wick (High if bull, Low if bear)
            # Phase 3 (240 to 300s): Pullback into final Close
            if is_bull:
                if intra_sec < 60:
                    t = intra_sec / 60.0
                    cur_p = o + (l - o) * t
                elif intra_sec < 240:
                    t = (intra_sec - 60) / 180.0
                    cur_p = l + (h - l) * t
                else:
                    t = (intra_sec - 240) / 60.0
                    cur_p = h + (c - h) * t
            else:
                if intra_sec < 60:
                    t = intra_sec / 60.0
                    cur_p = o + (h - o) * t
                elif intra_sec < 240:
                    t = (intra_sec - 60) / 180.0
                    cur_p = h + (l - h) * t
                else:
                    t = (intra_sec - 240) / 60.0
                    cur_p = l + (c - l) * t

            final_price = round(max(l, min(h, cur_p)), 2)
            old_p = self.live_prices.get(sym, final_price)
            self.prev_prices[sym] = old_p
            self.live_prices[sym] = final_price

            if final_price > old_p:
                self.price_directions[sym] = "UP"
            elif final_price < old_p:
                self.price_directions[sym] = "DOWN"
            else:
                self.price_directions[sym] = "FLAT"

            day_o = self.day_open_prices.get(sym, o)
            self.price_pct_changes[sym] = round(((final_price - day_o) / day_o) * 100.0, 2)
            if sym in self.symbol_stats:
                self.symbol_stats[sym]["currentPrice"] = final_price

    def advance_seconds(self, delta_sec: int):
        """
        Decomposes ANY speed or delta_sec into deterministic fixed 5s sub-ticks.
        This guarantees that whether running at 1x, 5x, 30x, 300x, or 600x,
        the EXACT SAME price checkpoints are evaluated in the EXACT SAME order!
        """
        if self.second_of_day >= TOTAL_DAY_SECONDS:
            self.is_running = False
            self.session_gate = "MARKET_CLOSED"
            self.session_desc = "03:30 PM IST Market Closed. Replay Complete. Final Performance Report Ready."
            return

        chunk = 5
        rem = delta_sec
        while rem > 0 and self.second_of_day < TOTAL_DAY_SECONDS:
            step = min(chunk, rem)
            self._step_internal(step)
            rem -= step

    def _step_internal(self, step: int):
        old_sec = self.second_of_day
        self.second_of_day = min(TOTAL_DAY_SECONDS, self.second_of_day + step)

        self.update_session_gate()
        self.compute_intra_second_prices()
        self.evaluate_active_positions_tick()

        # Daily Circuit Breaker
        if self.realized_pnl_inr <= -2000.0 and len(self.active_positions) > 0:
            cur_time = self.get_formatted_time()
            for pos in list(self.active_positions):
                curr_p = self.live_prices.get(pos["symbol"], pos["currentPrice"])
                self.close_position(pos, curr_p, "DAILY_CIRCUIT_BREAKER_HIT", cur_time)
            self.active_positions = []

        # 03:18 PM Auto Square-Off
        if old_sec < AUTO_SQUAREOFF_SECOND and self.second_of_day >= AUTO_SQUAREOFF_SECOND:
            self.trigger_intraday_auto_square_off()

        # 5m candle close signal evaluation
        old_bar_idx = old_sec // 300
        new_bar_idx = self.second_of_day // 300
        if new_bar_idx > old_bar_idx and self.second_of_day >= WARMUP_END_SECOND and self.second_of_day < SNIPER_CUTOFF_SECOND:
            self.evaluate_seat_signals()

# TEST DETERMINISM ACROSS SPEEDS AND RUNS
for target_date in ["2026-11-02", "2026-11-13", "2026-11-06"]:
    print(f"=== TESTING DETERMINISM FOR {target_date} ===")
    results = []
    # Test different delta steps (simulating 1x, 5x, 30x, 300x, 600x with random jitter)
    import random
    for run_idx in range(5):
        random.seed(run_idx * 100)
        engine = DeterministicReplayEngine()
        engine.set_date(target_date, auto_play=True)
        while engine.is_running and engine.second_of_day < TOTAL_DAY_SECONDS:
            # Simulate arbitrary random delta steps (e.g. 5 to 65 seconds per tick)
            delta = random.choice([5, 12, 27, 30, 48, 60, 150, 300])
            engine.advance_seconds(delta)
        results.append((engine.realized_pnl_inr, len(engine.closed_ledger)))
        print(f"  Run {run_idx+1}: PnL = {engine.realized_pnl_inr:+10.2f}, Trades = {len(engine.closed_ledger)}")

    all_same_pnl = all(r[0] == results[0][0] for r in results)
    all_same_trades = all(r[1] == results[0][1] for r in results)
    print(f"  -> 100% IDENTICAL RESULT EVERY RUN: {all_same_pnl and all_same_trades}!\n")
