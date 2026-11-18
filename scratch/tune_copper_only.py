import pandas as pd
import numpy as np
import json
from test_scaled_performance import raw_candles

# Let's inspect COPPER alone to see how it can be cleanly traded profitably
spec = {
    'symbol': 'COPPER',
    'raw_sym': 'COPPER',
    'point_val': 2500.0,
    'lots': 1,
    'tick_size': 0.05,
    'min_sl': 1.0,
    'max_sl': 1.5,
    'min_tp': 2.0,
}

candles = raw_candles.get('COPPER', [])
df = pd.DataFrame(candles)
df['dt'] = pd.to_datetime(df['timestamp'], unit='ms') + pd.Timedelta(hours=5, minutes=30)
df['date'] = df['dt'].dt.strftime('%Y-%m-%d')
df['time'] = df['dt'].dt.strftime('%H:%M')

closes = df['close'].values
highs = df['high'].values
lows = df['low'].values
opens = df['open'].values
volumes = df['volume'].values

typ = (highs + lows + closes) / 3.0
v = np.maximum(volumes, 1)
cum_pv = np.cumsum(typ * v)
cum_v = np.cumsum(v)
vwap = cum_pv / cum_v

std20 = pd.Series(typ).rolling(20, min_periods=5).std().fillna(1.0).values
upper2 = vwap + 2.0 * std20
lower2 = vwap - 2.0 * std20

ema9 = pd.Series(closes).ewm(span=9, adjust=False).mean().values
ema21 = pd.Series(closes).ewm(span=21, adjust=False).mean().values

tr = np.maximum(highs - lows, np.maximum(abs(highs - np.roll(closes, 1)), abs(lows - np.roll(closes, 1))))
tr[0] = highs[0] - lows[0]
atr14 = pd.Series(tr).rolling(14, min_periods=5).mean().fillna(1.0).values

hl2 = (highs + lows) / 2.0
upper_band = hl2 + 2.0 * atr14
lower_band = hl2 - 2.0 * atr14
supertrend = np.full(len(df), 'BULL')
for i in range(1, len(df)):
    if closes[i] > upper_band[i-1]:
        supertrend[i] = 'BULL'
    elif closes[i] < lower_band[i-1]:
        supertrend[i] = 'BEAR'
    else:
        supertrend[i] = supertrend[i-1]
        
delta = pd.Series(closes).diff()
gain = delta.clip(lower=0).rolling(9, min_periods=5).mean()
loss = (-delta.clip(upper=0)).rolling(9, min_periods=5).mean()
rs = gain / np.maximum(loss, 1e-8)
rsi9 = (100 - (100 / (1 + rs))).fillna(50.0).values

avg_vol = pd.Series(volumes).rolling(20, min_periods=5).mean().fillna(1.0).values
rvol = np.maximum(volumes / np.maximum(avg_vol, 1.0), 0.1)

body = abs(closes - opens)
rng = np.maximum(highs - lows, 1e-8)
body_ratio = body / rng
roc3 = (closes - np.roll(closes, 3)) / np.maximum(atr14, 1e-8)
roc3[:3] = 0.0
ag_score = np.minimum(100.0, np.abs(roc3) * 35.0 + rvol * 25.0 + body_ratio * 30.0)

upper_wick = (highs - np.maximum(opens, closes)) / rng
lower_wick = (np.minimum(opens, closes) - lows) / rng

