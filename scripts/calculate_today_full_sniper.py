import urllib.request
import json
import datetime
from typing import Dict, List, Any

# Fetch 5-day 5m candles from FastAPI
req = urllib.request.urlopen("http://127.0.0.1:8000/api/candles-batch?timeframe=5D")
raw_data = json.loads(req.read().decode("utf-8"))

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
TODAY = "2026-11-16"

# Top 50 F&O configs from foOptionSniperEngine.ts
FO_CONFIG = {
    'RELIANCE': {'lotSize': 250, 'strikeStep': 20},
    'HDFCBANK': {'lotSize': 550, 'strikeStep': 10},
    'ICICIBANK': {'lotSize': 700, 'strikeStep': 10},
    'SBIN': {'lotSize': 750, 'strikeStep': 5},
    'INFY': {'lotSize': 400, 'strikeStep': 20},
    'TCS': {'lotSize': 175, 'strikeStep': 50},
    'AXISBANK': {'lotSize': 625, 'strikeStep': 10},
    'TATAMOTORS': {'lotSize': 550, 'strikeStep': 10},
    'M_M': {'lotSize': 350, 'strikeStep': 20},
    'LT': {'lotSize': 150, 'strikeStep': 50},
    'BAJFINANCE': {'lotSize': 125, 'strikeStep': 50},
    'KOTAKBANK': {'lotSize': 400, 'strikeStep': 20},
    'BHARTIARTL': {'lotSize': 475, 'strikeStep': 10},
    'TATASTEEL': {'lotSize': 5500, 'strikeStep': 1},
    'MARUTI': {'lotSize': 50, 'strikeStep': 100},
    'SUNPHARMA': {'lotSize': 350, 'strikeStep': 20},
    'HINDUNILVR': {'lotSize': 300, 'strikeStep': 20},
    'ITC': {'lotSize': 1600, 'strikeStep': 5},
    'NTPC': {'lotSize': 1500, 'strikeStep': 5},
    'POWERGRID': {'lotSize': 1800, 'strikeStep': 5},
    'COALINDIA': {'lotSize': 2100, 'strikeStep': 5},
    'ONGC': {'lotSize': 3850, 'strikeStep': 2.5},
    'BPCL': {'lotSize': 1800, 'strikeStep': 5},
    'IOC': {'lotSize': 4875, 'strikeStep': 2.5},
    'HCLTECH': {'lotSize': 350, 'strikeStep': 20},
    'WIPRO': {'lotSize': 1500, 'strikeStep': 5},
    'TECHM': {'lotSize': 600, 'strikeStep': 20},
    'COFORGE': {'lotSize': 150, 'strikeStep': 50},
    'PERSISTENT': {'lotSize': 100, 'strikeStep': 50},
    'JINDALSTEL': {'lotSize': 625, 'strikeStep': 10},
    'JSWSTEEL': {'lotSize': 675, 'strikeStep': 10},
    'HINDALCO': {'lotSize': 1400, 'strikeStep': 5},
    'VEDL': {'lotSize': 1150, 'strikeStep': 5},
    'NMDC': {'lotSize': 4500, 'strikeStep': 2.5},
    'BAJAJFINSV': {'lotSize': 500, 'strikeStep': 20},
    'CHOLAFIN': {'lotSize': 500, 'strikeStep': 20},
    'SHRIRAMFIN': {'lotSize': 300, 'strikeStep': 20},
    'PFC': {'lotSize': 1300, 'strikeStep': 5},
    'RECLTD': {'lotSize': 1400, 'strikeStep': 5},
    'MUTHOOTFIN': {'lotSize': 300, 'strikeStep': 20},
    'PNB': {'lotSize': 8000, 'strikeStep': 1},
    'BANKBARODA': {'lotSize': 2925, 'strikeStep': 2.5},
    'FEDERALBNK': {'lotSize': 5000, 'strikeStep': 1},
    'INDUSINDBK': {'lotSize': 500, 'strikeStep': 20},
    'CIPLA': {'lotSize': 650, 'strikeStep': 20},
    'DRREDDY': {'lotSize': 125, 'strikeStep': 50},
    'DIVISLAB': {'lotSize': 100, 'strikeStep': 50},
    'APOLLOHOSP': {'lotSize': 125, 'strikeStep': 50},
    'ADANIENT': {'lotSize': 300, 'strikeStep': 20},
    'ADANIPORTS': {'lotSize': 400, 'strikeStep': 20},
}

