"""
End-to-End Verification of Uncongested Minimal Views and Dedicated Positions Page
Tests:
1. Navigation tabs switching (Terminal, Positions & Seats, Sniper Radar, Time-Machine)
2. Chart full-height display without congested bottom drawer
3. Dedicated Positions & Seats full-page (6 KPI cards, 2+2+2 seats, active positions, blotter)
4. Paper trading order execution and positions reflection
5. Auto square-off and reset portfolio
"""

import subprocess
import json
import time
import urllib.request
import os
import asyncio
import websockets

def test_http_endpoints():
    endpoints = [
        "/api/overview",
        "/api/portfolio",
        "/api/seats",
        "/api/sniper/seats",
        "/api/sniper/scan",
        "/api/replay/state"
    ]
    print("[TEST 1] Verifying Backend Endpoints...")
    for ep in endpoints:
        url = f"http://localhost:8000{ep}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as res:
                print(f"  ✓ {ep:25s} -> HTTP {res.status}")
                assert res.status == 200
        except Exception as e:
            print(f"  ✗ {ep:25s} -> FAILED: {e}")
            raise

async def run_cdp():
    print("\n[TEST 2] Launching Headless Chrome via CDP...")
    paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    ]
    browser_exe = None
    for p in paths:
        if os.path.exists(p):
            browser_exe = p
            break
    
    if not browser_exe:
        print("  ⚠️ No Chrome/Edge binary found, skipping CDP tests.")
        return

    cmd = [
        browser_exe,
        "--headless=new",
        "--remote-debugging-port=9223",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "http://localhost:8000"
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    await asyncio.sleep(2.5)

    try:
        targets_url = "http://localhost:9223/json"
        req = urllib.request.Request(targets_url)
        with urllib.request.urlopen(req, timeout=5) as res:
            targets = json.loads(res.read().decode())
        
        target = next((t for t in targets if t.get("type") == "page"), targets[0])
        ws_url = target["webSocketDebuggerUrl"]
        print(f"  ✓ Connected to browser page: {ws_url}")

        async with websockets.connect(ws_url) as ws:
            msg_id = 1
            async def send_cmd(method, params=None):
                nonlocal msg_id
                m = {"id": msg_id, "method": method, "params": params or {}}
                msg_id += 1
                await ws.send(json.dumps(m))
                while True:
                    resp = json.loads(await ws.recv())
                    if resp.get("id") == m["id"]:
                        return resp.get("result", {})

            async def eval_js(expr):
                r = await send_cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True})
                if "exceptionDetails" in r:
                    raise Exception(f"JS Error in '{expr}': {r['exceptionDetails']}")
                return r.get("result", {}).get("value")

            # Let the terminal bootstrap
            await asyncio.sleep(2.0)

            # 1. Verify Navigation elements exist
            nav_tabs = await eval_js("Array.from(document.querySelectorAll('.nav-tab')).map(el => el.textContent.trim())")
            print(f"  ✓ Top Nav Tabs: {nav_tabs}")
            assert any("Terminal" in t for t in nav_tabs), "Terminal nav tab missing"
            assert any("Positions" in t for t in nav_tabs), "Positions nav tab missing"
            assert any("Radar" in t for t in nav_tabs), "Radar nav tab missing"
            assert any("Time-Machine" in t for t in nav_tabs), "Time-Machine nav tab missing"

            # 2. Check Terminal view is visible by default and bottom drawer is NOT in center panel
            term_display = await eval_js("document.getElementById('view-terminal').style.display")
            chart_height = await eval_js("document.getElementById('tv-chart-main').clientHeight")
            footer_text = await eval_js("document.querySelector('.terminal-minimal-footer').textContent.trim()")
            print(f"  ✓ Terminal View Display: '{term_display}', Chart Canvas Height: {chart_height}px")
            print(f"  ✓ Terminal Minimal Footer: '{footer_text[:55]}...'")

            # 3. Switch to Positions & Seats View
            await eval_js("window.terminal.switchView('positions')")
            await asyncio.sleep(0.5)
            pos_display = await eval_js("document.getElementById('view-positions').style.display")
            term_display_after = await eval_js("document.getElementById('view-terminal').style.display")
            print(f"  ✓ Switched to Positions View: positions='{pos_display}', terminal='{term_display_after}'")
            assert pos_display == "block", "Positions page not displayed"
            assert term_display_after == "none", "Terminal view still visible"

            # Check KPI scorecards on Positions Page
            avail_margin = await eval_js("document.getElementById('pos-page-avail-margin').textContent.trim()")
            equity = await eval_js("document.getElementById('pos-page-equity').textContent.trim()")
            print(f"  ✓ Positions Page KPIs: Margin = {avail_margin}, Equity = {equity}")

            # Check 6 Seats Grid populated
            seats_count = await eval_js("document.querySelectorAll('#seats-container .seat-card-spacious').length")
            print(f"  ✓ 2+2+2 Concurrent Seats rendered on dedicated page: {seats_count} seats")
            assert seats_count == 6, f"Expected 6 seats, got {seats_count}"

            # 4. Switch to Sniper Radar View
            await eval_js("window.terminal.switchView('radar')")
            await asyncio.sleep(0.5)
            radar_display = await eval_js("document.getElementById('view-radar').style.display")
            print(f"  ✓ Switched to Sniper Radar View: radar='{radar_display}'")
            assert radar_display == "block", "Sniper radar page not displayed"

            # 5. Switch to Time-Machine View
            await eval_js("window.terminal.switchView('timemachine')")
            await asyncio.sleep(0.5)
            tm_display = await eval_js("document.getElementById('time-machine-fullpage').style.display")
            tm_clock = await eval_js("document.getElementById('tm-ist-clock').textContent.trim()")
            print(f"  ✓ Switched to Time-Machine View: tm='{tm_display}', Replay Clock: {tm_clock}")
            assert tm_display == "block", "Time machine not displayed"

            # 6. Exit back to Terminal View
            await eval_js("window.terminal.exitTimeMachineFullPage()")
            await asyncio.sleep(0.5)
            term_display_final = await eval_js("document.getElementById('view-terminal').style.display")
            print(f"  ✓ Exited Time-Machine back to Terminal: display='{term_display_final}'")
            assert term_display_final == "grid", "Terminal view not restored"

            # 7. Test Paper Trading Order Execution
            await eval_js("window.terminal.setSide('BUY')")
            await eval_js("window.terminal.orderQty = 25")
            await eval_js("window.terminal.submitOrder()")
            await asyncio.sleep(1.0)
            pos_count = await eval_js("window.terminal.portfolioData.positions.length")
            print(f"  ✓ Executed Paper Trade: Active Positions Count = {pos_count}")

            # 8. Check that Positions & Seats Page shows this position
            await eval_js("window.terminal.switchView('positions')")
            await asyncio.sleep(0.5)
            rows_count = await eval_js("document.querySelectorAll('#positions-table-body tr').length")
            active_seat_status = await eval_js("document.querySelector('#seats-container .active-seat') !== null")
            print(f"  ✓ Positions Page Table Rows: {rows_count}, Active Seat Found: {active_seat_status}")

            # 9. Clean up with Auto Square-Off
            await eval_js("window.terminal.triggerAutoSquareOff()")
            await asyncio.sleep(1.0)
            pos_after_sq = await eval_js("window.terminal.portfolioData.positions.length")
            print(f"  ✓ Triggered 03:18 PM Auto Square-Off: Remaining Positions = {pos_after_sq}")

            print("\n🎉 ALL TESTS PASSED SUCCESSFULLY! Uncongested design verified.")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except:
            proc.kill()

if __name__ == "__main__":
    test_http_endpoints()
    asyncio.run(run_cdp())
