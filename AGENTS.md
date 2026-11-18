# Nexus Bharat Quantitative Execution Rules

## 1. Priority of Index Option Seats (`OPTION_1` & `OPTION_2`)
- When Inter-Market Index Confluence (IMIC) and directional Market Breadth (>= 55%) align, prioritize capital deployment into `OPTION_1` (NIFTY ATM CE/PE) and `OPTION_2` (BANKNIFTY ATM CE/PE).
- Do not let low-volatility cash equity scalps saturate system capacity when clean index momentum is available.
- Always reserve `OPTION_1` and `OPTION_2` seats for Index Options before allocating the remaining 4 seats (`TREND_1/2`, `CHOP_1/2`) to cash equities.

## 2. Turnover Tax Friction & Profit Hurdle
- **Cash Equity Hurdle:** Because cash equity incurs ₹150+ in statutory turnover fees & STT per round-trip trade, the engine must never lock in trailing targets below +₹450 gross. Small scalps (< ₹300) are structurally penalized by statutory turnover charges on full stock price.
- **Option Trade Advantage:** In index options, total round-trip friction is only ~₹60–₹65 because STT and turnover charges apply exclusively to the option premium. The initial trailing lock at +₹250 (locking +₹100) successfully makes option positions 100% risk-free.

## 3. Smart SL & Extended Trailing Ladder (Up to +₹8,000)
- Initial Stop Loss is strictly capped at ₹2,500 loss per lot (i.e. -₹5,000 for standard 2-lot positions), providing a massive 166-point breathing buffer on NIFTY and 277-point buffer on BANKNIFTY.
- 8-Stage Extended Trailing Profit Ladder (Up to +₹8,000 Target):
  - Stage 1 (+₹500 unrealized): Lock +₹300 (Brokerage-Shielded & Risk-Free)
  - Stage 2 (+₹1,000 unrealized): Lock +₹700
  - Stage 3 (+₹1,500 unrealized): Lock +₹1,150
  - Stage 4 (+₹2,000 unrealized): Lock +₹1,600
  - Stage 5 (+₹3,000 unrealized): Lock +₹2,400
  - Stage 6 (+₹4,500 unrealized): Lock +₹3,600
  - Stage 7 (+₹6,000 unrealized): Lock +₹4,800
  - Stage 8 (+₹8,000 unrealized): Full Market Target Exit & Max Profit Booking

## 4. Strict Intraday Execution & Time Limits
- **Smart SL Removed (Breathing Room Guarantee):** Trades are NOT cut prematurely on minor dips, small wick penetrations, or early cuts. Positions hold full breathing room up to the hard ₹2,500/lot stop loss (-₹5,000 for 2 lots).
- **Strict 03:15 PM Cutoff:** Zero new trades can be initiated after 03:15:00 PM IST under any circumstances.
- **03:18 PM Mandatory Auto Square-Off:** All active positions must be squared off before 03:18 PM IST with zero overnight risk.

## 5. Top 50 F&O Stock Options Execution Engine (Zero Slippage & Tight Spread)
- **High-Liquidity Universe:** Top 50 most liquid F&O stocks on NSE with bid-ask spread between 0.05 to 0.50 paisa, guaranteeing near-zero slippage.
- **Pure Option Buying Execution (Zero Cash Equity):**
  - On BUY Signal: Automatically buys the **ATM Call Option (CE)** of that stock.
  - On SELL Signal: Automatically buys the **ATM Put Option (PE)** of that stock.
- **Per-Lot Risk & Trailing Rules:**
  - Maximum Loss per lot: Strictly capped at **-₹2,500** hard Stop Loss (providing full breathing room).
  - Trailing Ladder: Follows the 8-Stage Ladder up to +₹8,000 max target (+₹500 lock +₹300, +₹1,000 lock +₹700, +₹1,500 lock +₹1,150, +₹2,000 lock +₹1,600, +₹3,000 lock +₹2,400, +₹4,500 lock +₹3,600, +₹6,000 lock +₹4,800, +₹8,000 Full Target).
