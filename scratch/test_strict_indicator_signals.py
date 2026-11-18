import os
import sys
sys.path.insert(0, os.path.abspath("."))
import yfinance as yf
import pandas as pd
from backend.sniper_engine import indian_sniper_engine

watchlist = [
    ('^NSEI', True, 0.05),
    ('^NSEBANK', True, 0.05),
    ('RELIANCE.NS', False, 0.05),
    ('TCS.NS', False, 0.05),
    ('HDFCBANK.NS', False, 0.05),
    ('ICICIBANK.NS', False, 0.05),
    ('INFY.NS', False, 0.05),
    ('BHARTIARTL.NS', False, 0.05),
    ('SBIN.NS', False, 0.05),
    ('LT.NS', False, 0.05),
    ('BAJFINANCE.NS', False, 0.05),
    ('MARUTI.NS', False, 0.05),
    ('AXISBANK.NS', False, 0.05),
    ('TITAN.NS', False, 0.05),
    ('TATASTEEL.NS', False, 0.05)
]

symbols = [w[0] for w in watchlist]
print("Fetching 5m candles...")
df = yf.download(symbols, period='5d', interval='5m', progress=False)

print("\n" + "="*85)
print("EVALUATING 5-LAYER INSTITUTIONAL CONFLUENCE ENGINE ON LIVE DATA")
print("="*85)

for sym, is_idx, tick_sz in watchlist:
    try:
        sub_df = pd.DataFrame({
            'Open': df['Open'][sym].dropna(),
            'High': df['High'][sym].dropna(),
            'Low': df['Low'][sym].dropna(),
            'Close': df['Close'][sym].dropna(),
            'Volume': df['Volume'][sym].dropna() if sym in df['Volume'].columns else pd.Series([1.0]*len(df['Close'][sym].dropna()))
        }).dropna()

        if len(sub_df) < 30:
            continue

        sig = indian_sniper_engine.evaluate_symbol(
            symbol=sym,
            df=sub_df,
            is_index=is_idx,
            tick_size=tick_sz,
            bypass_session_check=True
        )

        clean_sym = sym.replace('.NS', '').replace('^', '')
        approved_icon = "✅ APPROVED" if sig.get('approved') else "❌ VETOED"
        print(f"{clean_sym:<12}: Score {sig.get('confluence_score', 0):>3}/100 | {approved_icon} | Action: {sig.get('action', 'WAIT'):<4} | Setup: {sig.get('setup_name', 'NONE')[:30]} | Veto: {sig.get('veto_reason')}")

    except Exception as e:
        print(f"Error evaluating {sym}: {e}")
