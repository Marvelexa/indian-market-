import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS, WHITELIST_14_SYMBOLS, INDEX_SET, DISPLAY_NAMES

class SingleIndexEngine(IndianPastDateReplayEngine):
    """
    Test: Limit active index positions to 1 (active_index_count >= 1)
    Why: Nifty, BankNifty, FinNifty move together. Holding 2 index options simultaneously doubles market exposure.
    Allowing 1 Index Option + 3 Equity Runners creates perfect risk diversification!
    """
    def evaluate_seat_signals(self):
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
        emas = {}
        for s in WHITELIST_14_SYMBOLS:
            s_bars = day_bars.get(s, [])
            if len(s_bars) > bar_idx:
                s_sess = s_bars[:bar_idx + 1]
                s_c = float(s_bars[bar_idx]["close"])
                s_pv = sum(((float(b["high"]) + float(b["low"]) + float(b["close"])) / 3.0) * max(float(b.get("volume", 1)), 1.0) for b in s_sess)
                s_v = sum(max(float(b.get("volume", 1)), 1.0) for b in s_sess)
                s_vwap = (s_pv / s_v) if s_v > 0 else s_c
                vwaps[s] = s_vwap

                closes = [float(b["close"]) for b in s_sess]
                k9 = 2.0 / 10
                k21 = 2.0 / 22
                e9 = closes[0]
                e21 = closes[0]
                for cl in closes:
                    e9 = cl * k9 + e9 * (1 - k9)
                    e21 = cl * k21 + e21 * (1 - k21)
                emas[s] = (e9, e21)

                if s_c > s_vwap and e9 >= e21: bull_count += 1
                elif s_c < s_vwap and e9 <= e21: bear_count += 1
                total_syms += 1

        breadth_ratio = (max(bull_count, bear_count) / max(1, total_syms)) * 100.0
        is_trend_confirmed = breadth_ratio >= 65.0
        market_is_bullish = bull_count > bear_count

        nifty_bars = day_bars.get("NIFTY", [])
        bnifty_bars = day_bars.get("BANKNIFTY", [])
        imic_bullish = False
        imic_bearish = False
        if len(nifty_bars) > bar_idx and len(bnifty_bars) > bar_idx:
            n_c = float(nifty_bars[bar_idx]["close"])
            n_vwap = vwaps.get("NIFTY", n_c)
            n_e9, n_e21 = emas.get("NIFTY", (n_c, n_c))

            bn_c = float(bnifty_bars[bar_idx]["close"])
            bn_vwap = vwaps.get("BANKNIFTY", bn_c)
            bn_e9, bn_e21 = emas.get("BANKNIFTY", (bn_c, bn_c))

            imic_bullish = (n_c > n_vwap and n_e9 >= n_e21) and (bn_c > bn_vwap and bn_e9 >= bn_e21)
            imic_bearish = (n_c < n_vwap and n_e9 <= n_e21) and (bn_c < bn_vwap and bn_e9 <= bn_e21)

        if not is_trend_confirmed:
            return

        # Here: Limit active index positions to 1!
        active_index_count = sum(1 for p in self.active_positions if p["symbol"] in INDEX_SET)

        for sym in WHITELIST_14_SYMBOLS:
            if len(self.active_positions) >= 4:
                break
            if any(p["symbol"] == sym for p in self.active_positions):
                continue
            if self.symbol_trades_today.get(sym, 0) >= 1:
                continue

            is_idx = sym in INDEX_SET
            if is_idx and active_index_count >= 1:  # Changed from >= 2 to >= 1
                continue

            if is_idx:
                if market_is_bullish and not imic_bullish: continue
                if not market_is_bullish and not imic_bearish: continue

            bars = day_bars.get(sym, [])
            if bar_idx < 3 or bar_idx >= len(bars) - 10:
                continue

            c = bars[bar_idx]
            close_p = float(c["close"])
            open_p = float(c["open"])
            high_p = float(c["high"])
            low_p = float(c["low"])
            vwap = vwaps.get(sym, close_p)
            ema9, ema21 = emas.get(sym, (close_p, close_p))

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

            if market_is_bullish and close_p > vwap and ema9 > ema21 and close_p > open_p and low_p <= ema9 * 1.002:
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
                    "tp2TargetPrice": tp2_target,
                    "tp3TargetPrice": tp3_target,
                    "tp4TargetPrice": tp4_target,
                    "tp5TargetPrice": tp5_target,
                    "tp6TargetPrice": tp6_target,
                    "targetType": "TP_6STAGE_500_3000_LADDER",
                    "reversalWallPrice": None,
                    "reversalWallSource": "TP_6STAGE_500_3000_LADDER",
                    "frontRunBuffer": 0.0,
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
                    "strategyName": f"SUPER_TREND_MOMENTUM ({'0.60Δ_CE' if is_idx else 'EQUITY_BUY'})"
                }
                self.active_positions.append(pos)

            elif (not market_is_bullish) and close_p < vwap and ema9 < ema21 and close_p < open_p and high_p >= ema9 * 0.998:
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
                    "tp2TargetPrice": tp2_target,
                    "tp3TargetPrice": tp3_target,
                    "tp4TargetPrice": tp4_target,
                    "tp5TargetPrice": tp5_target,
                    "tp6TargetPrice": tp6_target,
                    "targetType": "TP_6STAGE_500_3000_LADDER",
                    "reversalWallPrice": None,
                    "reversalWallSource": "TP_6STAGE_500_3000_LADDER",
                    "frontRunBuffer": 0.0,
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
                    "strategyName": f"SUPER_TREND_MOMENTUM ({'0.60Δ_PE' if is_idx else 'EQUITY_SHORT'})"
                }
                self.active_positions.append(pos)

if __name__ == "__main__":
    eng = SingleIndexEngine()
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

    print(f"\n==================== SINGLE INDEX CONCURRENCY (MAX 1 INDEX) ====================")
    print(f"{'Month':<10} | {'Days':^5} | {'Green/Red':^10} | {'Trades':^7} | {'Wins':^5} | {'WR %':^6} | {'Net Real PnL':^14} | {'Margin ROE':^12}")
    print("-------------------------------------------------------------------------------------")
    for m, v in sorted(monthly_stats.items()):
        wr = round((v['wins'] / v['trades']) * 100, 1) if v['trades'] > 0 else 0
        pnl_str = f"+INR {v['pnl']:,.2f}" if v['pnl'] >= 0 else f"-INR {abs(v['pnl']):,.2f}"
        margin_roe = f"+{v['pnl'] / 25000.0 * 100:.1f}%" if v['pnl'] >= 0 else f"-{abs(v['pnl']) / 25000.0 * 100:.1f}%"
        print(f"{m:<10} | {v['days']:^5} | {v['green']}G / {v['red']}R    | {v['trades']:^7} | {v['wins']:^5} | {wr:>5.1f}% | {pnl_str:>14} | {margin_roe:>12}")
    print("-------------------------------------------------------------------------------------")
    print(f"60-DAY CUMULATIVE NET P&L: INR {total_pnl:,.2f} | Margin ROE: +{total_pnl / 25000.0 * 100:.2f}%\n")
