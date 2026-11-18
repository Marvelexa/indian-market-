import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from backend.replay_engine import IndianPastDateReplayEngine, TOTAL_DAY_SECONDS, INDEX_SET, WHITELIST_14_SYMBOLS, DISPLAY_NAMES

class AntiChopReplayEngine(IndianPastDateReplayEngine):
    def evaluate_seat_signals(self):
        """
        Anti-Chop Enhanced Institutional Signal Engine:
        1. Max 2 Index Option Seats (Prevents correlated index blowout)
        2. Strict Market Tide Alignment (No buying Sensex when Nifty is Sell)
        3. Opening Range (ORH / ORL) Breakout Confirmation for Indices (No trading inside chop zone)
        """
        if len(self.active_positions) >= 4:
            return

        if self.realized_pnl_inr <= -2000.0:
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

        # Count active index seats
        active_index_count = sum(1 for p in self.active_positions if p["symbol"] in INDEX_SET)

        for sym in WHITELIST_14_SYMBOLS:
            if len(self.active_positions) >= 4:
                break
            if any(p["symbol"] == sym for p in self.active_positions):
                continue
            if self.symbol_trades_today.get(sym, 0) >= 1:
                continue

            is_idx = sym in INDEX_SET
            # ANTI-CHOP RULE 1: Max 2 Index seats allowed concurrently!
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

            # Session VWAP
            session_bars = bars[:bar_idx + 1]
            cum_pv = sum(((float(b["high"]) + float(b["low"]) + float(b["close"])) / 3.0) * max(float(b.get("volume", 1)), 1.0) for b in session_bars)
            cum_v = sum(max(float(b.get("volume", 1)), 1.0) for b in session_bars)
            vwap = (cum_pv / cum_v) if cum_v > 0 else close_p

            # EMA 9 / 21
            closes = [float(b["close"]) for b in session_bars]
            k9 = 2.0 / 10
            k21 = 2.0 / 22
            ema9 = closes[0]
            ema21 = closes[0]
            for cl in closes:
                ema9 = cl * k9 + ema9 * (1 - k9)
                ema21 = cl * k21 + ema21 * (1 - k21)

            # ANTI-CHOP RULE 2: Opening Range (ORH/ORL) Check for Indices
            # First 3 bars (09:15 - 09:30) define Opening Range
            first3 = bars[:3]
            orh = max(float(b["high"]) for b in first3)
            orl = min(float(b["low"]) for b in first3)

            # Structural & Volatility SL
            past5 = bars[max(0, bar_idx - 5):bar_idx + 1]
            swing_low5 = min(float(b["low"]) for b in past5)
            swing_high5 = max(float(b["high"]) for b in past5)

            if sym == "NIFTY":
                sl_pts_buy = max(45.0, close_p - swing_low5 + 10.0)
                sl_pts_sell = max(45.0, swing_high5 - close_p + 10.0)
                lot = 25
            elif sym == "BANKNIFTY":
                sl_pts_buy = max(90.0, close_p - swing_low5 + 15.0)
                sl_pts_sell = max(90.0, swing_high5 - close_p + 15.0)
                lot = 15
            elif sym == "SENSEX":
                sl_pts_buy = max(140.0, close_p - swing_low5 + 20.0)
                sl_pts_sell = max(140.0, swing_high5 - close_p + 20.0)
                lot = 10
            elif sym == "FINNIFTY":
                sl_pts_buy = max(45.0, close_p - swing_low5 + 10.0)
                sl_pts_sell = max(45.0, swing_high5 - close_p + 10.0)
                lot = 25
            else:
                sl_pts_buy = max(close_p * 0.008, (close_p - swing_low5) + (close_p * 0.002))
                sl_pts_sell = max(close_p * 0.008, (swing_high5 - close_p) + (close_p * 0.002))
                lot = max(10, min(100, int(1500.0 / sl_pts_buy)))

            # BUY SETUP:
            # For indices: MUST be above ORH (Confirmed Breakout) or above VWAP with strong momentum
            index_chop_filter_buy = (not is_idx) or (close_p > orh or close_p > vwap * 1.0015)
            index_chop_filter_sell = (not is_idx) or (close_p < orl or close_p < vwap * 0.9985)

            if market_is_bullish and close_p > vwap and ema9 > ema21 and close_p > open_p and low_p <= ema9 * 1.002 and index_chop_filter_buy:
                sl_price = round(close_p - sl_pts_buy, 2)
                multiplier = (lot * 0.60) if is_idx else lot
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
                    "quantity": lot,
                    "marginInr": 12000.0 if is_idx else round(close_p * lot * 0.20, 2),
                    "floatingPnlInr": 0.0,
                    "currentNetRoePct": 0.0,
                    "progressPct": 0.0,
                    "stage": 0,
                    "currentMilestone": "Running to TP 1 (+₹500)",
                    "stageNote": "RUNNING TO TP 1",
                    "peakRupeeGain": 0.0,
                    "maxLossCapInr": 1500.0,
                    "openedAtFormatted": cur_time_str,
                    "strategyName": f"SMART_SL_1500CAP ({'0.60Δ_CE' if is_idx else 'EQUITY_BUY'})"
                }
                self.active_positions.append(pos)

            elif (not market_is_bullish) and close_p < vwap and ema9 < ema21 and close_p < open_p and high_p >= ema9 * 0.998 and index_chop_filter_sell:
                sl_price = round(close_p + sl_pts_sell, 2)
                multiplier = (lot * 0.60) if is_idx else lot
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
                    "quantity": lot,
                    "marginInr": 12000.0 if is_idx else round(close_p * lot * 0.20, 2),
                    "floatingPnlInr": 0.0,
                    "currentNetRoePct": 0.0,
                    "progressPct": 0.0,
                    "stage": 0,
                    "currentMilestone": "Running to TP 1 (+₹500)",
                    "stageNote": "RUNNING TO TP 1",
                    "peakRupeeGain": 0.0,
                    "maxLossCapInr": 1500.0,
                    "openedAtFormatted": cur_time_str,
                    "strategyName": f"SMART_SL_1500CAP ({'0.60Δ_PE' if is_idx else 'EQUITY_SHORT'})"
                }
                self.active_positions.append(pos)

eng = AntiChopReplayEngine()
oct_dates = [d for d in eng.sorted_dates if "-10-" in d]

total_pnl = 0.0
total_trades = 0
total_wins = 0

print("Testing Anti-Chop 2-Index Cap + ORH/ORL Confirmation on October:")
for d in oct_dates:
    eng.set_date(d, auto_play=True)
    eng.is_running = True
    for _ in range(TOTAL_DAY_SECONDS // 5):
        eng.advance_seconds(5)
    st = eng.get_state()
    w = st['wallet']
    pnl = w['realizedPnlInr']
    total_pnl += pnl
    total_trades += w['totalTrades']
    total_wins += w['wins']
    sign = "+" if pnl >= 0 else ""
    print(f"  {d}: {sign}₹{pnl:>9,.2f} | Trades: {w['totalTrades']:>2} | Wins: {w['wins']:>2} | WR: {w['winRatePct']:>5.1f}%")

print("=" * 60)
print(f"Old October Net PnL:  ₹11,467.08 (186 trades)")
print(f"New Anti-Chop Net PnL: ₹{total_pnl:,.2f} ({total_trades} trades, {total_wins} wins, {total_wins/max(1,total_trades)*100:.1f}% WR)")
print("=" * 60)
