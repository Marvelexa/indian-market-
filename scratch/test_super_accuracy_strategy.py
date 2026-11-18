import os
import sys
import copy

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.replay_engine import WHITELIST_14_SYMBOLS, INDEX_SET, DISPLAY_NAMES, TOTAL_DAY_SECONDS, IndianPastDateReplayEngine

class SuperStrategyReplayEngine(IndianPastDateReplayEngine):
    def __init__(self, min_start_sec=1800, min_breadth_pct=70.0, index_lots=2, daily_loss_limit=-2500.0):
        super().__init__()
        self.min_start_sec = min_start_sec # 1800s = 09:45 AM, 2700s = 10:00 AM
        self.min_breadth_pct = min_breadth_pct
        self.index_lots = index_lots
        self.daily_loss_limit = daily_loss_limit

    def evaluate_seat_signals(self):
        # 1. Respect Daily Loss Circuit Breaker
        if self.realized_pnl_inr <= self.daily_loss_limit:
            return

        # 2. Timing Gate: Wait for morning whipsaws to settle
        if self.second_of_day < self.min_start_sec:
            return

        # Max 4 concurrent seats
        if len(self.active_positions) >= 4:
            return

        bar_idx = min(74, self.second_of_day // 300)
        day_bars = self.by_date_5m.get(self.current_date, {})
        cur_time_str = self.get_formatted_time()

        # 3. Market Breadth Consensus Check across all 14 symbols
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
        if breadth_ratio < self.min_breadth_pct:
            # Market is CHOPPY / SPLIT! DO NOT ENTER!
            return

        market_is_bullish = bull_count > bear_count

        # Master Market Bias from NIFTY
        nifty_bars = day_bars.get("NIFTY", [])
        if nifty_bars and bar_idx < len(nifty_bars):
            n_c = float(nifty_bars[bar_idx]["close"])
            n_vwap = vwaps.get("NIFTY", n_c)
            # If NIFTY itself disagrees with breadth, abort!
            if (market_is_bullish and n_c < n_vwap) or (not market_is_bullish and n_c > n_vwap):
                return

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

            # Opening Range Breakout Confirmation
            first3 = bars[:3]
            orh = max(float(b["high"]) for b in first3)
            orl = min(float(b["low"]) for b in first3)
            index_chop_filter_buy = (not is_idx) or (close_p > orh or close_p > vwap * 1.0015)
            index_chop_filter_sell = (not is_idx) or (close_p < orl or close_p < vwap * 0.9985)

            past5 = bars[max(0, bar_idx - 5):bar_idx + 1]
            swing_low5 = min(float(b["low"]) for b in past5)
            swing_high5 = max(float(b["high"]) for b in past5)

            lot_mult = self.index_lots
            if sym == "NIFTY":
                sl_pts_buy = max(45.0, close_p - swing_low5 + 10.0)
                sl_pts_sell = max(45.0, swing_high5 - close_p + 10.0)
                lot = 25 * lot_mult
            elif sym == "BANKNIFTY":
                sl_pts_buy = max(90.0, close_p - swing_low5 + 15.0)
                sl_pts_sell = max(90.0, swing_high5 - close_p + 15.0)
                lot = 15 * lot_mult
            elif sym == "SENSEX":
                sl_pts_buy = max(140.0, close_p - swing_low5 + 20.0)
                sl_pts_sell = max(140.0, swing_high5 - close_p + 20.0)
                lot = 10 * lot_mult
            elif sym == "FINNIFTY":
                sl_pts_buy = max(45.0, close_p - swing_low5 + 10.0)
                sl_pts_sell = max(45.0, swing_high5 - close_p + 10.0)
                lot = 25 * lot_mult
            else:
                sl_pts_buy = max(close_p * 0.008, (close_p - swing_low5) + (close_p * 0.002))
                sl_pts_sell = max(close_p * 0.008, (swing_high5 - close_p) + (close_p * 0.002))
                lot = max(10, min(100, int(1500.0 / sl_pts_buy))) * (2 if lot_mult > 1 else 1)

            # BUY SETUP
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
                if is_idx:
                    active_index_count += 1

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
                    "marginInr": (12000.0 * lot_mult) if is_idx else round(close_p * lot * 0.20, 2),
                    "floatingPnlInr": 0.0,
                    "currentNetRoePct": 0.0,
                    "progressPct": 0.0,
                    "stage": 0,
                    "currentMilestone": "ENTRY",
                    "peakRupeeGain": 0.0,
                    "maxLossCapInr": 1500.0,
                    "openedAtFormatted": cur_time_str,
                    "strategyName": f"SUPER_BREADTH_TREND ({'CE' if is_idx else 'BUY'})"
                }
                self.active_positions.append(pos)

            # SELL SETUP
            elif not market_is_bullish and close_p < vwap and ema9 < ema21 and close_p < open_p and high_p >= ema9 * 0.998 and index_chop_filter_sell:
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
                if is_idx:
                    active_index_count += 1

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
                    "marginInr": (12000.0 * lot_mult) if is_idx else round(close_p * lot * 0.20, 2),
                    "floatingPnlInr": 0.0,
                    "currentNetRoePct": 0.0,
                    "progressPct": 0.0,
                    "stage": 0,
                    "currentMilestone": "ENTRY",
                    "peakRupeeGain": 0.0,
                    "maxLossCapInr": 1500.0,
                    "openedAtFormatted": cur_time_str,
                    "strategyName": f"SUPER_BREADTH_TREND ({'PE' if is_idx else 'SELL'})"
                }
                self.active_positions.append(pos)

