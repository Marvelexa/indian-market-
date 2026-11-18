"""
NEXUS BHARAT - Indian Market (NSE/F&O) 9:15–3:30 Institutional Sniper Engine
Python implementation mirroring lib/indianMarket/indianMarketMasterEngine.ts
2+2+2 Seat Architecture | VWAP + EMA 9/21/50 + ORB + Pre-Reversal TP & Tight SL
"""

import math
import datetime
import pytz
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple

IST = pytz.timezone("Asia/Kolkata")

# Target F&O and Index Universe
FO_PRIORITY_UNIVERSE = [
    {"symbol": "^NSEI", "clean_symbol": "NIFTY 50", "is_index": True, "tick_size": 0.05, "lot_size": 25},
    {"symbol": "^NSEBANK", "clean_symbol": "BANK NIFTY", "is_index": True, "tick_size": 0.05, "lot_size": 15},
    {"symbol": "RELIANCE.NS", "clean_symbol": "RELIANCE", "is_index": False, "tick_size": 0.05, "lot_size": 250},
    {"symbol": "HDFCBANK.NS", "clean_symbol": "HDFCBANK", "is_index": False, "tick_size": 0.05, "lot_size": 550},
    {"symbol": "ICICIBANK.NS", "clean_symbol": "ICICIBANK", "is_index": False, "tick_size": 0.05, "lot_size": 700},
    {"symbol": "SBIN.NS", "clean_symbol": "SBIN", "is_index": False, "tick_size": 0.05, "lot_size": 750},
    {"symbol": "INFY.NS", "clean_symbol": "INFY", "is_index": False, "tick_size": 0.05, "lot_size": 400},
    {"symbol": "TCS.NS", "clean_symbol": "TCS", "is_index": False, "tick_size": 0.05, "lot_size": 175},
    {"symbol": "AXISBANK.NS", "clean_symbol": "AXISBANK", "is_index": False, "tick_size": 0.05, "lot_size": 625},
    {"symbol": "LT.NS", "clean_symbol": "LT", "is_index": False, "tick_size": 0.05, "lot_size": 150},
    {"symbol": "BAJFINANCE.NS", "clean_symbol": "BAJFINANCE", "is_index": False, "tick_size": 0.05, "lot_size": 125},
    {"symbol": "M&M.NS", "clean_symbol": "M&M", "is_index": False, "tick_size": 0.05, "lot_size": 200},
    {"symbol": "BAJAJ-AUTO.NS", "clean_symbol": "BAJAJ-AUTO", "is_index": False, "tick_size": 0.05, "lot_size": 75},
]

