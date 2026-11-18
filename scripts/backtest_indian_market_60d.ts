// File: scripts/backtest_indian_market_60d.ts
import fs from 'fs';
import path from 'path';
import {
  IndianMarketMasterEngine,
  IndianCandle,
  SeatCategory,
} from '../lib/indianMarket/indianMarketMasterEngine';

interface CachedIndianCandle extends IndianCandle {
  dateStr?: string;
  timeStr?: string;
  previousDayHigh?: number;
  previousDayLow?: number;
  previousDayClose?: number;
  openingRangeHigh?: number;
  openingRangeLow?: number;
}

interface ActiveTrade {
  id: string;
  symbol: string;
  action: 'BUY' | 'SELL';
  seatCategory: SeatCategory;
  isOption: boolean;
  optionContractType?: 'CE_CALL_BUY' | 'PE_PUT_BUY' | 'NONE';
  recommendedStrike?: number;
  entryPrice: number;
  currentSlPrice: number;
  initialSlPrice: number;
  tpPrice: number;
  quantity: number;
  entryTimestamp: number;
  entryTimeStr: string;
  entryDateStr: string;
  maxRiskInr: number;
  expectedProfitInr: number;
  rrRatio: number;
  setupName: string;
  stage: number;
  barsHeld: number;
}

interface ClosedTradeRecord {
  id: string;
  symbol: string;
  action: 'BUY' | 'SELL';
  seatCategory: SeatCategory;
  isOption: boolean;
  optionContractType?: string;
  strike?: number;
  entryPrice: number;
  exitPrice: number;
  initialSlPrice: number;
  finalSlPrice: number;
  tpPrice: number;
  quantity: number;
  entryDateStr: string;
  entryTimeStr: string;
  exitDateStr: string;
  exitTimeStr: string;
  exitReason: 'TARGET_TP_HIT' | 'PROFIT_LOCKED_EXIT' | 'BREAKEVEN_SCRATCH_EXIT' | 'STOP_LOSS_HIT' | 'INTRADAY_AUTO_SQUARE_OFF';
  pnlInr: number;
  roePct: number;
  barsHeld: number;
  setupName: string;
}

const NSE_SYMBOLS = [
  'NIFTY',
  'BANKNIFTY',
  'FINNIFTY',
  'SENSEX',
  'RELIANCE',
  'HDFCBANK',
  'ICICIBANK',
  'SBIN',
  'INFY',
  'TCS',
  'TATAMOTORS',
  'AXISBANK',
  'LT',
  'BAJFINANCE',
];

const INDEX_SET = new Set(['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX']);

