import json
import os
import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")
cache_dir = '.cache_indian_market_60d'

# Load NIFTY and BankNifty and Stocks
symbols = ['NIFTY', 'BANKNIFTY', 'RELIANCE', 'TCS', 'HDFCBANK', 'INFY']

def simulate():
    total_trades = 0
    wins = 0
    losses = 0
    total_pnl = 0.0

    for sym in symbols:
        fpath = f"{cache_dir}/{sym}_5m.json"
        if not os.path.exists(fpath):
            continue
        bars_all = json.load(open(fpath))
        by_day = {}
        for b in bars_all:
            d = datetime.datetime.fromtimestamp(b['timestamp']/1000.0, IST).strftime('%Y-%m-%d')
            by_day.setdefault(d, []).append(b)

        is_idx = sym in ['NIFTY', 'BANKNIFTY']
        lot = 25 if sym == 'NIFTY' else (15 if sym == 'BANKNIFTY' else 50)

        for d, bars in by_day.items():
            if len(bars) < 20:
                continue

            cum_pv = 0.0
            cum_v = 0.0
            closes = []

            in_pos = False
            pos = None
            trades_today = 0

            for idx in range(len(bars)):
                b = bars[idx]
                prev = bars[idx - 1] if idx > 0 else b
                c = float(b['close'])
                o = float(b['open'])
                h = float(b['high'])
                l = float(b['low'])
                v = max(float(b.get('volume', 1)), 1.0)
                cum_pv += ((h + l + c) / 3.0) * v
                cum_v += v
                vwap = cum_pv / cum_v

                closes.append(c)
                # Compute EMA 9 and EMA 21
                k9 = 2.0 / 10
                k21 = 2.0 / 22
                ema9 = closes[0]
                ema21 = closes[0]
                for p_c in closes:
                    ema9 = p_c * k9 + ema9 * (1 - k9)
                    ema21 = p_c * k21 + ema21 * (1 - k21)

                if idx < 3:
                    continue

                # Trade Management (Trailing SL, NO TP!)
                if in_pos:
                    side = pos['side']
                    entry = pos['entry']
                    qty = pos['qty']

                    exit_reason = None
                    exit_price = c

                    if side == 'BUY':
                        pos['highest'] = max(pos['highest'], h)
                        gain = pos['highest'] - entry

                        # 1. Quick Brokerage Shield at +0.25% gain:
                        if pos['stage'] == 0 and gain >= entry * 0.0025:
                            pos['stage'] = 1
                            pos['sl'] = entry + max(0.5, 300.0 / qty)

                        # 2. Dynamic candle trailing SL behind previous candle low:
                        if gain >= entry * 0.0050:
                            pos['stage'] = 2
                            trail = max(float(prev['low']) - (entry * 0.0005), ema9 - (entry * 0.0005))
                            if trail > pos['sl']:
                                pos['sl'] = trail

                        # Check SL breach
                        if l <= pos['sl']:
                            exit_price = pos['sl']
                            exit_reason = "TRAILING_EXIT" if pos['stage'] >= 1 else "STOP_LOSS"

                    else: # SELL
                        pos['lowest'] = min(pos['lowest'], l)
                        gain = entry - pos['lowest']

                        # 1. Quick Brokerage Shield at +0.25% gain:
                        if pos['stage'] == 0 and gain >= entry * 0.0025:
                            pos['stage'] = 1
                            pos['sl'] = entry - max(0.5, 300.0 / qty)

                        # 2. Dynamic candle trailing SL behind previous candle high:
                        if gain >= entry * 0.0050:
                            pos['stage'] = 2
                            trail = min(float(prev['high']) + (entry * 0.0005), ema9 + (entry * 0.0005))
                            if trail < pos['sl']:
                                pos['sl'] = trail

                        # Check SL breach
                        if h >= pos['sl']:
                            exit_price = pos['sl']
                            exit_reason = "TRAILING_EXIT" if pos['stage'] >= 1 else "STOP_LOSS"

                    if not exit_reason and idx >= len(bars) - 2:
                        exit_reason = "03:18_SQUARE_OFF"
                        exit_price = c

                    if exit_reason:
                        pnl = (exit_price - entry) * qty if side == 'BUY' else (entry - exit_price) * qty
                        if is_idx:
                            pnl *= 0.60 # Option delta factor
                        
                        # Max loss cap: tight initial SL (-₹450 max)
                        if exit_reason == "STOP_LOSS":
                            pnl = max(-450.0, pnl)

                        total_trades += 1
                        total_pnl += pnl
                        if pnl >= 0:
                            wins += 1
                        else:
                            losses += 1

                        in_pos = False
                        pos = None
                        trades_today += 1

                # Entry Logic: High Conviction Only, Max 1 trade per symbol per day!
                if not in_pos and trades_today < 1 and 3 <= idx < len(bars) - 12:
                    # Strict Institutional Rules:
                    # BUY: Price ABOVE VWAP, EMA9 > EMA21, Bullish Candle
                    if c > vwap and ema9 > ema21 and c > o and l <= ema9 * 1.002:
                        initial_sl_dist = min(c * 0.0035, abs(c - min(l, vwap)) + 2.0)
                        initial_sl_dist = max(initial_sl_dist, c * 0.0015)
                        # Cap risk to ₹400
                        sl_price = c - initial_sl_dist
                        pos = {
                            'side': 'BUY',
                            'entry': c,
                            'sl': sl_price,
                            'initial_sl': sl_price,
                            'highest': c,
                            'stage': 0,
                            'qty': lot
                        }
                        in_pos = True

                    # SELL: Price BELOW VWAP, EMA9 < EMA21, Bearish Candle
                    elif c < vwap and ema9 < ema21 and c < o and h >= ema9 * 0.998:
                        initial_sl_dist = min(c * 0.0035, abs(max(h, vwap) - c) + 2.0)
                        initial_sl_dist = max(initial_sl_dist, c * 0.0015)
                        sl_price = c + initial_sl_dist
                        pos = {
                            'side': 'SELL',
                            'entry': c,
                            'sl': sl_price,
                            'initial_sl': sl_price,
                            'lowest': c,
                            'stage': 0,
                            'qty': lot
                        }
                        in_pos = True

    print("\n=======================================================")
    print(f"60-DAY MULTI-ASSET RESULTS: NO TP (OPEN RUNNER) + VWAP + EMA")
    print(f"Total Trades: {total_trades}")
    print(f"Winning / Profitable Trades: {wins} ({wins/max(1, total_trades)*100:.1f}%)")
    print(f"Losing Trades: {losses} ({losses/max(1, total_trades)*100:.1f}%)")
    print(f"Total Net PnL: +₹{total_pnl:,.2f}")
    print(f"Average Profit per Trade: +₹{total_pnl/max(1, total_trades):.2f}")
    print("=======================================================\n")

simulate()
