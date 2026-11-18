import json, os, datetime, pytz

IST = pytz.timezone('Asia/Kolkata')
cache_dir = '.cache_indian_market_60d'
symbols = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX', 'RELIANCE', 'HDFCBANK', 'ICICIBANK', 'SBIN', 'INFY', 'TCS', 'TATAMOTORS', 'AXISBANK', 'LT', 'BAJFINANCE']

by_day_data = {}
for sym in symbols:
    fpath = f'{cache_dir}/{sym}_5m.json'
    if not os.path.exists(fpath): continue
    bars = json.load(open(fpath))
    for b in bars:
        d = datetime.datetime.fromtimestamp(b['timestamp']/1000.0, IST).strftime('%Y-%m-%d')
        by_day_data.setdefault(d, {}).setdefault(sym, []).append(b)

sorted_days = sorted(by_day_data.keys())

def test_user_ladder(tp1=1000.0, lock1=500.0, tp2=1300.0, lock2=1000.0, tp3=1500.0, exit_at_tp3=True, max_sl_cap=1000.0):
    total_trades = 0
    wins = 0
    total_pnl = 0.0
    tp1_count = 0
    tp2_count = 0
    tp3_count = 0
    sl_count = 0

    for d in sorted_days:
        d_data = by_day_data[d]
        nifty_bars = d_data.get('NIFTY', [])
        if len(nifty_bars) < 20: continue

        day_pnl = 0.0
        active_pos = []
        symbol_traded = {}

        for idx in range(3, min(74, len(nifty_bars))):
            if day_pnl <= -1500.0: break

            n_c = float(nifty_bars[idx]['close'])
            n_sess = nifty_bars[:idx+1]
            n_pv = sum(((float(b['high']) + float(b['low']) + float(b['close'])) / 3.0) * max(float(b.get('volume', 1)), 1.0) for b in n_sess)
            n_v = sum(max(float(b.get('volume', 1)), 1.0) for b in n_sess)
            n_vwap = n_pv / n_v if n_v > 0 else n_c
            market_bull = n_c >= n_vwap

            rem = []
            for pos in active_pos:
                sym = pos['symbol']
                bars = d_data.get(sym, [])
                if idx >= len(bars):
                    rem.append(pos)
                    continue
                b = bars[idx]
                h = float(b['high'])
                l = float(b['low'])
                c = float(b['close'])
                is_buy = pos['side'] == 'BUY'
                entry = pos['entry']
                qty = pos['qty']
                is_opt = pos['is_opt']
                mult = qty * (0.60 if is_opt else 1.0)

                # Rupee gain high / low
                best_gain = ((h - entry) if is_buy else (entry - l)) * mult
                worst_gain = ((l - entry) if is_buy else (entry - h)) * mult

                # Milestone 1: TP 1 (1000) -> lock
                if pos['stage'] == 0 and best_gain >= tp1:
                    pos['stage'] = 1
                    buf_pts = lock1 / mult
                    pos['sl'] = entry + buf_pts if is_buy else entry - buf_pts

                # Milestone 2: TP 2 (1300) -> lock higher
                if pos['stage'] <= 1 and best_gain >= tp2:
                    pos['stage'] = 2
                    buf_pts = lock2 / mult
                    new_sl = entry + buf_pts if is_buy else entry - buf_pts
                    if (is_buy and new_sl > pos['sl']) or (not is_buy and new_sl < pos['sl']):
                        pos['sl'] = new_sl

                # Milestone 3: TP 3 (1500)
                if exit_at_tp3 and best_gain >= tp3:
                    pnl = tp3
                    total_pnl += pnl
                    day_pnl += pnl
                    total_trades += 1
                    wins += 1
                    tp3_count += 1
                    continue
                elif not exit_at_tp3 and pos['stage'] <= 2 and best_gain >= tp3:
                    pos['stage'] = 3
                    buf_pts = lock2 / mult # e.g. lock 1200 or 1300
                    new_sl = entry + buf_pts if is_buy else entry - buf_pts
                    if (is_buy and new_sl > pos['sl']) or (not is_buy and new_sl < pos['sl']):
                        pos['sl'] = new_sl

                # Check SL hit
                sl_hit = (l <= pos['sl']) if is_buy else (h >= pos['sl'])
                if sl_hit:
                    exit_price = pos['sl']
                    trade_pnl = ((exit_price - entry) if is_buy else (entry - exit_price)) * mult
                    if trade_pnl < -max_sl_cap:
                        trade_pnl = -max_sl_cap
                    total_pnl += trade_pnl
                    day_pnl += trade_pnl
                    total_trades += 1
                    if trade_pnl > 0:
                        wins += 1
                        if pos['stage'] == 2: tp2_count += 1
                        elif pos['stage'] == 1: tp1_count += 1
                    else:
                        sl_count += 1
                    continue

                rem.append(pos)
            active_pos = rem

            # Entry condition
            if len(active_pos) >= 6: continue
            for sym in symbols:
                if len(active_pos) >= 6: break
                if any(p['symbol'] == sym for p in active_pos): continue
                if symbol_traded.get(sym, 0) >= 1: continue

                bars = d_data.get(sym, [])
                if idx < 3 or idx >= len(bars) - 5: continue
                c_bar = bars[idx]
                close_p = float(c_bar['close'])
                open_p = float(c_bar['open'])
                high_p = float(c_bar['high'])
                low_p = float(c_bar['low'])

                session_bars = bars[:idx+1]
                cum_pv = sum(((float(b['high']) + float(b['low']) + float(b['close'])) / 3.0) * max(float(b.get('volume', 1)), 1.0) for b in session_bars)
                cum_v = sum(max(float(b.get('volume', 1)), 1.0) for b in session_bars)
                vwap = cum_pv / cum_v if cum_v > 0 else close_p

                closes = [float(b['close']) for b in session_bars]
                k9 = 2.0 / 10
                k21 = 2.0 / 22
                ema9 = closes[0]
                ema21 = closes[0]
                for cl in closes:
                    ema9 = cl * k9 + ema9 * (1 - k9)
                    ema21 = cl * k21 + ema21 * (1 - k21)

                is_opt = sym in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX']
                past5 = bars[max(0, idx-5):idx+1]
                swing_low5 = min(float(b['low']) for b in past5)
                swing_high5 = max(float(b['high']) for b in past5)

                if sym == 'NIFTY':
                    sl_pts_buy = max(45.0, close_p - swing_low5 + 10.0)
                    sl_pts_sell = max(45.0, swing_high5 - close_p + 10.0)
                    lot = 25
                elif sym == 'BANKNIFTY':
                    sl_pts_buy = max(110.0, close_p - swing_low5 + 20.0)
                    sl_pts_sell = max(110.0, swing_high5 - close_p + 20.0)
                    lot = 15
                elif sym == 'SENSEX':
                    sl_pts_buy = max(160.0, close_p - swing_low5 + 30.0)
                    sl_pts_sell = max(160.0, swing_high5 - close_p + 30.0)
                    lot = 10
                elif sym == 'FINNIFTY':
                    sl_pts_buy = max(50.0, close_p - swing_low5 + 10.0)
                    sl_pts_sell = max(50.0, swing_high5 - close_p + 10.0)
                    lot = 25
                else:
                    sl_pts_buy = max(close_p * 0.008, (close_p - swing_low5) + (close_p * 0.002))
                    sl_pts_sell = max(close_p * 0.008, (swing_high5 - close_p) + (close_p * 0.002))
                    lot = max(10, min(100, int(max_sl_cap / sl_pts_buy)))

                if market_bull and close_p > vwap and ema9 > ema21 and close_p > open_p and low_p <= ema9 * 1.002:
                    active_pos.append({'symbol': sym, 'side': 'BUY', 'entry': close_p, 'sl': close_p - sl_pts_buy, 'stage': 0, 'qty': lot, 'is_opt': is_opt})
                    symbol_traded[sym] = 1
                elif not market_bull and close_p < vwap and ema9 < ema21 and close_p < open_p and high_p >= ema9 * 0.998:
                    active_pos.append({'symbol': sym, 'side': 'SELL', 'entry': close_p, 'sl': close_p + sl_pts_sell, 'stage': 0, 'qty': lot, 'is_opt': is_opt})
                    symbol_traded[sym] = 1

    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    return total_trades, wins, win_rate, total_pnl, tp1_count, tp2_count, tp3_count, sl_count

