import pandas as pd
import numpy as np
import json
from test_scaled_performance import raw_candles

SPECS = {
    'CRUDEOIL': {
        'symbol': 'CRUDEOIL',
        'raw_sym': 'CRUDEOIL',
        'point_val': 100.0,
        'lots': 2, # 2 lots Crude = ₹200/pt
        'tick_size': 1.0,
        'min_sl': 14.0,
        'max_sl': 22.0,
        'min_tp': 28.0,
    },
    'NATURALGAS': {
        'symbol': 'NATURALGAS',
        'raw_sym': 'NATURALGAS',
        'point_val': 1250.0,
        'lots': 1,
        'tick_size': 0.1,
        'min_sl': 1.4,
        'max_sl': 2.0,
        'min_tp': 2.6,
    },
    'GOLDM': {
        'symbol': 'GOLDM',
        'raw_sym': 'GOLD',
        'point_val': 10.0,
        'lots': 3, # 3 lots of GoldM = ₹30/pt
        'tick_size': 1.0,
        'min_sl': 75.0,
        'max_sl': 110.0,
        'min_tp': 140.0,
    },
    'SILVERM': {
        'symbol': 'SILVERM',
        'raw_sym': 'SILVER',
        'point_val': 5.0,
        'lots': 3, # 3 lots of SilverM = ₹15/pt
        'tick_size': 1.0,
        'min_sl': 180.0,
        'max_sl': 240.0,
        'min_tp': 300.0,
    },
    'NATGASMINI': {
        'symbol': 'NATGASMINI',
        'raw_sym': 'NATURALGAS',
        'point_val': 250.0,
        'lots': 4, # 4 lots of NatGasMini = ₹1000/pt
        'tick_size': 0.1,
        'min_sl': 1.4,
        'max_sl': 2.2,
        'min_tp': 2.6,
    },
    'COPPER': {
        'symbol': 'COPPER',
        'raw_sym': 'COPPER',
        'point_val': 2500.0,
        'lots': 1,
        'tick_size': 0.05,
        'min_sl': 1.2,
        'max_sl': 1.8,
        'min_tp': 2.2,
    }
}