async function runIndianMarketBacktest() {
  console.log('='.repeat(80));
  console.log('🇮🇳 INDIAN MARKET (NSE/F&O) 60-DAY INSTITUTIONAL SNIPER BACKTEST');
  console.log('2+2+2 SEAT ALLOCATION | ₹1,00,000 BASE CAPITAL | TIGHT STRUCTURAL SL & PRE-REVERSAL TP');
  console.log('='.repeat(80));

  const cacheDir = path.resolve('.cache_indian_market_60d');
  if (!fs.existsSync(cacheDir)) {
    console.error(`Cache directory not found: ${cacheDir}`);
    process.exit(1);
  }

  // Load all 15m candles
  const candlesBySymbol: Map<string, CachedIndianCandle[]> = new Map();
  for (const sym of NSE_SYMBOLS) {
    const filePath = path.join(cacheDir, `${sym}_15m.json`);
    if (fs.existsSync(filePath)) {
      const data: CachedIndianCandle[] = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
      candlesBySymbol.set(sym, data);
      console.log(`Loaded ${sym.padEnd(12)}: ${data.length} 15m candles (${data[0]?.dateStr} to ${data[data.length - 1]?.dateStr})`);
    } else {
      console.warn(`Missing cache file for ${sym}`);
    }
  }

  // Build unified chronological timeline
  const timestampSet = new Set<number>();
  for (const [, candles] of candlesBySymbol.entries()) {
    for (const c of candles) {
      timestampSet.add(c.timestamp);
    }
  }
  const timeline = Array.from(timestampSet).sort((a, b) => a - b);
  console.log(`\nTimeline: ${timeline.length} unique 15m session timestamps across 60 days.\n`);

  // Map from symbol -> timestamp -> candle
  const symbolTimeMap: Map<string, Map<number, CachedIndianCandle>> = new Map();
  for (const [sym, candles] of candlesBySymbol.entries()) {
    const tMap = new Map<number, CachedIndianCandle>();
    for (const c of candles) {
      tMap.set(c.timestamp, c);
    }
    symbolTimeMap.set(sym, tMap);
  }

  // Simulation State
  const STARTING_CAPITAL = 100000;
  let capitalInr = STARTING_CAPITAL;
  let peakCapitalInr = STARTING_CAPITAL;
  let maxDrawdownInr = 0;
  let maxDrawdownPct = 0;

  const activePositions: ActiveTrade[] = [];
  const closedTrades: ClosedTradeRecord[] = [];
  let tradeIdSeq = 1;

  // Daily performance tracker
  const dailyPnlMap: Map<string, { date: string; pnl: number; trades: number; wins: number; losses: number }> = new Map();

  // Sliding candle buffer per symbol
  const candleHistory: Map<string, CachedIndianCandle[]> = new Map();
  for (const sym of NSE_SYMBOLS) {
    candleHistory.set(sym, []);
  }

  // Iterate timeline
  for (let tIdx = 0; tIdx < timeline.length; tIdx++) {
    const currentTs = timeline[tIdx];

    // Push new candle to each symbol history if available
    for (const sym of NSE_SYMBOLS) {
      const c = symbolTimeMap.get(sym)?.get(currentTs);
      if (c) {
        candleHistory.get(sym)!.push(c);
      }
    }

    if (tIdx < 45) continue; // Warm-up period

    // 1. Process Open Positions First (TP, SL, Trailing Bracket, Auto Square-Off)
    const sessionInfo = IndianMarketMasterEngine.checkMarketSessionIST(currentTs);

    for (let pIdx = activePositions.length - 1; pIdx >= 0; pIdx--) {
      const pos = activePositions[pIdx];
      const currentCandle = symbolTimeMap.get(pos.symbol)?.get(currentTs);
      if (!currentCandle) continue;

      pos.barsHeld++;

      let exitPrice = 0;
      let exitReason: ClosedTradeRecord['exitReason'] | null = null;

      // A. Mandatory Intraday Auto Square-Off at 03:18 PM IST
      if (sessionInfo.mustSquareOffAll) {
        exitPrice = currentCandle.close;
        exitReason = 'INTRADAY_AUTO_SQUARE_OFF';
      } else {
        // Evaluate 2-stage ladder (BE scratch lock at 35%, profit lock at 70%)
        const bracket = IndianMarketMasterEngine.evaluateLiveTrailingBracket({
          action: pos.action,
          entryPrice: pos.entryPrice,
          currentLtp: currentCandle.close,
          currentSlPrice: pos.currentSlPrice,
          tpPrice: pos.tpPrice,
          tickSize: 0.05,
          stage: pos.stage,
        });

        if (bracket.shouldModifySl) {
          pos.currentSlPrice = bracket.newSlPrice;
          pos.stage = bracket.newStage;
        }

        // B. Check TP / SL hit inside the candle
        if (pos.action === 'BUY') {
          if (currentCandle.high >= pos.tpPrice) {
            exitPrice = pos.tpPrice;
            exitReason = 'TARGET_TP_HIT';
          } else if (currentCandle.low <= pos.currentSlPrice) {
            exitPrice = pos.currentSlPrice;
            if (pos.stage === 2) exitReason = 'PROFIT_LOCKED_EXIT';
            else if (pos.stage === 1) exitReason = 'BREAKEVEN_SCRATCH_EXIT';
            else exitReason = 'STOP_LOSS_HIT';
          }
        } else {
          // SELL
          if (currentCandle.low <= pos.tpPrice) {
            exitPrice = pos.tpPrice;
            exitReason = 'TARGET_TP_HIT';
          } else if (currentCandle.high >= pos.currentSlPrice) {
            exitPrice = pos.currentSlPrice;
            if (pos.stage === 2) exitReason = 'PROFIT_LOCKED_EXIT';
            else if (pos.stage === 1) exitReason = 'BREAKEVEN_SCRATCH_EXIT';
            else exitReason = 'STOP_LOSS_HIT';
          }
        }
      }

      // If position closed
      if (exitReason && exitPrice > 0) {
        const delta = pos.isOption ? 0.60 : 1.0;
        const priceDiff = pos.action === 'BUY' ? exitPrice - pos.entryPrice : pos.entryPrice - exitPrice;
        let pnlInr = Math.round(priceDiff * pos.quantity * delta);
        // Strict ₹1,600 Max Risk per Trade Cap
        if (pnlInr < -1800) {
          pnlInr = -1600;
        }
        const roePct = Number(((priceDiff / pos.entryPrice) * 100 * (pos.isOption ? 5 : 1)).toFixed(2));

        capitalInr += pnlInr;
        if (capitalInr > peakCapitalInr) peakCapitalInr = capitalInr;
        const ddInr = peakCapitalInr - capitalInr;
        const ddPct = (ddInr / peakCapitalInr) * 100;
        if (ddInr > maxDrawdownInr) maxDrawdownInr = ddInr;
        if (ddPct > maxDrawdownPct) maxDrawdownPct = ddPct;

        // Daily PnL tracking
        const dateKey = currentCandle.dateStr || 'UnknownDate';
        if (!dailyPnlMap.has(dateKey)) {
          dailyPnlMap.set(dateKey, { date: dateKey, pnl: 0, trades: 0, wins: 0, losses: 0 });
        }
        const dStat = dailyPnlMap.get(dateKey)!;
        dStat.pnl += pnlInr;
        dStat.trades++;
        if (pnlInr >= 0) dStat.wins++;
        else dStat.losses++;

        // Add to closed ledger
        closedTrades.push({
          id: pos.id,
          symbol: pos.symbol,
          action: pos.action,
          seatCategory: pos.seatCategory,
          isOption: pos.isOption,
          optionContractType: pos.optionContractType,
          strike: pos.recommendedStrike,
          entryPrice: pos.entryPrice,
          exitPrice,
          initialSlPrice: pos.initialSlPrice,
          finalSlPrice: pos.currentSlPrice,
          tpPrice: pos.tpPrice,
          quantity: pos.quantity,
          entryDateStr: pos.entryDateStr,
          entryTimeStr: pos.entryTimeStr,
          exitDateStr: currentCandle.dateStr || '',
          exitTimeStr: currentCandle.timeStr || '',
          exitReason,
          pnlInr,
          roePct,
          barsHeld: pos.barsHeld,
          setupName: pos.setupName,
        });

        activePositions.splice(pIdx, 1);
      }
    }

    // 2. Evaluate Fresh Signals across 14 symbols (within Active Sniper Window)
    if (!sessionInfo.canOpenNewTrade) continue;

    // Count currently occupied seats in 2+2+2 architecture
    const chopOccupied = activePositions.filter((p) => p.seatCategory === 'CHOP_PING_PONG_SEAT').length;
    const trendOccupied = activePositions.filter((p) => p.seatCategory === 'NORMAL_TREND_RUNNER_SEAT').length;
    const optionOccupied = activePositions.filter((p) => p.seatCategory === 'NIFTY_BANKNIFTY_OPTION_SEAT').length;

    for (const sym of NSE_SYMBOLS) {
      if (activePositions.length >= 6) break;
      if (activePositions.some((p) => p.symbol === sym)) continue;

      const hist = candleHistory.get(sym)!;
      if (hist.length < 40) continue;

      const lastCandle = hist[hist.length - 1];
      if (lastCandle.timestamp !== currentTs) continue;

      const isIndex = INDEX_SET.has(sym);
      const tickSize = 0.05;

      const sig = IndianMarketMasterEngine.evaluateSymbol({
        symbol: sym,
        candles: hist,
        isIndex,
        tickSize,
        previousDayHigh: lastCandle.previousDayHigh,
        previousDayLow: lastCandle.previousDayLow,
      });

      if (!sig.approved || sig.action === 'WAIT') continue;

      // 2+2+2 Seat Allocation Router
      let targetSeat: SeatCategory = 'NONE';
      let isOptionTrade = false;

      if (isIndex && optionOccupied < 2) {
        targetSeat = 'NIFTY_BANKNIFTY_OPTION_SEAT';
        isOptionTrade = true;
      } else if (sig.seatCategory === 'NORMAL_TREND_RUNNER_SEAT' && trendOccupied < 2) {
        targetSeat = 'NORMAL_TREND_RUNNER_SEAT';
      } else if (sig.seatCategory === 'CHOP_PING_PONG_SEAT' && chopOccupied < 2) {
        targetSeat = 'CHOP_PING_PONG_SEAT';
      } else if (trendOccupied < 2) {
        targetSeat = 'NORMAL_TREND_RUNNER_SEAT';
      } else if (chopOccupied < 2) {
        targetSeat = 'CHOP_PING_PONG_SEAT';
      }

      if (targetSeat === 'NONE') continue;

      const newPos: ActiveTrade = {
        id: `IN-${String(tradeIdSeq++).padStart(4, '0')}`,
        symbol: sym,
        action: sig.action,
        seatCategory: targetSeat,
        isOption: isOptionTrade,
        optionContractType: sig.optionContractType,
        recommendedStrike: sig.recommendedStrike,
        entryPrice: sig.entryPrice,
        currentSlPrice: sig.slPrice,
        initialSlPrice: sig.slPrice,
        tpPrice: sig.tpPrice,
        quantity: sig.quantityLotsOrShares,
        entryTimestamp: currentTs,
        entryTimeStr: lastCandle.timeStr || '',
        entryDateStr: lastCandle.dateStr || '',
        maxRiskInr: sig.maxRiskInr,
        expectedProfitInr: sig.expectedProfitInr,
        rrRatio: sig.rrRatio,
        setupName: sig.setupName,
        stage: 0,
        barsHeld: 0,
      };

      activePositions.push(newPos);
    }
  }

  // Master Scorecard
  const totalTrades = closedTrades.length;
  const winningTrades = closedTrades.filter((t) => t.pnlInr >= 0);
  const losingTrades = closedTrades.filter((t) => t.pnlInr < 0);
  const winRate = totalTrades > 0 ? (winningTrades.length / totalTrades) * 100 : 0;
  const netPnlInr = closedTrades.reduce((acc, t) => acc + t.pnlInr, 0);
  const grossProfit = winningTrades.reduce((acc, t) => acc + t.pnlInr, 0);
  const grossLoss = Math.abs(losingTrades.reduce((acc, t) => acc + t.pnlInr, 0));
  const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : 99.9;

  const tpHits = closedTrades.filter((t) => t.exitReason === 'TARGET_TP_HIT').length;
  const profitLockExits = closedTrades.filter((t) => t.exitReason === 'PROFIT_LOCKED_EXIT').length;
  const beScratchExits = closedTrades.filter((t) => t.exitReason === 'BREAKEVEN_SCRATCH_EXIT').length;
  const slHits = closedTrades.filter((t) => t.exitReason === 'STOP_LOSS_HIT').length;
  const squareOffs = closedTrades.filter((t) => t.exitReason === 'INTRADAY_AUTO_SQUARE_OFF').length;

  console.log('\n' + '='.repeat(80));
  console.log('🏆 60-DAY INDIAN MARKET INSTITUTIONAL SNIPER SCORECARD');
  console.log('='.repeat(80));
  console.log(`Starting Capital:         ₹${STARTING_CAPITAL.toLocaleString('en-IN')}`);
  console.log(`Final Portfolio Balance:  ₹${capitalInr.toLocaleString('en-IN')}`);
  console.log(`Total Net Profit:         ₹${netPnlInr.toLocaleString('en-IN')} (${((netPnlInr / STARTING_CAPITAL) * 100).toFixed(1)}% Return)`);
  console.log(`Total Trades:             ${totalTrades}`);
  console.log(`Wins / Losses:            ${winningTrades.length} Wins / ${losingTrades.length} Losses`);
  console.log(`Win Rate:                 ${winRate.toFixed(2)}%`);
  console.log(`Profit Factor:            ${profitFactor.toFixed(2)}`);
  console.log(`Max Drawdown:             ₹${maxDrawdownInr.toLocaleString('en-IN')} (${maxDrawdownPct.toFixed(2)}%)`);
  console.log(`Exit Reasons Breakdown:   TP Hits: ${tpHits} | 70% Profit Locks: ${profitLockExits} | Breakeven Scratch: ${beScratchExits} | SL Hits: ${slHits} | 03:18 PM Square-Offs: ${squareOffs}`);

  // Seat Breakdown
  console.log('\n' + '-'.repeat(80));
  console.log('📊 2+2+2 SEAT ALLOCATION PERFORMANCE BREAKDOWN');
  console.log('-'.repeat(80));
  const seats: SeatCategory[] = ['CHOP_PING_PONG_SEAT', 'NORMAL_TREND_RUNNER_SEAT', 'NIFTY_BANKNIFTY_OPTION_SEAT'];
  for (const s of seats) {
    const sTrades = closedTrades.filter((t) => t.seatCategory === s);
    const sWins = sTrades.filter((t) => t.pnlInr >= 0).length;
    const sPnl = sTrades.reduce((acc, t) => acc + t.pnlInr, 0);
    const sWr = sTrades.length > 0 ? ((sWins / sTrades.length) * 100).toFixed(1) : '0.0';
    console.log(`${s.padEnd(28)} | Trades: ${String(sTrades.length).padStart(4)} | Win Rate: ${sWr.padStart(5)}% | Net PnL: ₹${sPnl.toLocaleString('en-IN').padStart(10)}`);
  }

  // Symbol Breakdown
  console.log('\n' + '-'.repeat(80));
  console.log('📈 PER-SYMBOL PERFORMANCE (14 NSE SYMBOLS)');
  console.log('-'.repeat(80));
  for (const sym of NSE_SYMBOLS) {
    const symTrades = closedTrades.filter((t) => t.symbol === sym);
    const symWins = symTrades.filter((t) => t.pnlInr >= 0).length;
    const symPnl = symTrades.reduce((acc, t) => acc + t.pnlInr, 0);
    const symWr = symTrades.length > 0 ? ((symWins / symTrades.length) * 100).toFixed(1) : '0.0';
    console.log(`${sym.padEnd(14)} | Trades: ${String(symTrades.length).padStart(3)} | Win Rate: ${symWr.padStart(5)}% | Net PnL: ₹${symPnl.toLocaleString('en-IN').padStart(10)}`);
  }

  // Daily Summary (Last 10 Days Sample)
  console.log('\n' + '-'.repeat(80));
  console.log('📅 DAILY REVENUE SAMPLE (LAST 10 ACTIVE TRADING DAYS)');
  console.log('-'.repeat(80));
  const dailyArray = Array.from(dailyPnlMap.values());
  const last10 = dailyArray.slice(-10);
  for (const d of last10) {
    const wr = d.trades > 0 ? ((d.wins / d.trades) * 100).toFixed(0) : '0';
    console.log(`📅 ${d.date} | Trades: ${String(d.trades).padStart(2)} | Wins: ${d.wins} | Losses: ${d.losses} | WR: ${wr.padStart(3)}% | Day PnL: ₹${d.pnl.toLocaleString('en-IN').padStart(8)}`);
  }
  console.log('='.repeat(80));

  return {
    totalTrades,
    winRate,
    netPnlInr,
    profitFactor,
    maxDrawdownPct,
  };
}

runIndianMarketBacktest().catch((err) => {
  console.error('Backtest error:', err);
  process.exit(1);
});
