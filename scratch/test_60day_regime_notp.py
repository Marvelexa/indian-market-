import json
import os
import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")
cache_dir = '.cache_indian_market_60d'
symbols = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX', 'RELIANCE', 'HDFCBANK', 'ICICIBANK', 'SBIN', 'INFY', 'TCS', 'TATAMOTORS', 'AXISBANK', 'LT', 'BAJFINANCE']

# Load data by day
by_day_data = {}
for sym in symbols:
    fpath = f"{cache_dir}/{sym}_5m.json"
    if not os.path.exists(fpath):
        continue
    bars = json.load(open(fpath))
    for b in bars:
        d = datetime.datetime.fromtimestamp(b['timestamp']/1000.0, IST).strftime('%Y-%m-%d')
        by_day_data.setdefault(d, {}).setdefault(sym, []).append(b)

sorted_days = sorted(by_day_data.keys())

total_trades = 0
wins = 0
losses = 0
total_pnl = 0.0

for d in sorted_days:
    d_data = by_day_data[d]
    nifty_bars = d_data.get('NIFTY', [])
    if len(nifty_bars) < 20:
        continue

    # Active positions simulation for day
    active_pos = []
    closed = []
    symbol_traded = {}

    for idx in range(3, min(74, len(nifty_bars))):
        # 1. Determine Market Master Bias from NIFTY
        n_c = float(nifty_bars[idx]['close'])
        n_pv = sum(((float(b['high']) + float(b['low']) + float(b['close'])) / 3.0) * max(float(b.get('volume', 1)), 1.0) for b in nifty_bars[:idx+1])
        n_v = sum(max(float(b.get('volume', 1)), 1.0) for b in nifty_bars[:idx+1])
        n_vwap = n_pv / n_v if n_v > 0 else n_c
        market_bull = n_c >= n_vwap

        # 2. Update active positions
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

            # High/low gain
            gain = (h - entry) if is_buy else (entry - l)
            gain_pct = (gain / entry) * 100.0

            # Brokerage shield at +0.22%
            if pos['stage'] == 0 and gain_pct >= 0.22:
                pos['stage'] = 1
                pos['sl'] = entry + (14.0 if pos['is_opt'] else (entry * 0.0018)) if is_buy else entry - (14.0 if pos['is_opt'] else (entry * 0.0018))

            # Dynamic trailing at +0.45%
            if gain_pct >= 0.45:
                pos['stage'] = 2
                prev_b = bars[idx - 1]
                if is_buy:
                    trail = float(prev_b['low']) - (entry * 0.0005)
                    if trail > pos['sl']:
                        pos['sl'] = trail
                else:
                    trail = float(prev_b['high']) + (entry * 0.0005)
                    if trail < pos['sl']:
                        pos['sl'] = trail

            exit_r = None
            exit_p = c
            if is_buy and l <= pos['sl']:
                exit_p = pos['sl']
                exit_r = "TRAILING_RUNNER_EXIT" if pos['stage'] >= 2 else ("BROKERAGE_SHIELDED_SCRATCH" if pos['stage'] == 1 else "TIGHT_STOP_LOSS")
            elif not is_buy and h >= pos['sl']:
                exit_p = pos['sl']
                exit_r = "TRAILING_RUNNER_EXIT" if pos['stage'] >= 2 else ("BROKERAGE_SHIELDED_SCRATCH" if pos['stage'] == 1 else "TIGHT_STOP_LOSS")
            elif idx >= min(72, len(bars) - 2):
                exit_r = "03:18_AUTO_SQUARE_OFF"
                exit_p = c

            if exit_r:
                pnl = (exit_p - entry) * qty if is_buy else (entry - exit_p) * qty
                if pos['is_opt']:
                    pnl *= 0.60
                if exit_r == "TIGHT_STOP_LOSS":
                    pnl = max(-350.0, pnl)
                closed.append({'pnl': pnl, 'reason': exit_r})
            else:
                rem.append(pos)
        active_pos = rem

        # 3. Open new positions if seats available (max 6)
        if len(active_pos) < 6 and idx < len(nifty_bars) - 10:
            for sym in symbols:
                if len(active_pos) >= 6:
                    break
                if any(p['symbol'] == sym for p in active_pos) or symbol_traded.get(sym, 0) >= 1:
                    continue
                bars = d_data.get(sym, [])
                if idx >= len(bars):
                    continue
                c_b = bars[idx]
                close_p = float(c_b['close'])
                open_p = float(c_b['open'])
                high_p = float(c_b['high'])
                low_p = float(c_b['low'])

                sess_bars = bars[:idx+1]
                cum_pv = sum(((float(b['high']) + float(b['low']) + float(b['close'])) / 3.0) * max(float(b.get('volume', 1)), 1.0) for b in sess_bars)
                cum_v = sum(max(float(b.get('volume', 1)), 1.0) for b in sess_bars)
                vwap = cum_pv / cum_v if cum_v > 0 else close_p

                closes_list = [float(b['close']) for b in sess_bars]
                k9 = 2.0 / 10
                k21 = 2.0 / 22
                ema9 = closes_list[0]
                ema21 = closes_list[0]
                for cl in closes_list:
                    ema9 = cl * k9 + ema9 * (1 - k9)
                    ema21 = cl * k21 + ema21 * (1 - k21)

                is_opt = sym in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX']
                lot = 25 if sym == 'NIFTY' else (15 if sym == 'BANKNIFTY' else (40 if sym == 'FINNIFTY' else (10 if sym == 'SENSEX' else 50)))

                if market_bull and close_p > vwap and ema9 > ema21 and close_p > open_p and low_p <= ema9 * 1.002:
                    sl_dist = min(close_p * 0.0030, abs(close_p - min(low_p, vwap)) + (4.0 if is_opt else 1.5))
                    sl_dist = max(sl_dist, close_p * 0.0015)
                    sl_p = close_p - sl_dist
                    active_pos.append({
                        'symbol': sym,
                        'side': 'BUY',
                        'entry': close_p,
                        'sl': sl_p,
                        'stage': 0,
                        'qty': lot,
                        'is_opt': is_opt
                    })
                    symbol_traded[sym] = 1

                elif not market_bull and close_p < vwap and ema9 < ema21 and close_p < open_p and high_p >= ema9 * 0.998:
                    sl_dist = min(close_p * 0.0030, abs(max(high_p, vwap) - close_p) + (4.0 if is_opt else 1.5))
                    sl_dist = max(sl_dist, close_p * 0.0015)
                    sl_p = close_p + sl_dist
                    active_pos.append({
                        'symbol': sym,
                        'side': 'SELL',
                        'entry': close_p,
                        'sl': sl_p,
                        'stage': 0,
                        'qty': lot,
                        'is_opt': is_opt
                    })
                    symbol_traded[sym] = 1

    for c in closed:
        total_trades += 1
        total_pnl += c['pnl']
        if c['pnl'] >= 0:
            wins += 1
        else:
            losses += 1

print("==================================================")
print(f"60-DAY MULTI-ASSET WITH MARKET REGIME BIAS & NO TP:")
print(f"Total Trades: {total_trades}")
print(f"Wins / Scratches: {wins} ({wins/max(1, total_trades)*100:.1f}%)")
print(f"Losses: {losses} ({losses/max(1, total_trades)*100:.1f}%)")
print(f"Net Realized PnL: +₹{total_pnl:,.2f}")
print(f"Avg Profit/Trade: +₹{total_pnl/max(1, total_trades):.2f}")
print("==================================================")
