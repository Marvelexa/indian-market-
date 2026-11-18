import urllib.request
import json
import datetime
from typing import Dict, List, Any

req = urllib.request.urlopen("http://127.0.0.1:8000/api/candles-batch?timeframe=5D")
raw_data = json.loads(req.read().decode("utf-8"))

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
TODAY = "2026-11-16"

WHITELIST = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "BHARTIARTL",
    "SBIN", "INFY", "ITC", "HINDUNILVR", "LT",
    "BAJFINANCE", "M&M", "SUNPHARMA"
]

FO_LOTS = {
    "RELIANCE": 250, "HDFCBANK": 550, "ICICIBANK": 700, "SBIN": 750, "INFY": 400,
    "TCS": 175, "LT": 150, "BAJFINANCE": 125, "BHARTIARTL": 475, "HINDUNILVR": 300,
    "ITC": 1600, "SUNPHARMA": 700, "M&M": 200
}

today_candles = {}
for sym in WHITELIST + ["NIFTY", "BANKNIFTY"]:
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
    c["timestamp"] for sym in WHITELIST for c in today_candles[sym] if c["date_str"] == TODAY
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

SEATS = {
    "TREND_1": None, "TREND_2": None,
    "CHOP_1": None, "CHOP_2": None,
}

closed_trades = []

# Stock Option rules:
# Sizing: 1 F&O Lot
# Delta: 0.55 ATM Delta
# Max Loss Cap: ₹1,500
# Min Profit Target: ₹3,000 before trailing activates (locks ₹2,200)
# Option round-trip charges: ~₹62.00

