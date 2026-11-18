"""
Capture screenshots of all 4 views:
1. Terminal View (Full-height chart, clean layout)
2. Positions & Seats View (Dedicated paper trading workspace)
3. Sniper Radar View (High-conviction setups)
4. Time-Machine View (60D simulation)
"""

import subprocess
import json
import time
import os
import asyncio
import websockets
import base64

async def capture_views():
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
        print("No browser found")
        return

    out_dir = r"d:\new start\scratch\screenshots"
    os.makedirs(out_dir, exist_ok=True)

    cmd = [
        browser_exe,
        "--headless=new",
        "--remote-debugging-port=9224",
        "--window-size=1600,950",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "http://localhost:8000"
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    await asyncio.sleep(2.5)

    try:
        import urllib.request
        with urllib.request.urlopen("http://localhost:9224/json", timeout=5) as res:
            targets = json.loads(res.read().decode())
        target = next((t for t in targets if t.get("type") == "page"), targets[0])
        ws_url = target["webSocketDebuggerUrl"]

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
                return r.get("result", {}).get("value")

            async def take_screenshot(filename):
                r = await send_cmd("Page.captureScreenshot", {"format": "png"})
                data = base64.b64decode(r["data"])
                filepath = os.path.join(out_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(data)
                print(f"Captured: {filepath}")

            await asyncio.sleep(2.0)

            # View 1: Terminal
            await eval_js("window.terminal.switchView('terminal')")
            await asyncio.sleep(1.0)
            await take_screenshot("1_terminal_view.png")

            # View 2: Positions & Seats
            await eval_js("window.terminal.switchView('positions')")
            await asyncio.sleep(1.0)
            await take_screenshot("2_positions_view.png")

            # View 3: Radar
            await eval_js("window.terminal.switchView('radar')")
            await asyncio.sleep(1.0)
            await take_screenshot("3_radar_view.png")

            # View 4: Time-Machine
            await eval_js("window.terminal.switchView('timemachine')")
            await asyncio.sleep(1.0)
            await take_screenshot("4_timemachine_view.png")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except:
            proc.kill()

if __name__ == "__main__":
    asyncio.run(capture_views())
