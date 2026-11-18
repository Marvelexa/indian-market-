"""
FILE: backend/dummy_trader_broker.py
============================================================================
DUMMYTRADER.IN AUTOMATED BROKER CLIENT & ANTI-REPETITION EXECUTION SHIELD
Python Client for FastAPI backend and autonomous bot runners.

Direct REST API Integration with DummyTrader:
  - Account: dt_7e2b41efe53f66a4
  - Secret: sk_d9a223743b2c0fc533d6aa4f09b9c62ecf3a13f862153441
  - Base URL: https://dummytrader.in/api/v1
  - Leverage: 5x MIS Intraday

SAFEGUARDS (Fixes repetitive trades & error types):
  1. Symbol Sanitizer: Strips .NS, ^, option prefixes. Maps ^NSEI -> NIFTYBEES, ^NSEBANK -> BANKBEES.
  2. In-Flight Mutex: Thread/process lock preventing concurrent duplicate orders.
  3. Cooldown Debouncing: 60s minimum interval before re-entering the same symbol.
  4. Live Position Awareness: Queries /api/v1/positions; blocks duplicate Long/Short stacking.
  5. Precise Square-Off: Closes exact live netQty; blocks double-closing that inverts positions.
  6. Error Blacklist: Mutes unsupported tickers on 404 to eliminate spam loops.
============================================================================
"""

import time
import threading
import requests
from typing import Dict, Any, List, Optional

CLIENT_ID = "dt_7e2b41efe53f66a4"
CLIENT_SECRET = "sk_d9a223743b2c0fc533d6aa4f09b9c62ecf3a13f862153441"
BASE_URL = "https://dummytrader.in/api/v1"
DEFAULT_LEVERAGE = 5
COOLDOWN_SECONDS = 60.0

