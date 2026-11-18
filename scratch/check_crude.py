import urllib.request
import json

res = urllib.request.urlopen("http://127.0.0.1:3006/api/mcx/status", timeout=3)
data = json.loads(res.read().decode())
crude = [p for p in data["activePositions"] if p["commoditySymbol"] == "CRUDEOIL"]
print("Active Crude positions:", len(crude))
if crude:
    c = crude[0]
    print(f"Symbol: {c['optionSymbol']}")
    print(f"Entry Premium: ₹{c['entryPremium']}")
    print(f"Current Live Premium: ₹{c['currentPremium']}")
    print(f"Unrealized PnL: ₹{c['unrealizedPnlInr']}")
    print(f"Locked Profit: ₹{c['lockedProfitInr']}")
    print(f"Ladder Stage: {c['ladderStage']}")
    print(f"Peak Profit seen: ₹{c['peakProfitInr']}")
    print(f"Current Trailing SL: ₹{c['currentSlPremium']}")

# Also print underlying spot
if "CRUDEOIL" in data.get("sr15mMatrix", {}):
    spot = data["sr15mMatrix"]["CRUDEOIL"]["underlyingLtp"]
    print(f"Crude Oil Underlying Spot LTP: ₹{spot}")
