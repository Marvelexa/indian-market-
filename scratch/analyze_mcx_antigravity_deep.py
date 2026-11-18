import json
import urllib.request
import pandas as pd
import numpy as np

# Fetch the real 5m candles
res = urllib.request.urlopen('http://127.0.0.1:8000/api/mcx/candles-batch?timeframe=5D')
raw = json.loads(res.read().decode())

print("Loaded candle batches:")
for k, v in raw.items():
    print(f"  {k}: {len(v)} candles")

# Let's see what happens to the Anti-Gravity engine when we test per-commodity
# with quality filtering vs unconstrained