# Index Options configs: 2 Standard Lots
INDEX_CONFIG = {
    'NIFTY': {'lotSize': 50, 'strikeStep': 50, 'delta': 0.60},
    'BANKNIFTY': {'lotSize': 30, 'strikeStep': 100, 'delta': 0.60}
}

# 1. Parse candles
all_symbols = list(FO_CONFIG.keys()) + ['NIFTY', 'BANKNIFTY']
today_candles = {}
for sym in all_symbols:
    c_list = raw_data.get(sym, [])
    parsed = []
    for c in c_list:
        dt = datetime.datetime.fromtimestamp(c["timestamp"] / 1000, IST)
        c["dt"] = dt
        c["date_str"] = dt.strftime("%Y-%m-%d")
        c["time_str"] = dt.strftime("%H:%M")
        parsed.append(c)
    parsed.sort(key=lambda x: x["timestamp"])
    today_candles[sym] = parsed

timestamps = sorted(list(set(
    c["timestamp"] for sym in all_symbols for c in today_candles.get(sym, []) if c["date_str"] == TODAY
)))

def compute_ema(series: List[float], period: int) -> float:
    if len(series) < period:
        return series[-1] if series else 0.0
    k = 2.0 / (period + 1.0)
    ema = sum(series[:period]) / period
    for val in series[period:]:
        ema = val * k + ema * (1.0 - k)
    return ema

