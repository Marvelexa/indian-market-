import os
import sys
sys.path.insert(0, os.path.abspath("."))
import yfinance as yf
import pandas as pd
import numpy as np

WHITELIST_14_SYMBOLS = [
    "^NSEI", "^NSEBANK", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "SBIN.NS", "INFY.NS", "TCS.NS", "TATAMOTORS.NS", "AXISBANK.NS",
    "LT.NS", "BAJFINANCE.NS"
]

print("Downloading live 5m candles for 14 whitelist symbols...")
df = yf.download(WHITELIST_14_SYMBOLS, period='1d', interval='5m', progress=False)

closes = df['Close']
highs = df['High']
lows = df['Low']
opens = df['Open']
vols = df['Volume']

bull_count = 0
bear_count = 0
neutral_count = 0
total_syms = 0

print("\n" + "="*80)
print("AUDITED UNIFIED BREAKTHROUGH ENGINE — LIVE MARKET CHECK (10:40 AM IST)")
print("="*80)

metrics = []

for sym in WHITELIST_14_SYMBOLS:
    if sym not in closes.columns:
        continue
    c = closes[sym].dropna()
    h = highs[sym].dropna()
    l = lows[sym].dropna()
    o = opens[sym].dropna()
    v = vols[sym].dropna()
    
    if len(c) < 5:
        continue
        
    close_p = float(c.iloc[-1])
    open_p = float(o.iloc[-1])
    high_p = float(h.iloc[-1])
    low_p = float(l.iloc[-1])
    
    # Intraday VWAP
    cum_vol = v.cumsum()
    cum_pv = ((h + l + c) / 3.0 * v).cumsum()
    vwap = float(cum_pv.iloc[-1] / cum_vol.iloc[-1]) if cum_vol.iloc[-1] > 0 else close_p
    
    # EMA9 and EMA21
    ema9 = float(c.ewm(span=9, adjust=False).mean().iloc[-1])
    ema21 = float(c.ewm(span=21, adjust=False).mean().iloc[-1])
    
    clean_sym = sym.replace('.NS', '').replace('^', '')
    
    is_bull = close_p > vwap and ema9 >= ema21
    is_bear = close_p < vwap and ema9 <= ema21
    
    if is_bull:
        bull_count += 1
        status = "🟢 BULL"
    elif is_bear:
        bear_count += 1
        status = "🔴 BEAR"
    else:
        neutral_count += 1
        status = "🟡 CHOP"
        
    total_syms += 1
    metrics.append({
        'Symbol': clean_sym,
        'Close': round(close_p, 2),
        'VWAP': round(vwap, 2),
        'EMA9': round(ema9, 2),
        'EMA21': round(ema21, 2),
        'Status': status
    })

m_df = pd.DataFrame(metrics)
print(m_df.to_string(index=False))

breadth_ratio = (max(bull_count, bear_count) / max(1, total_syms)) * 100.0
is_trend_confirmed = breadth_ratio >= 65.0

print("\n" + "-"*80)
print(f"MARKET BREADTH: {breadth_ratio:.1f}% ({bull_count} Bullish, {bear_count} Bearish, {neutral_count} Neutral)")
print(f"RULE 1: Market Breadth >= 65.0% Confirmation: {'✅ PASSED (TREND MODE)' if is_trend_confirmed else '❌ FAILED (CHOP ZONE - NO TRADES)'}")

# IMIC Check
nifty_bull = any(m['Symbol'] == 'NSEI' and 'BULL' in m['Status'] for m in metrics)
bnifty_bull = any(m['Symbol'] == 'NSEBANK' and 'BULL' in m['Status'] for m in metrics)
imic_confirmed = nifty_bull and bnifty_bull

print(f"RULE 2: IMIC Confluence (Nifty + BankNifty Bullish): {'✅ PASSED' if imic_confirmed else '❌ FAILED (Divergence / Not in Sync)'}")
print("-"*80)
