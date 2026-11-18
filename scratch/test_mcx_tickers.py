import yfinance as yf

candidates = [
    'CRUDEOIL.MCX', 'CRUDEOIL-I.MCX', 'NATURALGAS.MCX', 'GOLD.MCX', 'SILVER.MCX', 'COPPER.MCX',
    'CL=F', 'NG=F', 'GC=F', 'SI=F', 'HG=F'
]

for c in candidates:
    try:
        t = yf.Ticker(c)
        df = t.history(period='2d', interval='5m')
        if not df.empty:
            print(f"{c:<15}: {len(df)} candles | Last Close: {df['Close'].iloc[-1]:.2f}")
        else:
            print(f"{c:<15}: EMPTY")
    except Exception as e:
        print(f"{c:<15}: ERROR ({e})")
