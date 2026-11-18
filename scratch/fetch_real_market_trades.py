import yfinance as yf
import pandas as pd
import datetime

# Define all trades that appeared in the blotter and user's screenshots
trades_list = [
    # Morning batch (09:17 - 09:30)
    {"time": "09:17", "symbol": "ADANIENT", "strike": 2680, "type": "CE", "side": "BUY", "qty": 300, "entry_prem": 58.93, "ticker": "ADANIENT.NS"},
    {"time": "09:23", "symbol": "ONGC", "strike": 225, "type": "PE", "side": "BUY", "qty": 3850, "entry_prem": 4.95, "ticker": "ONGC.NS"},
    {"time": "09:24", "symbol": "HINDALCO", "strike": 930, "type": "CE", "side": "BUY", "qty": 1400, "entry_prem": 20.42, "ticker": "HINDALCO.NS"},
    {"time": "09:24", "symbol": "VEDL", "strike": 255, "type": "CE", "side": "BUY", "qty": 1150, "entry_prem": 5.59, "ticker": "VEDL.NS"},
    {"time": "09:25", "symbol": "SBIN", "strike": 1100, "type": "CE", "side": "BUY", "qty": 750, "entry_prem": 24.16, "ticker": "SBIN.NS"},
    {"time": "09:26", "symbol": "NTPC", "strike": 320, "type": "PE", "side": "BUY", "qty": 1500, "entry_prem": 7.05, "ticker": "NTPC.NS"},
    {"time": "09:27", "symbol": "DIVISLAB", "strike": 11100, "type": "CE", "side": "BUY", "qty": 100, "entry_prem": 244.66, "ticker": "DIVISLAB.NS"},
    {"time": "09:30", "symbol": "NIFTY", "strike": 25300, "type": "CE", "side": "BUY", "qty": 75, "entry_prem": 180.00, "ticker": "^NSEI"},
    {"time": "09:30", "symbol": "BANKNIFTY", "strike": 61700, "type": "CE", "side": "BUY", "qty": 30, "entry_prem": 380.00, "ticker": "^NSEBANK"},
    {"time": "09:30", "symbol": "AXISBANK", "strike": 1360, "type": "CE", "side": "BUY", "qty": 625, "entry_prem": 29.79, "ticker": "AXISBANK.NS"},

    # 09:40 - 09:45 Scalps
    {"time": "09:40", "symbol": "HDFCBANK", "strike": 810, "type": "CE", "side": "BUY", "qty": 550, "entry_prem": 17.86, "exit_prem": 18.16, "ticker": "HDFCBANK.NS"},
    {"time": "09:41", "symbol": "LT", "strike": 4150, "type": "PE", "side": "BUY", "qty": 150, "entry_prem": 91.30, "exit_prem": 93.33, "ticker": "LT.NS"},
    {"time": "09:43", "symbol": "AXISBANK", "strike": 1350, "type": "PE", "side": "BUY", "qty": 625, "entry_prem": 29.74, "exit_prem": 28.86, "ticker": "AXISBANK.NS"},

    # 10:03 - 11:30 Re-entries & Index Rolls
    {"time": "10:03", "symbol": "NIFTY", "strike": 25350, "type": "CE", "side": "BUY", "qty": 75, "entry_prem": 180.00, "ticker": "^NSEI"},
    {"time": "10:03", "symbol": "BANKNIFTY", "strike": 62100, "type": "CE", "side": "BUY", "qty": 30, "entry_prem": 380.00, "ticker": "^NSEBANK"},
    {"time": "10:03", "symbol": "HCLTECH", "strike": 1380, "type": "PE", "side": "BUY", "qty": 350, "entry_prem": 30.22, "ticker": "HCLTECH.NS"},
    {"time": "10:56", "symbol": "ICICIBANK", "strike": 1600, "type": "PE", "side": "BUY", "qty": 700, "entry_prem": 35.41, "ticker": "ICICIBANK.NS"},
    {"time": "11:04", "symbol": "JINDALSTEL", "strike": 1130, "type": "PE", "side": "BUY", "qty": 625, "entry_prem": 25.00, "ticker": "JINDALSTEL.NS"},
    {"time": "11:09", "symbol": "JINDALSTEL", "strike": 1140, "type": "CE", "side": "BUY", "qty": 625, "entry_prem": 25.00, "ticker": "JINDALSTEL.NS"},
    {"time": "11:17", "symbol": "TATASTEEL", "strike": 182, "type": "PE", "side": "BUY", "qty": 5500, "entry_prem": 4.00, "ticker": "TATASTEEL.NS"},
    {"time": "11:22", "symbol": "JSWSTEEL", "strike": 1330, "type": "PE", "side": "BUY", "qty": 675, "entry_prem": 29.33, "ticker": "JSWSTEEL.NS"},
    {"time": "11:25", "symbol": "DIVISLAB", "strike": 11050, "type": "PE", "side": "BUY", "qty": 100, "entry_prem": 243.63, "ticker": "DIVISLAB.NS"},
    {"time": "11:26", "symbol": "TATASTEEL", "strike": 183, "type": "CE", "side": "BUY", "qty": 5500, "entry_prem": 4.02, "ticker": "TATASTEEL.NS"},
]

print(f"Total historical trades to analyze against real market: {len(trades_list)}")
tickers = list(set([t["ticker"] for t in trades_list]))
print(f"Tickers: {tickers}")

# Download today's 5m intraday data
data = yf.download(tickers=tickers, period="1d", interval="5m", progress=False)
print("Data downloaded successfully! Columns shape:", data.shape)
if not data.empty:
    print("Available timestamps:", [str(ts.strftime('%H:%M')) for ts in data.index[:5]], "to", [str(ts.strftime('%H:%M')) for ts in data.index[-3:]])
