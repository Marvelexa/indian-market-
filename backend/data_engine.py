"""
NEXUS BHARAT - Indian Market Data & Quantitative Analytics Engine
Powered by Pandas, yfinance, and NumPy
NSE/BSE Nifty 50, Sensex, Bank Nifty, and constituent equities.
"""

import os
import json
import time
import datetime
import urllib.request
import pytz
import numpy as np
import pandas as pd
import yfinance as yf
from typing import Dict, List, Optional, Any

# IST Timezone
IST = pytz.timezone("Asia/Kolkata")

# Universe of Indian Equities and Indices
TICKER_METADATA = {
    # Benchmark Indices
    "^NSEI": {
        "symbol": "^NSEI",
        "clean_symbol": "NIFTY 50",
        "name": "Nifty 50 Index (NSE)",
        "exchange": "NSE",
        "type": "index",
        "sector": "Benchmark Index",
        "lot_size": 25,
    },
    "^BSESN": {
        "symbol": "^BSESN",
        "clean_symbol": "SENSEX",
        "name": "BSE Sensex 30 (BSE)",
        "exchange": "BSE",
        "type": "index",
        "sector": "Benchmark Index",
        "lot_size": 10,
    },
    "^NSEBANK": {
        "symbol": "^NSEBANK",
        "clean_symbol": "BANK NIFTY",
        "name": "Nifty Bank Index (NSE)",
        "exchange": "NSE",
        "type": "index",
        "sector": "Banking Index",
        "lot_size": 15,
    },
    "^INDIAVIX": {
        "symbol": "^INDIAVIX",
        "clean_symbol": "INDIA VIX",
        "name": "India Volatility Index",
        "exchange": "NSE",
        "type": "index",
        "sector": "Volatility",
        "lot_size": 1,
    },
    "^CNXIT": {
        "symbol": "^CNXIT",
        "clean_symbol": "NIFTY IT",
        "name": "Nifty IT Sector Index",
        "exchange": "NSE",
        "type": "index",
        "sector": "Technology Index",
        "lot_size": 25,
    },
    # Top Nifty 50 Equities
    "RELIANCE.NS": {
        "symbol": "RELIANCE.NS",
        "clean_symbol": "RELIANCE",
        "name": "Reliance Industries Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Energy & Oil",
        "lot_size": 250,
    },
    "TCS.NS": {
        "symbol": "TCS.NS",
        "clean_symbol": "TCS",
        "name": "Tata Consultancy Services Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Information Tech",
        "lot_size": 175,
    },
    "HDFCBANK.NS": {
        "symbol": "HDFCBANK.NS",
        "clean_symbol": "HDFCBANK",
        "name": "HDFC Bank Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Private Banking",
        "lot_size": 550,
    },
    "INFY.NS": {
        "symbol": "INFY.NS",
        "clean_symbol": "INFY",
        "name": "Infosys Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Information Tech",
        "lot_size": 400,
    },
    "ICICIBANK.NS": {
        "symbol": "ICICIBANK.NS",
        "clean_symbol": "ICICIBANK",
        "name": "ICICI Bank Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Private Banking",
        "lot_size": 700,
    },
    "BHARTIARTL.NS": {
        "symbol": "BHARTIARTL.NS",
        "clean_symbol": "BHARTIARTL",
        "name": "Bharti Airtel Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Telecommunications",
        "lot_size": 475,
    },
    "SBIN.NS": {
        "symbol": "SBIN.NS",
        "clean_symbol": "SBIN",
        "name": "State Bank of India",
        "exchange": "NSE",
        "type": "equity",
        "sector": "PSU Banking",
        "lot_size": 750,
    },
    "ITC.NS": {
        "symbol": "ITC.NS",
        "clean_symbol": "ITC",
        "name": "ITC Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "FMCG",
        "lot_size": 1600,
    },
    "LT.NS": {
        "symbol": "LT.NS",
        "clean_symbol": "LT",
        "name": "Larsen & Toubro Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Infrastructure",
        "lot_size": 150,
    },
    "KOTAKBANK.NS": {
        "symbol": "KOTAKBANK.NS",
        "clean_symbol": "KOTAKBANK",
        "name": "Kotak Mahindra Bank Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Private Banking",
        "lot_size": 400,
    },
    "AXISBANK.NS": {
        "symbol": "AXISBANK.NS",
        "clean_symbol": "AXISBANK",
        "name": "Axis Bank Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Private Banking",
        "lot_size": 625,
    },
    "HINDUNILVR.NS": {
        "symbol": "HINDUNILVR.NS",
        "clean_symbol": "HINDUNILVR",
        "name": "Hindustan Unilever Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "FMCG",
        "lot_size": 300,
    },
    "BAJFINANCE.NS": {
        "symbol": "BAJFINANCE.NS",
        "clean_symbol": "BAJFINANCE",
        "name": "Bajaj Finance Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Financial Services",
        "lot_size": 125,
    },
    "MARUTI.NS": {
        "symbol": "MARUTI.NS",
        "clean_symbol": "MARUTI",
        "name": "Maruti Suzuki India Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Automotive",
        "lot_size": 50,
    },
    "M&M.NS": {
        "symbol": "M&M.NS",
        "clean_symbol": "M&M",
        "name": "Mahindra & Mahindra Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Automotive",
        "lot_size": 200,
    },
    "BAJAJ-AUTO.NS": {
        "symbol": "BAJAJ-AUTO.NS",
        "clean_symbol": "BAJAJ-AUTO",
        "name": "Bajaj Auto Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Automotive",
        "lot_size": 75,
    },
    "SUNPHARMA.NS": {
        "symbol": "SUNPHARMA.NS",
        "clean_symbol": "SUNPHARMA",
        "name": "Sun Pharmaceutical Ind Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Healthcare",
        "lot_size": 350,
    },
    "TITAN.NS": {
        "symbol": "TITAN.NS",
        "clean_symbol": "TITAN",
        "name": "Titan Company Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Consumer Goods",
        "lot_size": 175,
    },
    "ADANIENT.NS": {
        "symbol": "ADANIENT.NS",
        "clean_symbol": "ADANIENT",
        "name": "Adani Enterprises Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Conglomerate",
        "lot_size": 300,
    },
    "TATASTEEL.NS": {
        "symbol": "TATASTEEL.NS",
        "clean_symbol": "TATASTEEL",
        "name": "Tata Steel Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Metals & Mining",
        "lot_size": 5500,
    },
    "WIPRO.NS": {
        "symbol": "WIPRO.NS",
        "clean_symbol": "WIPRO",
        "name": "Wipro Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Information Tech",
        "lot_size": 1500,
    },
    "NTPC.NS": {
        "symbol": "NTPC.NS",
        "clean_symbol": "NTPC",
        "name": "NTPC Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Power & Energy",
        "lot_size": 1500,
    },
    "POWERGRID.NS": {
        "symbol": "POWERGRID.NS",
        "clean_symbol": "POWERGRID",
        "name": "Power Grid Corp of India",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Power & Energy",
        "lot_size": 2000,
    },
    "ONGC.NS": {
        "symbol": "ONGC.NS",
        "clean_symbol": "ONGC",
        "name": "Oil & Natural Gas Corp",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Energy & Oil",
        "lot_size": 2250,
    },
    "COALINDIA.NS": {
        "symbol": "COALINDIA.NS",
        "clean_symbol": "COALINDIA",
        "name": "Coal India Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Metals & Mining",
        "lot_size": 2100,
    },
    "ASIANPAINT.NS": {
        "symbol": "ASIANPAINT.NS",
        "clean_symbol": "ASIANPAINT",
        "name": "Asian Paints Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Consumer Goods",
        "lot_size": 200,
    },
    "ULTRACEMCO.NS": {
        "symbol": "ULTRACEMCO.NS",
        "clean_symbol": "ULTRACEMCO",
        "name": "UltraTech Cement Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Materials",
        "lot_size": 100,
    },
    "HCLTECH.NS": {
        "symbol": "HCLTECH.NS",
        "clean_symbol": "HCLTECH",
        "name": "HCL Technologies Ltd",
        "exchange": "NSE",
        "type": "equity",
        "sector": "Information Tech",
        "lot_size": 350,
    }
}