def compute_rsi(closes: List[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    if len(gains) < period:
        return 50.0
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

def compute_vwap(candles_today: List[Dict]) -> float:
    pv = sum(c["close"] * c.get("volume", 1) for c in candles_today)
    v = sum(c.get("volume", 1) for c in candles_today)
    return pv / v if v > 0 else (candles_today[-1]["close"] if candles_today else 0.0)

# Track seats: 2 Index Option Seats + 4 Stock Option Seats = 6 Total
SEATS = {
    'OPTION_1': None, # NIFTY
    'OPTION_2': None, # BANKNIFTY
    'TREND_1': None,
    'TREND_2': None,
    'CHOP_1': None,
    'CHOP_2': None,
}

closed_trades = []

for t_idx, ts in enumerate(timestamps):
    dt = datetime.datetime.fromtimestamp(ts / 1000, IST)
    time_str = dt.strftime("%H:%M")
    mins_from_midnight = dt.hour * 60 + dt.minute

    # 1. Manage existing positions using exact FoOptionSniperEngine ladder
    for seat_id, pos in list(SEATS.items()):
        if pos is None:
            continue
        sym = pos["stockSymbol"]
        sym_candles = [c for c in today_candles.get(sym, []) if c["timestamp"] <= ts]
        if not sym_candles:
            continue
        curr_bar = sym_candles[-1]
        hi, lo, cl = curr_bar["high"], curr_bar["low"], curr_bar["close"]
        qty = pos["qty"]
        delta = pos["delta"]
        mult = qty * delta

        # PnL calculations from underlying spot move
        if pos["optionType"] == "CE":
            worst_pts = lo - pos["spotEntry"]
            peak_pts = hi - pos["spotEntry"]
            cur_pts = cl - pos["spotEntry"]
        else: # PE
            worst_pts = pos["spotEntry"] - hi
            peak_pts = pos["spotEntry"] - lo
            cur_pts = pos["spotEntry"] - cl

        peak_pnl = peak_pts * mult
        cur_pnl = cur_pts * mult
        worst_pnl = worst_pts * mult

        pos["peakProfitInr"] = max(pos["peakProfitInr"], peak_pnl)

        # RULE 1: 03:18 PM AUTO SQUARE-OFF
        if mins_from_midnight >= 15 * 60 + 18:
            exit_pnl = max(-2500.0, cur_pnl)
            pos["exit_time"] = time_str
            pos["exit_reason"] = "03:18 PM Auto Square-Off"
            pos["gross_pnl"] = exit_pnl
            pos["charges"] = 62.0
            pos["net_pnl"] = round(exit_pnl - pos["charges"], 2)
            closed_trades.append(pos)
            SEATS[seat_id] = None
            continue

        # RULE 2: PROGRESSIVE PROFIT LADDER
        # STAGE 5: +₹8,000+ RUNNER
        if peak_pnl >= 8000.0:
            pos["ladderStage"] = 5
            dynamic_locked = max(6500.0, pos["peakProfitInr"] - 1000.0)
            pos["lockedProfitInr"] = dynamic_locked
        # STAGE 4: +₹4,000 MILESTONE -> Lock ₹3,000
        elif peak_pnl >= 4000.0 and pos["ladderStage"] < 4:
            pos["ladderStage"] = 4
            pos["lockedProfitInr"] = 3000.0
        # STAGE 3: +₹2,000 MILESTONE -> Lock ₹1,400
        elif peak_pnl >= 2000.0 and pos["ladderStage"] < 3:
            pos["ladderStage"] = 3
            pos["lockedProfitInr"] = 1400.0
        # STAGE 2: TP2 (+₹1,000) HIT -> Lock ₹600
        elif peak_pnl >= 1000.0 and pos["ladderStage"] < 2:
            pos["ladderStage"] = 2
            pos["lockedProfitInr"] = 600.0
        # STAGE 1: TP1 (+₹500) HIT -> Lock ₹150 (Risk Free)
        elif peak_pnl >= 500.0 and pos["ladderStage"] < 1:
            pos["ladderStage"] = 1
            pos["lockedProfitInr"] = 150.0

        # Check Trailed SL Hit (when stage >= 1)
        if pos["ladderStage"] >= 1:
            if cur_pnl <= pos["lockedProfitInr"]:
                exit_pnl = pos["lockedProfitInr"]
                pos["exit_time"] = time_str
                pos["exit_reason"] = f"TP{pos['ladderStage']} Trailed Lock (+₹{int(pos['lockedProfitInr'])})"
                pos["gross_pnl"] = exit_pnl
                pos["charges"] = 62.0
                pos["net_pnl"] = round(exit_pnl - pos["charges"], 2)
                closed_trades.append(pos)
                SEATS[seat_id] = None
                continue

        # RULE 3: HARD STOP LOSS (-₹2,500 PER LOT)
        if pos["ladderStage"] == 0 and worst_pnl <= -2500.0:
            exit_pnl = -2500.0
            pos["exit_time"] = time_str
            pos["exit_reason"] = "Hard SL Hit (-₹2,500 Cap)"
            pos["gross_pnl"] = exit_pnl
            pos["charges"] = 62.0
            pos["net_pnl"] = round(exit_pnl - pos["charges"], 2)
            closed_trades.append(pos)
            SEATS[seat_id] = None
            continue

    # Window Check: 09:25 AM to 03:15 PM
    if mins_from_midnight < 9 * 60 + 25 or mins_from_midnight >= 15 * 60 + 15:
        continue

    # 2. Check Index Option Seats (OPTION_1 & OPTION_2)
    for seat_id, idx_sym in [('OPTION_1', 'NIFTY'), ('OPTION_2', 'BANKNIFTY')]:
        if SEATS[seat_id] is not None:
            continue
        history = [c for c in today_candles.get(idx_sym, []) if c["timestamp"] <= ts]
        if len(history) < 20: continue
        today_sub = [c for c in history if c["date_str"] == TODAY]
        if len(today_sub) < 3: continue

        vw = compute_vwap(today_sub)
        closes = [c["close"] for c in history]
        e9 = compute_ema(closes, 9)
        e21 = compute_ema(closes, 21)
        rsi = compute_rsi(closes, 14)
        c0, c1 = history[-1], history[-2]

        cfg = INDEX_CONFIG[idx_sym]
        step = cfg['strikeStep']
        qty = cfg['lotSize']
        delta = cfg['delta']

        # BUY Signal -> ATM CE (EMA9 pull-back bounce from replay_engine.py)
        if c0["close"] > vw and e9 > e21 and c0["close"] > c0["open"] and c0["low"] <= e9 * 1.002 and 46 <= rsi <= 72:
            atm_strike = int(round(c0["close"] / step) * step)
            opt_symbol = f"{idx_sym} 26NOV {atm_strike} CE"
            SEATS[seat_id] = {
                'seatId': seat_id, 'stockSymbol': idx_sym, 'optionSymbol': opt_symbol,
                'optionType': 'CE', 'strike': atm_strike, 'qty': qty, 'delta': delta,
                'spotEntry': c0["close"], 'entry_time': time_str, 'ladderStage': 0,
                'lockedProfitInr': 0.0, 'peakProfitInr': 0.0, 'category': 'INDEX'
            }
        # SELL Signal -> ATM PE
        elif c0["close"] < vw and e9 < e21 and c0["close"] < c0["open"] and c0["high"] >= e9 * 0.998 and 28 <= rsi <= 54:
            atm_strike = int(round(c0["close"] / step) * step)
            opt_symbol = f"{idx_sym} 26NOV {atm_strike} PE"
            SEATS[seat_id] = {
                'seatId': seat_id, 'stockSymbol': idx_sym, 'optionSymbol': opt_symbol,
                'optionType': 'PE', 'strike': atm_strike, 'qty': qty, 'delta': delta,
                'spotEntry': c0["close"], 'entry_time': time_str, 'ladderStage': 0,
                'lockedProfitInr': 0.0, 'peakProfitInr': 0.0, 'category': 'INDEX'
            }

    # 3. Check Available Stock Option Seats (TREND_1, TREND_2, CHOP_1, CHOP_2)
    available_stock_seats = [sid for sid in ['TREND_1', 'TREND_2', 'CHOP_1', 'CHOP_2'] if SEATS[sid] is None]
    if not available_stock_seats:
        continue

    # Market Breadth
    whitelist14 = ["RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "BHARTIARTL", "SBIN", "INFY", "ITC", "HINDUNILVR", "LT", "BAJFINANCE", "M_M", "SUNPHARMA", "TATASTEEL"]
    bull_count, bear_count = 0, 0
    for sym in whitelist14:
        hist = [c for c in today_candles.get(sym, []) if c["timestamp"] <= ts]
        if len(hist) < 20: continue
        t_sub = [c for c in hist if c["date_str"] == TODAY]
        vw = compute_vwap(t_sub)
        cls = [c["close"] for c in hist]
        e9 = compute_ema(cls, 9)
        e21 = compute_ema(cls, 21)
        if cls[-1] > vw and e9 > e21: bull_count += 1
        elif cls[-1] < vw and e9 < e21: bear_count += 1

    dominant_bias = "BULLISH" if (bull_count / len(whitelist14)) >= 0.55 else ("BEARISH" if (bear_count / len(whitelist14)) >= 0.55 else "SECTOR_ROTATION")

    candidates = []
    for sym, cfg in FO_CONFIG.items():
        if any(p and p["stockSymbol"] == sym for p in SEATS.values()):
            continue
        history = [c for c in today_candles.get(sym, []) if c["timestamp"] <= ts]
        if len(history) < 25: continue
        today_sub = [c for c in history if c["date_str"] == TODAY]
        if len(today_sub) < 3: continue

        vw = compute_vwap(today_sub)
        closes = [c["close"] for c in history]
        e9 = compute_ema(closes, 9)
        e21 = compute_ema(closes, 21)
        rsi = compute_rsi(closes, 14)
        c0, c1, c2 = history[-1], history[-2], history[-3]

        allowed_side = None
        if dominant_bias == "BULLISH": allowed_side = "BUY"
        elif dominant_bias == "BEARISH": allowed_side = "SELL"
        else:
            if c0["close"] > vw and e9 > e21: allowed_side = "BUY"
            elif c0["close"] < vw and e9 < e21: allowed_side = "SELL"

        if not allowed_side: continue

        rng = max(c0["high"] - c0["low"], 0.05)
        body = abs(c0["close"] - c0["open"])
        upper_wick = (c0["high"] - max(c0["open"], c0["close"])) / rng
        lower_wick = (min(c0["open"], c0["close"]) - c0["low"]) / rng

        step = cfg['strikeStep']
        lot = cfg['lotSize']

        if allowed_side == "BUY":
            trend_ok = c0["close"] > vw and e9 > e21
            pa_ok = (c0["close"] > c0["open"] and (lower_wick >= 0.30 or c0["close"] > c1["high"]))
            if trend_ok and pa_ok and 46 <= rsi <= 72:
                atm_strike = int(round(c0["close"] / step) * step) if step >= 1 else round(c0["close"] / step) * step
                candidates.append({
                    'stockSymbol': sym, 'optionType': 'CE', 'strike': atm_strike,
                    'qty': lot, 'delta': 0.55, 'spotEntry': c0["close"], 'time': time_str,
                    'category': 'STOCK'
                })
        else:
            trend_ok = c0["close"] < vw and e9 < e21
            pa_ok = (c0["close"] < c0["open"] and (upper_wick >= 0.30 or c0["close"] < c1["low"]))
            if trend_ok and pa_ok and 28 <= rsi <= 54:
                atm_strike = int(round(c0["close"] / step) * step) if step >= 1 else round(c0["close"] / step) * step
                candidates.append({
                    'stockSymbol': sym, 'optionType': 'PE', 'strike': atm_strike,
                    'qty': lot, 'delta': 0.55, 'spotEntry': c0["close"], 'time': time_str,
                    'category': 'STOCK'
                })

    for i in range(min(len(candidates), len(available_stock_seats))):
        c = candidates[i]
        sid = available_stock_seats[i]
        opt_sym = f"{c['stockSymbol']} 26NOV {c['strike']} {c['optionType']}"
        SEATS[sid] = {
            'seatId': sid, 'stockSymbol': c['stockSymbol'], 'optionSymbol': opt_sym,
            'optionType': c['optionType'], 'strike': c['strike'], 'qty': c['qty'],
            'delta': c['delta'], 'spotEntry': c['spotEntry'], 'entry_time': c['time'],
            'ladderStage': 0, 'lockedProfitInr': 0.0, 'peakProfitInr': 0.0, 'category': 'STOCK'
        }

print("\n" + "=" * 115)
print("  AAJ (16-NOV-2026) KA EXACT TOTAL ORIGINAL PROFIT — INTEGRATED FO OPTION SNIPER ENGINE")
print("  Rules: Hard SL: -₹2,500/lot | TP1: +₹500 (Lock 150) | TP2: +₹1,000 (Lock 600) | Runner (+8K) | 03:18 PM EOD")
print("=" * 115)

total_net = sum(t["net_pnl"] for t in closed_trades)
wins = [t for t in closed_trades if t["net_pnl"] > 0]
losses = [t for t in closed_trades if t["net_pnl"] <= 0]
index_trades = [t for t in closed_trades if t["category"] == "INDEX"]
stock_trades = [t for t in closed_trades if t["category"] == "STOCK"]

index_pnl = sum(t["net_pnl"] for t in index_trades)
stock_pnl = sum(t["net_pnl"] for t in stock_trades)

print(f"{'#':<3} {'Time':<8} {'Seat':<9} {'Contract / Instrument':<26} {'Signal':<7} {'LotQty':<8} {'Exit Time':<10} {'Net P&L (₹)':<14} {'Exit Reason'}")
print("-" * 115)

for idx, t in enumerate(closed_trades):
    act = f"BUY {t['optionType']}"
    print(f"{idx+1:<3} {t['entry_time']:<8} {t['seatId']:<9} {t['optionSymbol']:<26} {act:<7} {t['qty']:<8} {t['exit_time']:<10} {t['net_pnl']:+12.2f}  {t['exit_reason']}")

print("-" * 115)
print(f"Index Options Net P&L (Nifty & BankNifty):  {index_pnl:+12.2f} INR  ({len(index_trades)} Trades)")
print(f"Top 50 Stock Options Net P&L:               {stock_pnl:+12.2f} INR  ({len(stock_trades)} Trades)")
print("=" * 115)
print(f"🏆 AAJ KA GRAND TOTAL ORIGINAL NET PROFIT:   {total_net:+12.2f} INR  ({len(closed_trades)} Trades: {len(wins)} Wins / {len(losses)} Loss)")
print("=" * 115)
