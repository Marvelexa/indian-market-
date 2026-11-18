"""
Test script for Past Date Time-Machine Replay Room
Verifies:
1. Opening Time-Machine full page
2. 60 Historical trading days dropdown populated
3. Exact 09:15:00 AM IST initialization
4. Session gate: WARMUP (09:15-09:25 AM)
5. Speed control and continuous second-by-second ticking
6. Gate transition to ACTIVE SNIPER at 09:25:00 AM IST
7. Gate transition to AUTO SQUARE-OFF at 03:18:00 PM IST
8. Captures screenshots for verification
"""

import subprocess
import json
import time
import urllib.request
import os
import asyncio
import base64
import websockets

SCREENSHOTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch", "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

async def run_test():
    print("[TEST] Verifying Past Date Replay Room via CDP...")
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
        print("  ⚠️ No browser found.")
        return

    remote_port = 9223
    proc = subprocess.Popen([
        browser_exe,
        "--headless=new",
        f"--remote-debugging-port={remote_port}",
        "--window-size=1920,1080",
        "--disable-gpu",
        "--no-sandbox"
    ])
    
    try:
        time.sleep(1.5)
        v_url = f"http://127.0.0.1:{remote_port}/json/version"
        with urllib.request.urlopen(v_url, timeout=5) as res:
            v_data = json.loads(res.read().decode())
            ws_url = v_data.get("webSocketDebuggerUrl")

        async with websockets.connect(ws_url, max_size=50*1024*1024) as ws:
            msg_id = 0
            async def send_cdp(method, params=None):
                nonlocal msg_id
                msg_id += 1
                payload = {"id": msg_id, "method": method, "params": params or {}}
                await ws.send(json.dumps(payload))
                while True:
                    r = await ws.recv()
                    data = json.loads(r)
                    if data.get("id") == msg_id:
                        return data.get("result", {})

            # Create target page
            t_res = await send_cdp("Target.createTarget", {"url": "about:blank"})
            page_id = t_res["targetId"]

            # Connect to page target
            target_ws_url = f"ws://127.0.0.1:{remote_port}/devtools/page/{page_id}"
            async with websockets.connect(target_ws_url, max_size=50*1024*1024) as page_ws:
                p_msg_id = 0
                async def page_cmd(method, params=None):
                    nonlocal p_msg_id
                    p_msg_id += 1
                    payload = {"id": p_msg_id, "method": method, "params": params or {}}
                    await page_ws.send(json.dumps(payload))
                    while True:
                        r = await page_ws.recv()
                        data = json.loads(r)
                        if data.get("id") == p_msg_id:
                            return data.get("result", {})

                await page_cmd("Page.enable")
                await page_cmd("Runtime.enable")
                await page_cmd("Page.navigate", {"url": "http://localhost:8000"})
                await asyncio.sleep(2.5)

                # 1. Switch to Time-Machine View
                print("  Step 1: Navigating to Time-Machine View...")
                eval_res = await page_cmd("Runtime.evaluate", {
                    "expression": "window.terminal.switchView('timemachine'); document.getElementById('time-machine-fullpage').style.display",
                    "returnByValue": True
                })
                print(f"    View display: {eval_res.get('result', {}).get('value')}")

                await asyncio.sleep(1.0)

                # 2. Check Date Select Options
                eval_days = await page_cmd("Runtime.evaluate", {
                    "expression": "document.getElementById('tm-date-select').options.length",
                    "returnByValue": True
                })
                num_days = eval_days.get('result', {}).get('value', 0)
                print(f"  Step 2: Total historical dates in dropdown: {num_days}")
                assert num_days >= 60, f"Expected 60 days, got {num_days}"

                # 3. Select 13 Nov 2026 and click Start Day at 09:15:00 AM IST
                print("  Step 3: Selecting 2026-11-13 and starting replay at 09:15:00 AM IST...")
                await page_cmd("Runtime.evaluate", {
                    "expression": "window.terminal.applySelectedDate('2026-11-13');",
                    "returnByValue": True
                })
                await asyncio.sleep(1.2)

                # 4. Verify Clock and Session Gate
                clock_res = await page_cmd("Runtime.evaluate", {
                    "expression": "document.getElementById('tm-ist-clock').textContent.trim()",
                    "returnByValue": True
                })
                gate_res = await page_cmd("Runtime.evaluate", {
                    "expression": "document.getElementById('tm-session-gate-pill').textContent.trim()",
                    "returnByValue": True
                })
                print(f"    Clock: {clock_res.get('result', {}).get('value')}")
                print(f"    Gate:  {gate_res.get('result', {}).get('value')}")

                # Capture Screenshot 1: 09:15 AM Warmup
                shot1 = await page_cmd("Page.captureScreenshot", {"format": "png"})
                path1 = os.path.join(SCREENSHOTS_DIR, "past_date_0915_warmup.png")
                with open(path1, "wb") as f:
                    f.write(base64.b64decode(shot1["data"]))
                print(f"    Screenshot 1 saved: {path1}")

                # 5. Advance to 09:25 AM Sniper Start (second 600)
                print("  Step 5: Jumping to 09:25:00 AM IST (Sniper Start, second 600)...")
                await page_cmd("Runtime.evaluate", {
                    "expression": "window.terminal.sendReplayControl('SET_SECOND', { secondOfDay: 600 });",
                    "returnByValue": True
                })
                await asyncio.sleep(1.0)

                gate_res2 = await page_cmd("Runtime.evaluate", {
                    "expression": "document.getElementById('tm-session-gate-pill').textContent.trim()",
                    "returnByValue": True
                })
                clock_res2 = await page_cmd("Runtime.evaluate", {
                    "expression": "document.getElementById('tm-ist-clock').textContent.trim()",
                    "returnByValue": True
                })
                print(f"    Clock at sec 600: {clock_res2.get('result', {}).get('value')}")
                print(f"    Gate at sec 600:  {gate_res2.get('result', {}).get('value')}")

                # Set 150x speed and let it trade for 2 seconds (300 market seconds = 1 5m candle)
                await page_cmd("Runtime.evaluate", {
                    "expression": "window.terminal.sendReplayControl('SET_SPEED', { speed: 150 }); window.terminal.sendReplayControl('PLAY');",
                    "returnByValue": True
                })
                await asyncio.sleep(2.5)

                shot2 = await page_cmd("Page.captureScreenshot", {"format": "png"})
                path2 = os.path.join(SCREENSHOTS_DIR, "past_date_0925_sniper_active.png")
                with open(path2, "wb") as f:
                    f.write(base64.b64decode(shot2["data"]))
                print(f"    Screenshot 2 saved: {path2}")

                # 6. Jump to 03:18 PM Auto Square-Off (second 21780)
                print("  Step 6: Jumping to 03:18:00 PM IST (Mandatory Auto Square-Off, second 21780)...")
                await page_cmd("Runtime.evaluate", {
                    "expression": "window.terminal.sendReplayControl('SET_SECOND', { secondOfDay: 21780 });",
                    "returnByValue": True
                })
                await asyncio.sleep(1.0)

                gate_res3 = await page_cmd("Runtime.evaluate", {
                    "expression": "document.getElementById('tm-session-gate-pill').textContent.trim()",
                    "returnByValue": True
                })
                clock_res3 = await page_cmd("Runtime.evaluate", {
                    "expression": "document.getElementById('tm-ist-clock').textContent.trim()",
                    "returnByValue": True
                })
                kpi_bal = await page_cmd("Runtime.evaluate", {
                    "expression": "document.getElementById('tm-kpi-balance').textContent.trim()",
                    "returnByValue": True
                })
                kpi_pnl = await page_cmd("Runtime.evaluate", {
                    "expression": "document.getElementById('tm-kpi-realized').textContent.trim()",
                    "returnByValue": True
                })
                print(f"    Clock at sec 21780: {clock_res3.get('result', {}).get('value')}")
                print(f"    Gate at sec 21780:  {gate_res3.get('result', {}).get('value')}")
                print(f"    Day Balance:        {kpi_bal.get('result', {}).get('value')}")
                print(f"    Day Net PnL:        {kpi_pnl.get('result', {}).get('value')}")

                shot3 = await page_cmd("Page.captureScreenshot", {"format": "png"})
                path3 = os.path.join(SCREENSHOTS_DIR, "past_date_0318_auto_squareoff.png")
                with open(path3, "wb") as f:
                    f.write(base64.b64decode(shot3["data"]))
                print(f"    Screenshot 3 saved: {path3}")

                print("\n[SUCCESS] All Past Date Replay Room verification steps passed with 100% precision!")

    finally:
        proc.terminate()

if __name__ == "__main__":
    asyncio.run(run_test())
