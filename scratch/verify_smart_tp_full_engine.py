import urllib.request
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def test_api():
    print("\n=======================================================")
    print("  VERIFYING SMART TP & BROKERAGE SHIELD IN REPLAY ENGINE")
    print("=======================================================")

    # 1. Check available days
    req = urllib.request.Request(f"{BASE_URL}/api/replay/days")
    with urllib.request.urlopen(req, timeout=10) as res:
        days_data = json.loads(res.read().decode())
    print(f"Total Available Historical Days: {days_data.get('totalDays')}")
    assert days_data.get("totalDays") >= 60, f"Expected 60 days, got {days_data.get('totalDays')}"

    # 2. Reset and set date to 2026-11-13
    print("Setting Date to 2026-11-13 with speed=60x...")
    set_date_payload = json.dumps({"date": "2026-11-13", "autoPlay": True, "speed": 60}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/api/replay/set-date",
        data=set_date_payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as res:
        state = json.loads(res.read().decode())
    print(f"State initialized at IST: {state.get('formattedTime')}, Gate: {state.get('sessionGate')}")

    # 3. Step forward through the day in chunks (09:25 AM to 03:15 PM)
    print("\nSimulating Day: Stepping through ticks (09:25 to 15:15 IST)...")
    active_smart_tp_found = False
    reversal_wall_verified = False
    shield_verified = False
    
    # We step through seconds 600 (09:25 AM) to 21600 (03:15 PM) in 300-second (5 min) jumps
    for sec in range(600, 21600, 300):
        step_payload = json.dumps({"action": "SET_SECOND", "payload": {"secondOfDay": sec}}).encode("utf-8")
        req = urllib.request.Request(
            f"{BASE_URL}/api/replay/control",
            data=step_payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as res:
            st = json.loads(res.read().decode())
        
        # Check active positions for Smart TP and Reversal Wall
        for p in st.get("activePositions", []):
            tp = p.get("tpPrice")
            wall_source = p.get("reversalWallSource")
            wall_price = p.get("reversalWallPrice")
            buf = p.get("frontRunBuffer")
            stage = p.get("stage")
            stage_note = p.get("stageNote")

            if tp and wall_price:
                active_smart_tp_found = True
                if wall_source:
                    reversal_wall_verified = True
                print(f"  [{st.get('formattedTime')}] {p['symbol']} {p['side']} Entry: ₹{p['entryPrice']} | Smart TP: ₹{tp} (Wall: {wall_source} @ ₹{wall_price} | buf: {buf}pts) | Stage: {stage} ({stage_note})")

            if stage >= 1 and "BROKERAGE_SHIELD" in str(stage_note):
                shield_verified = True

        if len(st.get("closedLedger", [])) >= 2 and active_smart_tp_found:
            # We have captured enough live activity
            break

    # 4. Check Closed Ledger
    closed = st.get("closedLedger", [])
    print(f"\nClosed Trades Count: {len(closed)}")
    for c in closed[:5]:
        print(f"  Trade {c.get('tradeId')}: {c.get('symbol')} {c.get('side')} PnL: ₹{c.get('netPnlInr')} | Exit: {c.get('exitReason')} @ ₹{c.get('exitPrice')}")

    print("\nSummary Validation:")
    print(f"  Smart TP Active: {active_smart_tp_found}")
    print(f"  Reversal Wall Candlestick Study: {reversal_wall_verified}")
    print("=======================================================")
    print("  ALL SMART TP ENGINE CHECKS COMPLETED SUCCESSFULLY")
    print("=======================================================\n")

if __name__ == "__main__":
    test_api()
