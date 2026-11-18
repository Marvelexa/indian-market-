import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.replay_engine import IndianPastDateReplayEngine, WHITELIST_14_SYMBOLS, INDEX_SET, TOTAL_DAY_SECONDS

class EquityTightenedEngine(IndianPastDateReplayEngine):
    def evaluate_active_positions_tick(self):
        # Override evaluate_active_positions_tick to enforce tighter loss cap for equities
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

            # Ladder
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

            # Progress
            pos["progressPct"] = round(min(100.0, max(0.0, float_pnl * 100.0 / 500.0)), 1) if pos["stage"] == 0 else 100.0

            # Exits
            exit_reason = None
            exit_price = curr_p

            # Tighter loss cap for equities (-₹750) vs indices (-₹1,500)
            max_cap = -1500.0 if is_opt else -750.0
            if float_pnl <= max_cap:
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

eng = EquityTightenedEngine()
eng.set_date("2026-10-05", auto_play=True)
for _ in range(TOTAL_DAY_SECONDS // 5):
    eng.advance_seconds(5)

st = eng.get_state()
w = st['wallet']
print(f"05 Oct with Equity Cap -INR 750: Net PnL = INR {w['realizedPnlInr']:,.2f} | Trades: {w['totalTrades']} | Wins: {w['wins']}")
for t in eng.closed_ledger:
    print(f"  {t['symbol']:<10} | Side: {t['side']} | PnL: INR {t['netPnlInr']:>+8.2f} | Reason: {t['exitReason']}")
