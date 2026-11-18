# NEXUS BHARAT // Indian Institutional Trading Terminal 🇮🇳

A high-density trading terminal designed for the Indian equity and derivatives markets (NSE & BSE), built with a modern institutional aesthetic (Bloomberg-meets-Linear design language) and powered by a **Python + Pandas** quantitative data engine.

---

## ⚡ Key Highlights

### 1. **Next-Generation Trading UI/UX**
- **Obsidian Matte Design System**: Engineered for prolonged professional trading desks (`#08090d` canvas, micro-borders, zero generic AI bloat).
- **Tabular Monospace Typography**: All real-time price feeds, depths, and volumes use `JetBrains Mono` with `font-variant-numeric: tabular-nums` to eliminate jitter.
- **60fps TradingView Lightweight Charts**: Full GPU-accelerated candlestick charting with zoom, pan, crosshair synchronization, and floating OHLCV legend.
- **Micro-Audio Feedback**: Tactile Web Audio feedback on order placement, side toggle, and fills.

### 2. **Pandas-Powered Quantitative Analytics Engine**
- **Live NSE/BSE Universe**: Real data for benchmark indices (`NIFTY 50`, `BSE SENSEX`, `BANK NIFTY`, `INDIA VIX`, `NIFTY IT`) and constituent heavyweights (`RELIANCE`, `TCS`, `HDFCBANK`, `INFY`, `ICICIBANK`, `BHARTIARTL`, `SBIN`, `ITC`, `LT`, etc.).
- **Pandas Calculations**:
  - **Moving Averages**: 20 EMA, 50 EMA, and Volume SMA.
  - **Momentum**: 14-period Wilder RSI (`df['Close'].diff()`, exponential moving average gain/loss).
  - **Trend**: MACD line, signal line, and histogram.
  - **Intraday VWAP**: Anchored Volume Weighted Average Price (`(df['Close'] * df['Volume']).cumsum() / df['Volume'].cumsum()`).
  - **Floor Trader Pivot Points**: Standard mathematical support and resistance levels (R3, R2, R1, PP, S1, S2, S3).
  - **Market Breadth**: Advancers, Decliners, and A/D ratio computed across the equity universe.

### 3. **Indian Market Level-2 Depth & Execution Ticket**
- **Level-2 Market Depth**: 5 Best Bids and 5 Best Asks with NSE standard ₹0.05 tick size, depth volume bars, spread tracker, and Buyer/Seller volume ratio.
- **Paper Trading Engine**: ₹10,00,000 (10 Lakhs) starting capital with real-time marked-to-market P&L.
- **Indian Regulatory Tax & Tariff Engine**:
  - MIS (Intraday with 5x leverage) vs CNC (Cash & Carry Delivery 1x).
  - Brokerage (₹20 flat / 0.03%).
  - STT (Securities Transaction Tax).
  - Exchange turnover charges (0.00345%).
  - Stamp duty (0.015% on buy).
  - SEBI turnover charges (₹10 / crore).
  - GST (18%).

---

## 🚀 Quick Start

### 1. Launch the Server
```bash
python run.py
```

### 2. Open the Terminal
Navigate to:
```
http://127.0.0.1:8000
```

---

## ⌨️ Professional Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl + K` | Focus quick stock & index search |
| `B` | Switch to **BUY** mode |
| `S` | Switch to **SELL** mode |
| `Shift + Enter` | Instant Order Execution |
| `Esc` | Blur active inputs |

---

## 📂 Project Architecture

```
d:\new start\
├── backend/
│   ├── data_engine.py      # Pandas data processing, technical indicators & cache
│   ├── portfolio.py        # Indian paper trading risk, margin & tax computation
│   └── main.py             # FastAPI REST endpoints & static file server
├── frontend/
│   ├── index.html          # High-density institutional terminal layout
│   ├── css/
│   │   └── terminal.css    # Custom dark matte design system
│   └── js/
│       ├── vendor/
│       │   └── lightweight-charts.standalone.js  # TradingView canvas engine
│       ├── chart.js        # Chart manager with indicators and crosshairs
│       └── app.js          # Core app controller, live ticks, order execution
├── run.py                  # Single-command launcher
└── README.md
```
