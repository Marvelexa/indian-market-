import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS, WHITELIST_14_SYMBOLS, INDEX_SET, DISPLAY_NAMES

class UltimateBreakthroughEngine(IndianPastDateReplayEngine):
    """
    Ultimate Confluence Anti-Chop Engine:
    1. Trend Regime (Breadth >= 70% OR Index Breaking ORH/ORL with momentum):
       - Allows Index Options (Nifty, BankNifty) + Equity Trend Runners
       - Rides the full 6-Stage Ladder: +500 -> +1000 -> +1500 -> +2000 -> +2500 -> +3000
    2. Chop / Rangebound Regime (Breadth < 70%):
       - ZERO Index Option buying (protects from theta bleed and false wicks)
       - Equities Only: Mean-Reversion Ping-Pong (+400 scalp, -350 tight SL)
    3. Daily Circuit Breaker: -INR 2,500 (Gives breathing room for big October trends, avoids suffocating multi-thousand rupee winners)
    4. Smart Cost Lock: When any trade reaches +INR 400 floating, immediately advance SL to Cost + 1 pt (Locks capital, eliminates winning trades turning into losers!)
    """
    def evaluate_seat_signals(self):
        if self.realized_pnl_inr <= -2500.0:
            return

        if self.second_of_day < 2700: # Wait until 10:00 AM IST
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
                total_syms += 1
                if s_c > s_vwap:
                    bull_count += 1
                elif s_c < s_vwap:
                    bear_count += 1

        breadth_ratio = (max(bull_count, bear_count) / total_syms) if total_syms > 0 else 0.50
        is_trend_regime = breadth_ratio >= 0.70
        market_is_bullish = bull_count >= bear_count

        active_index_count = sum(1 for p in self.active_positions if p.get("isOption"))

        for sym in WHITELIST_14_SYMBOLS:
            if len(self.active_positions) >= 4:
                break
            if any(p["symbol"] == sym for p in self.active_positions):
                continue
            if self.symbol_trades_today.get(sym, 0) >= 1:
                continue

            is_idx = sym in INDEX_SET

            # RULE A: In Chop Regime, NEVER trade Index Options!
            if is_idx and not is_trend_regime:
                continue

            if is_idx and active_index_count >= 2:
                continue

            bars = day_bars.get(sym, [])
            if bar_idx < 3 or bar_idx >= len(bars) - 10:
                continue

            c_bar = bars[bar_idx]
            close_p = float(c_bar["close"])
            open_p = float(c_bar["open"])
            high_p = float(c_bar["high"])
            low_p = float(c_bar["low"])

            vwap = vwaps.get(sym, close_p)
            sess = bars[:bar_idx + 1]
            closes = [float(b["close"]) for b in sess]
            if len(closes) < 21:
                continue

            # EMA 9 & EMA 21
            mult9 = 2.0 / 10.0
            mult21 = 2.0 / 22.0
            ema9 = closes[0]
            ema21 = closes[0]
            for c in closes[1:]:
                ema9 = (c - ema9) * mult9 + ema9
                ema21 = (c - ema21) * mult21 + ema21

            first3 = bars[:3]
            orh = max(float(b["high"]) for b in first3)
            orl = min(float(b["low"]) for b in first3)

            past5 = bars[max(0, bar_idx - 5):bar_idx + 1]
            swing_low5 = min(float(b["low"]) for b in past5)
            swing_high5 = max(float(b["high"]) for b in past5)

            if is_idx:
                sl_pts_buy = max(45.0, (close_p - swing_low5) + 10.0)
                sl_pts_sell = max(45.0, swing_high5 - close_p + 10.0)
                lot = 25
            else:
                sl_pts_buy = max(close_p * 0.008, (close_p - swing_low5) + (close_p * 0.002))
                sl_pts_sell = max(close_p * 0.008, (swing_high5 - close_p) + (close_p * 0.002))
                lot = max(10, min(100, int(1500.0 / sl_pts_buy)))

            multiplier = (lot * 0.60) if is_idx else float(lot)

            # =========================================================
            # REGIME 1: SUPER-TREND MOMENTUM (Breadth >= 70%)
            # =========================================================
            if is_trend_regime:
                index_chop_filter_buy = (not is_idx) or (close_p > orh or close_p > vwap * 1.0015)
                index_chop_filter_sell = (not is_idx) or (close_p < orl or close_p < vwap * 0.9985)

                if market_is_bullish and close_p > vwap and ema9 > ema21 and close_p > open_p and low_p <= ema9 * 1.002 and index_chop_filter_buy:
                    sl_price = round(close_p - sl_pts_buy, 2)
                    tp1_target = round(close_p + (500.0 / multiplier), 2)
                    self.trade_counter += 1
                    self.symbol_trades_today[sym] = 1
                    if is_idx: active_index_count += 1
                    self.active_positions.append({
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
                        "initialTpPrice": tp1_target,
                        "tpPrice": tp1_target,
                        "beTargetPrice": tp1_target,
                        "tp1TargetPrice": tp1_target,
                        "tp2TargetPrice": round(close_p + (1000.0 / multiplier), 2),
                        "tp3TargetPrice": round(close_p + (1500.0 / multiplier), 2),
                        "tp4TargetPrice": round(close_p + (2000.0 / multiplier), 2),
                        "tp5TargetPrice": round(close_p + (2500.0 / multiplier), 2),
                        "tp6TargetPrice": round(close_p + (3000.0 / multiplier), 2),
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
                        "strategyName": f"SUPER_TREND ({'0.60Δ_CE' if is_idx else 'EQUITY_BUY'})"
                    })

                elif not market_is_bullish and close_p < vwap and ema9 < ema21 and close_p < open_p and high_p >= ema9 * 0.998 and index_chop_filter_sell:
                    sl_price = round(close_p + sl_pts_sell, 2)
                    tp1_target = round(close_p - (500.0 / multiplier), 2)
                    self.trade_counter += 1
                    self.symbol_trades_today[sym] = 1
                    if is_idx: active_index_count += 1
                    self.active_positions.append({
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
                        "initialTpPrice": tp1_target,
                        "tpPrice": tp1_target,
                        "beTargetPrice": tp1_target,
                        "tp1TargetPrice": tp1_target,
                        "tp2TargetPrice": round(close_p - (1000.0 / multiplier), 2),
                        "tp3TargetPrice": round(close_p - (1500.0 / multiplier), 2),
                        "tp4TargetPrice": round(close_p - (2000.0 / multiplier), 2),
                        "tp5TargetPrice": round(close_p - (2500.0 / multiplier), 2),
                        "tp6TargetPrice": round(close_p - (3000.0 / multiplier), 2),
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
                        "strategyName": f"SUPER_TREND ({'0.60Δ_PE' if is_idx else 'EQUITY_SHORT'})"
                    })

            # =========================================================
            # REGIME 2: MEAN-REVERSION PING-PONG (EQUITIES ONLY, NO OPTIONS!)
            # =========================================================
            elif not is_trend_regime and not is_idx:
                dist_from_vwap_pct = ((close_p - vwap) / vwap) * 100.0
                rng = max(high_p - low_p, 0.05)
                lower_wick = (min(open_p, close_p) - low_p) / rng
                upper_wick = (high_p - max(open_p, close_p)) / rng

                if -0.70 <= dist_from_vwap_pct <= -0.20 and lower_wick >= 0.30 and close_p > open_p:
                    target_pts = 400.0 / multiplier
                    sl_pts = 350.0 / multiplier
                    sl_p = round(close_p - sl_pts, 2)
                    tp_p = round(close_p + target_pts, 2)
                    self.trade_counter += 1
                    self.symbol_trades_today[sym] = 1
                    self.active_positions.append({
                        "id": f"{self.trade_counter:04d}",
                        "symbol": sym,
                        "displayName": DISPLAY_NAMES.get(sym, sym),
                        "side": "BUY",
                        "seatBucket": "CHOP_PING_PONG_SEAT",
                        "isOption": False,
                        "optionType": None,
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
                        "marginInr": round(close_p * lot * 0.20, 2),
                        "floatingPnlInr": 0.0,
                        "currentNetRoePct": 0.0,
                        "progressPct": 0.0,
                        "stage": 0,
                        "currentMilestone": "CHOP_SCALP_400",
                        "peakRupeeGain": 0.0,
                        "maxLossCapInr": 400.0,
                        "openedAtFormatted": cur_time_str,
                        "strategyName": "CHOP_PING_PONG (EQUITY_BUY)"
                    })

                elif 0.20 <= dist_from_vwap_pct <= 0.70 and upper_wick >= 0.30 and close_p < open_p:
                    target_pts = 400.0 / multiplier
                    sl_pts = 350.0 / multiplier
                    sl_p = round(close_p + sl_pts, 2)
                    tp_p = round(close_p - target_pts, 2)
                    self.trade_counter += 1
                    self.symbol_trades_today[sym] = 1
                    self.active_positions.append({
                        "id": f"{self.trade_counter:04d}",
                        "symbol": sym,
                        "displayName": DISPLAY_NAMES.get(sym, sym),
                        "side": "SELL",
                        "seatBucket": "CHOP_PING_PONG_SEAT",
                        "isOption": False,
                        "optionType": None,
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
                        "marginInr": round(close_p * lot * 0.20, 2),
                        "floatingPnlInr": 0.0,
                        "currentNetRoePct": 0.0,
                        "progressPct": 0.0,
                        "stage": 0,
                        "currentMilestone": "CHOP_SCALP_400",
                        "peakRupeeGain": 0.0,
                        "maxLossCapInr": 400.0,
                        "openedAtFormatted": cur_time_str,
                        "strategyName": "CHOP_PING_PONG (EQUITY_SHORT)"
                    })

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

            # =========================================================
            # CHOP PING-PONG EXIT RULES
            # =========================================================
            if pos.get("targetType") == "CHOP_PING_PONG_SCALP":
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

            # =========================================================
            # TREND 6-STAGE LADDER (+500, +1000, +1500, +2000, +2500, +3000)
            # =========================================================
            # Fast Break-even / Cost lock at +INR 400
            if pos["stage"] == 0 and peak_gain >= 400.0:
                cost_buf = 50.0 / mult
                cost_sl = round(entry + cost_buf if is_buy else entry - cost_buf, 2)
                if (is_buy and cost_sl > pos["slPrice"]) or (not is_buy and cost_sl < pos["slPrice"]):
                    pos["slPrice"] = cost_sl

            # TP 1: +500
            if pos["stage"] == 0 and peak_gain >= 500.0:
                pos["stage"] = 1
                pos["currentMilestone"] = "TP 1 (+₹500)"
                buf_pts = 300.0 / mult
                new_sl = round(entry + buf_pts if is_buy else entry - buf_pts, 2)
                if (is_buy and new_sl > pos["slPrice"]) or (not is_buy and new_sl < pos["slPrice"]):
                    pos["slPrice"] = new_sl

            # TP 2: +1000
            if pos["stage"] <= 1 and peak_gain >= 1000.0:
                pos["stage"] = 2
                pos["currentMilestone"] = "TP 2 (+₹1,000)"
                buf_pts = 700.0 / mult
                new_sl = round(entry + buf_pts if is_buy else entry - buf_pts, 2)
                if (is_buy and new_sl > pos["slPrice"]) or (not is_buy and new_sl < pos["slPrice"]):
                    pos["slPrice"] = new_sl

            # TP 3: +1500
            if pos["stage"] <= 2 and peak_gain >= 1500.0:
                pos["stage"] = 3
                pos["currentMilestone"] = "TP 3 (+₹1,500)"
                buf_pts = 1150.0 / mult
                new_sl = round(entry + buf_pts if is_buy else entry - buf_pts, 2)
                if (is_buy and new_sl > pos["slPrice"]) or (not is_buy and new_sl < pos["slPrice"]):
                    pos["slPrice"] = new_sl

            # TP 4: +2000
            if pos["stage"] <= 3 and peak_gain >= 2000.0:
                pos["stage"] = 4
                pos["currentMilestone"] = "TP 4 (+₹2,000)"
                buf_pts = 1600.0 / mult
                new_sl = round(entry + buf_pts if is_buy else entry - buf_pts, 2)
                if (is_buy and new_sl > pos["slPrice"]) or (not is_buy and new_sl < pos["slPrice"]):
                    pos["slPrice"] = new_sl

            # TP 5: +2500
            if pos["stage"] <= 4 and peak_gain >= 2500.0:
                pos["stage"] = 5
                pos["currentMilestone"] = "TP 5 (+₹2,500)"
                buf_pts = 2100.0 / mult
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

if __name__ == "__main__":
    eng = UltimateBreakthroughEngine()
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
    print("ULTIMATE CONFLUENCE 60-DAY AUDIT RESULTS (REAL TICK DATA):")
    print("=" * 85)
    print(f"{'Month':<10} | {'Days':^5} | {'Green/Red':^10} | {'Trades':^7} | {'Wins':^5} | {'WR %':^6} | {'Net Real PnL':^14} | {'Margin ROE':^12}")
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
