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

def test_smart_sl_simulation():
    total_pnl = 0.0
    wins = 0
    trades = 0
    smart_sl_cuts = 0
    hard_cap_hits = 0
    tp1_hits = 0
    tp2_hits = 0
    tp3_hits = 0
    green_days = 0
    red_days = 0

    for d in sorted_days:
        d_data = by_day_data[d]
        nifty_bars = d_data.get('NIFTY', [])
        if len(nifty_bars) < 20: continue

        day_pnl = 0.0
        active_pos = []
        symbol_traded = {}

        for idx in range(3, min(74, len(nifty_bars))):
            if day_pnl <= -2500.0: break

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
                o = float(b['open'])
                entry = pos['entry']
                qty = pos['qty']
                is_opt = pos['is_opt']
                mult = qty * (0.60 if is_opt else 1.0)
                is_buy = pos['side'] == 'BUY'

                best_gain = ((h - entry) if is_buy else (entry - l)) * mult
                curr_gain = ((c - entry) if is_buy else (entry - c)) * mult
                worst_gain = ((l - entry) if is_buy else (entry - h)) * mult

                # Compute current stock indicators at this candle
                sess_bars = bars[:idx+1]
                stock_pv = sum(((float(sb['high']) + float(sb['low']) + float(sb['close'])) / 3.0) * max(float(sb.get('volume', 1)), 1.0) for sb in sess_bars)
                stock_v = sum(max(float(sb.get('volume', 1)), 1.0) for sb in sess_bars)
                stock_vwap = stock_pv / stock_v if stock_v > 0 else c

                stock_closes = [float(sb['close']) for sb in sess_bars]
                k9 = 2.0 / 10
                k21 = 2.0 / 22
                stock_ema9 = stock_closes[0]
                stock_ema21 = stock_closes[0]
                for sc in stock_closes:
                    stock_ema9 = sc * k9 + stock_ema9 * (1 - k9)
                    stock_ema21 = sc * k21 + stock_ema21 * (1 - k21)

                # Milestone 1: TP 1 (1000) -> Lock 700
                if pos['stage'] == 0 and best_gain >= 1000.0:
                    pos['stage'] = 1
                    buf_pts = 700.0 / mult
                    pos['sl'] = entry + buf_pts if is_buy else entry - buf_pts

                # Milestone 2: TP 2 (1300) -> Lock 1000
                if pos['stage'] <= 1 and best_gain >= 1300.0:
                    pos['stage'] = 2
                    buf_pts = 1000.0 / mult
                    new_sl = entry + buf_pts if is_buy else entry - buf_pts
                    if (is_buy and new_sl > pos['sl']) or (not is_buy and new_sl < pos['sl']):
                        pos['sl'] = new_sl

                # Milestone 3: TP 3 (1500) -> Full Target Exit
                if best_gain >= 1500.0:
                    pnl = 1500.0
                    total_pnl += pnl
                    day_pnl += pnl
                    trades += 1
                    wins += 1
                    tp3_hits += 1
                    continue

                # Trailing SL check (when already locked in profit)
                if pos['stage'] >= 1:
                    sl_hit = (l <= pos['sl']) if is_buy else (h >= pos['sl'])
                    if sl_hit:
                        exit_price = pos['sl']
                        trade_pnl = ((exit_price - entry) if is_buy else (entry - exit_price)) * mult
                        total_pnl += trade_pnl
                        day_pnl += trade_pnl
                        trades += 1
                        if trade_pnl > 0:
                            wins += 1
                            if pos['stage'] == 2: tp2_hits += 1
                            else: tp1_hits += 1
                        continue

                # --- SMART SL LOGIC (STAGE 0: BEFORE PROFIT LOCK) ---
                # 1. Hard Loss Cap (-1500): Emergency stop
                if worst_gain <= -1500.0:
                    trade_pnl = -1500.0
                    total_pnl += trade_pnl
                    day_pnl += trade_pnl
                    trades += 1
                    hard_cap_hits += 1
                    continue

                # 2. Smart Trend Invalidation Exit:
                # "aurr change naa lagee ki paka 1500 hit hoga to ussi same exit kar jaye"
                # If trade is in negative (loss < -300), and:
                # BUY: Candle closes BELOW VWAP AND BELOW EMA 21 (trend has broken!), OR Market Bullish bias flipped
                # SELL: Candle closes ABOVE VWAP AND ABOVE EMA 21, OR Market Bearish bias flipped
                trend_broken = False
                if is_buy and curr_gain <= -300.0:
                    if (c < stock_vwap and c < stock_ema21 and not market_bull) or (c < stock_vwap * 0.995):
                        trend_broken = True
                elif not is_buy and curr_gain <= -300.0:
                    if (c > stock_vwap and c > stock_ema21 and market_bull) or (c > stock_vwap * 1.005):
                        trend_broken = True

                if trend_broken:
                    # Early exit before losing full 1500!
                    exit_price = c
                    trade_pnl = curr_gain
                    if trade_pnl < -1500.0: trade_pnl = -1500.0
                    total_pnl += trade_pnl
                    day_pnl += trade_pnl
                    trades += 1
                    smart_sl_cuts += 1
                    continue

                # 3. Structural Swing SL hit (if price breaches initial swing level)
                swing_hit = (l <= pos['sl']) if is_buy else (h >= pos['sl'])
                if swing_hit:
                    # But check if rejection wick suggests reversal!
                    # "magar jab systsem ko lage kii reversal aasakta hai tab exit na kare"
                    lower_wick_ratio = (min(o, c) - l) / max(h - l, 0.1) if is_buy else 0
                    upper_wick_ratio = (h - max(o, c)) / max(h - l, 0.1) if not is_buy else 0
                    can_reverse = (lower_wick_ratio >= 0.35 if is_buy else upper_wick_ratio >= 0.35) and (c > pos['sl'])
                    
                    if not can_reverse:
                        exit_price = pos['sl']
                        trade_pnl = ((exit_price - entry) if is_buy else (entry - exit_price)) * mult
                        if trade_pnl < -1500.0: trade_pnl = -1500.0
                        total_pnl += trade_pnl
                        day_pnl += trade_pnl
                        trades += 1
                        continue

                rem.append(pos)
            active_pos = rem

            # Entry
            if len(active_pos) >= 4: continue
            for sym in symbols:
                if len(active_pos) >= 4: break
                if any(p['symbol'] == sym for p in active_pos): continue
                if symbol_traded.get(sym, 0) >= 1: continue

                bars = d_data.get(sym, [])
                if idx < 3 or idx >= len(bars) - 5: continue
                c_bar = bars[idx]
                close_p = float(c_bar['close'])
                open_p = float(c_bar['open'])
                low_p = float(c_bar['low'])
                high_p = float(c_bar['high'])

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
                    sl_pts = max(55.0, close_p - swing_low5 + 10.0)
                    lot = 25
                elif sym == 'BANKNIFTY':
                    sl_pts = max(120.0, close_p - swing_low5 + 20.0)
                    lot = 15
                elif sym == 'SENSEX':
                    sl_pts = max(180.0, close_p - swing_low5 + 30.0)
                    lot = 10
                elif sym == 'FINNIFTY':
                    sl_pts = max(60.0, close_p - swing_low5 + 10.0)
                    lot = 25
                else:
                    sl_pts = max(close_p * 0.009, (close_p - swing_low5) + (close_p * 0.002))
                    lot = max(10, min(100, int(1500.0 / sl_pts)))

                if market_bull and close_p > vwap and ema9 > ema21 and close_p > open_p and low_p <= ema9 * 1.002:
                    active_pos.append({'symbol': sym, 'side': 'BUY', 'entry': close_p, 'sl': close_p - sl_pts, 'stage': 0, 'qty': lot, 'is_opt': is_opt})
                    symbol_traded[sym] = 1
                elif not market_bull and close_p < vwap and ema9 < ema21 and close_p < open_p and high_p >= ema9 * 0.998:
                    active_pos.append({'symbol': sym, 'side': 'SELL', 'entry': close_p, 'sl': close_p + sl_pts, 'stage': 0, 'qty': lot, 'is_opt': is_opt})
                    symbol_traded[sym] = 1

        if day_pnl > 0: green_days += 1
        elif day_pnl < 0: red_days += 1

    win_rate = (wins / trades * 100) if trades > 0 else 0
    print(f"Smart SL Results:")
    print(f"  Trades: {trades}, Wins: {wins} ({win_rate:.1f}%), GreenDays: {green_days}, RedDays: {red_days}")
    print(f"  TP3: {tp3_hits}, TP2: {tp2_hits}, TP1: {tp1_hits}")
    print(f"  Smart Cuts (Early): {smart_sl_cuts}, Full Hard Cap Hits (-1500): {hard_cap_hits}")
    print(f"  Net PnL: Rs. {total_pnl:,.2f}")

test_smart_sl_simulation()
