import sys, os
sys.path.insert(0, os.path.abspath("."))
import json
from typing import Dict, Any, List
from backend.replay_engine import IndianPastDateReplayEngine, DISPLAY_NAMES

class EnhancedReplayEngine(IndianPastDateReplayEngine):
    def evaluate_active_positions_tick(self):
        """
        6-Stage TP Ladder + High-Precision Smart SL Engine:
        - TP 1 (+₹500): Locks in +₹300 profit (Trade is 100% Risk-Free!)
        - TP 2 (+₹1,000): Locks in +₹700 profit
        - TP 3 (+₹1,500): Locks in +₹1,150 profit
        - TP 4 (+₹2,000): Locks in +₹1,600 profit
        - TP 5 (+₹2,500): Locks in +₹2,100 profit
        - TP 6 (+₹3,000): Full Target Booked (+₹3,000 Exit!)
        
        Smart SL Rules:
        1. If in stage 0 and price breaches SL:
           - Check 5m candle wick.
           - If lower wick >= 28% (BUY) or upper wick >= 28% (SELL), price has strong absorption.
             Hold ONLY if price stays above candle low (BUY) / below candle high (SELL) and float_pnl > -900.
             If candle low breaks, absorption failed -> CUT IMMEDIATELY (SMART_SL_EXIT).
           - If no wick absorption (solid breakdown), CUT IMMEDIATELY at SL (SMART_SL_EXIT, e.g. -₹600 to -₹900).
        2. Stale losing trade cut (> 40 min / 8 bars negative) to prevent bleeding into 03:18 PM.
        3. Hard cap ceiling: -₹1,500 max cap.
        """
        remaining = []
        cur_time_str = self.get_formatted_time()
        day_bars = self.by_date_5m.get(self.current_date, {})
        bar_idx = min(74, self.second_of_day // 300)

        for pos in self.active_positions:
            sym = pos["symbol"]
            curr_p = self.live_prices.get(sym, pos["entryPrice"])
            pos["currentPrice"] = curr_p
            is_buy = pos["side"] == "BUY"
            is_opt = pos.get("isOption", False)
            entry = pos["entryPrice"]
            qty = pos.get("quantity", 1)

            profit_dist = (curr_p - entry) if is_buy else (entry - curr_p)
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

            # 6-STAGE LADDER
            # 1. TP 1: +₹500 -> Lock +₹300
            if pos["stage"] == 0 and peak_gain >= 500.0:
                pos["stage"] = 1
                pos["currentMilestone"] = "TP 1 (+₹500)"
                buf_pts = 300.0 / mult
                new_sl = round(entry + buf_pts if is_buy else entry - buf_pts, 2)
                if (is_buy and new_sl > pos["slPrice"]) or (not is_buy and new_sl < pos["slPrice"]):
                    pos["slPrice"] = new_sl
                pos["stageNote"] = "🎯 TP 1 HIT (+₹500) • Locked +₹300"

            # 2. TP 2: +₹1,000 -> Lock +₹700
            if pos["stage"] <= 1 and peak_gain >= 1000.0:
                pos["stage"] = 2
                pos["currentMilestone"] = "TP 2 (+₹1,000)"
                buf_pts = 700.0 / mult
                new_sl = round(entry + buf_pts if is_buy else entry - buf_pts, 2)
                if (is_buy and new_sl > pos["slPrice"]) or (not is_buy and new_sl < pos["slPrice"]):
                    pos["slPrice"] = new_sl
                pos["stageNote"] = "🎯 TP 2 HIT (+₹1,000) • Locked +₹700"

            # 3. TP 3: +₹1,500 -> Lock +₹1,150
            if pos["stage"] <= 2 and peak_gain >= 1500.0:
                pos["stage"] = 3
                pos["currentMilestone"] = "TP 3 (+₹1,500)"
                buf_pts = 1150.0 / mult
                new_sl = round(entry + buf_pts if is_buy else entry - buf_pts, 2)
                if (is_buy and new_sl > pos["slPrice"]) or (not is_buy and new_sl < pos["slPrice"]):
                    pos["slPrice"] = new_sl
                pos["stageNote"] = "🎯 TP 3 HIT (+₹1,500) • Locked +₹1,150"

            # 4. TP 4: +₹2,000 -> Lock +₹1,600
            if pos["stage"] <= 3 and peak_gain >= 2000.0:
                pos["stage"] = 4
                pos["currentMilestone"] = "TP 4 (+₹2,000)"
                buf_pts = 1600.0 / mult
                new_sl = round(entry + buf_pts if is_buy else entry - buf_pts, 2)
                if (is_buy and new_sl > pos["slPrice"]) or (not is_buy and new_sl < pos["slPrice"]):
                    pos["slPrice"] = new_sl
                pos["stageNote"] = "🎯 TP 4 HIT (+₹2,000) • Locked +₹1,600"

            # 5. TP 5: +₹2,500 -> Lock +₹2,100
            if pos["stage"] <= 4 and peak_gain >= 2500.0:
                pos["stage"] = 5
                pos["currentMilestone"] = "TP 5 (+₹2,500)"
                buf_pts = 2100.0 / mult
                new_sl = round(entry + buf_pts if is_buy else entry - buf_pts, 2)
                if (is_buy and new_sl > pos["slPrice"]) or (not is_buy and new_sl < pos["slPrice"]):
                    pos["slPrice"] = new_sl
                pos["stageNote"] = "🎯 TP 5 HIT (+₹2,500) • Locked +₹2,100"

            # Check Exit Conditions
            exit_reason = None
            exit_price = curr_p

            # 1. Hard Loss Cap per trade (-₹1,500)
            if float_pnl <= -1500.0:
                exit_price = curr_p
                exit_reason = "MAX_LOSS_CAP_HIT"
            # 2. TP 6 Full Target Hit (+₹3,000)
            elif float_pnl >= 3000.0:
                target_pts = 3000.0 / mult
                exit_price = round(entry + target_pts if is_buy else entry - target_pts, 2)
                exit_reason = "TP_6_EXIT"
            # 3. Trailing Stop Hit (when stage >= 1: already locked in profit)
            elif pos["stage"] >= 1 and ((is_buy and curr_p <= pos["slPrice"]) or (not is_buy and curr_p >= pos["slPrice"])):
                exit_price = pos["slPrice"]
                exit_reason = f"TP_{pos['stage']}_EXIT"
            # 4. Smart SL Evaluation (when stage == 0)
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
            # 6. Own VWAP & Structural Breakdown (Smart early cut if trend fails completely)
            # If position drops below its OWN VWAP + candle is solid breakdown and loss > -₹350
            sym_bars = day_bars.get(sym, [])
            if sym_bars and bar_idx < len(sym_bars) and pos["stage"] == 0 and float_pnl <= -350.0:
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

    def close_position(self, pos: Dict[str, Any], exit_price: float, exit_reason: str, exit_time_str: str):
        sym = pos["symbol"]
        is_buy = pos["side"] == "BUY"
        entry = pos["entryPrice"]
        qty = pos.get("quantity", 1)

        if pos.get("isOption"):
            pt_move = (exit_price - entry) if is_buy else (entry - exit_price)
            net_pnl = pt_move * 0.60 * qty
        else:
            net_pnl = (exit_price - entry) * qty if is_buy else (entry - exit_price) * qty

        if net_pnl < -1500.0:
            net_pnl = -1500.0

        net_pnl = round(net_pnl, 2)
        self.balance_inr = round(self.balance_inr + net_pnl, 2)
        self.realized_pnl_inr = round(self.realized_pnl_inr + net_pnl, 2)

        margin = pos.get("marginInr", 10000.0)
        roe = round((net_pnl / margin) * 100.0, 2) if margin > 0 else 0.0

        if exit_reason == "TP_6_EXIT":
            badge_label = "🎯 TP 6 (+₹3,000 TARGET)"
        elif exit_reason == "TP_5_EXIT":
            badge_label = "🎯 TP 5 (+₹2,500 / LOCK 2.1K)"
        elif exit_reason == "TP_4_EXIT":
            badge_label = "🎯 TP 4 (+₹2,000 / LOCK 1.6K)"
        elif exit_reason == "TP_3_EXIT":
            badge_label = "🎯 TP 3 (+₹1,500 / LOCK 1.15K)"
        elif exit_reason == "TP_2_EXIT":
            badge_label = "🎯 TP 2 (+₹1,000 / LOCK 700)"
        elif exit_reason in ["TP_1_EXIT", "BROKERAGE_SHIELDED_SCRATCH"]:
            badge_label = "🎯 TP 1 (+₹500 / LOCK 300)"
        elif exit_reason == "SMART_SL_EXIT":
            badge_label = f"🛡️ SMART SL EXIT (-₹{abs(net_pnl):.0f})"
        elif exit_reason == "MAX_LOSS_CAP_HIT":
            badge_label = "🛑 MAX LOSS CAP (-₹1,500)"
        elif exit_reason == "DAILY_CIRCUIT_BREAKER_HIT":
            badge_label = "🛡️ DAILY CIRCUIT BREAKER"
        elif exit_reason in ["INTRADAY_AUTO_SQUARE_OFF", "03:18_AUTO_SQUARE_OFF"]:
            badge_label = "⏰ 03:18 PM AUTO SQUARE-OFF"
        else:
            badge_label = "🛑 STOP LOSS HIT"

        closed_trade = {
            "id": f"IN-{pos['id']}",
            "symbol": sym,
            "displayName": DISPLAY_NAMES.get(sym, sym),
            "side": pos["side"],
            "seatBucket": pos["seatBucket"],
            "isOption": pos.get("isOption", False),
            "optionType": pos.get("optionType"),
            "optionStrike": pos.get("optionStrike"),
            "entryPrice": entry,
            "exitPrice": exit_price,
            "entryTimeFormatted": pos["openedAtFormatted"],
            "exitTimeFormatted": exit_time_str,
            "netPnlInr": net_pnl,
            "netRoePct": roe,
            "exitReason": exit_reason,
            "exitBadgeLabel": badge_label,
            "strategyName": "SMART_SL_6STAGE_TP500_3000"
        }
        self.closed_ledger.insert(0, closed_trade)

for test_date in ["2026-11-13", "2026-11-06", "2026-11-02"]:
    engine = EnhancedReplayEngine()
    engine.set_date(test_date)
    for sec in range(0, 22500, 5):
        engine.advance_seconds(5)

    print(f"=== ENHANCED {test_date} RESULT ===")
    print(f"Trades: {len(engine.closed_ledger)}")
    print(f"Balance: {engine.balance_inr}")
    print(f"Realized PnL: {engine.realized_pnl_inr:+10.2f}")
    for t in engine.closed_ledger:
        sym = t['symbol']
        side = t['side']
        en = t['entryPrice']
        ex = t['exitPrice']
        pnl = t['netPnlInr']
        badge = t.get('exitBadgeLabel', '')
        print(f"  {sym:12} {side:4} En: {en:8.2f} Ex: {ex:8.2f} PnL: {pnl:+8.1f} | Badge: {badge}")
    print()
