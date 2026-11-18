import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.replay_engine import IndianPastDateReplayEngine, WHITELIST_14_SYMBOLS, INDEX_SET, DISPLAY_NAMES, TOTAL_DAY_SECONDS

class AdaptiveDualRegimeEngine(IndianPastDateReplayEngine):
    """
    Adaptive Dual-Regime Market Engine:
    1. Trend Regime (Breadth >= 70%):
       - Activates 6-Stage Institutional Momentum Ladder (500 -> 1000 -> 1500 -> 2000 -> 2500 -> 3000)
    2. Chop / Rangebound Regime (Breadth < 70%):
       - Activates Mean-Reversion Ping-Pong Scalper
       - Buys dip at Lower Band/ORL back to VWAP (+₹400 quick lock, -₹350 tight SL)
       - Sells pop at Upper Band/ORH back to VWAP (+₹400 quick lock, -₹350 tight SL)
       - Capitalizes on the sideways churn instead of bleeding or sitting completely flat!
    """
    def evaluate_seat_signals(self):
        if self.realized_pnl_inr <= -2500.0:
            return

        if self.second_of_day < 2700: # Wait for 10:00 AM
            return

        if len(self.active_positions) >= 4:
            return

        bar_idx = min(74, self.second_of_day // 300)
        day_bars = self.by_date_5m.get(self.current_date, {})
        cur_time_str = self.get_formatted_time()

        # Compute Market Breadth across 14 symbols
        bull_count = 0
        bear_count = 0
        total_syms = 0
        vwaps = {}
        for s in WHITELIST_14_SYMBOLS:
            s_bars = day_bars.get(s, [])
            if len(s_bars) > bar_idx:
                s_sess = s_bars[:bar_idx + 1]
                s_c = float(s_bars[bar_idx]["close"])
                s_pv = sum(((float(b["high"]) + float(b["low"]) + float(b["close"])) / 3.0) * max(float(b.get("volume", 1)), 1.0) for b in s_sess)
                s_v = sum(max(float(b.get("volume", 1)), 1.0) for b in s_sess)
                s_vwap = (s_pv / s_v) if s_v > 0 else s_c
                vwaps[s] = s_vwap
                if s_c > s_vwap:
                    bull_count += 1
                else:
                    bear_count += 1
                total_syms += 1

        breadth_ratio = (max(bull_count, bear_count) / max(1, total_syms)) * 100.0
        is_trend_regime = breadth_ratio >= 70.0
        market_is_bullish = bull_count > bear_count

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
            vwap = vwaps.get(sym, close_p)

            # EMA 9 & EMA 21
            closes = [float(b["close"]) for b in bars[:bar_idx + 1]]
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

            past5 = bars[max(0, bar_idx - 5):bar_idx + 1]
            swing_low5 = min(float(b["low"]) for b in past5)
            swing_high5 = max(float(b["high"]) for b in past5)

            if sym == "NIFTY":
                lot = 25
                sl_pts_buy = max(45.0, close_p - swing_low5 + 10.0)
                sl_pts_sell = max(45.0, swing_high5 - close_p + 10.0)
            elif sym == "BANKNIFTY":
                lot = 15
                sl_pts_buy = max(90.0, close_p - swing_low5 + 15.0)
                sl_pts_sell = max(90.0, swing_high5 - close_p + 15.0)
            elif sym == "SENSEX":
                lot = 10
                sl_pts_buy = max(140.0, close_p - swing_low5 + 20.0)
                sl_pts_sell = max(140.0, swing_high5 - close_p + 20.0)
            elif sym == "FINNIFTY":
                lot = 25
                sl_pts_buy = max(45.0, close_p - swing_low5 + 10.0)
                sl_pts_sell = max(45.0, swing_high5 - close_p + 10.0)
            else:
                sl_pts_buy = max(close_p * 0.008, (close_p - swing_low5) + (close_p * 0.002))
                sl_pts_sell = max(close_p * 0.008, (swing_high5 - close_p) + (close_p * 0.002))
                lot = max(10, min(100, int(1500.0 / sl_pts_buy)))

            multiplier = (lot * 0.60) if is_idx else lot

            # =========================================================
            # REGIME 1: SUPER-TREND MOMENTUM (Breadth >= 70%)
            # =========================================================
            if is_trend_regime:
                index_chop_filter_buy = (not is_idx) or (close_p > orh or close_p > vwap * 1.0015)
                index_chop_filter_sell = (not is_idx) or (close_p < orl or close_p < vwap * 0.9985)

                if market_is_bullish and close_p > vwap and ema9 > ema21 and close_p > open_p and low_p <= ema9 * 1.002 and index_chop_filter_buy:
                    sl_price = round(close_p - sl_pts_buy, 2)
                    tp1_target = round(close_p + (500.0 / multiplier), 2)
                    tp2_target = round(close_p + (1000.0 / multiplier), 2)
                    tp3_target = round(close_p + (1500.0 / multiplier), 2)
                    tp4_target = round(close_p + (2000.0 / multiplier), 2)
                    tp5_target = round(close_p + (2500.0 / multiplier), 2)
                    tp6_target = round(close_p + (3000.0 / multiplier), 2)

                    self.trade_counter += 1
                    self.symbol_trades_today[sym] = 1
                    if is_idx: active_index_count += 1
                    pos = {
                        "id": f"{self.trade_counter:04d}",
                        "symbol": sym,
                        "displayName": sym,
                        "side": "BUY",
                        "seatBucket": "NIFTY_BANKNIFTY_OPTION_SEAT" if is_idx else "NORMAL_TREND_RUNNER_SEAT",
                        "isOption": is_idx,
                        "optionType": "CALL" if is_idx else None,
                        "optionStrike": round(close_p / 100) * 100 if is_idx else None,
                        "entryPrice": close_p,
                        "currentPrice": close_p,
                        "initialSlPrice": sl_price,
                        "slPrice": sl_price,
                        "initialTpPrice": tp1_target,
                        "tpPrice": tp1_target,
                        "beTargetPrice": tp1_target,
                        "tp1TargetPrice": tp1_target,
                        "tp2TargetPrice": tp2_target,
                        "tp3TargetPrice": tp3_target,
                        "tp4TargetPrice": tp4_target,
                        "tp5TargetPrice": tp5_target,
                        "tp6TargetPrice": tp6_target,
                        "targetType": "TP_6STAGE_500_3000_LADDER",
                        "quantity": lot,
                        "marginInr": 12000.0 if is_idx else round(close_p * lot * 0.20, 2),
                        "floatingPnlInr": 0.0,
                        "currentNetRoePct": 0.0,
                        "progressPct": 0.0,
                        "stage": 0,
                        "currentMilestone": "ENTRY",
                        "peakRupeeGain": 0.0,
                        "maxLossCapInr": 1500.0,
                        "openedAtFormatted": cur_time_str,
                        "strategyName": f"SUPER_TREND_MOMENTUM ({'CE' if is_idx else 'BUY'})"
                    }
                    self.active_positions.append(pos)

                elif not market_is_bullish and close_p < vwap and ema9 < ema21 and close_p < open_p and high_p >= ema9 * 0.998 and index_chop_filter_sell:
                    sl_price = round(close_p + sl_pts_sell, 2)
                    tp1_target = round(close_p - (500.0 / multiplier), 2)
                    tp2_target = round(close_p - (1000.0 / multiplier), 2)
                    tp3_target = round(close_p - (1500.0 / multiplier), 2)
                    tp4_target = round(close_p - (2000.0 / multiplier), 2)
                    tp5_target = round(close_p - (2500.0 / multiplier), 2)
                    tp6_target = round(close_p - (3000.0 / multiplier), 2)

                    self.trade_counter += 1
                    self.symbol_trades_today[sym] = 1
                    if is_idx: active_index_count += 1
                    pos = {
                        "id": f"{self.trade_counter:04d}",
                        "symbol": sym,
                        "displayName": sym,
                        "side": "SELL",
                        "seatBucket": "NIFTY_BANKNIFTY_OPTION_SEAT" if is_idx else "NORMAL_TREND_RUNNER_SEAT",
                        "isOption": is_idx,
                        "optionType": "PUT" if is_idx else None,
                        "optionStrike": round(close_p / 100) * 100 if is_idx else None,
                        "entryPrice": close_p,
                        "currentPrice": close_p,
                        "initialSlPrice": sl_price,
                        "slPrice": sl_price,
                        "initialTpPrice": tp1_target,
                        "tpPrice": tp1_target,
                        "beTargetPrice": tp1_target,
                        "tp1TargetPrice": tp1_target,
                        "tp2TargetPrice": tp2_target,
                        "tp3TargetPrice": tp3_target,
                        "tp4TargetPrice": tp4_target,
                        "tp5TargetPrice": tp5_target,
                        "tp6TargetPrice": tp6_target,
                        "targetType": "TP_6STAGE_500_3000_LADDER",
                        "quantity": lot,
                        "marginInr": 12000.0 if is_idx else round(close_p * lot * 0.20, 2),
                        "floatingPnlInr": 0.0,
                        "currentNetRoePct": 0.0,
                        "progressPct": 0.0,
                        "stage": 0,
                        "currentMilestone": "ENTRY",
                        "peakRupeeGain": 0.0,
                        "maxLossCapInr": 1500.0,
                        "openedAtFormatted": cur_time_str,
                        "strategyName": f"SUPER_TREND_MOMENTUM ({'PE' if is_idx else 'SELL'})"
                    }
                    self.active_positions.append(pos)

            # =========================================================
            # REGIME 2: MEAN-REVERSION PING-PONG SCALPER (Chop Regime: Breadth < 70%)
            # =========================================================
            else:
                # In Chop: Price oscillates around VWAP between Support (ORL/SwingLow) and Resistance (ORH/SwingHigh)
                # Quick Scalp: Target +₹400, Tight SL -₹350 (No runners, take quick cash from the chop!)
                dist_from_vwap_pct = ((close_p - vwap) / vwap) * 100.0
                rng = max(high_p - low_p, 0.05)
                lower_wick = (min(open_p, close_p) - low_p) / rng
                upper_wick = (high_p - max(open_p, close_p)) / rng

                # BUY DIP: Price is below VWAP by 0.25% - 0.70%, near swing low, lower rejection wick >= 30%
                if -0.70 <= dist_from_vwap_pct <= -0.20 and lower_wick >= 0.30 and close_p > open_p:
                    target_pts = 400.0 / multiplier
                    sl_pts = 350.0 / multiplier
                    sl_p = round(close_p - sl_pts, 2)
                    tp_p = round(close_p + target_pts, 2)

                    self.trade_counter += 1
                    self.symbol_trades_today[sym] = 1
                    if is_idx: active_index_count += 1

                    pos = {
                        "id": f"{self.trade_counter:04d}",
                        "symbol": sym,
                        "displayName": sym,
                        "side": "BUY",
                        "seatBucket": "CHOP_PING_PONG_SEAT",
                        "isOption": is_idx,
                        "optionType": "CALL" if is_idx else None,
                        "optionStrike": round(close_p / 100) * 100 if is_idx else None,
                        "entryPrice": close_p,
                        "currentPrice": close_p,
                        "initialSlPrice": sl_p,
                        "slPrice": sl_p,
                        "initialTpPrice": tp_p,
                        "tpPrice": tp_p,
                        "beTargetPrice": tp_p,
                        "tp1TargetPrice": tp_p,
                        "tp2TargetPrice": tp_p,
                        "tp3TargetPrice": tp_p,
                        "tp4TargetPrice": tp_p,
                        "tp5TargetPrice": tp_p,
                        "tp6TargetPrice": tp_p,
                        "targetType": "CHOP_PING_PONG_SCALP",
                        "quantity": lot,
                        "marginInr": 12000.0 if is_idx else round(close_p * lot * 0.20, 2),
                        "floatingPnlInr": 0.0,
                        "currentNetRoePct": 0.0,
                        "progressPct": 0.0,
                        "stage": 0,
                        "currentMilestone": "CHOP_SCALP_400",
                        "peakRupeeGain": 0.0,
                        "maxLossCapInr": 500.0,
                        "openedAtFormatted": cur_time_str,
                        "strategyName": f"CHOP_PING_PONG ({'CE' if is_idx else 'BUY'})"
                    }
                    self.active_positions.append(pos)

                # SELL POP: Price is above VWAP by 0.25% - 0.70%, near swing high, upper rejection wick >= 30%
                elif 0.20 <= dist_from_vwap_pct <= 0.70 and upper_wick >= 0.30 and close_p < open_p:
                    target_pts = 400.0 / multiplier
                    sl_pts = 350.0 / multiplier
                    sl_p = round(close_p + sl_pts, 2)
                    tp_p = round(close_p - target_pts, 2)

                    self.trade_counter += 1
                    self.symbol_trades_today[sym] = 1
                    if is_idx: active_index_count += 1

                    pos = {
                        "id": f"{self.trade_counter:04d}",
                        "symbol": sym,
                        "displayName": sym,
                        "side": "SELL",
                        "seatBucket": "CHOP_PING_PONG_SEAT",
                        "isOption": is_idx,
                        "optionType": "PUT" if is_idx else None,
                        "optionStrike": round(close_p / 100) * 100 if is_idx else None,
                        "entryPrice": close_p,
                        "currentPrice": close_p,
                        "initialSlPrice": sl_p,
                        "slPrice": sl_p,
                        "initialTpPrice": tp_p,
                        "tpPrice": tp_p,
                        "beTargetPrice": tp_p,
                        "tp1TargetPrice": tp_p,
                        "tp2TargetPrice": tp_p,
                        "tp3TargetPrice": tp_p,
                        "tp4TargetPrice": tp_p,
                        "tp5TargetPrice": tp_p,
                        "tp6TargetPrice": tp_p,
                        "targetType": "CHOP_PING_PONG_SCALP",
                        "quantity": lot,
                        "marginInr": 12000.0 if is_idx else round(close_p * lot * 0.20, 2),
                        "floatingPnlInr": 0.0,
                        "currentNetRoePct": 0.0,
                        "progressPct": 0.0,
                        "stage": 0,
                        "currentMilestone": "CHOP_SCALP_400",
                        "peakRupeeGain": 0.0,
                        "maxLossCapInr": 500.0,
                        "openedAtFormatted": cur_time_str,
                        "strategyName": f"CHOP_PING_PONG ({'PE' if is_idx else 'SELL'})"
                    }
                    self.active_positions.append(pos)

    def evaluate_active_positions_tick(self):
        cur_time_str = self.get_formatted_time()
        remaining = []
        day_bars = self.by_date_5m.get(self.current_date, {})
        bar_idx = min(74, self.second_of_day // 300)

        for pos in self.active_positions:
            sym = pos["symbol"]
            curr_p = self.live_prices.get(sym, pos["currentPrice"])
            pos["currentPrice"] = curr_p
            is_buy = pos["side"] == "BUY"
            entry = pos["entryPrice"]
            qty = pos.get("quantity", 1)
            is_opt = pos.get("isOption", False)

            profit_dist = (curr_p - entry) if is_buy else (entry - curr_p)
            gain_pct = (profit_dist / entry) * 100.0
            pos["gainPct"] = round(gain_pct, 2)

            float_pnl = profit_dist * 0.60 * qty if is_opt else profit_dist * qty
            pos["floatingPnlInr"] = round(float_pnl, 2)

            if "peakRupeeGain" not in pos:
                pos["peakRupeeGain"] = max(0.0, float_pnl)
            else:
                pos["peakRupeeGain"] = max(pos["peakRupeeGain"], float_pnl)
            peak_gain = pos["peakRupeeGain"]

            mult = (qty * 0.60) if is_opt else qty

            # Is this a CHOP Ping-Pong trade or a Trend Ladder trade?
            if pos.get("targetType") == "CHOP_PING_PONG_SCALP":
                # Quick scalp rules: TP +₹400, SL -₹350
                exit_reason = None
                exit_price = curr_p
                if float_pnl >= 400.0:
                    exit_reason = "CHOP_SCALP_TP_HIT"
                    pts = 400.0 / mult
                    exit_price = round(entry + pts if is_buy else entry - pts, 2)
                elif float_pnl <= -350.0 or ((is_buy and curr_p <= pos["slPrice"]) or (not is_buy and curr_p >= pos["slPrice"])):
                    exit_reason = "CHOP_SCALP_SL_HIT"
                    exit_price = pos["slPrice"]

                if exit_reason:
                    self.close_position(pos, exit_price, exit_reason, cur_time_str)
                else:
                    remaining.append(pos)
                continue

            # Standard 6-Stage Ladder for Trend trades:
            if pos["stage"] == 0 and peak_gain >= 500.0:
                pos["stage"] = 1
                pos["currentMilestone"] = "TP 1 (+₹500)"
                buf_pts = 300.0 / mult
                new_sl = round(entry + buf_pts if is_buy else entry - buf_pts, 2)
                if (is_buy and new_sl > pos["slPrice"]) or (not is_buy and new_sl < pos["slPrice"]):
                    pos["slPrice"] = new_sl
            if pos["stage"] <= 1 and peak_gain >= 1000.0:
                pos["stage"] = 2
                pos["currentMilestone"] = "TP 2 (+₹1,000)"
                buf_pts = 700.0 / mult
                new_sl = round(entry + buf_pts if is_buy else entry - buf_pts, 2)
                if (is_buy and new_sl > pos["slPrice"]) or (not is_buy and new_sl < pos["slPrice"]):
                    pos["slPrice"] = new_sl
            if pos["stage"] <= 2 and peak_gain >= 1500.0:
                pos["stage"] = 3
                pos["currentMilestone"] = "TP 3 (+₹1,500)"
                buf_pts = 1150.0 / mult
                new_sl = round(entry + buf_pts if is_buy else entry - buf_pts, 2)
                if (is_buy and new_sl > pos["slPrice"]) or (not is_buy and new_sl < pos["slPrice"]):
                    pos["slPrice"] = new_sl

            pos["progressPct"] = round(min(100.0, max(0.0, float_pnl * 100.0 / 500.0)), 1) if pos["stage"] == 0 else 100.0

            exit_reason = None
            exit_price = curr_p
            if float_pnl <= -1500.0:
                exit_price = curr_p
                exit_reason = "MAX_LOSS_CAP_HIT"
            elif float_pnl >= 3000.0:
                target_pts = 3000.0 / mult
                exit_price = round(entry + target_pts if is_buy else entry - target_pts, 2)
                exit_reason = "TP_6_EXIT"
            elif pos["stage"] >= 1 and ((is_buy and curr_p <= pos["slPrice"]) or (not is_buy and curr_p >= pos["slPrice"])):
                exit_price = pos["slPrice"]
                exit_reason = f"TP_{pos['stage']}_EXIT"
            elif pos["stage"] == 0 and ((is_buy and curr_p <= pos["slPrice"]) or (not is_buy and curr_p >= pos["slPrice"])):
                exit_price = pos["slPrice"]
                exit_reason = "SMART_SL_EXIT"
            elif pos["stage"] == 0 and float_pnl <= -350.0:
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

if __name__ == '__main__':
    eng = AdaptiveDualRegimeEngine()
    def test_month(month_str, month_name):
        dates = [d for d in eng.sorted_dates if f"-{month_str}-" in d]
        tot_pnl = 0.0
        tot_trades = 0
        tot_wins = 0
        win_days = 0
        for d in dates:
            eng.set_date(d, auto_play=True)
            for _ in range(TOTAL_DAY_SECONDS // 5):
                eng.advance_seconds(5)
            st = eng.get_state()
            w = st['wallet']
            pnl = w['realizedPnlInr']
            tot_pnl += pnl
            tot_trades += w['totalTrades']
            tot_wins += w['wins']
            if pnl > 0: win_days += 1
        
        wr = (tot_wins / max(1, tot_trades)) * 100.0
        ret_pct = (tot_pnl / 100000.0) * 100.0
        roe_margin = (tot_pnl / 25000.0) * 100.0
        print(f"{month_name:<16} | PnL: INR {tot_pnl:>10,.2f} ({ret_pct:>+6.2f}%) | Margin ROE: {roe_margin:>+6.1f}% | Trades: {tot_trades:>3} (WR: {wr:>5.1f}%) | Green Days: {win_days:>2}/{len(dates)}")
        return tot_pnl

    print("Adaptive Dual-Regime Results (Trend Runner + Chop Ping-Pong Scalper):")
    print("=" * 85)
    p_aug = test_month("08", "August 2026")
    p_sep = test_month("09", "September 2026")
    p_oct = test_month("10", "October 2026")
    p_nov = test_month("11", "November 2026")
    print("-" * 85)
    tot_all = p_aug + p_sep + p_oct + p_nov
    print(f"Total 60-Day PnL: INR {tot_all:,.2f} (+{tot_all/1000:.2f}% on 1L Base, +{tot_all/250:.2f}% on Deployed Margin)")
