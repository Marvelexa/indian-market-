import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS, INDEX_SET, WHITELIST_14_SYMBOLS, DISPLAY_NAMES

class Target30PctReplayEngine(IndianPastDateReplayEngine):
    def __init__(self, index_lots=1, daily_circuit_limit=-2000.0, allow_open_runner=True):
        super().__init__()
        self.index_lots = index_lots
        self.daily_circuit_limit = daily_circuit_limit
        self.allow_open_runner = allow_open_runner

    def evaluate_active_positions_tick(self):
        """
        Custom tick evaluator:
        Allows Super Runners to run beyond +₹3,000 if allow_open_runner=True,
        while locking in +₹2,100 at TP 5 and trailing by 20% pullback from peak!
        """
        if not self.active_positions:
            return

        bar_idx = min(74, self.second_of_day // 300)
        day_bars = self.by_date_5m.get(self.current_date, {})
        cur_time_str = self.get_formatted_time()
        remaining = []

        for pos in self.active_positions:
            sym = pos["symbol"]
            curr_p = self.live_prices.get(sym, pos["currentPrice"])
            pos["currentPrice"] = curr_p

            entry = pos["entryPrice"]
            qty = pos.get("quantity", 1)
            is_buy = pos["side"] == "BUY"
            is_opt = pos.get("isOption", False)

            profit_dist = (curr_p - entry) if is_buy else (entry - curr_p)
            gain_pct = (profit_dist / entry) * 100.0
            pos["gainPct"] = round(gain_pct, 2)

            if is_opt:
                float_pnl = profit_dist * 0.60 * qty
                margin = pos.get("marginInr", 12000.0 * self.index_lots)
            else:
                float_pnl = profit_dist * qty
                margin = pos.get("marginInr", entry * qty * 0.20)
            roe = (float_pnl / margin) * 100.0 if margin > 0 else 0.0

            pos["floatingPnlInr"] = round(float_pnl, 2)
            pos["currentNetRoePct"] = round(roe, 2)

            if "peakRupeeGain" not in pos:
                pos["peakRupeeGain"] = max(0.0, float_pnl)
            else:
                pos["peakRupeeGain"] = max(pos["peakRupeeGain"], float_pnl)

            peak_gain = pos["peakRupeeGain"]
            mult = (qty * 0.60) if is_opt else qty

            # 6-STAGE LADDER
            scale_factor = self.index_lots if is_opt else 1.0

            # TP 1: 500 * scale (Locks +300 * scale)
            tp1_target = 500.0 * scale_factor
            lock1 = 300.0 * scale_factor
            if pos["stage"] == 0 and peak_gain >= tp1_target:
                pos["stage"] = 1
                pos["currentMilestone"] = f"TP 1 (+₹{tp1_target:.0f})"
                buf_pts = lock1 / mult
                new_sl = round(entry + buf_pts if is_buy else entry - buf_pts, 2)
                if (is_buy and new_sl > pos["slPrice"]) or (not is_buy and new_sl < pos["slPrice"]):
                    pos["slPrice"] = new_sl
                pos["stageNote"] = f"🎯 TP 1 HIT (+₹{tp1_target:.0f}) • Locked +₹{lock1:.0f}"

            # TP 2: 1000 * scale (Locks +700 * scale)
            tp2_target = 1000.0 * scale_factor
            lock2 = 700.0 * scale_factor
            if pos["stage"] <= 1 and peak_gain >= tp2_target:
                pos["stage"] = 2
                pos["currentMilestone"] = f"TP 2 (+₹{tp2_target:.0f})"
                buf_pts = lock2 / mult
                new_sl = round(entry + buf_pts if is_buy else entry - buf_pts, 2)
                if (is_buy and new_sl > pos["slPrice"]) or (not is_buy and new_sl < pos["slPrice"]):
                    pos["slPrice"] = new_sl
                pos["stageNote"] = f"🎯 TP 2 HIT (+₹{tp2_target:.0f}) • Locked +₹{lock2:.0f}"

            # TP 3: 1500 * scale (Locks +1150 * scale)
            tp3_target = 1500.0 * scale_factor
            lock3 = 1150.0 * scale_factor
            if pos["stage"] <= 2 and peak_gain >= tp3_target:
                pos["stage"] = 3
                pos["currentMilestone"] = f"TP 3 (+₹{tp3_target:.0f})"
                buf_pts = lock3 / mult
                new_sl = round(entry + buf_pts if is_buy else entry - buf_pts, 2)
                if (is_buy and new_sl > pos["slPrice"]) or (not is_buy and new_sl < pos["slPrice"]):
                    pos["slPrice"] = new_sl
                pos["stageNote"] = f"🎯 TP 3 HIT (+₹{tp3_target:.0f}) • Locked +₹{lock3:.0f}"

            # TP 4: 2000 * scale (Locks +1600 * scale)
            tp4_target = 2000.0 * scale_factor
            lock4 = 1600.0 * scale_factor
            if pos["stage"] <= 3 and peak_gain >= tp4_target:
                pos["stage"] = 4
                pos["currentMilestone"] = f"TP 4 (+₹{tp4_target:.0f})"
                buf_pts = lock4 / mult
                new_sl = round(entry + buf_pts if is_buy else entry - buf_pts, 2)
                if (is_buy and new_sl > pos["slPrice"]) or (not is_buy and new_sl < pos["slPrice"]):
                    pos["slPrice"] = new_sl
                pos["stageNote"] = f"🎯 TP 4 HIT (+₹{tp4_target:.0f}) • Locked +₹{lock4:.0f}"

            # TP 5: 2500 * scale (Locks +2100 * scale)
            tp5_target = 2500.0 * scale_factor
            lock5 = 2100.0 * scale_factor
            if pos["stage"] <= 4 and peak_gain >= tp5_target:
                pos["stage"] = 5
                pos["currentMilestone"] = f"TP 5 (+₹{tp5_target:.0f})"
                buf_pts = lock5 / mult
                new_sl = round(entry + buf_pts if is_buy else entry - buf_pts, 2)
                if (is_buy and new_sl > pos["slPrice"]) or (not is_buy and new_sl < pos["slPrice"]):
                    pos["slPrice"] = new_sl
                pos["stageNote"] = f"🎯 TP 5 HIT (+₹{tp5_target:.0f}) • Locked +₹{lock5:.0f}"

            # TP 6: If allow_open_runner, trail 80% of peak gain after +3000
            tp6_target = 3000.0 * scale_factor
            if peak_gain >= tp6_target:
                pos["stage"] = 6
                # Dynamic high-watermark trail: Lock 75% of peak gain
                trail_lock = peak_gain * 0.75
                buf_pts = trail_lock / mult
                new_sl = round(entry + buf_pts if is_buy else entry - buf_pts, 2)
                if (is_buy and new_sl > pos["slPrice"]) or (not is_buy and new_sl < pos["slPrice"]):
                    pos["slPrice"] = new_sl
                pos["stageNote"] = f"🚀 SUPER RUNNER (+₹{peak_gain:.0f}) • Locked +₹{trail_lock:.0f}"

            # Check Exits
            exit_reason = None
            exit_price = curr_p

            max_cap = 1500.0 * scale_factor
            if float_pnl <= -max_cap:
                exit_price = curr_p
                exit_reason = "MAX_LOSS_CAP_HIT"
            elif not self.allow_open_runner and float_pnl >= tp6_target:
                target_pts = tp6_target / mult
                exit_price = round(entry + target_pts if is_buy else entry - target_pts, 2)
                exit_reason = "TP_6_EXIT"
            elif pos["stage"] >= 1 and ((is_buy and curr_p <= pos["slPrice"]) or (not is_buy and curr_p >= pos["slPrice"])):
                exit_price = pos["slPrice"]
                exit_reason = f"TP_{pos['stage']}_EXIT"
            elif pos["stage"] == 0 and ((is_buy and curr_p <= pos["slPrice"]) or (not is_buy and curr_p >= pos["slPrice"])):
                bars = day_bars.get(sym, [])
                c_bar = bars[bar_idx] if bar_idx < len(bars) else None
                reversal_likely = False
                wick_invalidation = False
                if c_bar:
                    h_b = float(c_bar["high"])
                    l_b = float(c_bar["low"])
                    o_b = float(c_bar["open"])
                    c_b = float(c_bar["close"])
                    rng = max(h_b - l_b, 0.05)
                    lower_wick = (min(o_b, c_b) - l_b) / rng
                    upper_wick = (h_b - max(o_b, c_b)) / rng
                    reversal_likely = (lower_wick >= 0.28) if is_buy else (upper_wick >= 0.28)
                    wick_invalidation = (curr_p < l_b) if is_buy else (curr_p > h_b)

                if reversal_likely and not wick_invalidation and float_pnl > (-900.0 * scale_factor):
                    pass
                else:
                    exit_price = pos["slPrice"]
                    exit_reason = "SMART_SL_EXIT"
            elif pos["stage"] == 0 and float_pnl <= (-350.0 * scale_factor):
                sym_bars = day_bars.get(sym, [])
                if sym_bars and bar_idx < len(sym_bars):
                    s_c = float(sym_bars[bar_idx]["close"])
                    s_sess = sym_bars[:bar_idx + 1]
                    s_pv = sum(((float(b["high"]) + float(b["low"]) + float(b["close"])) / 3.0) * max(float(b.get("volume", 1)), 1.0) for b in s_sess)
                    s_v = sum(max(float(b.get("volume", 1)), 1.0) for b in s_sess)
                    s_vwap = (s_pv / s_v) if s_v > 0 else s_c
                    own_trend_broken = (is_buy and s_c < s_vwap * 0.997) or (not is_buy and s_c > s_vwap * 1.003)
                    if own_trend_broken:
                        exit_price = curr_p
                        exit_reason = "SMART_SL_EXIT"

            if exit_reason:
                self.close_position(pos, exit_price, exit_reason, cur_time_str)
            else:
                remaining.append(pos)

        self.active_positions = remaining

    def evaluate_seat_signals(self):
        # Strict Daily Circuit Breaker: If today's realized loss touches daily_circuit_limit, HALT!
        if self.realized_pnl_inr <= self.daily_circuit_limit:
            return

        # 2 Consecutive Morning Losses Chop Shield:
        losses_so_far = [t for t in self.closed_ledger if t.get('netPnlInr', 0) < 0]
        wins_so_far = [t for t in self.closed_ledger if t.get('netPnlInr', 0) > 0]
        if len(losses_so_far) >= 2 and len(wins_so_far) == 0:
            return

        if len(self.active_positions) >= 4:
            return

        bar_idx = min(74, self.second_of_day // 300)
        day_bars = self.by_date_5m.get(self.current_date, {})
        cur_time_str = self.get_formatted_time()

        nifty_bars = day_bars.get("NIFTY", [])
        if nifty_bars and bar_idx < len(nifty_bars):
            n_c = float(nifty_bars[bar_idx]["close"])
            n_sess = nifty_bars[:bar_idx + 1]
            n_pv = sum(((float(b["high"]) + float(b["low"]) + float(b["close"])) / 3.0) * max(float(b.get("volume", 1)), 1.0) for b in n_sess)
            n_v = sum(max(float(b.get("volume", 1)), 1.0) for b in n_sess)
            n_vwap = (n_pv / n_v) if n_v > 0 else n_c
            market_is_bullish = n_c >= n_vwap
        else:
            market_is_bullish = True

        active_index_count = sum(1 for p in self.active_positions if p["symbol"] in INDEX_SET)

        for sym in WHITELIST_14_SYMBOLS:
            if len(self.active_positions) >= 4:
                break
            if any(p["symbol"] == sym for p in self.active_positions):
                continue
            if self.symbol_trades_today.get(sym, 0) >= 1:
                continue

            is_idx = sym in INDEX_SET
            if is_idx and active_index_count >= 2:
                continue

            bars = day_bars.get(sym, [])
            if bar_idx < 3 or bar_idx >= len(bars) - 10:
                continue

            c = bars[bar_idx]
            close_p = float(c["close"])
            open_p = float(c["open"])
            high_p = float(c["high"])
            low_p = float(c["low"])

            session_bars = bars[:bar_idx + 1]
            cum_pv = sum(((float(b["high"]) + float(b["low"]) + float(b["close"])) / 3.0) * max(float(b.get("volume", 1)), 1.0) for b in session_bars)
            cum_v = sum(max(float(b.get("volume", 1)), 1.0) for b in session_bars)
            vwap = (cum_pv / cum_v) if cum_v > 0 else close_p

            closes = [float(b["close"]) for b in session_bars]
            k9 = 2.0 / 10
            k21 = 2.0 / 22
            ema9 = closes[0]
            ema21 = closes[0]
            for cl in closes:
                ema9 = cl * k9 + ema9 * (1 - k9)
                ema21 = cl * k21 + ema21 * (1 - k21)

            first3 = bars[:3]
            orh = max(float(b["high"]) for b in first3)
            orl = min(float(b["low"]) for b in first3)
            index_chop_filter_buy = (not is_idx) or (close_p > orh or close_p > vwap * 1.0015)
            index_chop_filter_sell = (not is_idx) or (close_p < orl or close_p < vwap * 0.9985)

            past5 = bars[max(0, bar_idx - 5):bar_idx + 1]
            swing_low5 = min(float(b["low"]) for b in past5)
            swing_high5 = max(float(b["high"]) for b in past5)

            scale = self.index_lots if is_idx else 1

            if sym == "NIFTY":
                sl_pts_buy = max(45.0, close_p - swing_low5 + 10.0)
                sl_pts_sell = max(45.0, swing_high5 - close_p + 10.0)
                lot = 25 * scale
            elif sym == "BANKNIFTY":
                sl_pts_buy = max(90.0, close_p - swing_low5 + 15.0)
                sl_pts_sell = max(90.0, swing_high5 - close_p + 15.0)
                lot = 15 * scale
            elif sym == "SENSEX":
                sl_pts_buy = max(140.0, close_p - swing_low5 + 20.0)
                sl_pts_sell = max(140.0, swing_high5 - close_p + 20.0)
                lot = 10 * scale
            elif sym == "FINNIFTY":
                sl_pts_buy = max(45.0, close_p - swing_low5 + 10.0)
                sl_pts_sell = max(45.0, swing_high5 - close_p + 10.0)
                lot = 25 * scale
            else:
                sl_pts_buy = max(close_p * 0.008, (close_p - swing_low5) + (close_p * 0.002))
                sl_pts_sell = max(close_p * 0.008, (swing_high5 - close_p) + (close_p * 0.002))
                lot = max(10, min(100, int(1500.0 / sl_pts_buy)))

            if market_is_bullish and close_p > vwap and ema9 > ema21 and close_p > open_p and low_p <= ema9 * 1.002 and index_chop_filter_buy:
                sl_price = round(close_p - sl_pts_buy, 2)
                multiplier = (lot * 0.60) if is_idx else lot

                self.trade_counter += 1
                self.symbol_trades_today[sym] = 1
                if is_idx: active_index_count += 1

                pos = {
                    "id": f"{self.trade_counter:04d}",
                    "symbol": sym,
                    "displayName": DISPLAY_NAMES.get(sym, sym),
                    "side": "BUY",
                    "seatBucket": "NIFTY_BANKNIFTY_OPTION_SEAT" if is_idx else "NORMAL_TREND_RUNNER_SEAT",
                    "isOption": is_idx,
                    "optionType": "CALL" if is_idx else None,
                    "optionStrike": round(close_p / 100) * 100 if is_idx else None,
                    "entryPrice": close_p,
                    "currentPrice": close_p,
                    "initialSlPrice": sl_price,
                    "slPrice": sl_price,
                    "quantity": lot,
                    "marginInr": (12000.0 * scale) if is_idx else round(close_p * lot * 0.20, 2),
                    "floatingPnlInr": 0.0,
                    "currentNetRoePct": 0.0,
                    "progressPct": 0.0,
                    "stage": 0,
                    "currentMilestone": "Running to TP 1",
                    "stageNote": "RUNNING TO TP 1",
                    "peakRupeeGain": 0.0,
                    "maxLossCapInr": 1500.0 * scale,
                    "openedAtFormatted": cur_time_str,
                    "strategyName": f"SMART_SL_{scale}X ({'0.60Δ_CE' if is_idx else 'EQUITY_BUY'})"
                }
                self.active_positions.append(pos)

            elif (not market_is_bullish) and close_p < vwap and ema9 < ema21 and close_p < open_p and high_p >= ema9 * 0.998 and index_chop_filter_sell:
                sl_price = round(close_p + sl_pts_sell, 2)
                multiplier = (lot * 0.60) if is_idx else lot

                self.trade_counter += 1
                self.symbol_trades_today[sym] = 1
                if is_idx: active_index_count += 1

                pos = {
                    "id": f"{self.trade_counter:04d}",
                    "symbol": sym,
                    "displayName": DISPLAY_NAMES.get(sym, sym),
                    "side": "SELL",
                    "seatBucket": "NIFTY_BANKNIFTY_OPTION_SEAT" if is_idx else "NORMAL_TREND_RUNNER_SEAT",
                    "isOption": is_idx,
                    "optionType": "PUT" if is_idx else None,
                    "optionStrike": round(close_p / 100) * 100 if is_idx else None,
                    "entryPrice": close_p,
                    "currentPrice": close_p,
                    "initialSlPrice": sl_price,
                    "slPrice": sl_price,
                    "quantity": lot,
                    "marginInr": (12000.0 * scale) if is_idx else round(close_p * lot * 0.20, 2),
                    "floatingPnlInr": 0.0,
                    "currentNetRoePct": 0.0,
                    "progressPct": 0.0,
                    "stage": 0,
                    "currentMilestone": "Running to TP 1",
                    "stageNote": "RUNNING TO TP 1",
                    "peakRupeeGain": 0.0,
                    "maxLossCapInr": 1500.0 * scale,
                    "openedAtFormatted": cur_time_str,
                    "strategyName": f"SMART_SL_{scale}X ({'0.60Δ_PE' if is_idx else 'EQUITY_SHORT'})"
                }
                self.active_positions.append(pos)

def test_config(lots, circuit, open_runner, label):
    eng = Target30PctReplayEngine(index_lots=lots, daily_circuit_limit=circuit, allow_open_runner=open_runner)
    oct_dates = [d for d in eng.sorted_dates if "-10-" in d]

    total_pnl = 0.0
    total_trades = 0
    total_wins = 0

    for d in oct_dates:
        eng.set_date(d, auto_play=True)
        eng.is_running = True
        for _ in range(TOTAL_DAY_SECONDS // 5):
            eng.advance_seconds(5)
        st = eng.get_state()
        w = st['wallet']
        total_pnl += w['realizedPnlInr']
        total_trades += w['totalTrades']
        total_wins += w['wins']

    wr = total_wins / max(1, total_trades) * 100.0
    ret_pct = total_pnl / 100000.0 * 100.0
    print(f"{label:<38} | Net PnL: ₹{total_pnl:>9,.2f} ({ret_pct:>+5.1f}%) | Trades: {total_trades:>3} | WR: {wr:>5.1f}%")
    return total_pnl

if __name__ == '__main__':
    print("=" * 80)
    print("  OCTOBER 2026 ROADMAP TO 25% - 35% MONTHLY RETURN")
    print("=" * 80)
    test_config(1, -2000.0, False, "1. 1-Lot Baseline + Strict Chop Halt")
    test_config(1, -2000.0, True,  "2. 1-Lot + Open Super-Runner Trail")
    test_config(2, -2500.0, False, "3. 2-Lot Sizing + Strict Chop Halt")
    test_config(2, -2500.0, True,  "4. 2-Lot Sizing + Open Super-Runner")
    print("=" * 80)
