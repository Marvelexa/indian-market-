import asyncio
import json
import os
import subprocess
import time
import urllib.request
import base64
import websockets

async def run_test():
    print("[TEST] Verifying Smart TP & Brokerage Shield in Past Date Replay Room via CDP...")
    
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

    remote_port = 9224
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

            t_res = await send_cdp("Target.createTarget", {"url": "about:blank"})
            page_id = t_res["targetId"]

            target_ws_url = f"ws://127.0.0.1:{remote_port}/devtools/page/{page_id}"
            async with websockets.connect(target_ws_url, max_size=50*1024*1024) as page_ws:
                page_msg_id = 0
                async def page_cmd(method, params=None):
                    nonlocal page_msg_id
                    page_msg_id += 1
                    payload = {"id": page_msg_id, "method": method, "params": params or {}}
                    await page_ws.send(json.dumps(payload))
                    while True:
                        r = await page_ws.recv()
                        data = json.loads(r)
                        if data.get("id") == page_msg_id:
                            return data.get("result", {})

                await page_cmd("Page.enable")
                await page_cmd("Runtime.enable")
                await page_cmd("Page.navigate", {"url": "http://127.0.0.1:8000"})
                await asyncio.sleep(2.0)

                # 1. Switch to Past Date Time-Machine View
                print("  Step 1: Navigating to Past Date Time Machine...")
                await page_cmd("Runtime.evaluate", {
                    "expression": "window.terminal.switchView('timemachine');",
                    "returnByValue": True
                })
                await asyncio.sleep(1.2)

                # 2. Select Date and Set Speed to 60x for fast simulation
                print("  Step 2: Selecting Date 2026-11-13 and setting speed to 60x...")
                await page_cmd("Runtime.evaluate", {
                    "expression": "window.terminal.applySelectedDate('2026-11-13'); window.terminal.sendReplayControl('SET_SPEED', {speed: 60});",
                    "returnByValue": True
                })
                await asyncio.sleep(1.0)

                # 3. Fast-forward into active trading session (around 10:30 AM IST = second 4500)
                print("  Step 3: Fast-forwarding to 10:30 AM IST (second 4500) to observe Smart TP and active seats...")
                await page_cmd("Runtime.evaluate", {
                    "expression": "window.terminal.sendReplayControl('SET_SECOND', {secondOfDay: 4500});",
                    "returnByValue": True
                })
                await asyncio.sleep(2.0)

                # Check seat positions
                seats_res = await page_cmd("Runtime.evaluate", {
                    "expression": """
                        (() => {
                            const container = document.getElementById('tm-active-positions-container');
                            return {
                                text: container ? container.innerText : '',
                                html: container ? container.innerHTML : ''
                            };
                        })()
                    """,
                    "returnByValue": True
                })
                seats_data = seats_res.get("result", {}).get("value", {})
                print(f"  Step 4: Active Seats Container Text:\n{seats_data.get('text', '')[:300]}...")

                # 4. Fast-forward to 01:00 PM IST (second 13500)
                print("  Step 5: Advancing to 01:00 PM IST (second 13500)...")
                await page_cmd("Runtime.evaluate", {
                    "expression": "window.terminal.sendReplayControl('SET_SECOND', {secondOfDay: 13500});",
                    "returnByValue": True
                })
                await asyncio.sleep(2.0)

                # Capture full page screenshot
                screenshot_res = await page_cmd("Page.captureScreenshot", {"format": "png"})
                os.makedirs("scratch/screenshots", exist_ok=True)
                img_data = base64.b64decode(screenshot_res["data"])
                screenshot_path = os.path.abspath("scratch/screenshots/past_date_smart_tp_live.png")
                with open(screenshot_path, "wb") as f:
                    f.write(img_data)
                print(f"  Step 6: Live Screenshot saved to {screenshot_path}")

                # Check closed trades ledger
                ledger_res = await page_cmd("Runtime.evaluate", {
                    "expression": "document.getElementById('tm-closed-ledger-tbody').innerText",
                    "returnByValue": True
                })
                ledger_text = ledger_res.get("result", {}).get("value", "")
                print(f"  Step 7: Closed Ledger Status:\n{ledger_text[:400]}")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()
        print("\n[VERIFICATION COMPLETE]")

if __name__ == "__main__":
    asyncio.run(run_test())