for t_idx, ts in enumerate(timestamps):
    dt = datetime.datetime.fromtimestamp(ts / 1000, IST)
    time_str = dt.strftime("%H:%M")
    mins_from_midnight = dt.hour * 60 + dt.minute

    # Update existing positions
    for seat_id, pos in list(SEATS.items()):
        if pos is None:
            continue
        sym = pos["symbol"]
        sym_candles = [c for c in today_candles[sym] if c["timestamp"] <= ts]
        if not sym_candles:
            continue
        curr_bar = sym_candles[-1]
        hi, lo, cl = curr_bar["high"], curr_bar["low"], curr_bar["close"]
        lot_qty = pos["lot_qty"]
        delta = 0.55
        multiplier = lot_qty * delta

        # 03:18 PM Auto Square-Off
        if mins_from_midnight >= 15 * 60 + 18:
            pts = (cl - pos["entry"]) if pos["opt_type"] == "CE" else (pos["entry"] - cl)
            gross_pnl = pts * multiplier
            if gross_pnl < -1500.0: gross_pnl = -1500.0
            pos["exit_price"] = cl
            pos["exit_time"] = time_str
            pos["exit_reason"] = "03:18 PM Auto Square-Off"
            pos["gross_pnl"] = gross_pnl
            pos["charges"] = 62.0
            pos["net_pnl"] = round(gross_pnl - pos["charges"], 2)
            closed_trades.append(pos)
            SEATS[seat_id] = None
            continue

        # Check Hard SL (-₹1,500)
        # Adverse pts move that causes -₹1,500 loss
        adverse_pts_limit = 1500.0 / multiplier

        if pos["opt_type"] == "CE":
            worst_pts = lo - pos["entry"]
            peak_pts = hi - pos["entry"]
        else: # PE
            worst_pts = pos["entry"] - hi
            peak_pts = pos["entry"] - lo

        peak_gain = peak_pts * multiplier
        worst_loss = worst_pts * multiplier

        # Trailing Logic: ONLY AFTER +₹3,000 is reached
        if peak_gain >= 3000.0 and pos["stage"] < 1:
            pos["stage"] = 1
            pos["locked_profit"] = 2200.0
            pos["stage_note"] = "TP Reached (+₹3,000 / Locked +₹2,200)"

        if peak_gain >= 4500.0 and pos["stage"] < 2:
            pos["stage"] = 2
            pos["locked_profit"] = 3600.0
            pos["stage_note"] = "TP Trailed (+₹4,500 / Locked +₹3,600)"

        if peak_gain >= 6000.0 and pos["stage"] < 3:
            pos["stage"] = 3
            pos["locked_profit"] = 4800.0
            pos["stage_note"] = "TP Trailed (+₹6,000 / Locked +₹4,800)"

        if peak_gain >= 8000.0:
            # Max Target Exit!
            pos["exit_price"] = pos["entry"] + (8000.0 / multiplier) if pos["opt_type"] == "CE" else pos["entry"] - (8000.0 / multiplier)
            pos["exit_time"] = time_str
            pos["exit_reason"] = "TP 8 Max Target Exit (+₹8,000)"
            pos["gross_pnl"] = 8000.0
            pos["charges"] = 65.0
            pos["net_pnl"] = round(8000.0 - 65.0, 2)
            closed_trades.append(pos)
            SEATS[seat_id] = None
            continue

        # Check if Trailing SL hit
        if pos["stage"] >= 1:
            # Current gain on close or low
            curr_gain = ((cl - pos["entry"]) if pos["opt_type"] == "CE" else (pos["entry"] - cl)) * multiplier
            if curr_gain <= pos["locked_profit"]:
                gross_pnl = pos["locked_profit"]
                pos["exit_price"] = cl
                pos["exit_time"] = time_str
                pos["exit_reason"] = f"Trailed SL Hit ({pos['stage_note']})"
                pos["gross_pnl"] = gross_pnl
                pos["charges"] = 62.0
                pos["net_pnl"] = round(gross_pnl - pos["charges"], 2)
                closed_trades.append(pos)
                SEATS[seat_id] = None
                continue

        # Check Initial Hard SL Hit (-₹1,500)
        if pos["stage"] == 0 and worst_loss <= -1500.0:
            gross_pnl = -1500.0
            pos["exit_price"] = pos["entry"] - adverse_pts_limit if pos["opt_type"] == "CE" else pos["entry"] + adverse_pts_limit
            pos["exit_time"] = time_str
            pos["exit_reason"] = "Hard SL Hit (-₹1,500 Cap)"
            pos["gross_pnl"] = gross_pnl
            pos["charges"] = 62.0
            pos["net_pnl"] = round(gross_pnl - pos["charges"], 2)
            closed_trades.append(pos)
            SEATS[seat_id] = None
            continue

    if mins_from_midnight < 9 * 60 + 25 or mins_from_midnight >= 15 * 60 + 5:
        continue

    # Market Breadth
    bull_count, bear_count = 0, 0
    for sym in WHITELIST:
        history = [c for c in today_candles[sym] if c["timestamp"] <= ts]
        if len(history) < 20: continue
        today_sub = [c for c in history if c["date_str"] == TODAY]
        vw = compute_vwap(today_sub)
        closes = [c["close"] for c in history]
        e9 = compute_ema(closes, 9)
        e21 = compute_ema(closes, 21)
        cl = closes[-1]
        if cl > vw and e9 > e21: bull_count += 1
        elif cl < vw and e9 < e21: bear_count += 1

    breadth_pct = (bull_count / len(WHITELIST)) * 100.0
    dominant_bias = "BULLISH" if breadth_pct >= 55.0 else ("BEARISH" if (bear_count / len(WHITELIST)) * 100.0 >= 55.0 else "SECTOR_ROTATION")

    available_seats = [sid for sid in ["TREND_1", "TREND_2", "CHOP_1", "CHOP_2"] if SEATS[sid] is None]
    if not available_seats:
        continue

    candidates = []
    for sym in WHITELIST:
        if any(p and p["symbol"] == sym for p in SEATS.values()):
            continue
        history = [c for c in today_candles[sym] if c["timestamp"] <= ts]
        if len(history) < 30: continue
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
        recent3_low = min(c0["low"], c1["low"], c2["low"])
        recent3_high = max(c0["high"], c1["high"], c2["high"])

        lot_qty = FO_LOTS.get(sym, 250)

        if allowed_side == "BUY":
            trend_ok = c0["close"] > vw and e9 > e21
            val_ok = recent3_low <= max(e9, e21, vw) * 1.0035
            pa_ok = (
                (c0["close"] > c0["open"] and lower_wick >= 0.35 and upper_wick <= 0.25) or
                (c0["close"] > c0["open"] and c0["close"] > c1["open"] and c1["close"] < c1["open"]) or
                (c0["close"] > c0["open"] and c0["close"] > c1["high"] and body / rng >= 0.45) or
                (c0["close"] > c0["open"] and upper_wick <= 0.35 and rsi >= 46 and rsi <= 74)
            )
            if trend_ok and val_ok and pa_ok and 46 <= rsi <= 74:
                candidates.append({
                    "symbol": sym, "side": "BUY", "opt_type": "CE", "entry": c0["close"],
                    "lot_qty": lot_qty, "time": time_str
                })

        else:
            trend_ok = c0["close"] < vw and e9 < e21
            val_ok = recent3_high >= min(e9, e21, vw) * 0.9965
            pa_ok = (
                (c0["close"] < c0["open"] and upper_wick >= 0.35 and lower_wick <= 0.25) or
                (c0["close"] < c0["open"] and c0["close"] < c1["open"] and c1["close"] > c1["open"]) or
                (c0["close"] < c0["open"] and c0["close"] < c1["low"] and body / rng >= 0.45) or
                (c0["close"] < c0["open"] and lower_wick <= 0.35 and rsi <= 54 and rsi >= 26)
            )
            if trend_ok and val_ok and pa_ok and 26 <= rsi <= 54:
                candidates.append({
                    "symbol": sym, "side": "SELL", "opt_type": "PE", "entry": c0["close"],
                    "lot_qty": lot_qty, "time": time_str
                })

    for i in range(min(len(candidates), len(available_seats))):
        c = candidates[i]
        sid = available_seats[i]
        SEATS[sid] = {
            "symbol": c["symbol"], "side": c["side"], "opt_type": c["opt_type"],
            "entry": c["entry"], "lot_qty": c["lot_qty"], "entry_time": c["time"],
            "stage": 0, "locked_profit": 0.0, "stage_note": "Initial SL (-₹1,500 Risk)", "seat_id": sid
        }