def test_config(start_sec, breadth_pct, lots, name):
    eng = SuperStrategyReplayEngine(min_start_sec=start_sec, min_breadth_pct=breadth_pct, index_lots=lots)
    oct_dates = [d for d in eng.sorted_dates if "-10-" in d]

    total_pnl = 0.0
    total_trades = 0
    total_wins = 0
    day_pnls = []

    for d in oct_dates:
        eng.set_date(d, auto_play=True)
        eng.is_running = True
        for _ in range(TOTAL_DAY_SECONDS // 5):
            eng.advance_seconds(5)
        st = eng.get_state()
        w = st['wallet']
        pnl = w['realizedPnlInr']
        trades = w['totalTrades']
        wins = w['wins']
        day_pnls.append((d, pnl, trades, wins))
        total_pnl += pnl
        total_trades += trades
        total_wins += wins

    wr = (total_wins / max(1, total_trades)) * 100.0
    win_days = sum(1 for _, pnl, _, _ in day_pnls if pnl > 0)
    loss_days = sum(1 for _, pnl, _, _ in day_pnls if pnl <= 0)
    print(f"\n{name} (Lots={lots}, StartSec={start_sec}, Breadth={breadth_pct}%):")
    print(f"  Net PnL: INR {total_pnl:>10,.2f} ({total_pnl/1000:>+5.1f}% Return on 1 Lakh)")
    print(f"  Trades: {total_trades:>3} | Wins: {total_wins:>3} | Losses: {total_trades-total_wins:>3} | Win Rate: {wr:>5.1f}%")
    print(f"  Winning Days: {win_days:>2} / {len(oct_dates)} ({win_days/len(oct_dates)*100:.1f}%) | Losing Days: {loss_days:>2}")
    return total_pnl, wr, day_pnls

if __name__ == "__main__":
    print("Testing High-Accuracy '15 Oct Model' across October 2026:")
    print("=" * 80)
    test_config(1800, 70.0, 1, "Config 1: 1-Lot + 09:45 AM Start + 70% Breadth")
    test_config(2700, 70.0, 1, "Config 2: 1-Lot + 10:00 AM Start + 70% Breadth")
    test_config(1800, 70.0, 2, "Config 3: 2-Lot + 09:45 AM Start + 70% Breadth")
    test_config(2700, 70.0, 2, "Config 4: 2-Lot + 10:00 AM Start + 70% Breadth")
    test_config(1800, 75.0, 2, "Config 5: 2-Lot + 09:45 AM Start + 75% Breadth (High Conviction)")
