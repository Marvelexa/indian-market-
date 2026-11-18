import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS, WHITELIST_14_SYMBOLS, INDEX_SET, DISPLAY_NAMES

class Refined2500CleanEngine(IndianPastDateReplayEngine):
    def evaluate_seat_signals(self):
        if len(self.active_positions) >= 4:
            return

        if self.realized_pnl_inr <= -2500.0:
            return

        if self.second_of_day < 2700: # Wait until 10:00 AM IST
            return

        bar_idx = min(74, self.second_of_day // 300)
        day_bars = self.by_date_5m.get(self.current_date, {})
        cur_time_str = self.get_formatted_time()

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
            if self.realized_pnl_inr <= -2500.0:
                break
            if any(p["symbol"] == sym for p in self.active_positions):
                continue
            if self.symbol_trades_today.get(sym, 0) >= 1:
                continue

            is_idx = sym in INDEX_SET

            # Rule 2: NO INDEX TRADING IN CHOP REGIME! (Only trade Index Options in Trend Regime)
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

            # EMA 9 & 21
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

            index_chop_filter_buy = (not is_idx) or (close_p > orh or close_p > vwap * 1.0015)
            index_chop_filter_sell = (not is_idx) or (close_p < orl or close_p < vwap * 0.9985)

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

            # Trend Momentum Buy
            if is_trend_regime and market_is_bullish and close_p > vwap and ema9 > ema21 and close_p > open_p and low_p <= ema9 * 1.002 and index_chop_filter_buy:
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
                    "stage": 0,
                    "currentMilestone": "ENTRY",
                    "peakRupeeGain": 0.0,
                    "maxLossCapInr": 1500.0,
                    "openedAtFormatted": cur_time_str,
                    "strategyName": f"SUPER_TREND ({'0.60Δ_CE' if is_idx else 'EQUITY_BUY'})"
                })

            # Trend Momentum Sell
            elif is_trend_regime and not market_is_bullish and close_p < vwap and ema9 < ema21 and close_p < open_p and high_p >= ema9 * 0.998 and index_chop_filter_sell:
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
                    "stage": 0,
                    "currentMilestone": "ENTRY",
                    "peakRupeeGain": 0.0,
                    "maxLossCapInr": 1500.0,
                    "openedAtFormatted": cur_time_str,
                    "strategyName": f"SUPER_TREND ({'0.60Δ_PE' if is_idx else 'EQUITY_SHORT'})"
                })

            # Regime 2: Chop Ping-Pong Scalper (EQUITIES ONLY!)
            elif not is_trend_regime and not is_idx:
                dist_from_vwap_pct = ((close_p - vwap) / vwap) * 100.0
                rng = max(high_p - low_p, 0.05)
                lower_wick = (min(open_p, close_p) - low_p) / rng
                upper_wick = (high_p - max(open_p, close_p)) / rng

                if -0.70 <= dist_from_vwap_pct <= -0.20 and lower_wick >= 0.30 and close_p > open_p:
                    target_pts = 400.0 / multiplier
                    sl_pts = 350.0 / multiplier
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
                        "initialSlPrice": round(close_p - sl_pts, 2),
                        "slPrice": round(close_p - sl_pts, 2),
                        "initialTpPrice": round(close_p + target_pts, 2),
                        "tpPrice": round(close_p + target_pts, 2),
                        "targetType": "CHOP_PING_PONG_SCALP",
                        "quantity": lot,
                        "marginInr": round(close_p * lot * 0.20, 2),
                        "floatingPnlInr": 0.0,
                        "currentNetRoePct": 0.0,
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
                        "initialSlPrice": round(close_p + sl_pts, 2),
                        "slPrice": round(close_p + sl_pts, 2),
                        "initialTpPrice": round(close_p - target_pts, 2),
                        "tpPrice": round(close_p - target_pts, 2),
                        "targetType": "CHOP_PING_PONG_SCALP",
                        "quantity": lot,
                        "marginInr": round(close_p * lot * 0.20, 2),
                        "floatingPnlInr": 0.0,
                        "currentNetRoePct": 0.0,
                        "stage": 0,
                        "currentMilestone": "CHOP_SCALP_400",
                        "peakRupeeGain": 0.0,
                        "maxLossCapInr": 400.0,
                        "openedAtFormatted": cur_time_str,
                        "strategyName": "CHOP_PING_PONG (EQUITY_SHORT)"
                    })

if __name__ == "__main__":
    eng = Refined2500CleanEngine()
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
    print("REFINED 2500 CLEAN RESULTS (REAL TICK DATA):")
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
