"""
NEXUS BHARAT - Indian Market (NSE/F&O) Portfolio & 2+2+2 Seat Execution Engine
Total Base Capital: ₹1,00,000 INR | Daily Target: ₹20,000+ INR | Max Risk Cap: ₹2,500 INR per lot
Features real Indian Brokerage & Statutory Taxes computation (STT, GST, Stamp Duty, SEBI turnover)
"""

import time
import uuid
import datetime
import re
import pytz
from typing import Dict, List, Optional, Any

from backend.sniper_engine import IndianMarketMasterSniper

IST = pytz.timezone("Asia/Kolkata")

class PortfolioEngine:
    """
    Manages 2+2+2 Seat Allocation:
    - 2 Chopping Seats (CHOP_PING_PONG_SEAT)
    - 2 Normal Trend Seats (NORMAL_TREND_RUNNER_SEAT)
    - 2 Option Seats (NIFTY_BANKNIFTY_OPTION_SEAT)
    """

    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.daily_target = 20000.0
        self.max_risk_per_trade = 2500.0
        self.cash = initial_capital
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.orders: List[Dict[str, Any]] = []
        self.realized_pnl: float = 0.0

        # 2+2+2 Seat State
        self.seats = {
            "CHOP_1": {
                "seat_id": "CHOP_1",
                "seat_name": "Chopping Ping-Pong Seat 1",
                "category": "CHOP_PING_PONG_SEAT",
                "min_rr": 1.85,
                "status": "IDLE", # IDLE or ACTIVE
                "active_position_id": None
            },
            "CHOP_2": {
                "seat_id": "CHOP_2",
                "seat_name": "Chopping Ping-Pong Seat 2",
                "category": "CHOP_PING_PONG_SEAT",
                "min_rr": 1.85,
                "status": "IDLE",
                "active_position_id": None
            },
            "TREND_1": {
                "seat_id": "TREND_1",
                "seat_name": "Normal Trend Runner Seat 1",
                "category": "NORMAL_TREND_RUNNER_SEAT",
                "min_rr": 2.40,
                "status": "IDLE",
                "active_position_id": None
            },
            "TREND_2": {
                "seat_id": "TREND_2",
                "seat_name": "Normal Trend Runner Seat 2",
                "category": "NORMAL_TREND_RUNNER_SEAT",
                "min_rr": 2.40,
                "status": "IDLE",
                "active_position_id": None
            },
            "OPTION_1": {
                "seat_id": "OPTION_1",
                "seat_name": "Nifty/BankNifty Option Seat 1",
                "category": "NIFTY_BANKNIFTY_OPTION_SEAT",
                "min_rr": 2.40,
                "status": "IDLE",
                "active_position_id": None
            },
            "OPTION_2": {
                "seat_id": "OPTION_2",
                "seat_name": "Nifty/BankNifty Option Seat 2",
                "category": "NIFTY_BANKNIFTY_OPTION_SEAT",
                "min_rr": 2.40,
                "status": "IDLE",
                "active_position_id": None
            },
        }

    def calculate_charges(self, price: float, quantity: int, side: str, product: str) -> Dict[str, float]:
        """
        Calculates exact Indian equity charges based on NSE/SEBI tariff schedule:
        - Brokerage: ₹20 flat or 0.03%
        - STT: 0.1% for Delivery (CNC), 0.025% for Intraday (MIS sell only)
        - Exchange Turnover fee: 0.00345%
        - Stamp Duty: 0.015% on Buy orders
        - SEBI Charges: 0.0001% (₹10 / Crore)
        - GST: 18% on (Brokerage + Exchange Fees + SEBI Fees)
        """
        turnover = price * quantity
        
        # Brokerage (Discount broker standard model)
        brokerage = min(20.0, turnover * 0.0003) if product == "MIS" else 0.0
        if product == "MIS" and brokerage < 1.0:
            brokerage = 1.0

        # STT
        if product == "CNC":
            stt = turnover * 0.001
        else:
            stt = turnover * 0.00025 if side == "SELL" else 0.0

        exchange_charges = turnover * 0.0000345
        stamp_duty = (turnover * 0.00015) if side == "BUY" else 0.0
        sebi_charges = turnover * 0.000001
        taxable_services = brokerage + exchange_charges + sebi_charges
        gst = taxable_services * 0.18
        total_charges = brokerage + stt + exchange_charges + stamp_duty + sebi_charges + gst

        return {
            "turnover": round(turnover, 2),
            "brokerage": round(brokerage, 2),
            "stt": round(stt, 2),
            "exchange_charges": round(exchange_charges, 2),
            "stamp_duty": round(stamp_duty, 2),
            "sebi_charges": round(sebi_charges, 2),
            "gst": round(gst, 2),
            "total_charges": round(total_charges, 2)
        }

    def allocate_seat(self, category: str) -> Optional[str]:
        """Finds first available idle seat for the matching category."""
        for seat_id, s in self.seats.items():
            if s["category"] == category and s["status"] == "IDLE":
                return seat_id
        return None

    def place_sniper_order(self, signal: Dict[str, Any], current_ltp: float) -> Dict[str, Any]:
        """
        Places an approved institutional sniper order into an available 2+2+2 seat.
        """
        if not signal.get("approved"):
            return {"success": False, "error": f"Signal vetoed: {signal.get('veto_reason')}"}

        category = signal["seat_category"]
        
        # If it's an index (NIFTY/BANKNIFTY) with an option contract, allocate to OPTION seat first if available
        if signal.get("option_contract_type") in ["CE_CALL_BUY", "PE_PUT_BUY"]:
            opt_seat = self.allocate_seat("NIFTY_BANKNIFTY_OPTION_SEAT")
            if opt_seat:
                seat_id = opt_seat
            else:
                seat_id = self.allocate_seat(category)
        else:
            seat_id = self.allocate_seat(category)

        if not seat_id:
            # Fallback to any idle seat if primary category is filled
            for sid, s in self.seats.items():
                if s["status"] == "IDLE":
                    seat_id = sid
                    break

        if not seat_id:
            return {"success": False, "error": f"All 6 seats are currently occupied! Square off an open seat first."}

        symbol = signal["symbol"]
        clean_symbol = signal.get("clean_symbol") or symbol.replace(".NS", "").replace("^", "")
        action = signal["action"]
        entry_price = signal.get("entry_price") or current_ltp
        sl_price = signal["sl_price"]
        tp_price = signal["tp_price"]
        qty = signal["quantity_lots_or_shares"]
        product = "MIS"

        # Check if option contract
        if "OPTION" in seat_id or signal.get("option_contract_type") in ["CE_CALL_BUY", "PE_PUT_BUY"]:
            # Premium pricing for options: ~0.8% of spot (e.g. ₹200 on Nifty = ₹5,000 margin for 25 lot)
            est_premium = round(entry_price * 0.008, 2)
            strike = signal.get("recommended_strike") or round(entry_price / 50) * 50
            opt_type = "CE" if action == "BUY" else "PE"
            clean_symbol = f"{clean_symbol} {strike} {opt_type}"
            exec_price = est_premium
        else:
            exec_price = entry_price

        # Execute Order
        res = self.place_order(
            symbol=symbol,
            clean_symbol=clean_symbol,
            side="BUY" if "OPTION" in seat_id else action, # Options are always BOUGHT (CE or PE)
            order_type="MARKET",
            product=product,
            quantity=qty,
            price=exec_price,
            current_ltp=exec_price,
            sl_price=sl_price,
            tp_price=tp_price,
            seat_id=seat_id,
            signal_meta=signal
        )

        if res["success"]:
            pos_key = f"{symbol}_{product}"
            self.seats[seat_id]["status"] = "ACTIVE"
            self.seats[seat_id]["active_position_id"] = pos_key
            res["seat_id"] = seat_id

        return res

    def place_order(
        self,
        symbol: str,
        clean_symbol: str,
        side: str,              # "BUY" or "SELL"
        order_type: str,        # "MARKET", "LIMIT", "SL"
        product: str,           # "MIS" (Intraday 5x) or "CNC" (Delivery 1x)
        quantity: int,
        price: float,
        current_ltp: float,
        sl_price: Optional[float] = None,
        tp_price: Optional[float] = None,
        seat_id: Optional[str] = None,
        signal_meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Executes or logs a paper trading order."""
        if quantity <= 0:
            return {"success": False, "error": "Quantity must be greater than 0"}

        if not seat_id:
            if "OPTION" in symbol or symbol.startswith("^"):
                seat_id = self.allocate_seat("NIFTY_BANKNIFTY_OPTION_SEAT")
            else:
                seat_id = self.allocate_seat("NORMAL_TREND_RUNNER_SEAT") or self.allocate_seat("CHOP_PING_PONG_SEAT")

        exec_price = current_ltp if order_type == "MARKET" else price
        turnover = exec_price * quantity
        
        # Margin: MIS gets 5x leverage (20%), CNC requires 100%
        margin_multiplier = 0.20 if product == "MIS" else 1.0
        margin_required = turnover * margin_multiplier

        charges = self.calculate_charges(exec_price, quantity, side, product)
        total_cost = margin_required + charges["total_charges"]

        pos_key = f"{symbol}_{product}"
        current_pos = self.positions.get(pos_key)

        # Basic fund validation for buying
        if side == "BUY" and (not current_pos or current_pos["side"] == "BUY"):
            if current_pos and current_pos["side"] == "BUY":
                return {
                    "success": False,
                    "error": f"DUPLICATE_ORDER_BLOCKED: Already holding {current_pos['quantity']}x {symbol} in seat {current_pos.get('seat_id')}"
                }
            if self.cash < total_cost:
                return {
                    "success": False,
                    "error": f"Insufficient margin: Required ₹{total_cost:,.2f}, Available ₹{self.cash:,.2f}"
                }

        order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        now_ist = datetime.datetime.now(IST).strftime("%H:%M:%S")

        # Update Cash & Positions
        realized_pnl_on_order = None
        if side == "BUY":
            if current_pos and current_pos["side"] == "SELL":
                realized_pnl_on_order = self._close_or_reduce_position(pos_key, quantity, exec_price, charges["total_charges"])
            else:
                self.cash -= total_cost
                if pos_key in self.positions:
                    p = self.positions[pos_key]
                    total_q = p["quantity"] + quantity
                    avg_p = ((p["avg_price"] * p["quantity"]) + (exec_price * quantity)) / total_q
                    p["quantity"] = total_q
                    p["avg_price"] = avg_p
                    p["margin_blocked"] += margin_required
                else:
                    self.positions[pos_key] = {
                        "id": pos_key,
                        "symbol": symbol,
                        "clean_symbol": clean_symbol,
                        "side": "BUY",
                        "product": product,
                        "quantity": quantity,
                        "avg_price": round(exec_price, 2),
                        "current_ltp": round(exec_price, 2),
                        "margin_blocked": round(margin_required, 2),
                        "sl_price": sl_price,
                        "tp_price": tp_price,
                        "seat_id": seat_id,
                        "signal_meta": signal_meta,
                        "entry_time": now_ist,
                        "entry_epoch": time.time(),
                        "hard_locked": True,
                        "trailing_stage": "HANDS_OFF_STAGE (0-35% to Smart TP)",
                        "progress_pct": 0.0
                    }
        else: # SELL
            if current_pos and current_pos["side"] == "BUY":
                realized_pnl_on_order = self._close_or_reduce_position(pos_key, quantity, exec_price, charges["total_charges"])
            else:
                if current_pos and current_pos["side"] == "SELL":
                    return {
                        "success": False,
                        "error": f"DUPLICATE_ORDER_BLOCKED: Already holding short {current_pos['quantity']}x {symbol} in seat {current_pos.get('seat_id')}"
                    }
                if product != "MIS":
                    return {"success": False, "error": "Short selling is only permitted in MIS (Intraday) mode on NSE"}
                if self.cash < total_cost:
                    return {"success": False, "error": f"Insufficient margin for short sell: Required ₹{total_cost:,.2f}"}
                self.cash -= total_cost
                if pos_key in self.positions:
                    p = self.positions[pos_key]
                    total_q = p["quantity"] + quantity
                    avg_p = ((p["avg_price"] * p["quantity"]) + (exec_price * quantity)) / total_q
                    p["quantity"] = total_q
                    p["avg_price"] = avg_p
                    p["margin_blocked"] += margin_required
                else:
                    self.positions[pos_key] = {
                        "id": pos_key,
                        "symbol": symbol,
                        "clean_symbol": clean_symbol,
                        "side": "SELL",
                        "product": product,
                        "quantity": quantity,
                        "avg_price": round(exec_price, 2),
                        "current_ltp": round(exec_price, 2),
                        "margin_blocked": round(margin_required, 2),
                        "sl_price": sl_price,
                        "tp_price": tp_price,
                        "seat_id": seat_id,
                        "signal_meta": signal_meta,
                        "entry_time": now_ist,
                        "entry_epoch": time.time(),
                        "hard_locked": True,
                        "trailing_stage": "HANDS_OFF_STAGE (0-35% to Smart TP)",
                        "progress_pct": 0.0
                    }

        if seat_id and seat_id in self.seats:
            self.seats[seat_id]["status"] = "ACTIVE"
            self.seats[seat_id]["active_position_id"] = pos_key

        filled_amount = round(exec_price * quantity, 2)
        effective_seat_id = seat_id or (current_pos.get("seat_id") if current_pos else None) or "DESK"
        order_record = {
            "order_id": order_id,
            "timestamp": now_ist,
            "symbol": symbol,
            "clean_symbol": clean_symbol,
            "side": side,
            "order_type": order_type,
            "product": product,
            "quantity": quantity,
            "price": round(exec_price, 2),
            "filled_amount": filled_amount,
            "exit_price": round(exec_price, 2) if realized_pnl_on_order is not None else None,
            "realized_pnl": round(realized_pnl_on_order, 2) if realized_pnl_on_order is not None else None,
            "status": "FILLED",
            "seat_id": effective_seat_id,
            "charges": charges
        }
        self.orders.insert(0, order_record)

        return {
            "success": True,
            "order": order_record,
            "portfolio": self.get_portfolio_state({symbol: exec_price})
        }

    def _close_or_reduce_position(self, pos_key: str, quantity: int, exec_price: float, charges: float):
        """Helper to compute realized P&L when reducing or squaring off a position."""
        pos = self.positions[pos_key]
        close_qty = min(quantity, pos["quantity"])
        
        if pos["side"] == "BUY":
            gross_pnl = (exec_price - pos["avg_price"]) * close_qty
        else: # Short position
            gross_pnl = (pos["avg_price"] - exec_price) * close_qty

        net_pnl = gross_pnl - charges
        self.realized_pnl += net_pnl

        margin_freed = (pos["margin_blocked"] / pos["quantity"]) * close_qty
        self.cash += (margin_freed + net_pnl)

        if close_qty >= pos["quantity"]:
            seat_id = pos.get("seat_id")
            if seat_id and seat_id in self.seats:
                self.seats[seat_id]["status"] = "IDLE"
                self.seats[seat_id]["active_position_id"] = None
            del self.positions[pos_key]
        else:
            pos["quantity"] -= close_qty
            pos["margin_blocked"] -= margin_freed

        return net_pnl

    def square_off_position(self, pos_key: str, current_ltp: float) -> Dict[str, Any]:
        """Squares off an open position at market price."""
        if pos_key not in self.positions:
            return {"success": False, "error": "Position not found"}

        pos = self.positions[pos_key]
        exit_side = "SELL" if pos["side"] == "BUY" else "BUY"
        return self.place_order(
            symbol=pos["symbol"],
            clean_symbol=pos["clean_symbol"],
            side=exit_side,
            order_type="MARKET",
            product=pos["product"],
            quantity=pos["quantity"],
            price=current_ltp,
            current_ltp=current_ltp,
            seat_id=pos.get("seat_id") or "DESK"
        )

    def square_off_all_intraday(self, current_ltps: Dict[str, float]) -> List[Dict[str, Any]]:
        """Mandatory 03:18 PM IST auto square-off for all open positions."""
        results = []
        pos_keys = list(self.positions.keys())
        for k in pos_keys:
            p = self.positions.get(k)
            if p:
                ltp = self.resolve_position_ltp(p, current_ltps)
                r = self.square_off_position(k, ltp)
                results.append(r)
        return results

    def reset_account(self):
        """Resets paper account to starting ₹1,00,000 state."""
        self.cash = self.initial_capital
        self.positions = {}
        self.orders = []
        self.realized_pnl = 0.0
        for s in self.seats.values():
            s["status"] = "IDLE"
            s["active_position_id"] = None

    @staticmethod
    def resolve_position_ltp(p: Dict[str, Any], current_ltps: Dict[str, float]) -> float:
        sym = p.get("symbol", "")
        clean = p.get("clean_symbol", sym).replace(".NS", "").replace("_MIS", "").strip()
        avg_price = float(p.get("avg_price", 0.0))

        # 1. Exact direct match
        if sym in current_ltps and current_ltps[sym] > 0:
            return current_ltps[sym]
        if clean in current_ltps and current_ltps[clean] > 0:
            return current_ltps[clean]

        # 2. Check if option contract
        is_ce = clean.endswith("CE") or " CE" in clean or "_CE" in clean
        is_pe = clean.endswith("PE") or " PE" in clean or "_PE" in clean
        if not (is_ce or is_pe):
            return current_ltps.get(sym, avg_price)

        opt_type = "CE" if is_ce else "PE"

        # Extract underlying symbol and strike (supporting 2026 format: e.g. MARUTI29DEC2612700CE)
        m1 = re.match(r"^([A-Z_&]+)[_\s]+(\d+(?:\.\d+)?)[_\s]*(CE|PE)?$", clean)
        m2 = re.match(r"^([A-Z_&]+)\d{2}[A-Z]{3}(?:\d{2})?(\d+(?:\.\d+)?)(CE|PE)$", clean)
        m3 = re.match(r"^([A-Z]+).*?(\d+)(CE|PE)$", clean)

        und_sym = None
        strike = None
        if m1:
            und_sym = m1.group(1).replace("_", "")
            strike = float(m1.group(2))
        elif m2:
            und_sym = m2.group(1)
            strike = float(m2.group(2))
        elif m3:
            und_sym = m3.group(1)
            strike = float(m3.group(2))
        else:
            return avg_price

        # Map to spot quote candidates
        candidates = [
            und_sym,
            f"{und_sym}.NS",
            f"NSE:{und_sym}",
            f"BSE:{und_sym}",
            f"^{und_sym}",
            "^NSEI" if und_sym in ("NIFTY", "NIFTY50") else None,
            "^NSEBANK" if und_sym in ("BANKNIFTY", "BANK_NIFTY") else None,
            "^BSESN" if und_sym == "SENSEX" else None,
            "^CNXIT" if und_sym == "CNXIT" else None,
            "NIFTY 50" if und_sym == "NIFTY" else None,
            "BANK NIFTY" if und_sym == "BANKNIFTY" else None,
        ]

        und_ltp = None
        for c in candidates:
            if c and c in current_ltps and current_ltps[c] > 0:
                und_ltp = current_ltps[c]
                break

        if not und_ltp or not strike:
            return avg_price

        # Track entry spot price
        if "entry_spot" not in p or not p["entry_spot"]:
            # If entering ATM, entry spot was near strike or current underlying
            p["entry_spot"] = und_ltp

        entry_spot = float(p.get("entry_spot") or und_ltp)
        spot_move = (und_ltp - entry_spot) if opt_type == "CE" else (entry_spot - und_ltp)

        # 100% Real Live Option LTP from Exchange (Zero Synthetic Formula)
        for opt_key in (sym, p.get("clean_symbol"), f"{sym}.NS"):
            if opt_key and opt_key in current_ltps and current_ltps[opt_key] > 0:
                return float(current_ltps[opt_key])

        return avg_price

    def update_trailing_brackets(self, current_ltps: Dict[str, float]) -> List[Dict[str, Any]]:
        """Runs the Brokerage-Shielded + Institutional Profit Lock ladder on all open positions."""
        updates = []
        for pos_key, p in self.positions.items():
            if not p.get("sl_price") or not p.get("tp_price"):
                continue

            sym = p["symbol"]
            ltp = self.resolve_position_ltp(p, current_ltps)
            is_opt = "OPTION" in str(p.get("seat_id", "")) or "CE" in str(p.get("clean_symbol", "")) or "PE" in str(p.get("clean_symbol", ""))
            eval_res = IndianMarketMasterSniper.evaluate_live_trailing_bracket(
                action=p["side"],
                entry_price=p["avg_price"],
                current_ltp=ltp,
                current_sl_price=p["sl_price"],
                tp_price=p["tp_price"],
                tick_size=0.05,
                quantity=p.get("quantity", 1),
                is_option=is_opt,
                symbol=sym
            )

            p["trailing_stage"] = eval_res["stage_note"]
            p["progress_pct"] = eval_res["progress_pct"]
            if eval_res["should_modify_sl"]:
                p["sl_price"] = eval_res["new_sl_price"]
                updates.append({
                    "position_id": pos_key,
                    "symbol": sym,
                    "new_sl": eval_res["new_sl_price"],
                    "note": eval_res["stage_note"],
                    "stage": eval_res.get("stage", 0)
                })
        return updates

    def get_portfolio_state(self, current_ltps: Dict[str, float]) -> Dict[str, Any]:
        """Calculates live marked-to-market unrealized P&L and total portfolio value."""
        unrealized_pnl = 0.0
        total_margin_used = 0.0
        positions_list = []

        self.update_trailing_brackets(current_ltps)

        # Master Exit Management is handled authoritatively by the Node Daemon (server.ts)
        # using live unadjusted TradingView quotes and DiamondHandsHoldManager.
        # Python backend records positions and executes explicit square-offs via /api/orders/square-off.

        for k, p in self.positions.items():
            sym = p["symbol"]
            ltp = self.resolve_position_ltp(p, current_ltps)
            p["current_ltp"] = round(ltp, 2)
            qty = p["quantity"]
            avg = p["avg_price"]

            if p["side"] == "BUY":
                m2m = (ltp - avg) * qty
                pct = ((ltp - avg) / avg * 100.0) if avg else 0.0
            else:
                m2m = (avg - ltp) * qty
                pct = ((avg - ltp) / avg * 100.0) if avg else 0.0

            unrealized_pnl += m2m
            total_margin_used += p["margin_blocked"]

            positions_list.append({
                **p,
                "pnl": round(m2m, 2),
                "pnl_pct": round(pct, 2),
                "current_value": round(ltp * qty, 2),
                "is_positive": m2m >= 0
            })

        net_equity = self.cash + total_margin_used + unrealized_pnl
        total_pnl = self.realized_pnl + unrealized_pnl
        total_pnl_pct = round((total_pnl / self.initial_capital) * 100.0, 2)
        target_progress_pct = round(min(100.0, max(0.0, (total_pnl / self.daily_target) * 100.0)), 1)

        return {
            "initial_capital": self.initial_capital,
            "daily_target": self.daily_target,
            "max_risk_per_trade": self.max_risk_per_trade,
            "target_progress_pct": target_progress_pct,
            "cash": round(self.cash, 2),
            "margin_used": round(total_margin_used, 2),
            "available_margin": round(self.cash, 2),
            "net_equity": round(net_equity, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": total_pnl_pct,
            "is_positive": total_pnl >= 0,
            "positions": positions_list,
            "positions_count": len(positions_list),
            "orders": [
                {
                    **o,
                    "filled_amount": round(o.get("filled_amount") or (o.get("price", 0.0) * o.get("quantity", 1)), 2)
                }
                for o in self.orders[:100]
            ],
            "seats": list(self.seats.values())
        }

# Global Singleton
portfolio_engine = PortfolioEngine()
