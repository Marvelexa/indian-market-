import sys
import os
sys.path.append(r"d:\new start")

from backend.replay_engine import IndianPastDateReplayEngine as ReplayEngine, WHITELIST_14_SYMBOLS, INDEX_SET

def run_simulation(tp1_gain=1000.0, tp2_gain=1300.0, tp3_gain=1500.0, max_sl_cap=1000.0, lock_at_tp1=600.0, lock_at_tp2=1000.0, exit_at_tp3=True):
    engine = ReplayEngine()
    engine.load_all_cached_data()
    
    total_pnl = 0.0
    total_trades = 0
    wins = 0
    losses = 0
    tp1_hits = 0
    tp2_hits = 0
    tp3_hits = 0
    sl_hits = 0
    
    # Test across all available dates
    for d_info in engine.available_days:
        d = d_info["date"]
        engine.set_date(d)
        
        # Simulate day
        day_bars = engine.by_date_5m.get(d, {})
        if not day_bars:
            continue
            
        active_positions = []
        symbol_trades = {}
        
        # Step through 5m bars
        for bar_idx in range(3, 70):
            # Check open positions
            rem = []
            for pos in active_positions:
                sym = pos["symbol"]
                bars = day_bars.get(sym, [])
                if bar_idx >= len(bars):
                    rem.append(pos)
                    continue
                b = bars[bar_idx]
                h = float(b["high"])
                l = float(b["low"])
                c = float(b["close"])
                entry = pos["entryPrice"]
                qty = pos["quantity"]
                is_buy = pos["side"] == "BUY"
                is_opt = pos["isOption"]
                mult = (qty * 0.60) if is_opt else qty
                
                # Intra-bar peak and trough
                best_p = h if is_buy else l
                worst_p = l if is_buy else h
                
                max_gain = ((best_p - entry) if is_buy else (entry - best_p)) * mult
                max_loss = ((worst_p - entry) if is_buy else (entry - worst_p)) * mult
                pos["peak_gain"] = max(pos.get("peak_gain", 0.0), max_gain)
                
                # Check stages
                peak = pos["peak_gain"]
                # TP 1
                if pos["stage"] == 0 and peak >= tp1_gain:
                    pos["stage"] = 1
                    # lock
                    locked_rupees = lock_at_tp1
                    buf = locked_rupees / mult
                    pos["slPrice"] = round(entry + buf if is_buy else entry - buf, 2)
                    
                # TP 2
                if pos["stage"] <= 1 and peak >= tp2_gain:
                    pos["stage"] = 2
                    locked_rupees = lock_at_tp2
                    buf = locked_rupees / mult
                    new_sl = round(entry + buf if is_buy else entry - buf, 2)
                    if (is_buy and new_sl > pos["slPrice"]) or (not is_buy and new_sl < pos["slPrice"]):
                        pos["slPrice"] = new_sl
                        
                # TP 3
                if exit_at_tp3 and peak >= tp3_gain:
                    # Target 3 hit -> exit
                    exit_price = round(entry + (tp3_gain / mult) if is_buy else entry - (tp3_gain / mult), 2)
                    pnl = tp3_gain
                    total_pnl += pnl
                    total_trades += 1
                    wins += 1
                    tp3_hits += 1
                    continue
                elif not exit_at_tp3 and pos["stage"] <= 2 and peak >= tp3_gain:
                    pos["stage"] = 3
                    locked_rupees = tp2_gain
                    buf = locked_rupees / mult
                    new_sl = round(entry + buf if is_buy else entry - buf, 2)
                    if (is_buy and new_sl > pos["slPrice"]) or (not is_buy and new_sl < pos["slPrice"]):
                        pos["slPrice"] = new_sl

                # Check SL hit
                sl_hit = (worst_p <= pos["slPrice"]) if is_buy else (worst_p >= pos["slPrice"])
                if sl_hit:
                    exit_p = pos["slPrice"]
                    pnl = ((exit_p - entry) if is_buy else (entry - exit_p)) * mult
                    if pnl < -max_sl_cap:
                        pnl = -max_sl_cap
                    total_pnl += pnl
                    total_trades += 1
                    if pnl > 0:
                        wins += 1
                        if pos["stage"] == 2:
                            tp2_hits += 1
                        elif pos["stage"] == 1:
                            tp1_hits += 1
                    else:
                        losses += 1
                        sl_hits += 1
                    continue
                rem.append(pos)
            active_positions = rem
            
            # Entry logic
            if len(active_positions) >= 6:
                continue
            for sym in WHITELIST_14_SYMBOLS:
                if len(active_positions) >= 6:
                    break
                if any(p["symbol"] == sym for p in active_positions):
                    continue
                if symbol_trades.get(sym, 0) >= 1:
                    continue
                bars = day_bars.get(sym, [])
                if bar_idx < 3 or bar_idx >= len(bars) - 5:
                    continue
                c = bars[bar_idx]
                close_p = float(c["close"])
                open_p = float(c["open"])
                high_p = float(c["high"])
                low_p = float(c["low"])
                
                # Session VWAP & EMA
                session_bars = bars[:bar_idx + 1]
                cum_pv = sum(((float(b["high"]) + float(b["low"]) + float(b["close"])) / 3.0) * max(float(b.get("volume", 1)), 1.0) for b in session_bars)
                cum_v = sum(max(float(b.get("volume", 1)), 1.0) for b in session_bars)
                vwap = (cum_pv / cum_v) if cum_v > 0 else close_p
                
                closes = [float(b["close"]) for b in session_bars]
                k9 = 2.0 / 10
                k21 = 2.0 / 22
                ema9 = closes[0]
                ema21 = closes[0]
                for cl in closes:
                    ema9 = cl * k9 + ema9 * (1 - k9)
                    ema21 = cl * k21 + ema21 * (1 - k21)
                
                is_idx = sym in INDEX_SET
                past5 = bars[max(0, bar_idx - 5):bar_idx + 1]
                swing_low5 = min(float(b["low"]) for b in past5)
                
                if sym == "NIFTY":
                    sl_pts = max(40.0, close_p - swing_low5 + 10.0)
                    lot = 25
                elif sym == "BANKNIFTY":
                    sl_pts = max(100.0, close_p - swing_low5 + 20.0)
                    lot = 15
                elif sym == "SENSEX":
                    sl_pts = max(150.0, close_p - swing_low5 + 30.0)
                    lot = 10
                elif sym == "FINNIFTY":
                    sl_pts = max(50.0, close_p - swing_low5 + 10.0)
                    lot = 25
                else:
                    sl_pts = max(close_p * 0.008, (close_p - swing_low5) + (close_p * 0.002))
                    lot = max(10, min(100, int(max_sl_cap / sl_pts)))
                
                if close_p > vwap and ema9 > ema21 and close_p > open_p and low_p <= ema9 * 1.002:
                    sl_price = round(close_p - sl_pts, 2)
                    pos = {
                        "symbol": sym,
                        "side": "BUY",
                        "isOption": is_idx,
                        "entryPrice": close_p,
                        "slPrice": sl_price,
                        "quantity": lot,
                        "stage": 0,
                        "peak_gain": 0.0
                    }
                    active_positions.append(pos)
                    symbol_trades[sym] = 1

    print(f"Results for TP1={tp1_gain}, TP2={tp2_gain}, TP3={tp3_gain}, MaxSL={max_sl_cap}, Lock1={lock_at_tp1}, Lock2={lock_at_tp2}, ExitTP3={exit_at_tp3}:")
    print(f"Total Trades: {total_trades}, Wins: {wins}, Losses: {losses}, WinRate: {wins/total_trades*100:.1f}%")
    print(f"TP3 Hits: {tp3_hits}, TP2 Hits: {tp2_hits}, TP1 Hits: {tp1_hits}, SL Hits: {sl_hits}")
    print(f"Net PnL: Rs. {total_pnl:,.2f}")
    print("-" * 50)

if __name__ == "__main__":
    # Test Config 1: TP1=1000 (lock 500), TP2=1300 (lock 900), TP3=1500 (exit), MaxSL=1000
    run_simulation(tp1_gain=1000, tp2_gain=1300, tp3_gain=1500, max_sl_cap=1000, lock_at_tp1=500, lock_at_tp2=1000, exit_at_tp3=True)
    # Test Config 2: TP1=1000 (lock 600), TP2=1300 (lock 1000), TP3=1500 (runner trail at 1200), MaxSL=800
    run_simulation(tp1_gain=1000, tp2_gain=1300, tp3_gain=1500, max_sl_cap=800, lock_at_tp1=600, lock_at_tp2=1000, exit_at_tp3=True)
    # Test Config 3: TP1=1000 (lock Cost + 150), TP2=1300 (lock 700), TP3=1500 (exit), MaxSL=1000
    run_simulation(tp1_gain=1000, tp2_gain=1300, tp3_gain=1500, max_sl_cap=1000, lock_at_tp1=150, lock_at_tp2=700, exit_at_tp3=True)
