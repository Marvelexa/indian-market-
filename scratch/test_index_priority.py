import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS, WHITELIST_14_SYMBOLS, INDEX_SET, DISPLAY_NAMES

# Let's test prioritizing SENSEX, FINNIFTY over BANKNIFTY, or removing BANKNIFTY as an option vehicle
# Let's test two variations:
# Option A: Prioritize SENSEX and FINNIFTY ahead of NIFTY and BANKNIFTY in index selection
# Option B: SENSEX + FINNIFTY + NIFTY (Exclude BANKNIFTY from active trading, but KEEP it in IMIC confluence calculation!)

class PriorityEngine(IndianPastDateReplayEngine):
    def __init__(self, mode="SENSEX_FIRST"):
        super().__init__()
        self.mode = mode

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

        active_index_count = sum(1 for p in self.active_positions if p["symbol"] in INDEX_SET)

        # Ordering of symbols based on mode
        if self.mode == "SENSEX_FIRST":
            # SENSEX and FINNIFTY prioritized for Index Options
            sym_list = [
                "SENSEX", "FINNIFTY", "NIFTY", "BANKNIFTY",
                "RELIANCE", "BAJFINANCE", "ICICIBANK", "HDFCBANK", "SBIN", "LT", "INFY", "TCS", "TATAMOTORS", "AXISBANK"
            ]
        elif self.mode == "NO_BANKNIFTY":
            # SENSEX, FINNIFTY, NIFTY (BANKNIFTY excluded from trading, but used in IMIC!)
            sym_list = [
                "SENSEX", "FINNIFTY", "NIFTY",
                "RELIANCE", "BAJFINANCE", "ICICIBANK", "HDFCBANK", "SBIN", "LT", "INFY", "TCS", "TATAMOTORS", "AXISBANK"
            ]
        elif self.mode == "TOP_TIER_ONLY":
            # Only trade instruments with historically proven positive alpha
            sym_list = [
                "SENSEX", "FINNIFTY",
                "RELIANCE", "BAJFINANCE", "ICICIBANK", "HDFCBANK", "SBIN", "LT", "INFY"
            ]
        else:
            sym_list = WHITELIST_14_SYMBOLS

        for sym in sym_list:
            if len(self.active_positions) >= 4:
                break
            if any(p["symbol"] == sym for p in self.active_positions):
                continue
            if self.symbol_trades_today.get(sym, 0) >= 1:
                continue

            is_idx = sym in INDEX_SET
            if is_idx and active_index_count >= 2:
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
                sl_pts_buy = max(110.0, close_p - swing_low5 + 25.0)
                sl_pts_sell = max(110.0, swing_high5 - close_p + 25.0)
            elif sym == "FINNIFTY":
                lot = 25
                sl_pts_buy = max(45.0, close_p - swing_low5 + 10.0)
                sl_pts_sell = max(45.0, swing_high5 - close_p + 10.0)
            elif sym == "SENSEX":
                lot = 10
                sl_pts_buy = max(140.0, close_p - swing_low5 + 30.0)
                sl_pts_sell = max(140.0, swing_high5 - close_p + 30.0)
            else:
                lot = max(1, int(10000.0 / (close_p * 0.20)))
                sl_pts_buy = max(close_p * 0.007, close_p - swing_low5 + close_p * 0.002)
                sl_pts_sell = max(close_p * 0.007, swing_high5 - close_p + close_p * 0.002)

            is_bull_sym = close_p > vwap and ema9 >= ema21 and close_p > open_p
            is_bear_sym = close_p < vwap and ema9 <= ema21 and close_p < open_p

            if market_is_bullish and is_bull_sym:
                self.trade_counter += 1
                self.symbol_trades_today[sym] = self.symbol_trades_today.get(sym, 0) + 1
                if is_idx: active_index_count += 1
                margin = (lot * 120.0) if is_idx else (close_p * lot * 0.20)
                pos = {
                    "id": self.trade_counter,
                    "symbol": sym,
                    "side": "BUY",
                    "seatBucket": "INDEX_DERIVATIVE" if is_idx else "EQUITY_CASH",
                    "isOption": is_idx,
                    "optionType": "CE" if is_idx else None,
                    "optionStrike": f"{round(close_p, -2)} CE" if is_idx else None,
                    "entryPrice": close_p,
                    "currentPrice": close_p,
                    "slPrice": round(close_p - sl_pts_buy, 2),
                    "quantity": lot,
                    "marginInr": margin,
                    "floatingPnlInr": 0.0,
                    "currentNetRoePct": 0.0,
                    "progressPct": 0.0,
                    "stage": 0,
                    "currentMilestone": "ENTRY",
                    "peakRupeeGain": 0.0,
                    "maxLossCapInr": 1500.0,
                    "openedAtFormatted": cur_time_str,
                    "strategyName": f"PRIORITY ({'0.60Δ_CE' if is_idx else 'EQUITY_LONG'})"
                }
                self.active_positions.append(pos)

            elif (not market_is_bullish) and is_bear_sym:
                self.trade_counter += 1
                self.symbol_trades_today[sym] = self.symbol_trades_today.get(sym, 0) + 1
                if is_idx: active_index_count += 1
                margin = (lot * 120.0) if is_idx else (close_p * lot * 0.20)
                pos = {
                    "id": self.trade_counter,
                    "symbol": sym,
                    "side": "SELL",
                    "seatBucket": "INDEX_DERIVATIVE" if is_idx else "EQUITY_CASH",
                    "isOption": is_idx,
                    "optionType": "PE" if is_idx else None,
                    "optionStrike": f"{round(close_p, -2)} PE" if is_idx else None,
                    "entryPrice": close_p,
                    "currentPrice": close_p,
                    "slPrice": round(close_p + sl_pts_sell, 2),
                    "quantity": lot,
                    "marginInr": margin,
                    "floatingPnlInr": 0.0,
                    "currentNetRoePct": 0.0,
                    "progressPct": 0.0,
                    "stage": 0,
                    "currentMilestone": "ENTRY",
                    "peakRupeeGain": 0.0,
                    "maxLossCapInr": 1500.0,
                    "openedAtFormatted": cur_time_str,
                    "strategyName": f"PRIORITY ({'0.60Δ_PE' if is_idx else 'EQUITY_SHORT'})"
                }
                self.active_positions.append(pos)

