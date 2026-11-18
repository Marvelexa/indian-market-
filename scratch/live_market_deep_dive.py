import yfinance as yf
import pandas as pd
import numpy as np

symbols = [
    '^NSEI', '^NSEBANK', '^INDIAVIX',
    'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'ICICIBANK.NS',
    'INFY.NS', 'BHARTIARTL.NS', 'SBIN.NS', 'LT.NS',
    'BAJFINANCE.NS', 'MARUTI.NS', 'AXISBANK.NS', 'TITAN.NS', 'TATASTEEL.NS'
]

print("Downloading live 5m data for today...")
df = yf.download(symbols, period='1d', interval='5m', progress=False)

print("\n" + "="*80)
print(f"NEXUS BHARAT LIVE MARKET INTELLIGENCE — 16 NOV 2026 (10:23 AM IST)")
print("="*80)

# Extract close, open, high, low, volume
closes = df['Close']
highs = df['High']
lows = df['Low']
opens = df['Open']
vols = df['Volume']

summary_rows = []

for sym in symbols:
    if sym not in closes.columns:
        continue
    c = closes[sym].dropna()
    h = highs[sym].dropna()
    l = lows[sym].dropna()
    o = opens[sym].dropna()
    v = vols[sym].dropna()
    
    if len(c) == 0:
        continue
        
    ltp = c.iloc[-1]
    day_open = o.iloc[0]
    day_high = h.max()
    day_low = l.min()
    chg_from_open = ((ltp - day_open) / day_open) * 100
    
    # Calculate EMA9 and EMA21
    ema9 = c.ewm(span=9, adjust=False).mean().iloc[-1]
    ema21 = c.ewm(span=21, adjust=False).mean().iloc[-1]
    
    # VWAP
    cum_vol = v.cumsum()
    cum_pv = ((h + l + c) / 3 * v).cumsum()
    vwap = (cum_pv / cum_vol).iloc[-1] if cum_vol.iloc[-1] > 0 else ltp
    
    trend = "🟢 BULL" if ltp > ema9 > ema21 else ("🔴 BEAR" if ltp < ema9 < ema21 else "🟡 CHOP")
    
    summary_rows.append({
        'Symbol': sym.replace('.NS', '').replace('^', ''),
        'LTP': round(ltp, 2),
        'Open': round(day_open, 2),
        'High': round(day_high, 2),
        'Low': round(day_low, 2),
        'Chg_Open%': round(chg_from_open, 2),
        'EMA9': round(ema9, 2),
        'EMA21': round(ema21, 2),
        'VWAP': round(vwap, 2),
        'Trend': trend
    })

sum_df = pd.DataFrame(summary_rows)
print(sum_df.to_string(index=False))

# Breadth calculation on equities
equities = sum_df[~sum_df['Symbol'].isin(['NSEI', 'NSEBANK', 'INDIAVIX'])]
green_stocks = equities[equities['Chg_Open%'] > 0]
red_stocks = equities[equities['Chg_Open%'] < 0]
breadth_pct = (len(green_stocks) / len(equities)) * 100

print("\n" + "-"*80)
print(f"EQUITY BREADTH (vs Day Open): {breadth_pct:.1f}% Bullish ({len(green_stocks)} Green / {len(red_stocks)} Red)")
if breadth_pct >= 65:
    print("🚨 INSTITUTIONAL RULE: Breadth >= 65% -> INDEX CALLS (CE) & MOMENTUM LONGS UNLOCKED!")
elif breadth_pct <= 35:
    print("🚨 INSTITUTIONAL RULE: Breadth <= 35% -> INDEX PUTS (PE) & SHORT RUNNERS UNLOCKED!")
else:
    print("⚠️ INSTITUTIONAL RULE: Breadth in 35-65% Neutral Zone -> CHOPPING PING-PONG / BOX REVERSALS ONLY!")
print("-"*80)
