import json
import glob
import pandas as pd
import numpy as np

# Load real candles
data = {}
for path in glob.glob("scratch/mcx_real_data/*.json"):
    sym = path.split("\\")[-1].replace(".json", "").replace("/", "")
    with open(path) as f:
        candles = json.load(f)
    data[sym] = candles
    print(f"Loaded {sym}: {len(candles)} candles")

# Let's inspect typical ATR and price levels
for sym, candles in data.items():
    df = pd.DataFrame(candles)
    df["dt"] = pd.to_datetime(df["timestamp"], unit="ms")
    df["tr"] = np.maximum(df["high"] - df["low"], 
                          np.maximum(abs(df["high"] - df["close"].shift(1)), 
                                     abs(df["low"] - df["close"].shift(1))))
    df["atr14"] = df["tr"].rolling(14).mean()
    last_c = df.iloc[-1]
    print(f"{sym:<12} | Last Price: ₹{last_c['close']:>9.2f} | 5m ATR-14: {last_c['atr14']:>6.2f} pts ({last_c['atr14']/last_c['close']*100:.2f}%)")