for min_ag in [48.0, 52.0, 55.0]:
    for min_rvol in [1.1, 1.25, 1.5]:
        trades = []
        active_pos = None
        last_exit_idx = -999
        for i in range(40, len(df)):
            c_time = df['time'].iloc[i]
            c_date = df['date'].iloc[i]
            h = int(c_time.split(':')[0])
            m = int(c_time.split(':')[1])
            mins = h * 60 + m
            is_session = (9 * 60 + 15) <= mins <= (23 * 60 + 20)
            
            if active_pos:
                closed = False
                exit_price = 0.0
                pos = active_pos
                if pos['action'] == 'BUY':
                    if lows[i] <= pos['sl_price']:
                        exit_price = pos['sl_price']
                        closed = True
                    elif highs[i] >= pos['tp2_price']:
                        exit_price = pos['tp2_price']
                        closed = True
                    elif highs[i] >= pos['tp1_price'] and not pos['tp1_hit']:
                        pos['tp1_hit'] = True
                        pos['sl_price'] = pos['entry_price'] + spec['tick_size'] * 2
                else:
                    if highs[i] >= pos['sl_price']:
                        exit_price = pos['sl_price']
                        closed = True
                    elif lows[i] <= pos['tp2_price']:
                        exit_price = pos['tp2_price']
                        closed = True
                    elif lows[i] <= pos['tp1_price'] and not pos['tp1_hit']:
                        pos['tp1_hit'] = True
                        pos['sl_price'] = pos['entry_price'] - spec['tick_size'] * 2
                        
                if not closed and mins >= (23 * 60 + 20):
                    exit_price = closes[i]
                    closed = True
                    
                if closed:
                    pts = (exit_price - pos['entry_price']) if pos['action'] == 'BUY' else (pos['entry_price'] - exit_price)
                    pnl = pts * spec['point_val'] * spec['lots']
                    trades.append({'date': pos['entry_date'], 'pnl': pnl})
                    active_pos = None
                    last_exit_idx = i
                    
            if not active_pos and is_session and mins < (23 * 60 + 10) and (i - last_exit_idx >= 3):
                entry_price = closes[i]
                recent3_low = min(lows[i], lows[i-1], lows[i-2])
                recent3_high = max(highs[i], highs[i-1], highs[i-2])
                
                action = 'WAIT'
                is_bull_thrust = (
                    closes[i] > opens[i] and closes[i] > highs[i-1] and entry_price > vwap[i] and
                    ema9[i] >= ema21[i] and supertrend[i] == 'BULL' and body_ratio[i] >= 0.50 and
                    upper_wick[i] <= 0.25 and rvol[i] >= min_rvol and ag_score[i] >= min_ag and 52 <= rsi9[i] <= 78
                )
                is_bear_thrust = (
                    closes[i] < opens[i] and closes[i] < lows[i-1] and entry_price < vwap[i] and
                    ema9[i] <= ema21[i] and supertrend[i] == 'BEAR' and body_ratio[i] >= 0.50 and
                    lower_wick[i] <= 0.25 and rvol[i] >= min_rvol and ag_score[i] >= min_ag and 22 <= rsi9[i] <= 48
                )
                if is_bull_thrust: action = 'BUY'
                elif is_bear_thrust: action = 'SELL'
                
                if action != 'WAIT':
                    raw_sl = (entry_price - recent3_low + atr14[i] * 0.3) if action == 'BUY' else (recent3_high - entry_price + atr14[i] * 0.3)
                    clamped_sl = min(spec['max_sl'], max(spec['min_sl'], raw_sl))
                    sl_price = round(entry_price - clamped_sl if action == 'BUY' else entry_price + clamped_sl, 2)
                    tp1_pts = max(spec['min_tp'], clamped_sl * 1.6)
                    tp2_pts = max(spec['min_tp'] * 1.6, clamped_sl * 2.6)
                    tp1_price = round(entry_price + tp1_pts if action == 'BUY' else entry_price - tp1_pts, 2)
                    tp2_price = round(entry_price + tp2_pts if action == 'BUY' else entry_price - tp2_pts, 2)
                    active_pos = {
                        'action': action, 'entry_date': c_date, 'entry_time': c_time,
                        'entry_price': entry_price, 'sl_price': sl_price,
                        'tp1_price': tp1_price, 'tp2_price': tp2_price, 'tp1_hit': False
                    }
        tdf = pd.DataFrame(trades)
        if len(tdf) > 0:
            tot = tdf['pnl'].sum()
            wins = (tdf['pnl'] > 0).sum()
            print(f"Copper AG>={min_ag} RVOL>={min_rvol} | Trades: {len(tdf)} | Wins: {wins} ({wins/len(tdf)*100:.1f}%) | Net: ₹{tot:+,.2f}")
