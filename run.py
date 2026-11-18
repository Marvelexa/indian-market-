"""
NEXUS BHARAT - Launcher Script
Starts the FastAPI server with Pandas-driven Indian Market Data Engine
"""

import sys
import uvicorn

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  NEXUS BHARAT // Indian Institutional Trading Terminal")
    print("  NSE / BSE Nifty 50, Sensex, Bank Nifty Quantitative Engine")
    print("=" * 60)
    print("  Local Server: http://127.0.0.1:8000")
    print("  API Docs:     http://127.0.0.1:8000/docs")
    print("=" * 60 + "\n")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False, log_level="info")