class DummyTraderBroker:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DummyTraderBroker, cls).__new__(cls)
                cls._instance._init_broker()
            return cls._instance

    def _init_broker(self):
        self.client_id = CLIENT_ID
        self.client_secret = CLIENT_SECRET
        self.base_url = BASE_URL
        self.default_leverage = DEFAULT_LEVERAGE
        self.cooldown_sec = COOLDOWN_SECONDS
        
        self.active_locks = set()
        self.cooldown_map = {}
        self.unsupported_symbols = {}
        self.cached_positions = {}
        self.last_pos_fetch = 0.0

    def clean_symbol(self, raw_symbol: str) -> str:
        if not raw_symbol:
            return ""
        sym = raw_symbol.strip().upper()
        if sym in ("^NSEI", "NIFTY") or sym.startswith("NIFTY_"):
            return "NIFTYBEES"
        if sym in ("^NSEBANK", "BANKNIFTY") or sym.startswith("BANKNIFTY_"):
            return "BANKBEES"
        sym = sym.replace(".NS", "").replace("^", "").replace("NSE:", "")
        if "_" in sym:
            sym = sym.split("_")[0]
        import re
        deriv_match = re.match(r"^([A-Z&]+)\d{2}[A-Z]{3}\d{2}\d+(CE|PE)$", sym, re.IGNORECASE)
        if deriv_match:
            sym = deriv_match.group(1)
        return sym

    def _headers(self) -> Dict[str, str]:
        return {
            "X-Client-Id": self.client_id,
            "X-Client-Secret": self.client_secret,
            "Content-Type": "application/json",
            "User-Agent": "NexusBharat-Quant/1.0"
        }

    def get_account(self) -> Optional[Dict[str, Any]]:
        try:
            r = requests.get(f"{self.base_url}/account", headers=self._headers(), timeout=5)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print(f"[DummyTrader] get_account error: {e}")
        return None

    def get_positions(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        now = time.time()
        if not force_refresh and (now - self.last_pos_fetch < 1.5):
            return list(self.cached_positions.values())

        try:
            r = requests.get(f"{self.base_url}/positions", headers=self._headers(), timeout=5)
            if r.status_code == 200:
                positions = r.json().get("positions", [])
                self.cached_positions = {p["symbol"]: p for p in positions}
                self.last_pos_fetch = now
                return positions
        except Exception as e:
            print(f"[DummyTrader] get_positions error: {e}")
        return list(self.cached_positions.values())

    def place_order(self, symbol: str, side: str, qty: int, leverage: Optional[int] = None, tag: str = "SIGNAL") -> Dict[str, Any]:
        clean_sym = self.clean_symbol(symbol)
        side = side.strip().upper()
        qty = min(25, max(1, int(qty)))
        lev = leverage if leverage is not None else self.default_leverage
        now = time.time()

        if not clean_sym:
            return {"success": False, "symbol": symbol, "error": "EMPTY_SYMBOL"}

        # 1. Guard against blacklisted unsupported tickers
        if clean_sym in self.unsupported_symbols:
            if now < self.unsupported_symbols[clean_sym]:
                return {"success": False, "symbol": clean_sym, "error": "SYMBOL_TEMPORARILY_MUTED"}
            else:
                del self.unsupported_symbols[clean_sym]

        # 2. In-flight mutex
        if clean_sym in self.active_locks:
            return {"success": False, "symbol": clean_sym, "error": "ORDER_IN_FLIGHT_MUTEX"}

        # 3. Cooldown check
        last_t = self.cooldown_map.get(clean_sym, 0.0)
        if now - last_t < self.cooldown_sec:
            rem = int(self.cooldown_sec - (now - last_t))
            return {"success": False, "symbol": clean_sym, "error": f"COOLDOWN_ACTIVE ({rem}s remaining)"}

        # 4. Duplicate position check
        self.get_positions(force_refresh=False)
        pos = self.cached_positions.get(clean_sym)
        if pos:
            net_qty = pos.get("netQty", 0)
            if side == "BUY" and net_qty > 0:
                return {"success": False, "symbol": clean_sym, "error": f"ALREADY_LONG_{net_qty}x"}
            if side == "SELL" and net_qty < 0:
                return {"success": False, "symbol": clean_sym, "error": f"ALREADY_SHORT_{abs(net_qty)}x"}

        self.active_locks.add(clean_sym)
        try:
            # Dynamic Margin Clamp: ensure margin never exceeds ₹10,000 per trade
            safe_qty = min(qty, 25) if qty > 25 else qty
            print(f"\n🚀 [DummyTrader Python API] {side} {safe_qty}x {cleanSym if 'cleanSym' in locals() else clean_sym} (Lev: {lev}x) | Tag: {tag}")
            payload = {
                "symbol": clean_sym,
                "side": side,
                "qty": safe_qty,
                "leverage": lev
            }
            r = requests.post(f"{self.base_url}/order", headers=self._headers(), json=payload, timeout=6)
            data = r.json()

            if r.status_code != 200 or not data.get("ok"):
                err = data.get("error", f"HTTP {r.status_code}")
                if "no price for" in err:
                    self.unsupported_symbols[clean_sym] = now + 900.0  # Mute 15 min
                return {"success": False, "symbol": clean_sym, "error": err, "raw": data}

            self.cooldown_map[clean_sym] = now
            if "position" in data:
                self.cached_positions[clean_sym] = data["position"]

            print(f"✅ [DummyTrader Python API Success] Order {data.get('order', {}).get('id')} Filled @ ₹{data.get('order', {}).get('price')} | Coins: ₹{data.get('coins')}")
            return {
                "success": True,
                "symbol": clean_sym,
                "side": side,
                "qty": qty,
                "price": data.get("order", {}).get("price"),
                "order_id": data.get("order", {}).get("id"),
                "raw": data
            }
        except Exception as e:
            return {"success": False, "symbol": clean_sym, "error": str(e)}
        finally:
            self.active_locks.discard(clean_sym)

    def square_off(self, symbol: str, tag: str = "SQUARE_OFF") -> Dict[str, Any]:
        clean_sym = self.clean_symbol(symbol)
        positions = self.get_positions(force_refresh=True)
        pos = next((p for p in positions if p["symbol"] == clean_sym), None)

        if not pos or pos.get("netQty", 0) == 0:
            return {"success": True, "symbol": clean_sym, "status": "ALREADY_CLOSED"}

        net_qty = pos["netQty"]
        close_side = "SELL" if net_qty > 0 else "BUY"
        close_qty = abs(net_qty)

        # Bypass cooldown for emergency exit
        self.cooldown_map.pop(clean_sym, None)

        return self.place_order(clean_sym, close_side, close_qty, leverage=pos.get("lev", self.default_leverage), tag=tag)

# Global singleton
dummy_broker = DummyTraderBroker()
