import json
import re

with open("scratch/legitimate_buys_0915_1515.json") as f:
    buys = json.load(f)

print(f"Total buys between 09:15 and 15:15: {len(buys)}")

# Notice that when a daemon restarted or when an order was rejected/cut, the engine re-bought.
# Let's see: which stocks were bought, at what time, and what was the underlying?

stock_map = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "ADANIENT": "ADANIENT.NS",
    "ADANIPORTS": "ADANIPORTS.NS",
    "APOLLOHOSP": "APOLLOHOSP.NS",
    "AXISBANK": "AXISBANK.NS",
    "BAJAJFINSV": "BAJAJFINSV.NS",
    "BAJFINANCE": "BAJFINANCE.NS",
    "BHARTIARTL": "BHARTIARTL.NS",
    "BPCL": "BPCL.NS",
    "CIPLA": "CIPLA.NS",
    "COALINDIA": "COALINDIA.NS",
    "DIVISLAB": "DIVISLAB.NS",
    "DRREDDY": "DRREDDY.NS",
    "HCLTECH": "HCLTECH.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "HINDALCO": "HINDALCO.NS",
    "HINDUNILVR": "HINDUNILVR.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "INFY": "INFY.NS",
    "IOC": "IOC.NS",
    "ITC": "ITC.NS",
    "JINDALSTEL": "JINDALSTEL.NS",
    "JSWSTEEL": "JSWSTEEL.NS",
    "KOTAKBANK": "KOTAKBANK.NS",
    "LT": "LT.NS",
    "MARUTI": "MARUTI.NS",
    "NTPC": "NTPC.NS",
    "ONGC": "ONGC.NS",
    "POWERGRID": "POWERGRID.NS",
    "RELIANCE": "RELIANCE.NS",
    "SBIN": "SBIN.NS",
    "SUNPHARMA": "SUNPHARMA.NS",
    "TATASTEEL": "TATASTEEL.NS",
    "TCS": "TCS.NS",
    "TECHM": "TECHM.NS",
    "VEDL": "VEDL.NS",
    "WIPRO": "WIPRO.NS",
}

parsed_signals = []
for b in buys:
    sym = b["symbol"].replace(".NS", "").replace("_MIS", "")
    # Parse symbol into stock, strike, type
    # e.g., SUNPHARMA26NOV1880CE or NIFTY_25300_CE or SBIN 1100 CE or ADANIENT26NOV2680CE
    m = re.match(r"([A-Z]+)(?:26NOV|_|\s+)(\d+)(?:_|\s+)?(CE|PE)", sym)
    if not m:
        # try without strike
        m2 = re.match(r"([A-Z]+)", sym)
        stock = m2.group(1) if m2 else sym
        strike = 0
        opt_type = "CE" if "CE" in sym else "PE"
    else:
        stock = m.group(1)
        strike = int(m.group(2))
        opt_type = m.group(3)
        
    ticker = stock_map.get(stock)
    parsed_signals.append({
        "time": b["time"],
        "raw_symbol": sym,
        "stock": stock,
        "strike": strike,
        "opt_type": opt_type,
        "qty": b["qty"],
        "price": b["price"],
        "seat": b["seat"],
        "ticker": ticker,
        "log_file": b["log_file"]
    })

print(f"Parsed {len(parsed_signals)} signals.")

# Let's count unique underlying stocks traded
unique_stocks = sorted(list(set([p["stock"] for p in parsed_signals if p["ticker"]])))
print(f"Unique underlying symbols ({len(unique_stocks)}): {', '.join(unique_stocks)}")