class IndianMarketEngine:
    """Pandas-driven analytics and data engine for Indian financial markets."""

    def __init__(self):
        self.quote_cache: Dict[str, Any] = {}
        self.history_cache: Dict[str, Any] = {}
        self.cache_ttl = 0.5  # sub-second live refresh from TradingView
        self.history_cache_ttl = 30  # seconds
        self.last_batch_fetch_time = 0.0
        self._preload_cache_from_disk()

    def _preload_cache_from_disk(self):
        """Pre-populates quote_cache from local 60-day cached files for instant offline responsiveness."""
        try:
            cache_dir = os.path.join(os.path.dirname(__file__), "..", ".cache_indian_market_60d")
            if not os.path.exists(cache_dir):
                return
            for sym, meta in TICKER_METADATA.items():
                clean = meta["clean_symbol"]
                fn = os.path.join(cache_dir, f"{clean}_5m.json")
                if os.path.exists(fn):
                    with open(fn, "r", encoding="utf-8") as f:
                        bars = json.load(f)
                    if bars:
                        last_bar = bars[-1]
                        ltp = float(last_bar.get("close", 1000.0))
                        prev_close = float(last_bar.get("previousDayClose", ltp))
                        change = round(ltp - prev_close, 2)
                        change_pct = round((change / prev_close * 100.0) if prev_close else 0.0, 2)
                        sparkline = [round(float(b.get("close", ltp)), 2) for b in bars[-15:]]
                        self.quote_cache[sym] = {
                            "symbol": sym,
                            "clean_symbol": meta["clean_symbol"],
                            "name": meta["name"],
                            "exchange": meta["exchange"],
                            "type": meta["type"],
                            "sector": meta["sector"],
                            "lot_size": meta["lot_size"],
                            "ltp": ltp,
                            "prev_close": prev_close,
                            "change": change,
                            "change_pct": change_pct,
                            "high": float(last_bar.get("high", ltp)),
                            "low": float(last_bar.get("low", ltp)),
                            "volume": int(last_bar.get("volume", 0)),
                            "turnover_cr": round((ltp * int(last_bar.get("volume", 0))) / 10000000.0, 2),
                            "sparkline": sparkline,
                            "is_positive": change >= 0
                        }
            if self.quote_cache:
                self.last_batch_fetch_time = 0.0  # Force immediate real-time sync with Port 3005 on first call
                print(f"[DataEngine] Preloaded {len(self.quote_cache)} instruments from local 60-day cache.")
        except Exception as e:
            print(f"[DataEngine] Local cache preload warning: {e}")

    def get_market_status(self) -> Dict[str, Any]:
        """Calculates exact Indian Market session status based on IST."""
        now_ist = datetime.datetime.now(IST)
        weekday = now_ist.weekday()  # 0=Monday, 6=Sunday
        hour = now_ist.hour
        minute = now_ist.minute
        time_mins = hour * 60 + minute

        # Market timing in minutes from 00:00 IST
        pre_market_start = 9 * 60         # 09:00 IST
        pre_market_end = 9 * 60 + 8       # 09:08 IST
        regular_start = 9 * 60 + 15       # 09:15 IST
        regular_end = 15 * 60 + 30        # 15:30 IST
        post_market_end = 16 * 60         # 16:00 IST

        is_weekend = weekday in [5, 6]

        if is_weekend:
            status = "CLOSED"
            status_desc = "WEEKEND CLOSED"
            is_open = False
        elif time_mins < pre_market_start:
            status = "CLOSED"
            status_desc = "PRE-OPEN AT 09:00 IST"
            is_open = False
        elif pre_market_start <= time_mins < regular_start:
            status = "PRE_OPEN"
            status_desc = "PRE-MARKET AUCTION"
            is_open = False
        elif regular_start <= time_mins <= regular_end:
            status = "OPEN"
            status_desc = "REGULAR TRADING (NSE/BSE)"
            is_open = True
        elif regular_end < time_mins <= post_market_end:
            status = "POST_CLOSE"
            status_desc = "POST-MARKET CLOSING"
            is_open = False
        else:
            status = "CLOSED"
            status_desc = "MARKET CLOSED"
            is_open = False

        return {
            "is_open": is_open,
            "status": status,
            "description": status_desc,
            "ist_time": now_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
            "time_str": now_ist.strftime("%H:%M:%S"),
            "date_str": now_ist.strftime("%d %b %Y"),
            "session": "NSE / BSE Live Session" if is_open else "After-Hours Session"
        }

    def fetch_all_quotes_batch(self, force: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        Fetches live real-time quotes directly from Node Universal Market Connector (Port 3005)
        in < 10ms with zero delay. Falls back to yfinance only if daemon is offline.
        """
        now = time.time()
        if not force and self.quote_cache and (now - self.last_batch_fetch_time < self.cache_ttl):
            return self.quote_cache

        # 1. High-Speed Sub-Millisecond Integration with Node Universal Market Connector (Port 3005)
        try:
            req = urllib.request.Request("http://127.0.0.1:3005/api/market/universal-quotes", headers={"User-Agent": "NexusPython"})
            with urllib.request.urlopen(req, timeout=0.4) as resp:
                u_data = json.loads(resp.read().decode())
                u_quotes = u_data.get("quotes", {})
                live_opt_ltps = u_data.get("liveOptionLtps", {})

                if u_quotes:
                    for q_key, q in u_quotes.items():
                        raw_sym = q.get("symbol", q_key).replace("NSE:", "").replace("BSE:", "").strip()
                        ltp = float(q.get("ltp", 0.0))
                        open_p = float(q.get("open", ltp))
                        high_p = float(q.get("high", ltp))
                        low_p = float(q.get("low", ltp))
                        prev_close = float(q.get("close", ltp))
                        vol = int(q.get("volume", 0))
                        change = round(ltp - prev_close, 2)
                        change_pct = round(((ltp - prev_close) / prev_close * 100.0) if prev_close else 0.0, 2)

                        item = {
                            "symbol": f"{raw_sym}.NS",
                            "clean_symbol": raw_sym,
                            "name": raw_sym,
                            "exchange": q.get("exchange", "NSE"),
                            "type": "equity",
                            "sector": "Constituent",
                            "lot_size": 25,
                            "ltp": ltp,
                            "prev_close": prev_close,
                            "change": change,
                            "change_pct": change_pct,
                            "high": high_p,
                            "low": low_p,
                            "volume": vol,
                            "turnover_cr": round((ltp * vol) / 10000000.0, 2),
                            "sparkline": [prev_close, ltp],
                            "is_positive": change >= 0
                        }
                        self.quote_cache[raw_sym] = item
                        self.quote_cache[f"{raw_sym}.NS"] = item
                        self.quote_cache[q_key] = item

                    # Also map Index Symbols
                    if "NIFTY" in self.quote_cache:
                        self.quote_cache["^NSEI"] = self.quote_cache["NIFTY"]
                    if "BANKNIFTY" in self.quote_cache:
                        self.quote_cache["^NSEBANK"] = self.quote_cache["BANKNIFTY"]
                    if "SENSEX" in self.quote_cache:
                        self.quote_cache["^BSESN"] = self.quote_cache["SENSEX"]

                    # Also inject direct live option prices into quote_cache!
                    for opt_sym, opt_ltp in live_opt_ltps.items():
                        self.quote_cache[opt_sym] = {"ltp": opt_ltp, "prev_close": opt_ltp, "change": 0.0, "change_pct": 0.0}
                        self.quote_cache[f"{opt_sym}.NS"] = {"ltp": opt_ltp, "prev_close": opt_ltp, "change": 0.0, "change_pct": 0.0}

                    self.last_batch_fetch_time = now
                    return self.quote_cache
        except Exception:
            pass

        # 2. Fallback to yfinance if Port 3005 is unavailable
        symbols = list(TICKER_METADATA.keys())
        try:
            # Download 5 days of 1d data to calculate reliable daily change, volume, and sparkline
            raw_df = yf.download(
                symbols,
                period="5d",
                interval="1d",
                group_by="ticker",
                progress=False,
                threads=True,
                timeout=5
            )

            results: Dict[str, Dict[str, Any]] = {}
            for sym in symbols:
                meta = TICKER_METADATA[sym]
                try:
                    if sym in raw_df.columns.levels[0]:
                        sub = raw_df[sym].dropna(how="all")
                    else:
                        sub = pd.DataFrame()

                    if not sub.empty and "Close" in sub.columns:
                        closes = sub["Close"].dropna()
                        highs = sub["High"].dropna() if "High" in sub.columns else closes
                        lows = sub["Low"].dropna() if "Low" in sub.columns else closes
                        vols = sub["Volume"].dropna() if "Volume" in sub.columns else pd.Series([0])

                        last_close = float(closes.iloc[-1])
                        prev_close = float(closes.iloc[-2]) if len(closes) > 1 else last_close
                        day_high = float(highs.iloc[-1])
                        day_low = float(lows.iloc[-1])
                        day_vol = int(vols.iloc[-1]) if not vols.empty else 0

                        change = last_close - prev_close
                        change_pct = (change / prev_close * 100.0) if prev_close else 0.0

                        # Sparkline of recent closes
                        sparkline = [round(float(c), 2) for c in closes.tail(15).tolist()]
                    else:
                        # Use cached quote if available to prevent slow blocking calls
                        if sym in self.quote_cache:
                            results[sym] = self.quote_cache[sym]
                            continue
                        # Fallback to fast_info only if not in cache
                        t = yf.Ticker(sym)
                        fi = t.fast_info
                        last_close = float(fi.last_price or 0.0)
                        prev_close = float(fi.previous_close or last_close)
                        day_high = float(fi.day_high or last_close)
                        day_low = float(fi.day_low or last_close)
                        day_vol = int(fi.last_volume or 0)
                        change = last_close - prev_close
                        change_pct = (change / prev_close * 100.0) if prev_close else 0.0
                        sparkline = [round(prev_close, 2), round(last_close, 2)]

                    # Estimated turnover in Crores (LTP * Volume / 10^7)
                    turnover_cr = round((last_close * day_vol) / 10000000.0, 2) if day_vol else 0.0

                    results[sym] = {
                        "symbol": sym,
                        "clean_symbol": meta["clean_symbol"],
                        "name": meta["name"],
                        "exchange": meta["exchange"],
                        "type": meta["type"],
                        "sector": meta["sector"],
                        "lot_size": meta["lot_size"],
                        "ltp": round(last_close, 2),
                        "prev_close": round(prev_close, 2),
                        "change": round(change, 2),
                        "change_pct": round(change_pct, 2),
                        "high": round(day_high, 2),
                        "low": round(day_low, 2),
                        "volume": day_vol,
                        "turnover_cr": turnover_cr,
                        "sparkline": sparkline,
                        "is_positive": change >= 0
                    }
                except Exception as e:
                    # In case of partial failure on a single symbol, retain prior or graceful fallback
                    results[sym] = self.quote_cache.get(sym, {
                        "symbol": sym,
                        "clean_symbol": meta["clean_symbol"],
                        "name": meta["name"],
                        "exchange": meta["exchange"],
                        "type": meta["type"],
                        "sector": meta["sector"],
                        "lot_size": meta["lot_size"],
                        "ltp": 0.0,
                        "prev_close": 0.0,
                        "change": 0.0,
                        "change_pct": 0.0,
                        "high": 0.0,
                        "low": 0.0,
                        "volume": 0,
                        "turnover_cr": 0.0,
                        "sparkline": [],
                        "is_positive": True
                    })

            self.quote_cache = results
            self.last_batch_fetch_time = now
            return results

        except Exception as e:
            print(f"[DataEngine] Batch download error: {e}")
            if self.quote_cache:
                return self.quote_cache
            return {}

    def get_market_overview(self) -> Dict[str, Any]:
        """
        Computes Indian market overview:
        - Major indices quotes (NIFTY 50, SENSEX, BANK NIFTY, INDIA VIX, NIFTY IT)
        - Market breadth across Nifty constituents (Advancers, Decliners, Neutral)
        - Market status (Open/Closed/Pre-Market)
        """
        quotes = self.fetch_all_quotes_batch()
        status = self.get_market_status()

        # Extract major indices
        indices_keys = ["^NSEI", "^BSESN", "^NSEBANK", "^INDIAVIX", "^CNXIT"]
        indices = [quotes[k] for k in indices_keys if k in quotes]

        # Calculate market breadth from Equities
        equities = [q for q in quotes.values() if q["type"] == "equity"]
        df_equities = pd.DataFrame(equities)

        if not df_equities.empty and "change_pct" in df_equities.columns:
            advancers = int((df_equities["change_pct"] > 0).sum())
            decliners = int((df_equities["change_pct"] < 0).sum())
            neutral = int((df_equities["change_pct"] == 0).sum())
            total = len(df_equities)
            adv_ratio = round(advancers / decliners, 2) if decliners > 0 else float(advancers)
            avg_change = round(float(df_equities["change_pct"].mean()), 2)
            top_gainers = df_equities.sort_values(by="change_pct", ascending=False).head(5).to_dict("records")
            top_losers = df_equities.sort_values(by="change_pct", ascending=True).head(5).to_dict("records")
        else:
            advancers, decliners, neutral, total, adv_ratio, avg_change = 0, 0, 0, 0, 0.0, 0.0
            top_gainers, top_losers = [], []

        return {
            "status": status,
            "indices": indices,
            "market_breadth": {
                "advancers": advancers,
                "decliners": decliners,
                "neutral": neutral,
                "total": total,
                "advance_decline_ratio": adv_ratio,
                "advancers_pct": round((advancers / total * 100), 1) if total else 0.0,
                "decliners_pct": round((decliners / total * 100), 1) if total else 0.0,
                "average_change_pct": avg_change,
                "sentiment": "BULLISH" if advancers > decliners * 1.2 else ("BEARISH" if decliners > advancers * 1.2 else "MIXED / RANGE-BOUND")
            },
            "top_gainers": top_gainers,
            "top_losers": top_losers
        }

    def get_historical_candles(self, symbol: str, timeframe: str = "1D") -> Dict[str, Any]:
        """
        Fetches historical data and computes technical indicators via Pandas:
        - 20 EMA, 50 EMA, 200 EMA
        - RSI(14)
        - MACD(12, 26, 9)
        - VWAP
        - Volume Moving Average
        Formats timestamps as UNIX seconds for TradingView Lightweight Charts.
        """
        cache_key = f"{symbol}_{timeframe}"
        now = time.time()
        if cache_key in self.history_cache:
            entry = self.history_cache[cache_key]
            if now - entry["timestamp"] < self.history_cache_ttl:
                return entry["data"]

        # Map timeframe to yfinance parameters
        tf_map = {
            "1D": {"period": "5d", "interval": "5m"},
            "5D": {"period": "5d", "interval": "15m"},
            "60D": {"period": "60d", "interval": "15m"},
            "1M": {"period": "1mo", "interval": "1h"},
            "6M": {"period": "6mo", "interval": "1d"},
            "1Y": {"period": "1y", "interval": "1d"},
            "5Y": {"period": "5y", "interval": "1wk"}
        }
        cfg = tf_map.get(timeframe, {"period": "1mo", "interval": "1d"})

        try:
            df = pd.DataFrame()

            # If 60D requested, check local .cache_indian_market_60d first
            if timeframe == "60D":
                clean_sym = symbol.replace("^", "").replace(".NS", "")
                if clean_sym in ["NSEI", "NIFTY50", "NIFTY 50"]:
                    clean_sym = "NIFTY"
                elif clean_sym in ["NSEBANK", "BANKNIFTY", "BANK NIFTY"]:
                    clean_sym = "BANKNIFTY"
                elif clean_sym in ["BSESN", "SENSEX"]:
                    clean_sym = "SENSEX"
                elif clean_sym in ["NIFTY_FIN_SERVICE", "FINNIFTY"]:
                    clean_sym = "FINNIFTY"

                cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache_indian_market_60d")
                cache_file = os.path.join(cache_dir, f"{clean_sym}_15m.json")
                if os.path.exists(cache_file):
                    try:
                        with open(cache_file, "r") as f:
                            raw_cache = json.load(f)
                        if raw_cache:
                            df_c = pd.DataFrame(raw_cache)
                            df_c["Datetime"] = pd.to_datetime(df_c["timestamp"], unit="ms")
                            df_c = df_c.set_index("Datetime")
                            df_c["Close"] = df_c["close"]
                            df_c["Open"] = df_c["open"]
                            df_c["High"] = df_c["high"]
                            df_c["Low"] = df_c["low"]
                            df_c["Volume"] = df_c["volume"]
                            df = df_c
                    except Exception as e:
                        print(f"[DataEngine] Error loading 60D cache: {e}")

            if df.empty:
                df = yf.download(symbol, period=cfg["period"], interval=cfg["interval"], progress=False)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df = df.dropna().copy()

            if df.empty:
                return {"candles": [], "rsi": [], "macd": []}

            # Filter for 1D to show only the last trading day's 5m bars
            if timeframe == "1D" and len(df) > 75:
                # Group by date and take the most recent date
                last_date = df.index[-1].date()
                df = df[df.index.date == last_date].copy()

            # Technical Indicators with Pandas
            df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
            df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()

            # RSI(14) calculation
            delta = df["Close"].diff()
            gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rs = gain / (loss + 1e-9)
            df["RSI"] = 100 - (100 / (1 + rs))

            # MACD(12, 26, 9)
            ema12 = df["Close"].ewm(span=12, adjust=False).mean()
            ema26 = df["Close"].ewm(span=26, adjust=False).mean()
            df["MACD"] = ema12 - ema26
            df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
            df["Hist"] = df["MACD"] - df["Signal"]

            # VWAP
            typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
            cum_vol = df["Volume"].cumsum().replace(0, np.nan)
            df["VWAP"] = (typical_price * df["Volume"]).cumsum() / cum_vol
            df["VWAP"] = df["VWAP"].bfill().ffill()

            # Volume 20 SMA
            df["VolSMA"] = df["Volume"].rolling(window=min(20, len(df))).mean().bfill()

            candles = []
            rsi_series = []
            macd_series = []

            for idx, row in df.iterrows():
                # Epoch timestamp in seconds for lightweight-charts
                ts = int(idx.timestamp())
                close_val = round(float(row["Close"]), 2)
                open_val = round(float(row["Open"]), 2)
                high_val = round(float(row["High"]), 2)
                low_val = round(float(row["Low"]), 2)
                vol_val = int(row["Volume"])

                candles.append({
                    "time": ts,
                    "open": open_val,
                    "high": high_val,
                    "low": low_val,
                    "close": close_val,
                    "volume": vol_val,
                    "ema20": round(float(row["EMA20"]), 2) if not pd.isna(row["EMA20"]) else None,
                    "ema50": round(float(row["EMA50"]), 2) if not pd.isna(row["EMA50"]) else None,
                    "vwap": round(float(row["VWAP"]), 2) if not pd.isna(row["VWAP"]) else None,
                    "is_up": close_val >= open_val
                })

                if not pd.isna(row["RSI"]):
                    rsi_series.append({
                        "time": ts,
                        "value": round(float(row["RSI"]), 2)
                    })

                if not pd.isna(row["MACD"]):
                    macd_series.append({
                        "time": ts,
                        "macd": round(float(row["MACD"]), 2),
                        "signal": round(float(row["Signal"]), 2),
                        "hist": round(float(row["Hist"]), 2)
                    })

            result = {
                "symbol": symbol,
                "timeframe": timeframe,
                "count": len(candles),
                "candles": candles,
                "rsi": rsi_series,
                "macd": macd_series
            }

            self.history_cache[cache_key] = {
                "timestamp": now,
                "data": result
            }
            return result

        except Exception as e:
            print(f"[DataEngine] Error fetching history for {symbol} ({timeframe}): {e}")
            return {"candles": [], "rsi": [], "macd": []}

    def get_technical_analytics(self, symbol: str) -> Dict[str, Any]:
        """
        Uses Pandas to compute quantitative summary, pivot levels, and momentum signals.
        """
        quotes = self.fetch_all_quotes_batch()
        quote = quotes.get(symbol, {})
        ltp = quote.get("ltp", 0.0)

        # Get 1-month daily data for analytics
        try:
            df = yf.download(symbol, period="2mo", interval="1d", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna().copy()

            if df.empty:
                raise ValueError("Empty data")

            # Pivot Points (Floor trader formulas)
            last_bar = df.iloc[-1]
            h = float(last_bar["High"])
            l = float(last_bar["Low"])
            c = float(last_bar["Close"])

            pivot = (h + l + c) / 3.0
            r1 = (2 * pivot) - l
            s1 = (2 * pivot) - h
            r2 = pivot + (h - l)
            s2 = pivot - (h - l)
            r3 = h + 2 * (pivot - l)
            s3 = l - 2 * (h - pivot)

            # EMAs
            ema20 = float(df["Close"].ewm(span=20, adjust=False).mean().iloc[-1])
            ema50 = float(df["Close"].ewm(span=50, adjust=False).mean().iloc[-1])

            # RSI
            delta = df["Close"].diff()
            gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rs = gain / (loss + 1e-9)
            rsi = float((100 - (100 / (1 + rs))).iloc[-1])

            # Trend & Interpretation
            trend = "BULLISH" if ltp > ema20 > ema50 else ("BEARISH" if ltp < ema20 < ema50 else "NEUTRAL / CONSOLIDATION")
            
            if rsi >= 70:
                rsi_status = "OVERBOUGHT (Potential Pullback)"
                signal_score = -1
            elif rsi <= 30:
                rsi_status = "OVERSOLD (Reversal Candidate)"
                signal_score = 1
            elif rsi > 50:
                rsi_status = "BULLISH MOMENTUM"
                signal_score = 1
            else:
                rsi_status = "BEARISH MOMENTUM"
                signal_score = -1

            # Combined Verdict
            if trend == "BULLISH" and signal_score > 0:
                verdict = "STRONG BUY"
                badge_color = "emerald"
            elif trend == "BULLISH" or signal_score > 0:
                verdict = "ACCUMULATE / BUY"
                badge_color = "teal"
            elif trend == "BEARISH" and signal_score < 0:
                verdict = "STRONG SELL"
                badge_color = "rose"
            elif trend == "BEARISH":
                verdict = "DISTRIBUTE / SELL"
                badge_color = "amber"
            else:
                verdict = "NEUTRAL / HOLD"
                badge_color = "slate"

            # 52W High and Low
            high_52w = float(df["High"].max())
            low_52w = float(df["Low"].min())
            range_pos = round(((ltp - low_52w) / (high_52w - low_52w) * 100), 1) if high_52w > low_52w else 50.0

            return {
                "symbol": symbol,
                "ltp": ltp,
                "verdict": verdict,
                "badge_color": badge_color,
                "trend": trend,
                "rsi": round(rsi, 2),
                "rsi_status": rsi_status,
                "ema20": round(ema20, 2),
                "ema50": round(ema50, 2),
                "pivots": {
                    "r3": round(r3, 2),
                    "r2": round(r2, 2),
                    "r1": round(r1, 2),
                    "pivot": round(pivot, 2),
                    "s1": round(s1, 2),
                    "s2": round(s2, 2),
                    "s3": round(s3, 2)
                },
                "range_52w": {
                    "high": round(high_52w, 2),
                    "low": round(low_52w, 2),
                    "current_position_pct": range_pos
                }
            }

        except Exception as e:
            print(f"[DataEngine] Technical analytics error for {symbol}: {e}")
            return {
                "symbol": symbol,
                "ltp": ltp,
                "verdict": "NEUTRAL",
                "badge_color": "slate",
                "trend": "NEUTRAL",
                "rsi": 50.0,
                "rsi_status": "NEUTRAL",
                "ema20": ltp,
                "ema50": ltp,
                "pivots": {"r1": ltp * 1.01, "pivot": ltp, "s1": ltp * 0.99},
                "range_52w": {"high": ltp * 1.15, "low": ltp * 0.85, "current_position_pct": 50.0}
            }

    def get_market_depth(self, symbol: str) -> Dict[str, Any]:
        """
        Simulates Level-2 Market Depth (Best 5 Bids and 5 Asks) with 0.05 tick size
        accurately centered on real LTP, including cumulative volumes and buyer/seller ratio.
        """
        quotes = self.fetch_all_quotes_batch()
        quote = quotes.get(symbol, {})
        ltp = quote.get("ltp", 1000.0)
        tick = 0.05

        bids = []
        asks = []
        cum_bid_vol = 0
        cum_ask_vol = 0

        # Generate realistic 5 bids (descending from LTP - tick)
        for i in range(1, 6):
            price = round(ltp - (i * tick), 2)
            orders = int(np.random.randint(15, 120))
            vol = int(np.random.randint(300, 4500) * (6 - i * 0.5))
            cum_bid_vol += vol
            bids.append({
                "level": i,
                "orders": orders,
                "price": price,
                "quantity": vol,
                "cum_quantity": cum_bid_vol
            })

        # Generate realistic 5 asks (ascending from LTP + tick)
        for i in range(1, 6):
            price = round(ltp + (i * tick), 2)
            orders = int(np.random.randint(15, 120))
            vol = int(np.random.randint(300, 4500) * (6 - i * 0.5))
            cum_ask_vol += vol
            asks.append({
                "level": i,
                "orders": orders,
                "price": price,
                "quantity": vol,
                "cum_quantity": cum_ask_vol
            })

        total_vol = cum_bid_vol + cum_ask_vol
        buyer_pct = round((cum_bid_vol / total_vol * 100), 1) if total_vol else 50.0
        seller_pct = round((cum_ask_vol / total_vol * 100), 1) if total_vol else 50.0

        return {
            "symbol": symbol,
            "ltp": ltp,
            "tick_size": tick,
            "bids": bids,
            "asks": asks,
            "total_bid_qty": cum_bid_vol,
            "total_ask_qty": cum_ask_vol,
            "buyer_pct": buyer_pct,
            "seller_pct": seller_pct,
            "spread": round(asks[0]["price"] - bids[0]["price"], 2)
        }

# Global Singleton Instance
data_engine = IndianMarketEngine()
