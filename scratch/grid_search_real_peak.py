import os
import sys
sys.path.insert(0, os.path.abspath('.'))
from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS, WHITELIST_14_SYMBOLS, INDEX_SET

class ParamGridEngine(IndianPastDateReplayEngine):
    def __init__(self, tp_ladder=(500, 1000, 1500, 2000, 2500, 3000), locks=(300, 700, 1150, 1600, 2100), max_loss_cap=1500.0, breaker=2500.0, early_cut=350.0, max_positions=4):
        super().__init__()
        self.tp_ladder = tp_ladder
        self.locks = locks
        self.max_loss_cap = max_loss_cap
        self.breaker = breaker
        self.early_cut = early_cut
        self.max_positions = max_positions

    def evaluate_seat_signals(self):
        if self.realized_pnl_inr <= -self.breaker:
            return

        if self.second_of_day < 2700:
            return

        if len(self.active_positions) >= self.max_positions:
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

        for sym in WHITELIST_14_SYMBOLS:
            if len(self.active_positions) >= self.max_positions:
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
                    "maxLossCapInr": self.max_loss_cap,
                    "openedAtFormatted": cur_time_str,
                    "strategyName": f"PEAK ({'0.60Δ_CE' if is_idx else 'EQUITY_LONG'})"
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
                    "maxLossCapInr": self.max_loss_cap,
                    "openedAtFormatted": cur_time_str,
                    "strategyName": f"PEAK ({'0.60Δ_PE' if is_idx else 'EQUITY_SHORT'})"
                }
                self.active_positions.append(pos)

    def evaluate_active_positions_tick(self):
        remaining = []
        cur_time_str = self.get_formatted_time()
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

            if is_opt:
                float_pnl = profit_dist * 0.60 * qty
                margin = pos.get("marginInr", 12000.0)
                roe = (float_pnl / margin) * 100.0 if margin > 0 else 0.0
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

            # TP Ladder Stages
            # Ladder: tp_ladder = (500, 1000, 1500, 2000, 2500, 3000)
            # Locks: locks = (300, 700, 1150, 1600, 2100)
            for st_i in range(len(self.locks)):
                tp_val = self.tp_ladder[st_i]
                lock_val = self.locks[st_i]
                if pos["stage"] <= st_i and peak_gain >= tp_val:
                    pos["stage"] = st_i + 1
                    pos["currentMilestone"] = f"TP {st_i+1} (+INR {tp_val:,.0f})"
                    buf_pts = lock_val / mult
                    new_sl = round(entry + buf_pts if is_buy else entry - buf_pts, 2)
                    if (is_buy and new_sl > pos["slPrice"]) or (not is_buy and new_sl < pos["slPrice"]):
                        pos["slPrice"] = new_sl

            exit_reason = None
            exit_price = curr_p

            final_tp = self.tp_ladder[-1]
            if float_pnl <= -self.max_loss_cap:
                exit_price = curr_p
                exit_reason = "MAX_LOSS_CAP_HIT"
            elif float_pnl >= final_tp:
                target_pts = final_tp / mult
                exit_price = round(entry + target_pts if is_buy else entry - target_pts, 2)
                exit_reason = "TP_FINAL_EXIT"
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

                if reversal_likely and not wick_invalidation and float_pnl > -900.0:
                    pass
                else:
                    exit_price = pos["slPrice"]
                    exit_reason = "SMART_SL_EXIT"
            elif pos["stage"] == 0 and float_pnl <= -self.early_cut:
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

def run_simulation(eng, label):
    monthly_pnl = {}
    total_pnl = 0.0
    for d in eng.sorted_dates:
        m = d[:7]
        if m not in monthly_pnl: monthly_pnl[m] = 0.0
        eng.set_date(d, auto_play=True)
        for _ in range(TOTAL_DAY_SECONDS // 5):
            eng.advance_seconds(5)
        st = eng.get_state()
        p = round(st['wallet']['realizedPnlInr'], 2)
        monthly_pnl[m] += p
        total_pnl += p
    print(f"[{label}] -> Total: INR {total_pnl:,.2f} | Aug: {monthly_pnl['2026-08']:,.2f} | Sep: {monthly_pnl['2026-09']:,.2f} | Oct: {monthly_pnl['2026-10']:,.2f} | Nov: {monthly_pnl['2026-11']:,.2f}")
    return total_pnl

if __name__ == "__main__":
    # Baseline (Current Engine)
    eng_base = ParamGridEngine()
    run_simulation(eng_base, "BASELINE (500-1000-1500-2000-2500-3000, 1500cap, 2500brk, 350cut)")

    # Test 1: Let runners expand to TP 3500 (lock 300, 700, 1200, 1800, 2400, 3000, 3500)
    eng_tp3500 = ParamGridEngine(tp_ladder=(500, 1000, 1500, 2000, 2500, 3000, 3500), locks=(300, 700, 1150, 1600, 2100, 2600))
    run_simulation(eng_tp3500, "TP 3500 RUNNER")

    # Test 2: Circuit Breaker at -3000 (allows full day recovery on volatile trend days)
    eng_brk3000 = ParamGridEngine(breaker=3000.0)
    run_simulation(eng_brk3000, "CIRCUIT BREAKER -3000")

    # Test 3: Early Cut at -300 (faster exit on failed breakouts)
    eng_cut300 = ParamGridEngine(early_cut=300.0)
    run_simulation(eng_cut300, "EARLY CUT -300")
