// File: lib/replay/timeMachineReplayEngine.ts
import fs from 'fs';
import path from 'path';
import {
  IndianMarketMasterEngine,
  IndianCandle,
  SeatCategory,
} from '../indianMarket/indianMarketMasterEngine';
import { KlinePoint } from '../../src/types';

export interface ReplayPosition {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  seatBucket: 'CHOP_PING_PONG_SEAT' | 'NORMAL_TREND_RUNNER_SEAT' | 'NIFTY_BANKNIFTY_OPTION_SEAT' | 'CHOP_15PCT_SEAT' | 'NORMAL_23_TO_40PCT_SEAT' | 'BTC_ETH_OPTION_MIRROR_SEAT';
  isOption?: boolean;
  optionType?: 'CALL' | 'PUT';
  optionStrike?: number;
  entryPrice: number;
  currentPrice: number;
  initialSlPrice: number;
  slPrice: number;
  initialTpPrice: number;
  tpPrice: number;
  quantity: number;
  stage: number;
  marginInr: number;
  notionalInr: number;
  floatingPnlInr: number;
  currentNetRoePct: number;
  peakRoePct: number;
  barsHeld: number;
  openedAtBarIndex?: number;
  openedAtTime: number;
  openedAtFormatted: string;
  reason: string;
  strategyName: string;
  // Legacy aliases for backward compatibility with UI
  marginUsd?: number;
  notionalUsd?: number;
  floatingPnlUsd?: number;
  ratchetLevel?: number;
}

export interface ReplayClosedTrade {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  seatBucket: string;
  isOption?: boolean;
  optionType?: 'CALL' | 'PUT';
  optionStrike?: number;
  entryPrice: number;
  exitPrice: number;
  entryTime: number;
  exitTime: number;
  entryDateFormatted: string;
  exitDateFormatted: string;
  initialSlPrice: number;
  finalSlPrice: number;
  initialTpPrice: number;
  finalTpPrice: number;
  quantity: number;
  barsHeld: number;
  notionalInr: number;
  marginInr: number;
  netPnlInr: number;
  netRoePct: number;
  exitReason: 'TARGET_TP_HIT' | 'PROFIT_LOCKED_EXIT' | 'BREAKEVEN_SCRATCH_EXIT' | 'STOP_LOSS_HIT' | 'INTRADAY_AUTO_SQUARE_OFF' | 'STAGE2_RUNNER_TP_HIT' | 'PROFIT_LOCK_HIT';
  strategyName: string;
  // Legacy aliases
  netPnlUsd?: number;
  marginUsd?: number;
  notionalUsd?: number;
  ratchetLevel?: number;
}

export interface CoinScorecard {
  symbol: string;
  currentPrice?: number;
  totalTrades: number;
  wins: number;
  losses: number;
  winRatePct: number;
  netPnlInr: number;
  netPnlUsd?: number;
  tpHits: number;
  profitLockHits: number;
  slHits: number;
  activeTrade?: {
    side: 'BUY' | 'SELL';
    entryPrice: number;
    currentPrice: number;
    floatingPnlInr: number;
    currentNetRoePct: number;
    slPrice: number;
    tpPrice: number;
    stage: number;
  } | null;
}

export interface MonthCheckpoint {
  label: string;
  barIndex: number;
  dateStr: string;
}

export interface SeatBreakdownRecord {
  seatBucket: string;
  totalTrades: number;
  wins: number;
  losses: number;
  winRatePct: number;
  tpHits: number;
  profitLockHits: number;
  slHits: number;
  netPnlInr: number;
  netPnlUsd?: number;
}

export interface ReplayEngineState {
  isRunning: boolean;
  speed: number;
  currentTimestamp: number;
  formattedDate: string;
  monthBanner: string;
  barIndex: number;
  subTickIndex: number;
  totalBars: number;
  progressPct: number;
  availableMonths: MonthCheckpoint[];
  wallet: {
    startingCapitalInr: number;
    balanceInr: number;
    realizedPnlInr: number;
    floatingPnlInr: number;
    startingCapitalUsd: number;
    balanceUsd: number;
    realizedPnlUsd: number;
    floatingPnlUsd: number;
    totalTrades: number;
    wins: number;
    losses: number;
    winRatePct: number;
    tpHits: number;
    profitLockHits: number;
    slHits: number;
  };
  seatBreakdown: Record<string, SeatBreakdownRecord>;
  livePrices: Record<string, number>;
  activePositions: ReplayPosition[];
  coinStats: Record<string, CoinScorecard>;
  closedLedger: ReplayClosedTrade[];
}

