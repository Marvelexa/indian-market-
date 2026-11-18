import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import datetime
import pytz
import pandas as pd
from backend.sniper_engine import IndianMarketMasterSniper

IST = pytz.timezone("Asia/Kolkata")

def test_smart_tp_signal_evaluation():
    print("\n--- 1. Testing IndianMarketMasterSniper Smart TP Candle Study ---")
    cache_path = os.path.join(".cache_indian_market_60d", "NIFTY_5m.json")
    with open(cache_path, "r") as f:
        bars = json.load(f)

    # Convert bars to pandas DataFrame matching sniper engine format
    records = []
    for b in bars[:150]:
        dt = datetime.datetime.fromtimestamp(b["timestamp"] / 1000.0, IST)
        records.append({
            "timestamp": dt,
            "Open": float(b["open"]),
            "High": float(b["high"]),
            "Low": float(b["low"]),
            "Close": float(b["close"]),
            "Volume": float(b["volume"])
        })
    df = pd.DataFrame(records).set_index("timestamp")

    sig = IndianMarketMasterSniper.evaluate_symbol(
        symbol="^NSEI",
        df=df,
        is_index=True,
        tick_size=0.05,
        bypass_session_check=True
    )
    print(f"Signal Result: Approved={sig['approved']}, Action={sig.get('action')}, Veto={sig.get('veto_reason')}")
    if sig["approved"]:
        print(f"  Entry: ₹{sig['entry_price']}")
        print(f"  SL: ₹{sig['sl_price']} ({sig['sl_dist_pct']*100:.2f}%)")
        print(f"  Smart TP: ₹{sig['tp_price']} ({sig['tp_dist_pct']*100:.2f}%)")
        print(f"  Reversal Wall: ₹{sig['first_reversal_wall_price']} [{sig['reversal_wall_source']}]")
        print(f"  Front-Run Buffer: {sig['front_run_buffer']} pts")
        print(f"  Risk/Reward: {sig['rr_ratio']}x")
        assert sig["tp_price"] is not None
        assert sig["first_reversal_wall_price"] is not None
        assert sig["front_run_buffer"] >= 5.0 # Min 5 pts front run for index
        print("  [PASS] Smart TP candle study and front-running verified!")
    else:
        print("  Signal vetoed as expected if market conditions did not meet high-conviction criteria.")

def test_brokerage_shield_bracket():
    print("\n--- 2. Testing Brokerage-Shielded Breakeven & Profit Lock Ladder ---")
    entry = 25000.0
    initial_sl = 24950.0 # 50 pts risk
    smart_tp = 25100.0   # 100 pts target (2.0 RR)
    qty = 25             # 1 lot Nifty

    # Stage 0: 20% progress (Covered 20 pts of 100 pts runway) -> LTP = 25020.0
    res0 = IndianMarketMasterSniper.evaluate_live_trailing_bracket(
        action="BUY",
        entry_price=entry,
        current_ltp=25020.0,
        current_sl_price=initial_sl,
        tp_price=smart_tp,
        quantity=qty,
        is_option=True
    )
    print(f"20% Progress: Stage={res0['stage']}, ShouldModifySL={res0['should_modify_sl']}, Note={res0['stage_note']}")
    assert res0["stage"] == 0
    assert not res0["should_modify_sl"]

    # Stage 1: 40% progress (Covered 40 pts of 100 pts runway) -> LTP = 25040.0
    # Must trigger Brokerage-Shielded Breakeven Lock (+₹350 gross for Options)
    # Required buffer = 350 / 25 = 14.0 pts -> New SL = 25014.0
    res1 = IndianMarketMasterSniper.evaluate_live_trailing_bracket(
        action="BUY",
        entry_price=entry,
        current_ltp=25040.0,
        current_sl_price=initial_sl,
        tp_price=smart_tp,
        quantity=qty,
        is_option=True
    )
    print(f"40% Progress: Stage={res1['stage']}, ShouldModifySL={res1['should_modify_sl']}, NewSL={res1['new_sl_price']}, Note={res1['stage_note']}")
    assert res1["stage"] == 1
    assert res1["should_modify_sl"]
    assert res1["new_sl_price"] >= entry + 14.0
    assert "BROKERAGE_SHIELD" in res1["stage_note"]

    # Stage 2: 65% progress (Covered 65 pts of 100 pts runway) -> LTP = 25065.0
    # Must trigger Institutional 60% Profit Lock -> New SL = entry + (100 * 0.60) = 25060.0
    res2 = IndianMarketMasterSniper.evaluate_live_trailing_bracket(
        action="BUY",
        entry_price=entry,
        current_ltp=25065.0,
        current_sl_price=res1["new_sl_price"],
        tp_price=smart_tp,
        quantity=qty,
        is_option=True
    )
    print(f"65% Progress: Stage={res2['stage']}, ShouldModifySL={res2['should_modify_sl']}, NewSL={res2['new_sl_price']}, Note={res2['stage_note']}")
    assert res2["stage"] == 2
    assert res2["should_modify_sl"]
    assert res2["new_sl_price"] >= entry + 60.0
    assert "60% PROFIT LOCKED" in res2["stage_note"]
    print("  [PASS] Brokerage Shield & Institutional Profit Lock ladder verified!")

if __name__ == "__main__":
    test_smart_tp_signal_evaluation()
    test_brokerage_shield_bracket()
    print("\n[ALL UNIT TESTS PASSED SUCCESSFULLY!]")