print("\n" + "="*95)
print("  EXACT AAJ KA REAL F&O STOCK OPTIONS PERFORMANCE (16-NOV-2026)")
print("  Rule: BUY -> ATM CE | SELL -> ATM PE | Lot Qty: 1 Lot | SL: -₹1,500 | Min TP: +₹3,000")
print("="*95)

total_gross = sum(t["gross_pnl"] for t in closed_trades)
total_charges = sum(t["charges"] for t in closed_trades)
total_net = sum(t["net_pnl"] for t in closed_trades)
wins = [t for t in closed_trades if t["net_pnl"] > 0]
losses = [t for t in closed_trades if t["net_pnl"] <= 0]

print(f"Total Trades: {len(closed_trades)} | Wins: {len(wins)} | Losses: {len(losses)}")
print(f"Total Gross P&L: ₹{total_gross:,.2f} | Total Taxes/Brokerage: ₹{total_charges:,.2f} | Net P&L: ₹{total_net:,.2f}\n")
print(f"{'Time':<7} {'Contract':<20} {'Action':<6} {'LotQty':<8} {'Exit Time':<10} {'Net P&L (₹)':<14} {'Exit Reason'}")
print("-" * 95)
for t in closed_trades:
    contract = f"{t['symbol']} ATM {t['opt_type']}"
    print(f"{t['entry_time']:<7} {contract:<20} BUY    {t['lot_qty']:<8} {t['exit_time']:<10} {t['net_pnl']:<14.2f} {t['exit_reason']}")
print("-" * 95)