def test_config(ema_trend_span=34, min_ag=46.0, rvol_req=1.0):
    all_trades = []
    
    for sym, spec in SPECS.items():
        raw_sym = spec['raw_sym']
        candles = raw_candles.get(raw_sym, [])
        if len(candles) < 60:
            continue
            
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
        ema_trend = pd.Series(closes).ewm(span=ema_trend_span, adjust=False).mean().values
        
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
                exit_reason = ""
                pos = active_pos
                
                if pos['action'] == 'BUY':
                    if lows[i] <= pos['sl_price']:
                        exit_price = pos['sl_price']
                        exit_reason = "TRAILED_SL_HIT" if pos['tp1_hit'] else "INITIAL_SL_HIT"
                        closed = True
                    elif highs[i] >= pos['tp2_price']:
                        exit_price = pos['tp2_price']
                        exit_reason = "TP2_RUNNER_TARGET_HIT"
                        closed = True
                    elif highs[i] >= pos['tp1_price'] and not pos['tp1_hit']:
                        pos['tp1_hit'] = True
                        pos['sl_price'] = pos['entry_price'] + spec['tick_size'] * 2
                else: # SELL
                    if highs[i] >= pos['sl_price']:
                        exit_price = pos['sl_price']
                        exit_reason = "TRAILED_SL_HIT" if pos['tp1_hit'] else "INITIAL_SL_HIT"
                        closed = True
                    elif lows[i] <= pos['tp2_price']:
                        exit_price = pos['tp2_price']
                        exit_reason = "TP2_RUNNER_TARGET_HIT"
                        closed = True
                    elif lows[i] <= pos['tp1_price'] and not pos['tp1_hit']:
                        pos['tp1_hit'] = True
                        pos['sl_price'] = pos['entry_price'] - spec['tick_size'] * 2
                        
                if not closed and mins >= (23 * 60 + 20):
                    exit_price = closes[i]
                    exit_reason = "AUTO_SQUARE_OFF_1120PM"
                    closed = True
                    
                if closed:
                    pts = (exit_price - pos['entry_price']) if pos['action'] == 'BUY' else (pos['entry_price'] - exit_price)
                    pnl = pts * spec['point_val'] * spec['lots']
                    all_trades.append({
                        'date': pos['entry_date'],
                        'symbol': sym,
                        'action': pos['action'],
                        'mode': pos['mode'],
                        'entry_time': pos['entry_time'],
                        'exit_time': c_time,
                        'entry_price': pos['entry_price'],
                        'exit_price': round(exit_price, 2),
                        'points': round(pts, 2),
                        'pnl': round(pnl, 2),
                        'reason': exit_reason
                    })
                    active_pos = None
                    last_exit_idx = i
                    
            if not active_pos and is_session and mins < (23 * 60 + 10) and (i - last_exit_idx >= 2):
                entry_price = closes[i]
                recent3_low = min(lows[i], lows[i-1], lows[i-2])
                recent3_high = max(highs[i], highs[i-1], highs[i-2])
                
                action = 'WAIT'
                mode = 'NONE'
                
                # Trend alignment filter:
                # BUY requires entry_price >= ema_trend
                # SELL requires entry_price <= ema_trend
                trend_bull = (entry_price >= ema_trend[i] and ema21[i] >= ema_trend[i] * 0.999)
                trend_bear = (entry_price <= ema_trend[i] and ema21[i] <= ema_trend[i] * 1.001)
                
                # Mode 1: AntiGravity Thrust
                is_bull_thrust = (
                    trend_bull and
                    closes[i] > opens[i] and
                    closes[i] > highs[i-1] and
                    entry_price > vwap[i] and
                    ema9[i] >= ema21[i] and
                    supertrend[i] == 'BULL' and
                    body_ratio[i] >= 0.48 and
                    upper_wick[i] <= 0.25 and
                    rvol[i] >= rvol_req and
                    ag_score[i] >= min_ag and
                    50 <= rsi9[i] <= 78
                )
                
                is_bear_thrust = (
                    trend_bear and
                    closes[i] < opens[i] and
                    closes[i] < lows[i-1] and
                    entry_price < vwap[i] and
                    ema9[i] <= ema21[i] and
                    supertrend[i] == 'BEAR' and
                    body_ratio[i] >= 0.48 and
                    lower_wick[i] <= 0.25 and
                    rvol[i] >= rvol_req and
                    ag_score[i] >= min_ag and
                    22 <= rsi9[i] <= 50
                )
                
                if is_bull_thrust:
                    action = 'BUY'
                    mode = 'ANTI_GRAVITY_THRUST'
                elif is_bear_thrust:
                    action = 'SELL'
                    mode = 'ANTI_GRAVITY_THRUST'
                    
                # Mode 2: VWAP + EMA9 Pullback Scalp
                if action == 'WAIT':
                    bull_pin = (closes[i] > opens[i] and upper_wick[i] <= 0.28 and 
                                (lower_wick[i] >= 0.30 or (closes[i-1] < opens[i-1] and closes[i] > (opens[i-1]+closes[i-1])/2)))
                    bear_pin = (closes[i] < opens[i] and lower_wick[i] <= 0.28 and 
                                (upper_wick[i] >= 0.30 or (closes[i-1] > opens[i-1] and closes[i] < (opens[i-1]+closes[i-1])/2)))
                    
                    touched_bull = (trend_bull and entry_price > vwap[i] and ema9[i] > ema21[i] and 
                                    recent3_low <= max(ema9[i], vwap[i]) * 1.002 and entry_price >= ema9[i])
                    touched_bear = (trend_bear and entry_price < vwap[i] and ema9[i] < ema21[i] and 
                                    recent3_high >= min(ema9[i], vwap[i]) * 0.998 and entry_price <= ema9[i])
                    
                    if touched_bull and bull_pin and (45 <= rsi9[i] <= 68) and rvol[i] >= 0.90 and ag_score[i] >= 42.0:
                        action = 'BUY'
                        mode = 'VWAP_EMA_PULLBACK_SCALP'
                    elif touched_bear and bear_pin and (32 <= rsi9[i] <= 55) and rvol[i] >= 0.90 and ag_score[i] >= 42.0:
                        action = 'SELL'
                        mode = 'VWAP_EMA_PULLBACK_SCALP'
                        
                # Mode 3: 2-Sigma Band Reversal (Only with trend)
                if action == 'WAIT':
                    swept_lower = (trend_bull and recent3_low <= lower2[i] and closes[i] > opens[i] and 
                                   (lower_wick[i] >= 0.35 or body_ratio[i] >= 0.45) and rsi9[i] <= 36 and rsi9[i] > rsi9[i-1] and rvol[i] >= 1.0)
                    swept_upper = (trend_bear and recent3_high >= upper2[i] and closes[i] < opens[i] and 
                                   (upper_wick[i] >= 0.35 or body_ratio[i] >= 0.45) and rsi9[i] >= 64 and rsi9[i] < rsi9[i-1] and rvol[i] >= 1.0)
                    if swept_lower:
                        action = 'BUY'
                        mode = 'EXTREME_BAND_REVERSAL'
                    elif swept_upper:
                        action = 'SELL'
                        mode = 'EXTREME_BAND_REVERSAL'
                        
                if action != 'WAIT':
                    raw_sl = (entry_price - recent3_low + atr14[i] * 0.3) if action == 'BUY' else (recent3_high - entry_price + atr14[i] * 0.3)
                    clamped_sl = min(spec['max_sl'], max(spec['min_sl'], raw_sl))
                    sl_price = round(entry_price - clamped_sl if action == 'BUY' else entry_price + clamped_sl, 2)
                    
                    tp1_pts = max(spec['min_tp'], clamped_sl * 1.6)
                    tp2_pts = max(spec['min_tp'] * 1.6, clamped_sl * 2.6)
                    
                    tp1_price = round(entry_price + tp1_pts if action == 'BUY' else entry_price - tp1_pts, 2)
                    tp2_price = round(entry_price + tp2_pts if action == 'BUY' else entry_price - tp2_pts, 2)
                    
                    active_pos = {
                        'action': action,
                        'mode': mode,
                        'entry_date': c_date,
                        'entry_time': c_time,
                        'entry_price': entry_price,
                        'sl_price': sl_price,
                        'tp1_price': tp1_price,
                        'tp2_price': tp2_price,
                        'tp1_hit': False
                    }
                    
    return pd.DataFrame(all_trades)

for span in [21, 30, 34, 45]:
    for ag in [44.0, 48.0]:
        df = test_config(ema_trend_span=span, min_ag=ag, rvol_req=1.0)
        tot = df['pnl'].sum()
        days = df['date'].nunique()
        wins = df[df['pnl'] > 0]
        wr = len(wins) / len(df) * 100 if len(df) else 0
        print(f"Span: {span:2d} | AG: {ag:4.1f} | Trades: {len(df):3d} ({len(df)/days:4.1f}/day) | WR: {wr:5.1f}% | Tot PnL: ₹{tot:+11,.2f} | Avg Daily: ₹{tot/days:+9,.2f}/day")