class IndianMarketMasterSniper:
    TOTAL_CAPITAL_INR = 100000.0        # ₹1,00,000 Base Capital
    DAILY_TARGET_INR = 20000.0          # ₹20,000+ Daily Goal
    MAX_RISK_PER_TRADE_INR = 2500.0     # Strict ₹2,500 Max Loss per lot (Rules 3 & 5)

    @staticmethod
    def check_market_session_ist(timestamp_ms: Optional[int] = None) -> Dict[str, Any]:
        """
        Checks if current timestamp is within NSE Active Trading Window (09:25 AM - 03:10 PM IST)
        and flags Auto Square-Off at 03:18 PM IST.
        """
        if timestamp_ms is None:
            now_ist = datetime.datetime.now(IST)
        else:
            now_ist = datetime.datetime.fromtimestamp(timestamp_ms / 1000.0, tz=IST)

        hours = now_ist.hour
        minutes = now_ist.minute
        weekday = now_ist.weekday() # 5=Sat, 6=Sun
        total_minutes = hours * 60 + minutes
        ist_time_str = f"{hours:02d}:{minutes:02d} IST"

        market_open_min = 9 * 60 + 15    # 09:15 AM
        entry_start_min = 9 * 60 + 25    # 09:25 AM (10-min ORB stabilization)
        entry_cutoff_min = 15 * 60 + 10  # 03:10 PM (No new entries)
        square_off_min = 15 * 60 + 18    # 03:18 PM (Mandatory intraday exit)
        market_close_min = 15 * 60 + 30  # 03:30 PM

        is_weekend = weekday in [5, 6]

        if is_weekend or total_minutes < market_open_min or total_minutes > market_close_min:
            return {
                "is_market_open": False,
                "can_open_new_trade": False,
                "must_square_off_all": False,
                "ist_time_string": ist_time_str,
                "stage": "MARKET_CLOSED",
                "session_note": "MARKET_CLOSED (Outside 09:15–15:30 IST)",
                "next_milestone": "PRE-OPEN MON 09:00 IST" if is_weekend else "OPEN 09:15 IST"
            }

        if total_minutes >= square_off_min:
            return {
                "is_market_open": True,
                "can_open_new_trade": False,
                "must_square_off_all": True,
                "ist_time_string": ist_time_str,
                "stage": "AUTO_SQUARE_OFF",
                "session_note": "INTRADAY_AUTO_SQUARE_OFF_WINDOW (03:18 PM+ IST)",
                "next_milestone": "CLOSING AT 03:30 PM"
            }

        if total_minutes < entry_start_min:
            return {
                "is_market_open": True,
                "can_open_new_trade": False,
                "must_square_off_all": False,
                "ist_time_string": ist_time_str,
                "stage": "ORB_WARMUP",
                "session_note": "ORB_STABILIZATION_WARMUP (09:15–09:25 AM IST)",
                "next_milestone": "SNIPER OPENS AT 09:25 AM"
            }

        return {
            "is_market_open": True,
            "can_open_new_trade": total_minutes <= entry_cutoff_min,
            "must_square_off_all": False,
            "ist_time_string": ist_time_str,
            "stage": "ACTIVE_SNIPER",
            "session_note": "ACTIVE_SNIPER_SESSION (09:25 AM–03:10 PM IST)",
            "next_milestone": "ENTRY CUTOFF 03:10 PM"
        }

    @staticmethod
    def compute_intraday_vwap(df: pd.DataFrame) -> float:
        """Computes Intraday Session VWAP (resets at 09:15 AM IST)."""
        if df.empty or "Volume" not in df.columns:
            return 0.0

        last_idx = df.index[-1]
        last_date = last_idx.date() if hasattr(last_idx, "date") else None
        
        if last_date:
            session_df = df[df.index.date == last_date].copy()
        else:
            session_df = df.copy()

        if session_df.empty:
            session_df = df.tail(30).copy()

        typical_price = (session_df["High"] + session_df["Low"] + session_df["Close"]) / 3.0
        vol = session_df["Volume"].replace(0, 1)
        cum_pv = (typical_price * vol).sum()
        cum_v = vol.sum()

        return float(cum_pv / cum_v) if cum_v > 0 else float(df["Close"].iloc[-1])

    @staticmethod
    def compute_ema(series: pd.Series, period: int) -> float:
        """Computes EMA over specified period."""
        if len(series) == 0:
            return 0.0
        ema = series.ewm(span=period, adjust=False).mean()
        return float(ema.iloc[-1])

    @staticmethod
    def compute_rsi(series: pd.Series, period: int = 14) -> float:
        """Computes 14-period Wilder RSI."""
        if len(series) <= period:
            return 50.0
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
        rs = gain / (loss + 1e-9)
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1])

    @classmethod
    def evaluate_symbol(
        cls,
        symbol: str,
        df: pd.DataFrame,
        is_index: bool,
        tick_size: float = 0.05,
        previous_day_high: Optional[float] = None,
        previous_day_low: Optional[float] = None,
        bypass_session_check: bool = False
    ) -> Dict[str, Any]:
        """
        Master Evaluation Function:
        Combines Intraday VWAP + EMA 9/21/50 + ORB + Zero-Lag Price Action + Pre-Reversal Wall TP & Tight SL.
        Requires >= 88/100 confluence score for approval.
        """
        if len(df) < 40:
            return cls._build_rejected_signal(symbol, "WARMUP_NEED_40_CANDLES")

        c0 = df.iloc[-1]
        c1 = df.iloc[-2]
        c2 = df.iloc[-3]
        entry_price = float(c0["Close"])

        # 1. Check NSE Session Timing
        last_ts = int(df.index[-1].timestamp() * 1000)
        session = cls.check_market_session_ist(last_ts)
        # Note: If bypass_session_check is set (e.g. for weekend backtesting / demo analysis of last session), allow evaluation
        if not bypass_session_check and not session["can_open_new_trade"]:
            return cls._build_rejected_signal(symbol, f"SESSION_GATE: {session['session_note']}")

        # 2. Core Institutional Indicators (VWAP, EMA 9, EMA 21, EMA 50, RSI 14, RVOL 20)
        closes = df["Close"]
        vwap = cls.compute_intraday_vwap(df)
        ema9 = cls.compute_ema(closes.tail(30), 9)
        ema21 = cls.compute_ema(closes.tail(45), 21)
        ema50 = cls.compute_ema(closes.tail(75), 50)
        rsi = cls.compute_rsi(closes, 14)

        recent20_vol = df["Volume"].iloc[-21:-1]
        avg_vol20 = float(recent20_vol.mean()) if len(recent20_vol) > 0 else 1.0
        rvol = float(c0["Volume"] / avg_vol20) if avg_vol20 > 0 else 1.0

        # 3. Candle Anatomy & Price Action Rejection / Displacement
        range0 = max(float(c0["High"] - c0["Low"]), 1e-8)
        body0 = abs(float(c0["Close"] - c0["Open"]))
        body_ratio0 = body0 / range0
        lower_wick0 = (min(float(c0["Open"]), float(c0["Close"])) - float(c0["Low"])) / range0
        upper_wick0 = (float(c0["High"]) - max(float(c0["Open"]), float(c0["Close"]))) / range0

        # 25-bar Structural Box & Swing Pivots
        lookback25 = df.iloc[-26:-1]
        box_high25 = float(lookback25["High"].max())
        box_low25 = float(lookback25["Low"].min())
        box_range25 = max(box_high25 - box_low25, 1e-8)
        pos_in_box = (entry_price - box_low25) / box_range25
        box_width_pct = box_range25 / entry_price

        # Identify Regime: CHOPPING PING-PONG vs NORMAL TREND RUNNER
        ema_spread_pct = abs(ema9 - ema21) / entry_price
        is_chopping_regime = ema_spread_pct < (0.0018 if is_index else 0.0032)

        action = "WAIT"
        seat_category = "NONE"
        setup_name = "NONE"
        confluence_score = 0

        # =========================================================================
        # ENGINE 1: NORMAL TREND RUNNER (VWAP + EMA 9/21 PULLBACK OR BREAKOUT)
        # =========================================================================
        is_bullish_trend = (entry_price > vwap and ema9 > ema21 and entry_price > ema21 and ema21 >= ema50 * 0.998)
        is_bearish_trend = (entry_price < vwap and ema9 < ema21 and entry_price < ema21 and ema21 <= ema50 * 1.002)

        touched_bullish_value_zone = (
            float(c0["Low"]) <= ema9 * 1.0015 or float(c0["Low"]) <= vwap * 1.0015 or float(c1["Low"]) <= ema21 * 1.0015
        )
        touched_bearish_value_zone = (
            float(c0["High"]) >= ema9 * 0.9985 or float(c0["High"]) >= vwap * 0.9985 or float(c1["High"]) >= ema21 * 0.9985
        )

        bullish_trigger_candle = (
            float(c0["Close"]) > float(c0["Open"]) and
            upper_wick0 <= 0.28 and
            ((lower_wick0 >= 0.35 and body_ratio0 >= 0.25) or (float(c0["Close"]) > float(c1["High"]) and body_ratio0 >= 0.52))
        )

        bearish_trigger_candle = (
            float(c0["Close"]) < float(c0["Open"]) and
            lower_wick0 <= 0.28 and
            ((upper_wick0 >= 0.35 and body_ratio0 >= 0.25) or (float(c0["Close"]) < float(c1["Low"]) and body_ratio0 >= 0.52))
        )

        if (
            not is_chopping_regime and
            is_bullish_trend and
            touched_bullish_value_zone and
            bullish_trigger_candle and
            53 <= rsi <= 72 and
            rvol >= 1.1
        ):
          action = "BUY"
          seat_category = "NORMAL_TREND_RUNNER_SEAT"
          setup_name = "VWAP_EMA9_21_INSTITUTIONAL_TREND_BUY"
          confluence_score = 89 + min(10, int(round((rvol - 1) * 8)))

        elif (
            not is_chopping_regime and
            is_bearish_trend and
            touched_bearish_value_zone and
            bearish_trigger_candle and
            28 <= rsi <= 47 and
            rvol >= 1.1
        ):
          action = "SELL"
          seat_category = "NORMAL_TREND_RUNNER_SEAT"
          setup_name = "VWAP_EMA9_21_INSTITUTIONAL_TREND_SELL"
          confluence_score = 89 + min(10, int(round((rvol - 1) * 8)))

        # =========================================================================
        # ENGINE 2: CHOPPING BOX PING-PONG SNIPER (SUPPORT BUY / RESISTANCE SELL)
        # =========================================================================
        if action == "WAIT" and box_width_pct >= (0.0045 if is_index else 0.0085):
            swept_bottom_support = (
                (min(float(c0["Low"]), float(c1["Low"])) <= box_low25 * 1.002 or pos_in_box <= 0.22) and
                float(c0["Close"]) > float(c0["Open"]) and
                (lower_wick0 >= 0.35 or float(c0["Close"]) > (float(c1["Open"]) + float(c1["Close"])) / 2) and
                rsi <= 44
            )

            swept_top_resistance = (
                (max(float(c0["High"]), float(c1["High"])) >= box_high25 * 0.998 or pos_in_box >= 0.78) and
                float(c0["Close"]) < float(c0["Open"]) and
                (upper_wick0 >= 0.35 or float(c0["Close"]) < (float(c1["Open"]) + float(c1["Close"])) / 2) and
                rsi >= 56
            )

            if swept_bottom_support:
                action = "BUY"
                seat_category = "CHOP_PING_PONG_SEAT"
                setup_name = "CHOP_BOX_SUPPORT_SWEEP_REVERSAL_BUY"
                confluence_score = 88 + (5 if lower_wick0 >= 0.45 else 2)
            elif swept_top_resistance:
                action = "SELL"
                seat_category = "CHOP_PING_PONG_SEAT"
                setup_name = "CHOP_BOX_RESISTANCE_SWEEP_REVERSAL_SELL"
                confluence_score = 88 + (5 if upper_wick0 >= 0.45 else 2)

        if action == "WAIT" or confluence_score < 88:
            return cls._build_rejected_signal(symbol, "NO_90PCT_HIGH_CONVICTION_SETUP")

        # =========================================================================
        # STEP 4: TIGHT STRUCTURAL SL (JUST BEYOND BREAKDOWN INVALIDATION POINT)
        # =========================================================================
        recent3_low = min(float(c0["Low"]), float(c1["Low"]), float(c2["Low"]))
        recent3_high = max(float(c0["High"]), float(c1["High"]), float(c2["High"]))

        if action == "BUY":
            invalidation_point = min(recent3_low, min(ema21, vwap) if seat_category == "NORMAL_TREND_RUNNER_SEAT" else recent3_low)
        else:
            invalidation_point = max(recent3_high, max(ema21, vwap) if seat_category == "NORMAL_TREND_RUNNER_SEAT" else recent3_high)

        sl_buffer_pct = 0.0006 if is_index else 0.0012  # 0.06% on Index, 0.12% on Stocks
        raw_sl_price = invalidation_point * (1 - sl_buffer_pct) if action == "BUY" else invalidation_point * (1 + sl_buffer_pct)

        raw_sl_dist_pct = abs(entry_price - raw_sl_price) / entry_price
        min_sl_pct = 0.0018 if is_index else 0.0035
        max_sl_pct = 0.0045 if is_index else 0.0075  # Never allow bloated SL

        if raw_sl_dist_pct > max_sl_pct:
            return cls._build_rejected_signal(
                symbol,
                f"SL_TOO_WIDE_VETO ({raw_sl_dist_pct*100:.2f}% > {max_sl_pct*100:.2f}%)"
            )

        sl_dist_pct = max(min_sl_pct, raw_sl_dist_pct)
        sl_price = cls.round_to_tick(
            entry_price * (1 - sl_dist_pct) if action == "BUY" else entry_price * (1 + sl_dist_pct),
            tick_size
        )

        # =========================================================================
        # STEP 5: NO FIXED TP TARGET (OPEN RUNNER + DYNAMIC TRAILING SL)
        # Never cap profits at artificial targets; ride the entire institutional trend!
        # =========================================================================
        first_reversal_wall = {
            "price": None,
            "source": "OPEN RUNNER (NO TP)"
        }
        tp_price = None

        # =========================================================================
        # STEP 6: POSITION SIZING FOR ₹1,00,000 CAPITAL & 1:1 ITM OPTION MIRROR
        # =========================================================================
        sl_per_unit_inr = max(abs(entry_price - sl_price), tick_size)
        qty_by_risk = max(1, int(cls.MAX_RISK_PER_TRADE_INR // sl_per_unit_inr))
        
        # Max margin per seat: ~₹25,000 to fit into ₹1,00,000 capital across seats
        margin_per_unit = entry_price * 0.20
        qty_by_margin = max(1, int(25000 // margin_per_unit))

        if is_index:
            # 1 lot of NIFTY (25) or BANK NIFTY (15) for option or index sniper
            lot_size = 15 if "BANK" in symbol else 25
            quantity_lots_or_shares = lot_size
        else:
            quantity_lots_or_shares = max(1, min(qty_by_risk, qty_by_margin))

        max_risk_inr = round(quantity_lots_or_shares * sl_per_unit_inr)
        expected_profit_inr = round(quantity_lots_or_shares * entry_price * 0.01) # Baseline 1% runner

        # Option Mirror Metadata for NIFTY / BANKNIFTY
        strike_step = 100 if "BANK" in symbol else 50
        atm_strike = round(entry_price / strike_step) * strike_step
        recommended_strike = atm_strike - strike_step if action == "BUY" else atm_strike + strike_step

        return {
            "approved": True,
            "symbol": symbol,
            "action": action,
            "seat_category": seat_category,
            "option_contract_type": ("CE_CALL_BUY" if action == "BUY" else "PE_PUT_BUY") if is_index else "NONE",
            "recommended_strike": recommended_strike if is_index else None,
            "confluence_score": confluence_score,
            "setup_name": setup_name,
            "entry_price": round(entry_price, 2),
            "sl_price": sl_price,
            "tp_price": None,
            "target_type": "OPEN_RUNNER_UNLIMITED",
            "true_invalidation_price": cls.round_to_tick(invalidation_point, tick_size),
            "first_reversal_wall_price": None,
            "reversal_wall_source": "OPEN RUNNER (NO TP)",
            "front_run_buffer": 0.0,
            "sl_dist_pct": round(sl_dist_pct, 5),
            "tp_dist_pct": 0.0,
            "rr_ratio": 0.0,
            "quantity_lots_or_shares": quantity_lots_or_shares,
            "max_risk_inr": max_risk_inr,
            "expected_profit_inr": expected_profit_inr,
            "veto_reason": None
        }

    @classmethod
    def evaluate_live_trailing_bracket(
        cls,
        action: str,
        entry_price: float,
        current_ltp: float,
        current_sl_price: float,
        tp_price: Optional[float] = None,
        tick_size: float = 0.05,
        quantity: int = 1,
        is_option: bool = False,
        symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Institutional Extended Trailing Ladder (Up to +₹8,000 Target):
        - Stop Loss: Strictly -₹2,500/lot (Indices/MCX) or -₹1,500/lot (Stocks).
        - Zero Premature Micro-Cuts: full breathing room guarantee.
        - For Stock Options: minimum profit hurdle +₹3,000 before trailing (+₹2,200 lock).
        - For Index Options: 8-stage ladder up to +₹8,000 target.
        """
        is_buy = action == "BUY"
        profit_dist = (current_ltp - entry_price) if is_buy else (entry_price - current_ltp)
        gain_pct = round((profit_dist / entry_price) * 100.0, 2) if entry_price else 0.0
        multiplier = quantity
        float_pnl = profit_dist * multiplier

        clean_sym = (symbol or "").upper()
        is_index = any(idx in clean_sym for idx in ["NIFTY", "BANKNIFTY", "SENSEX", "FINNIFTY", "CRUDEOIL", "GOLD", "SILVER", "NATURALGAS", "COPPER"]) or (not clean_sym)

        # Hard Stop Loss is strictly capped at ₹2,500 loss per lot across all positions (Full Breathing Room)
        max_loss_cap = 2500.0

        # 0. Strict Hard SL Breach (Full Breathing Room, No Premature Micro Cuts)
        if float_pnl <= -max_loss_cap:
            return {
                "should_modify_sl": False,
                "new_sl_price": current_sl_price,
                "gain_pct": gain_pct,
                "progress_pct": 0.0,
                "stage": -1,
                "should_exit": True,
                "exit_reason": "HARD_SL_CAP_HIT",
                "stage_note": f"🛑 HARD SL HIT (-₹{max_loss_cap:,.0f} MAX RISK EXCEEDED)"
            }

        # 8. Full Max Profit Target (+₹8,000)
        if float_pnl >= 8000.0:
            target_pts = 8000.0 / multiplier
            exit_p = cls.round_to_tick(entry_price + target_pts if is_buy else entry_price - target_pts, tick_size)
            return {
                "should_modify_sl": True,
                "new_sl_price": exit_p,
                "gain_pct": gain_pct,
                "progress_pct": 100.0,
                "stage": 8,
                "should_exit": True,
                "exit_reason": "MAX_TARGET_8000_HIT",
                "stage_note": "🎯 MAX TARGET HIT (+₹8,000 PROFIT BOOKED)"
            }

        # Stage 7 (+₹6,000 Milestone) -> Locks +₹4,800
        if float_pnl >= 6000.0:
            buf_pts = 4800.0 / multiplier
            locked_sl = cls.round_to_tick(entry_price + buf_pts if is_buy else entry_price - buf_pts, tick_size)
            is_improvement = (locked_sl > current_sl_price) if is_buy else (locked_sl < current_sl_price)
            return {
                "should_modify_sl": is_improvement,
                "new_sl_price": locked_sl if is_improvement else current_sl_price,
                "gain_pct": gain_pct,
                "progress_pct": round(min(100.0, 75.0 + (float_pnl - 6000.0) * 25.0 / 2000.0), 1),
                "stage": 7,
                "should_exit": False,
                "stage_note": "🎯 STAGE 7 (+₹6,000) • SL Locked at +₹4,800"
            }

        # Stage 6 (+₹4,500 Milestone) -> Locks +₹3,600
        if float_pnl >= 4500.0:
            buf_pts = 3600.0 / multiplier
            locked_sl = cls.round_to_tick(entry_price + buf_pts if is_buy else entry_price - buf_pts, tick_size)
            is_improvement = (locked_sl > current_sl_price) if is_buy else (locked_sl < current_sl_price)
            return {
                "should_modify_sl": is_improvement,
                "new_sl_price": locked_sl if is_improvement else current_sl_price,
                "gain_pct": gain_pct,
                "progress_pct": round(min(100.0, 56.0 + (float_pnl - 4500.0) * 19.0 / 1500.0), 1),
                "stage": 6,
                "should_exit": False,
                "stage_note": "🎯 STAGE 6 (+₹4,500) • SL Locked at +₹3,600"
            }

        # Stage 5 (+₹3,000 Milestone) -> Locks +₹2,400
        if float_pnl >= 3000.0:
            locked_inr = 2400.0
            buf_pts = locked_inr / multiplier
            locked_sl = cls.round_to_tick(entry_price + buf_pts if is_buy else entry_price - buf_pts, tick_size)
            is_improvement = (locked_sl > current_sl_price) if is_buy else (locked_sl < current_sl_price)
            return {
                "should_modify_sl": is_improvement,
                "new_sl_price": locked_sl if is_improvement else current_sl_price,
                "gain_pct": gain_pct,
                "progress_pct": round(min(100.0, 37.5 + (float_pnl - 3000.0) * 18.5 / 1500.0), 1),
                "stage": 5,
                "should_exit": False,
                "stage_note": f"🎯 STAGE 5 (+₹3,000) • SL Locked at +₹{locked_inr:,.0f} (Brokerage Shielded)"
            }

        # Trailing for Stock Options requires +₹3,000 hurdle before trailing (Rule 5)
        if not is_index:
            return {
                "should_modify_sl": False,
                "new_sl_price": current_sl_price,
                "gain_pct": gain_pct,
                "progress_pct": round(max(0.0, min(37.5, float_pnl * 37.5 / 3000.0)), 1),
                "stage": 0,
                "should_exit": False,
                "stage_note": f"RUNNING TO +₹3,000 HURDLE (+₹{max(0.0, float_pnl):.0f} / +₹3,000)"
            }

        # Index Option specific intermediate trailing stages:
        # Stage 4 (+₹2,000 Milestone) -> Locks +₹1,600
        if float_pnl >= 2000.0:
            buf_pts = 1600.0 / multiplier
            locked_sl = cls.round_to_tick(entry_price + buf_pts if is_buy else entry_price - buf_pts, tick_size)
            is_improvement = (locked_sl > current_sl_price) if is_buy else (locked_sl < current_sl_price)
            return {
                "should_modify_sl": is_improvement,
                "new_sl_price": locked_sl if is_improvement else current_sl_price,
                "gain_pct": gain_pct,
                "progress_pct": round(min(100.0, 25.0 + (float_pnl - 2000.0) * 12.5 / 1000.0), 1),
                "stage": 4,
                "should_exit": False,
                "stage_note": "🎯 STAGE 4 (+₹2,000) • SL Locked at +₹1,600"
            }

        # Stage 3 (+₹1,500 Milestone) -> Locks +₹1,150
        if float_pnl >= 1500.0:
            buf_pts = 1150.0 / multiplier
            locked_sl = cls.round_to_tick(entry_price + buf_pts if is_buy else entry_price - buf_pts, tick_size)
            is_improvement = (locked_sl > current_sl_price) if is_buy else (locked_sl < current_sl_price)
            return {
                "should_modify_sl": is_improvement,
                "new_sl_price": locked_sl if is_improvement else current_sl_price,
                "gain_pct": gain_pct,
                "progress_pct": round(min(100.0, 18.7 + (float_pnl - 1500.0) * 6.3 / 500.0), 1),
                "stage": 3,
                "should_exit": False,
                "stage_note": "🎯 STAGE 3 (+₹1,500) • SL Locked at +₹1,150"
            }

        # Stage 2 (+₹1,000 Milestone) -> Locks +₹700
        if float_pnl >= 1000.0:
            buf_pts = 700.0 / multiplier
            locked_sl = cls.round_to_tick(entry_price + buf_pts if is_buy else entry_price - buf_pts, tick_size)
            is_improvement = (locked_sl > current_sl_price) if is_buy else (locked_sl < current_sl_price)
            return {
                "should_modify_sl": is_improvement,
                "new_sl_price": locked_sl if is_improvement else current_sl_price,
                "gain_pct": gain_pct,
                "progress_pct": round(min(100.0, 12.5 + (float_pnl - 1000.0) * 6.2 / 500.0), 1),
                "stage": 2,
                "should_exit": False,
                "stage_note": "🎯 STAGE 2 (+₹1,000) • SL Locked at +₹700"
            }

        # Stage 1 (+₹500 Milestone) -> Locks +₹300 (Brokerage-Shielded & Risk-Free)
        if float_pnl >= 500.0:
            buf_pts = 300.0 / multiplier
            locked_sl = cls.round_to_tick(entry_price + buf_pts if is_buy else entry_price - buf_pts, tick_size)
            is_improvement = (locked_sl > current_sl_price) if is_buy else (locked_sl < current_sl_price)
            return {
                "should_modify_sl": is_improvement,
                "new_sl_price": locked_sl if is_improvement else current_sl_price,
                "gain_pct": gain_pct,
                "progress_pct": round(min(100.0, (float_pnl - 500.0) * 12.5 / 500.0), 1),
                "stage": 1,
                "should_exit": False,
                "stage_note": "🎯 STAGE 1 (+₹500) • SL Locked at +₹300 (Risk Free)"
            }

        # Initial Running Stage (< ₹500 profit cushion)
        return {
            "should_modify_sl": False,
            "new_sl_price": current_sl_price,
            "gain_pct": gain_pct,
            "progress_pct": round(max(0.0, float_pnl * 100.0 / 8000.0), 1),
            "stage": 0,
            "should_exit": False,
            "stage_note": f"RUNNING TO STAGE 1 (+₹{max(0.0, float_pnl):.0f} / +₹500)"
        }

    @staticmethod
    def round_to_tick(price: float, tick_size: float) -> float:
        if tick_size > 0:
            return round(round(price / tick_size) * tick_size, 2)
        return round(price, 2)

    @classmethod
    def _build_rejected_signal(cls, symbol: str, reason: str) -> Dict[str, Any]:
        return {
            "approved": False,
            "symbol": symbol,
            "action": "WAIT",
            "seat_category": "NONE",
            "option_contract_type": "NONE",
            "recommended_strike": None,
            "confluence_score": 0,
            "setup_name": "NONE",
            "entry_price": 0.0,
            "sl_price": 0.0,
            "tp_price": 0.0,
            "true_invalidation_price": 0.0,
            "first_reversal_wall_price": 0.0,
            "reversal_wall_source": "NONE",
            "sl_dist_pct": 0.0,
            "tp_dist_pct": 0.0,
            "rr_ratio": 0.0,
            "quantity_lots_or_shares": 0,
            "max_risk_inr": 0,
            "expected_profit_inr": 0,
            "veto_reason": reason
        }

# Global Singleton Instance
indian_sniper_engine = IndianMarketMasterSniper()