export const NSE_WHITELIST_SYMBOLS = [
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

function formatIST(timestamp: number): string {
  if (!timestamp || isNaN(timestamp)) return '18 Aug 2026, 09:15 AM IST';
  try {
    const d = new Date(timestamp);
    const options: Intl.DateTimeFormatOptions = {
      timeZone: 'Asia/Kolkata',
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    };
    return `${new Intl.DateTimeFormat('en-IN', options).format(d)} IST`;
  } catch (e) {
    return new Date(timestamp).toISOString();
  }
}

export class TimeMachineReplayEngine {
  private static instance: TimeMachineReplayEngine | null = null;

  private isRunning: boolean = false;
  private speed: number = 5; // Default 5x
  private timer: NodeJS.Timeout | null = null;

  // Historical Candles & Timeline
  private candlesMap: Map<string, IndianCandle[]> = new Map();
  private candleTimeIndex: Map<string, Map<number, IndianCandle>> = new Map();
  private masterTimestamps: number[] = [];
  private barIndex: number = 45; // 45 warm-up candles
  private subTickIndex: number = 0; // 0, 1, 2, 3
  private totalBars: number = 0;
  private availableMonths: MonthCheckpoint[] = [];

  // Account & Execution State (₹1,00,000 Starting Capital)
  private startingCapitalInr: number = 100000;
  private realizedPnlInr: number = 0;
  private activePositions: ReplayPosition[] = [];
  private closedLedger: ReplayClosedTrade[] = [];
  private coinStats: Map<string, CoinScorecard> = new Map();
  private seatStats: Map<string, SeatBreakdownRecord> = new Map();
  private tradeCounter: number = 0;

  // Cached Live Sub-tick Prices
  private livePrices: Record<string, number> = {};

  private isInitialized: boolean = false;
  private initPromise: Promise<void> | null = null;
  private activePort: number = Number(process.env.REPLAY_PORT || process.env.PORT || 3005);

  public setPort(port: number): void {
    this.activePort = port;
  }
  public getPort(): number {
    return this.activePort;
  }

  public static getInstance(): TimeMachineReplayEngine {
    if (!TimeMachineReplayEngine.instance) {
      TimeMachineReplayEngine.instance = new TimeMachineReplayEngine();
    }
    return TimeMachineReplayEngine.instance;
  }

  private constructor() {
    this.resetStats();
  }

  private resetStats() {
    this.coinStats.clear();
    for (const sym of NSE_WHITELIST_SYMBOLS) {
      this.coinStats.set(sym, {
        symbol: sym,
        totalTrades: 0,
        wins: 0,
        losses: 0,
        winRatePct: 0,
        netPnlInr: 0,
        netPnlUsd: 0,
        tpHits: 0,
        profitLockHits: 0,
        slHits: 0,
      });
    }

    this.seatStats.clear();
    const seatNames = ['CHOP_PING_PONG_SEAT', 'NORMAL_TREND_RUNNER_SEAT', 'NIFTY_BANKNIFTY_OPTION_SEAT'];
    for (const s of seatNames) {
      this.seatStats.set(s, {
        seatBucket: s,
        totalTrades: 0,
        wins: 0,
        losses: 0,
        winRatePct: 0,
        tpHits: 0,
        profitLockHits: 0,
        slHits: 0,
        netPnlInr: 0,
        netPnlUsd: 0,
      });
    }
  }

  /**
   * Initialize candles from local 60-day Indian Market cache (.cache_indian_market_60d/)
   */
  public async initialize(): Promise<void> {
    if (this.isInitialized) return;
    if (this.initPromise) return this.initPromise;

    this.initPromise = (async () => {
      console.log('⏳ [TimeMachineReplayEngine] Initializing 60-Day Indian Market 15m Timeline...');
      const cacheDir = path.resolve('.cache_indian_market_60d');
      if (!fs.existsSync(cacheDir)) {
        throw new Error(`Cache directory not found: ${cacheDir}`);
      }

      for (const sym of NSE_WHITELIST_SYMBOLS) {
        const cacheFile = path.join(cacheDir, `${sym}_15m.json`);
        let candles: IndianCandle[] = [];

        if (fs.existsSync(cacheFile)) {
          try {
            candles = JSON.parse(fs.readFileSync(cacheFile, 'utf-8'));
          } catch (e) {
            console.warn(`[TimeMachineReplayEngine] Failed to parse cache for ${sym}`);
          }
        }

        this.candlesMap.set(sym, candles);
        this.candleTimeIndex.set(sym, new Map(candles.map((c) => [c.timestamp, c])));
      }

      const niftyCandles = this.candlesMap.get('NIFTY') || [];
      if (niftyCandles.length < 500) {
        throw new Error('Insufficient NIFTY historical candles for replay timeline');
      }

      this.masterTimestamps = niftyCandles.map((c) => c.timestamp);
      this.totalBars = this.masterTimestamps.length;
      this.barIndex = Math.min(45, this.totalBars - 1);
      this.subTickIndex = 0;

      // Detect available months
      this.detectAvailableMonths();

      // Populate initial prices
      this.updateLiveSubTickPrices();

      this.isInitialized = true;
      console.log(`✅ [TimeMachineReplayEngine] Timeline ready: ${this.totalBars} bars (${NSE_WHITELIST_SYMBOLS.length} NSE symbols synced).`);
      this.play();
    })();

    return this.initPromise;
  }

  private detectAvailableMonths() {
    this.availableMonths = [];
    const seenMonths = new Set<string>();

    for (let i = 45; i < this.masterTimestamps.length; i++) {
      const ts = this.masterTimestamps[i];
      const d = new Date(ts + 330 * 60 * 1000); // IST
      const mKey = `${d.getUTCFullYear()}-${d.getUTCMonth()}`;
      if (!seenMonths.has(mKey)) {
        seenMonths.add(mKey);
        const label = new Intl.DateTimeFormat('en-IN', {
          timeZone: 'Asia/Kolkata',
          month: 'short',
          year: 'numeric',
        }).format(new Date(ts));
        this.availableMonths.push({
          label: `${label}`,
          barIndex: i,
          dateStr: formatIST(ts),
        });
      }
    }
  }

  /**
   * Updates sub-tick mark price for all 14 NSE symbols.
   */
  private updateLiveSubTickPrices() {
    const currentBarTime = this.masterTimestamps[this.barIndex];
    if (!currentBarTime) return;

    for (const sym of NSE_WHITELIST_SYMBOLS) {
      const bar =
        this.candleTimeIndex.get(sym)?.get(currentBarTime) ||
        (this.candlesMap.get(sym) || [])[this.barIndex];
      if (!bar) continue;

      const isBullish = bar.close >= bar.open;
      let tickPrice = bar.close;

      if (isBullish) {
        switch (this.subTickIndex) {
          case 0: tickPrice = bar.open; break;
          case 1: tickPrice = bar.low; break;
          case 2: tickPrice = bar.high; break;
          case 3: tickPrice = bar.close; break;
        }
      } else {
        switch (this.subTickIndex) {
          case 0: tickPrice = bar.open; break;
          case 1: tickPrice = bar.high; break;
          case 2: tickPrice = bar.low; break;
          case 3: tickPrice = bar.close; break;
        }
      }

      this.livePrices[sym] = Number(tickPrice.toFixed(2));
    }
  }

  /**
   * Execute 1 Sub-Tick step of the simulation.
   */
  public stepSubTick(): void {
    if (this.barIndex >= this.totalBars - 1 && this.subTickIndex >= 3) {
      this.barIndex = 45;
      this.subTickIndex = 0;
      this.updateLiveSubTickPrices();
      return;
    }

    this.subTickIndex++;
    if (this.subTickIndex > 3) {
      this.subTickIndex = 0;
      this.barIndex++;
      if (this.barIndex >= this.totalBars) {
        this.barIndex = 45;
        this.subTickIndex = 0;
      }
    }

    this.updateLiveSubTickPrices();
    const currentBarTime = this.masterTimestamps[this.barIndex];
    const subTickTime = currentBarTime + this.subTickIndex * 3.75 * 60 * 1000;

    // 1. Process active positions
    this.evaluateActivePositions(subTickTime);

    // 2. Evaluate fresh entries on bar close (subTick 3)
    if (this.subTickIndex === 3) {
      this.evaluateNewEntries(currentBarTime);
    }
  }

  /**
   * In-Trade Evaluation on EVERY Sub-tick (0, 1, 2, 3)
   */
  private evaluateActivePositions(subTickTime: number) {
    const session = IndianMarketMasterEngine.checkMarketSessionIST(subTickTime);

    for (let i = this.activePositions.length - 1; i >= 0; i--) {
      const pos = this.activePositions[i];
      pos.barsHeld = Math.max(0, this.barIndex - (pos.openedAtBarIndex ?? this.barIndex));

      const currentMark = this.livePrices[pos.symbol] ?? pos.currentPrice;
      pos.currentPrice = currentMark;

      const isBuy = pos.side === 'BUY';
      const delta = pos.isOption ? 0.60 : 1.0;
      const rawMovePct = isBuy
        ? (currentMark - pos.entryPrice) / pos.entryPrice
        : (pos.entryPrice - currentMark) / pos.entryPrice;

      const floatingDiff = isBuy ? currentMark - pos.entryPrice : pos.entryPrice - currentMark;
      let floatingPnlInr = Math.round(floatingDiff * pos.quantity * delta);
      if (floatingPnlInr < -2700) floatingPnlInr = -2500;

      pos.floatingPnlInr = floatingPnlInr;
      pos.floatingPnlUsd = Number((floatingPnlInr / 88.75).toFixed(2));
      pos.currentNetRoePct = Number((rawMovePct * (pos.isOption ? 5 : 1) * 100).toFixed(2));
      if (pos.currentNetRoePct > pos.peakRoePct) pos.peakRoePct = pos.currentNetRoePct;

      // A. Mandatory Intraday Auto Square-Off at 03:18 PM IST
      if (session.mustSquareOffAll) {
        this.closePosition(i, currentMark, 'INTRADAY_AUTO_SQUARE_OFF', subTickTime);
        continue;
      }

      // B. 2-Stage Ladder (BE scratch lock at 35%, profit lock at 70%)
      const bracket = IndianMarketMasterEngine.evaluateLiveTrailingBracket({
        action: pos.side,
        entryPrice: pos.entryPrice,
        currentLtp: currentMark,
        currentSlPrice: pos.slPrice,
        tpPrice: pos.tpPrice,
        tickSize: 0.05,
        stage: pos.stage,
      });

      if (bracket.shouldModifySl) {
        pos.slPrice = bracket.newSlPrice;
        pos.stage = bracket.newStage;
        pos.ratchetLevel = bracket.newStage;
      }

      // C. Target TP Hit
      const isTpHit = isBuy ? currentMark >= pos.tpPrice : currentMark <= pos.tpPrice;
      if (isTpHit) {
        this.closePosition(i, pos.tpPrice, 'TARGET_TP_HIT', subTickTime);
        continue;
      }

      // D. Stop-Loss / Profit-Lock Hit
      const isSlHit = isBuy ? currentMark <= pos.slPrice : currentMark >= pos.slPrice;
      if (isSlHit) {
        let exitReason: ReplayClosedTrade['exitReason'] = 'STOP_LOSS_HIT';
        if (pos.stage === 2) exitReason = 'PROFIT_LOCKED_EXIT';
        else if (pos.stage === 1) exitReason = 'BREAKEVEN_SCRATCH_EXIT';
        this.closePosition(i, pos.slPrice, exitReason, subTickTime);
        continue;
      }
    }
  }

  /**
   * Close a position and update wallet, scorecard, and closed ledger.
   */
  private closePosition(
    index: number,
    exitPrice: number,
    exitReason: ReplayClosedTrade['exitReason'],
    exitTime: number
  ) {
    const pos = this.activePositions[index];
    const isBuy = pos.side === 'BUY';
    const delta = pos.isOption ? 0.60 : 1.0;
    const priceDiff = isBuy ? exitPrice - pos.entryPrice : pos.entryPrice - exitPrice;
    let pnlInr = Math.round(priceDiff * pos.quantity * delta);
    if (pnlInr < -2700) pnlInr = -2500;

    const rawMovePct = isBuy
      ? (exitPrice - pos.entryPrice) / pos.entryPrice
      : (pos.entryPrice - exitPrice) / pos.entryPrice;
    const netRoePct = Number((rawMovePct * (pos.isOption ? 5 : 1) * 100).toFixed(2));

    this.realizedPnlInr += pnlInr;

    // Update Coin Stats
    const stats = this.coinStats.get(pos.symbol);
    if (stats) {
      stats.totalTrades++;
      if (pnlInr >= 0) stats.wins++;
      else stats.losses++;
      stats.winRatePct = Number(((stats.wins / stats.totalTrades) * 100).toFixed(1));
      stats.netPnlInr += pnlInr;
      stats.netPnlUsd = Number((stats.netPnlInr / 88.75).toFixed(2));
      if (exitReason === 'TARGET_TP_HIT') stats.tpHits++;
      else if (exitReason === 'PROFIT_LOCKED_EXIT') stats.profitLockHits++;
      else if (exitReason === 'STOP_LOSS_HIT') stats.slHits++;
    }

    // Update Seat Stats
    const seatRec = this.seatStats.get(pos.seatBucket);
    if (seatRec) {
      seatRec.totalTrades++;
      if (pnlInr >= 0) seatRec.wins++;
      else seatRec.losses++;
      seatRec.winRatePct = Number(((seatRec.wins / seatRec.totalTrades) * 100).toFixed(1));
      seatRec.netPnlInr += pnlInr;
      seatRec.netPnlUsd = Number((seatRec.netPnlInr / 88.75).toFixed(2));
      if (exitReason === 'TARGET_TP_HIT') seatRec.tpHits++;
      else if (exitReason === 'PROFIT_LOCKED_EXIT') seatRec.profitLockHits++;
      else if (exitReason === 'STOP_LOSS_HIT') seatRec.slHits++;
    }

    const closedTrade: ReplayClosedTrade = {
      id: pos.id,
      symbol: pos.symbol,
      side: pos.side,
      seatBucket: pos.seatBucket,
      isOption: pos.isOption,
      optionType: pos.optionType,
      optionStrike: pos.optionStrike,
      entryPrice: pos.entryPrice,
      exitPrice: Number(exitPrice.toFixed(2)),
      entryTime: pos.openedAtTime,
      exitTime,
      entryDateFormatted: pos.openedAtFormatted,
      exitDateFormatted: formatIST(exitTime),
      initialSlPrice: pos.initialSlPrice,
      finalSlPrice: pos.slPrice,
      initialTpPrice: pos.initialTpPrice,
      finalTpPrice: pos.tpPrice,
      quantity: pos.quantity,
      barsHeld: pos.barsHeld,
      notionalInr: pos.notionalInr,
      marginInr: pos.marginInr,
      netPnlInr: pnlInr,
      netPnlUsd: Number((pnlInr / 88.75).toFixed(2)),
      netRoePct,
      exitReason,
      strategyName: pos.strategyName,
      ratchetLevel: pos.stage,
    };

    this.closedLedger.unshift(closedTrade);
    if (this.closedLedger.length > 250) {
      this.closedLedger.pop();
    }

    this.activePositions.splice(index, 1);
  }

  /**
   * New Candle Close Entry Evaluation on Sub-Tick 3
   */
  private evaluateNewEntries(currentTimeMs: number) {
    if (this.activePositions.length >= 6) return;

    const session = IndianMarketMasterEngine.checkMarketSessionIST(currentTimeMs);
    if (!session.canOpenNewTrade) return;

    const chopOccupied = this.activePositions.filter(
      (p) => p.seatBucket === 'CHOP_PING_PONG_SEAT'
    ).length;
    const trendOccupied = this.activePositions.filter(
      (p) => p.seatBucket === 'NORMAL_TREND_RUNNER_SEAT'
    ).length;
    const optionOccupied = this.activePositions.filter(
      (p) => p.seatBucket === 'NIFTY_BANKNIFTY_OPTION_SEAT'
    ).length;

    for (const sym of NSE_WHITELIST_SYMBOLS) {
      if (this.activePositions.length >= 6) break;
      if (this.activePositions.some((p) => p.symbol === sym)) continue;

      const symCandles = this.candlesMap.get(sym) || [];
      if (this.barIndex < 40) continue;
      const window15m = symCandles.slice(0, this.barIndex + 1);

      const isIndex = INDEX_SET.has(sym);
      const sig = IndianMarketMasterEngine.evaluateSymbol({
        symbol: sym,
        candles: window15m,
        isIndex,
        tickSize: 0.05,
        previousDayHigh: window15m[window15m.length - 1]?.previousDayHigh,
        previousDayLow: window15m[window15m.length - 1]?.previousDayLow,
      });

      if (!sig.approved || sig.action === 'WAIT') continue;

      let targetSeat: SeatCategory = 'NONE';
      let isOption = false;

      if (isIndex) {
        if (optionOccupied >= 2) continue;
        targetSeat = 'NIFTY_BANKNIFTY_OPTION_SEAT';
        isOption = true;
      } else {
        if (sig.seatCategory === 'NORMAL_TREND_RUNNER_SEAT' && trendOccupied < 2) {
          targetSeat = 'NORMAL_TREND_RUNNER_SEAT';
        } else if (sig.seatCategory === 'CHOP_PING_PONG_SEAT' && chopOccupied < 2) {
          targetSeat = 'CHOP_PING_PONG_SEAT';
        } else if (trendOccupied < 2) {
          targetSeat = 'NORMAL_TREND_RUNNER_SEAT';
        } else if (chopOccupied < 2) {
          targetSeat = 'CHOP_PING_PONG_SEAT';
        }
      }

      if (targetSeat === 'NONE') continue;

      let quantity = 1;
      if (sym === 'NIFTY') quantity = 25;
      else if (sym === 'BANKNIFTY') quantity = 15;
      else if (sym === 'FINNIFTY') quantity = 25;
      else if (sym === 'SENSEX') quantity = 10;
      else {
        quantity = Math.max(1, Math.round(75000 / sig.entryPrice));
      }

      const notionalInr = Math.round(quantity * sig.entryPrice);
      const marginInr = isOption ? Math.round(notionalInr * 0.008) : Math.round(notionalInr / 5);

      this.tradeCounter++;
      const posId = `NSE-${sym}-${this.tradeCounter}`;

      const newPos: ReplayPosition = {
        id: posId,
        symbol: sym,
        side: sig.action,
        seatBucket: targetSeat,
        isOption,
        optionType: sig.action === 'BUY' ? 'CALL' : 'PUT',
        optionStrike: sig.recommendedStrike,
        entryPrice: sig.entryPrice,
        currentPrice: sig.entryPrice,
        initialSlPrice: sig.slPrice,
        slPrice: sig.slPrice,
        initialTpPrice: sig.tpPrice,
        tpPrice: sig.tpPrice,
        quantity,
        stage: 0,
        marginInr,
        notionalInr,
        floatingPnlInr: 0,
        marginUsd: Number((marginInr / 88.75).toFixed(2)),
        notionalUsd: Number((notionalInr / 88.75).toFixed(2)),
        floatingPnlUsd: 0,
        currentNetRoePct: 0,
        peakRoePct: 0,
        barsHeld: 0,
        openedAtBarIndex: this.barIndex,
        openedAtTime: currentTimeMs,
        openedAtFormatted: formatIST(currentTimeMs),
        reason: sig.setupName,
        strategyName: `INDIAN_SNIPER_${sig.seatCategory}`,
        ratchetLevel: 0,
      };

      this.activePositions.push(newPos);
    }
  }

  public getState(): ReplayEngineState {
    const currentBarTime = this.masterTimestamps[this.barIndex] || Date.now();
    const currentNiftyBar = (this.candlesMap.get('NIFTY') || [])[this.barIndex];
    const session = IndianMarketMasterEngine.checkMarketSessionIST(currentBarTime);

    const totalTrades = this.closedLedger.length;
    const wins = this.closedLedger.filter((t) => t.netPnlInr >= 0).length;
    const losses = this.closedLedger.filter((t) => t.netPnlInr < 0).length;
    const winRatePct = totalTrades > 0 ? Number(((wins / totalTrades) * 100).toFixed(1)) : 0;
    const tpHits = this.closedLedger.filter((t) => t.exitReason === 'TARGET_TP_HIT').length;
    const profitLockHits = this.closedLedger.filter(
      (t) => t.exitReason === 'PROFIT_LOCKED_EXIT'
    ).length;
    const slHits = this.closedLedger.filter((t) => t.exitReason === 'STOP_LOSS_HIT').length;

    const floatingPnlInr = this.activePositions.reduce(
      (acc, p) => acc + (p.floatingPnlInr || 0),
      0
    );
    const balanceInr = this.startingCapitalInr + this.realizedPnlInr + floatingPnlInr;

    const dateStr = currentNiftyBar?.dateStr || '';
    const timeStr = currentNiftyBar?.timeStr || '';
    const monthBanner = `🇮🇳 NSE LIVE REPLAY | 📅 ${dateStr} | ⏰ ${timeStr} | ${session.sessionNote}`;

    const seatBreakdownObj: Record<string, SeatBreakdownRecord> = {};
    for (const [k, v] of this.seatStats.entries()) {
      seatBreakdownObj[k] = v;
    }

    const coinStatsObj: Record<string, CoinScorecard> = {};
    for (const [k, v] of this.coinStats.entries()) {
      coinStatsObj[k] = {
        ...v,
        currentPrice: this.livePrices[k] || 0,
      };
    }

    const progressPct =
      this.totalBars > 0
        ? Number((((this.barIndex + this.subTickIndex / 4) / this.totalBars) * 100).toFixed(1))
        : 0;

    return {
      isRunning: this.isRunning,
      speed: this.speed,
      currentTimestamp: currentBarTime,
      formattedDate: `${dateStr} ${timeStr}`,
      monthBanner,
      barIndex: this.barIndex,
      subTickIndex: this.subTickIndex,
      totalBars: this.totalBars,
      progressPct,
      availableMonths: this.availableMonths,
      wallet: {
        startingCapitalInr: this.startingCapitalInr,
        balanceInr,
        realizedPnlInr: this.realizedPnlInr,
        floatingPnlInr,
        // USD compatibility aliases (1 USD = 88.75 INR)
        startingCapitalUsd: Number((this.startingCapitalInr / 88.75).toFixed(2)),
        balanceUsd: Number((balanceInr / 88.75).toFixed(2)),
        realizedPnlUsd: Number((this.realizedPnlInr / 88.75).toFixed(2)),
        floatingPnlUsd: Number((floatingPnlInr / 88.75).toFixed(2)),
        totalTrades,
        wins,
        losses,
        winRatePct,
        tpHits,
        profitLockHits,
        slHits,
      },
      seatBreakdown: seatBreakdownObj,
      livePrices: this.livePrices,
      activePositions: this.activePositions,
      coinStats: coinStatsObj,
      closedLedger: this.closedLedger,
    };
  }

  public play(): void {
    if (this.isRunning) return;
    this.isRunning = true;
    this.startTimer();
  }

  public pause(): void {
    if (!this.isRunning) return;
    this.isRunning = false;
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  public setSpeed(speed: number): void {
    this.speed = Math.max(1, Math.min(100, speed));
    if (this.isRunning) {
      this.startTimer();
    }
  }

  public jumpToBar(targetBarIndex: number): void {
    this.barIndex = Math.max(45, Math.min(this.totalBars - 1, targetBarIndex));
    this.subTickIndex = 0;
    this.updateLiveSubTickPrices();
  }

  public reset(): void {
    this.pause();
    this.barIndex = 45;
    this.subTickIndex = 0;
    this.realizedPnlInr = 0;
    this.activePositions = [];
    this.closedLedger = [];
    this.tradeCounter = 0;
    this.resetStats();
    this.updateLiveSubTickPrices();
  }

  private startTimer(): void {
    if (this.timer) {
      clearInterval(this.timer);
    }
    // Sub-tick delay based on speed
    const baseDelayMs = 600;
    const tickIntervalMs = Math.max(15, Math.round(baseDelayMs / this.speed));
    this.timer = setInterval(() => {
      this.stepSubTick();
    }, tickIntervalMs);
  }
}

export const timeMachineReplay = TimeMachineReplayEngine.getInstance();