def test_engine_mode(mode_name):
    eng = PriorityEngine(mode=mode_name)
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

    print(f"\n==================== MODE: {mode_name} ====================")
    print(f"{'Month':<10} | {'Days':^5} | {'Green/Red':^10} | {'Trades':^7} | {'Wins':^5} | {'WR %':^6} | {'Net Real PnL':^14} | {'Margin ROE':^12}")
    print("-------------------------------------------------------------------------------------")
    for m, v in sorted(monthly_stats.items()):
        wr = round((v['wins'] / v['trades']) * 100, 1) if v['trades'] > 0 else 0
        pnl_str = f"+INR {v['pnl']:,.2f}" if v['pnl'] >= 0 else f"-INR {abs(v['pnl']):,.2f}"
        margin_roe = f"+{v['pnl'] / 25000.0 * 100:.1f}%" if v['pnl'] >= 0 else f"-{abs(v['pnl']) / 25000.0 * 100:.1f}%"
        print(f"{m:<10} | {v['days']:^5} | {v['green']}G / {v['red']}R    | {v['trades']:^7} | {v['wins']:^5} | {wr:>5.1f}% | {pnl_str:>14} | {margin_roe:>12}")
    print("-------------------------------------------------------------------------------------")
    print(f"60-DAY CUMULATIVE NET P&L: INR {total_pnl:,.2f} | Margin ROE: +{total_pnl / 25000.0 * 100:.2f}%\n")
    return total_pnl

if __name__ == "__main__":
    test_engine_mode("SENSEX_FIRST")
    test_engine_mode("NO_BANKNIFTY")
