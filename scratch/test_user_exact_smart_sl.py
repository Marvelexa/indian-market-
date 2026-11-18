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

def test_day_smart_sl(target_date):
    d_data = by_day_data.get(target_date, {})
    nifty_bars = d_data.get('NIFTY', [])
    if not nifty_bars: return

    day_pnl = 0.0
    active_pos = []
    symbol_traded = {}
    ledger = []

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
            worst_gain = ((l - entry) if is_buy else (entry - h)) * mult

            # Stage 1: TP 1 (1000) -> Lock 700
            if pos['stage'] == 0 and best_gain >= 1000.0:
                pos['stage'] = 1
                buf_pts = 700.0 / mult
                pos['sl'] = entry + buf_pts if is_buy else entry - buf_pts

            # Stage 2: TP 2 (1300) -> Lock 1000
            if pos['stage'] <= 1 and best_gain >= 1300.0:
                pos['stage'] = 2
                buf_pts = 1000.0 / mult
                new_sl = entry + buf_pts if is_buy else entry - buf_pts
                if (is_buy and new_sl > pos['sl']) or (not is_buy and new_sl < pos['sl']):
                    pos['sl'] = new_sl

            # Stage 3: TP 3 (1500) -> Full Target Exit
            if best_gain >= 1500.0:
                pnl = 1500.0
                day_pnl += pnl
                ledger.append({'sym': sym, 'pnl': pnl, 'badge': '🎯 TP 3 (+₹1,500 TARGET)'})
                continue

            # Trailing SL check for locked stages
            if pos['stage'] >= 1:
                sl_hit = (l <= pos['sl']) if is_buy else (h >= pos['sl'])
                if sl_hit:
                    exit_p = pos['sl']
                    pnl = ((exit_p - entry) if is_buy else (entry - exit_p)) * mult
                    day_pnl += pnl
                    badge = '🎯 TP 2 (+₹1,300 / LOCK 1K)' if pos['stage'] == 2 else '🎯 TP 1 (+₹1,000 / LOCK 700)'
                    ledger.append({'sym': sym, 'pnl': pnl, 'badge': badge})
                    continue

            # Stage 0: Smart SL Evaluation
            # 1. Hard cap -1500
            if worst_gain <= -1500.0:
                pnl = -1500.0
                day_pnl += pnl
                ledger.append({'sym': sym, 'pnl': pnl, 'badge': '🛑 MAX LOSS CAP (-₹1,500)'})
                continue

            # 2. Check if SL crossed
            sl_crossed = (l <= pos['sl']) if is_buy else (h >= pos['sl'])
            if sl_crossed:
                rng = max(h - l, 0.05)
                lower_wick = (min(o, c) - l) / rng
                upper_wick = (h - max(o, c)) / rng

                reversal_likely = (lower_wick >= 0.28) if is_buy else (upper_wick >= 0.28)
                if reversal_likely:
                    # Do NOT exit, reversal can come!
                    pass
                else:
                    # Trend breakdown confirmed! Paka 1500 hit hoga -> Exit immediately!
                    exit_p = pos['sl']
                    pnl = ((exit_p - entry) if is_buy else (entry - exit_p)) * mult
                    if pnl < -1500.0: pnl = -1500.0
                    day_pnl += pnl
                    ledger.append({'sym': sym, 'pnl': pnl, 'badge': f'🛡️ SMART SL EXIT (-₹{abs(pnl):.0f})'})
                    continue

            rem.append(pos)
        active_pos = rem

        # Entry logic
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
                sl_pts = max(50.0, close_p - swing_low5 + 10.0)
                lot = 25
            elif sym == 'BANKNIFTY':
                sl_pts = max(110.0, close_p - swing_low5 + 20.0)
                lot = 15
            elif sym == 'SENSEX':
                sl_pts = max(160.0, close_p - swing_low5 + 30.0)
                lot = 10
            elif sym == 'FINNIFTY':
                sl_pts = max(50.0, close_p - swing_low5 + 10.0)
                lot = 25
            else:
                sl_pts = max(close_p * 0.009, (close_p - swing_low5) + (close_p * 0.002))
                lot = max(10, min(100, int(1200.0 / sl_pts)))

            if market_bull and close_p > vwap and ema9 > ema21 and close_p > open_p and low_p <= ema9 * 1.002:
                active_pos.append({'symbol': sym, 'side': 'BUY', 'entry': close_p, 'sl': close_p - sl_pts, 'stage': 0, 'qty': lot, 'is_opt': is_opt})
                symbol_traded[sym] = 1
            elif not market_bull and close_p < vwap and ema9 < ema21 and close_p < open_p and high_p >= ema9 * 0.998:
                active_pos.append({'symbol': sym, 'side': 'SELL', 'entry': close_p, 'sl': close_p + sl_pts, 'stage': 0, 'qty': lot, 'is_opt': is_opt})
                symbol_traded[sym] = 1

    print(f"=== Date: {target_date} ===")
    print(f"Day PnL: Rs. {day_pnl:,.2f}")
    for item in ledger:
        print(f"  {item['sym']:12} | PnL: Rs. {item['pnl']:+8.1f} | Badge: {item['badge']}")

test_day_smart_sl('2026-11-02')
print("-" * 50)
test_day_smart_sl('2026-11-04')
