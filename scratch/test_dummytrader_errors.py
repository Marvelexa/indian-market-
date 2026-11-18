import requests

headers = {
    "X-Client-Id": "dt_7e2b41efe53f66a4",
    "X-Client-Secret": "sk_d9a223743b2c0fc533d6aa4f09b9c62ecf3a13f862153441",
    "Content-Type": "application/json"
}

tests = [
    ("Invalid Symbol", {"symbol": "INVALID_XYZ", "side": "BUY", "qty": 10, "leverage": 5}),
    ("Zero Qty", {"symbol": "RELIANCE", "side": "BUY", "qty": 0, "leverage": 5}),
    ("Negative Qty", {"symbol": "RELIANCE", "side": "BUY", "qty": -5, "leverage": 5}),
    ("Invalid Side", {"symbol": "RELIANCE", "side": "HOLD", "qty": 10, "leverage": 5}),
    ("Excessive Qty (insufficient funds)", {"symbol": "RELIANCE", "side": "BUY", "qty": 1000000, "leverage": 5}),
    ("Zero Leverage", {"symbol": "RELIANCE", "side": "BUY", "qty": 10, "leverage": 0}),
    ("Negative Leverage", {"symbol": "RELIANCE", "side": "BUY", "qty": 10, "leverage": -1}),
    ("High Leverage", {"symbol": "RELIANCE", "side": "BUY", "qty": 10, "leverage": 100}),
]

print("--- DUMMYTRADER ERROR TYPES TEST ---")
for name, payload in tests:
    try:
        r = requests.post("https://dummytrader.in/api/v1/order", headers=headers, json=payload, timeout=5)
        print(f"[{name}] Status: {r.status_code} | Body: {r.text.strip()}")
    except Exception as e:
        print(f"[{name}] Exception: {e}")

# Test invalid secret
r_auth = requests.post("https://dummytrader.in/api/v1/order", headers={"X-Client-Id": "dt_7e2b41efe53f66a4", "X-Client-Secret": "wrong_secret", "Content-Type": "application/json"}, json={"symbol": "RELIANCE", "side": "BUY", "qty": 10, "leverage": 5})
print(f"[Invalid Auth] Status: {r_auth.status_code} | Body: {r_auth.text.strip()}")