configs = [
    # (name, tp1, lock1, tp2, lock2, tp3, exit_tp3, max_sl)
    ("User Ladder: TP1=1000(lock 500), TP2=1300(lock 1000), TP3=1500(exit), SL_Cap=1000", 1000, 500, 1300, 1000, 1500, True, 1000),
    ("User Ladder: TP1=1000(lock Breakeven+100), TP2=1300(lock 800), TP3=1500(exit), SL_Cap=1000", 1000, 100, 1300, 800, 1500, True, 1000),
    ("User Ladder: TP1=1000(lock 700), TP2=1300(lock 1100), TP3=1500(exit), SL_Cap=800", 1000, 700, 1300, 1100, 1500, True, 800),
    ("User Ladder: TP1=1000(lock 500), TP2=1300(lock 1000), TP3=1500(exit), SL_Cap=800", 1000, 500, 1300, 1000, 1500, True, 800),
    ("User Ladder with Runner: TP1=1000(lock 500), TP2=1300(lock 1000), TP3=1500(lock 1200+trail), SL_Cap=1000", 1000, 500, 1300, 1000, 1500, False, 1000),
]

for name, tp1, lock1, tp2, lock2, tp3, exit_tp3, max_sl in configs:
    t, w, wr, pnl, tp1c, tp2c, tp3c, slc = test_user_ladder(tp1, lock1, tp2, lock2, tp3, exit_tp3, max_sl)
    print(f"[{name}]")
    print(f"  Trades: {t}, Wins: {w} ({wr:.1f}%), TP3 Hits: {tp3c}, TP2: {tp2c}, TP1: {tp1c}, SL: {slc}, Net PnL: Rs. {pnl:,.2f}")
    print("-" * 60)
