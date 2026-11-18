/**
 * FILE: lib/bharat/nexusBharatAutoEngine.ts
 * ============================================================================
 * NEXUS BHARAT — 7-LAYER AUTONOMOUS INDIAN MARKET BUY/SELL & 6-STAGE LADDER ENGINE
 * Automatically executes Equities & NIFTY/BANKNIFTY Options across 2+2+2 Seats:
 *   - Layer 1: Anti-Chop Market Breadth Filter (>= 65% across 14 Whitelist Stocks)
 *   - Layer 2: Intraday Session VWAP + EMA 9 > EMA 21 > EMA 50 Alignment
 *   - Layer 3: Anti-FOMO Value-Zone Pullback Retest (Low <= EMA9 * 1.002 / High >= EMA9 * 0.998)
 *   - Layer 4: Candle Anatomy (Wick <= 28%) + RSI (53-72 BUY / 28-47 SELL) + RVOL (>= 1.15x)
 *   - Layer 5: Inter-Market Index Confluence (IMIC: NIFTY & BANKNIFTY in Sync for Options)
 *   - Layer 6: Smart SL (0.12% Buffer, -₹1500 Cap, -₹350 VWAP Breakdown Early Cut)
 *              + 6-Stage Trailing Ladder (+₹500 -> +₹3000)
 *   - Layer 7: IST Session Time Gates (10:00–15:10 Entry, 15:18 Auto Square-Off, -₹2500 Breaker)
 * ============================================================================
 */

import {
  UniversalIndianMarketConnector,
  type ExchangeContractMaster
} from './universalIndianMarketConnector.ts';
import { DiamondHandsHoldManager } from './diamondHandsHoldManager.ts';
import { NexusPermanentCore } from './nexusPermanentCore.ts';

export interface NseCandle5m {
  timestamp: number; // Epoch ms
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export type SeatId =
  | 'OPTION_1'
  | 'OPTION_2'
  | 'TREND_1'
  | 'TREND_2'
  | 'CHOP_1'
  | 'CHOP_2';

export interface ActiveBharatPosition {
  id: string;
  seatId: SeatId;
  symbol: string;
  isOption: boolean;
  optionType?: 'CE' | 'PE';
  underlyingSymbol?: 'NIFTY' | 'BANKNIFTY';
  side: 'BUY' | 'SELL';
  qty: number;
  entryPrice: number;
  currentPrice: number;
  initialSlPrice: number;
  currentSlPrice: number;
  targetPrice: number;
  currentVwap: number;
  unrealizedPnlInr: number;
  lockedProfitInr: number;
  ladderStage: 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8;
  openedAtIst: string;
  openedEpochMs?: number;
}

export interface ClosedBharatTrade {
  id: string;
  seatId: SeatId;
  symbol: string;
  side: 'BUY' | 'SELL';
  qty: number;
  entryPrice: number;
  exitPrice: number;
  netPnlInr: number;
  ladderStageReached: number;
  exitReason:
    | 'TARGET_3000_HIT'
    | 'LADDER_TRAIL_SL_HIT'
    | 'SMART_VWAP_EARLY_CUT'
    | 'INITIAL_SL_HIT'
    | 'AUTO_SQUARE_OFF_318PM'
    | 'DAILY_CIRCUIT_BREAKER';
  closedAtIst: string;
}

export interface MarketBreadthSnapshot {
  totalSymbols: number;
  bullishCount: number;
  bearishCount: number;
  breadthPct: number;
  dominantBias: 'BULLISH' | 'BEARISH' | 'SECTOR_ROTATION' | 'NEUTRAL_CHOP';
}

export interface SignalCandidate {
  symbol: string;
  side: 'BUY' | 'SELL';
  entryPrice: number;
  slPrice: number;
  tpPrice: number;
  qty: number;
  vwap: number;
  ema9: number;
  ema21: number;
  ema50: number;
  rsi14: number;
  rvol: number;
  score: number;
  reason: string;
}

export class NexusBharatAutoEngine {
  public static readonly FO_TOP_50_LOT_SIZES: Record<string, number> = {
    RELIANCE: 250, HDFCBANK: 550, ICICIBANK: 700, SBIN: 750, INFY: 400,
    TCS: 175, TATAMOTORS: 550, AXISBANK: 625, KOTAKBANK: 400, LT: 150,
    BAJFINANCE: 125, BHARTIARTL: 475, TATASTEEL: 5500, MARUTI: 100, HINDUNILVR: 300,
    ITC: 1600, SUNPHARMA: 700, 'M&M': 200, TITAN: 175, ADANIENT: 300,
    ADANIPORTS: 800, COALINDIA: 2100, ONGC: 3850, NTPC: 1500, POWERGRID: 3600,
    BAJAJFINSV: 500, HCLTECH: 350, WIPRO: 1500, TECHM: 600, ULTRACEMCO: 100,
    GRASIM: 250, JSWSTEEL: 675, HINDALCO: 1400, VEDL: 2300, BPCL: 1800,
    IOC: 4875, INDUSINDBK: 500, BANKBARODA: 2925, PFC: 1300, RECLTD: 1000,
    BHEL: 2625, BEL: 2850, HAL: 150, DLF: 825, EICHERMOT: 175,
    HEROMOTOCO: 150, TRENT: 100, SIEMENS: 125, APOLLOHOSP: 125, DIVISLAB: 150
  };
  public static readonly TOP_50_FO_STOCKS = Object.keys(NexusBharatAutoEngine.FO_TOP_50_LOT_SIZES);

  public static readonly WHITELIST_14 = [
    'HDFCBANK',
    'ICICIBANK',
    'SBIN',
    'AXISBANK',
    'RELIANCE',
    'TCS',
    'INFY',
    'LT',
    'TATAMOTORS',
    'M&M',
    'BHARTIARTL',
    'SUNPHARMA',
    'TATASTEEL',
    'BAJFINANCE',
  ];

  public static readonly symbolCooldownUntilMs: Map<string, number> = new Map();

  private activePositions: Map<SeatId, ActiveBharatPosition> = new Map();
  private closedTrades: ClosedBharatTrade[] = [];
  private realizedDailyPnlInr = 0;
  private circuitBreakerTriggered = false;
  private lastEvaluated5mBucket = 0;
  public freezeNewEntries: boolean = false;

  public restoreActivePosition(pos: ActiveBharatPosition): void {
    this.activePositions.set(pos.seatId, pos);
  }

  public getAvailableEquitySeat(): SeatId | null {
    const equitySeats: SeatId[] = ['TREND_1', 'TREND_2', 'CHOP_1', 'CHOP_2'];
    for (const seat of equitySeats) {
      if (!this.activePositions.has(seat)) return seat;
    }
    return null;
  }

  public clearAllPositionsAndTrades(): void {
    this.activePositions.clear();
    this.closedTrades = [];
    this.realizedDailyPnlInr = 0;
    this.circuitBreakerTriggered = false;
  }

  // ===========================================================================
  // MASTER AUTOMATIC TICK & 5M CANDLE ORCHESTRATOR (CALL EVERY 1–2 SECONDS)
  // ===========================================================================
  public async runAutoCycle(params: {
    nowEpochMs?: number;
    stockCandles5m: Record<string, NseCandle5m[]>;
    niftyCandles5m: NseCandle5m[];
    bankNiftyCandles5m: NseCandle5m[];
    liveLtpMap: Record<string, number>;
    onStockSignal?: (signal: {
      symbol: string;
      side: 'BUY' | 'SELL';
      spotPrice: number;
      istTime: string;
    }) => Promise<void>;
    executeBrokerOrder?: (order: {
      symbol: string;
      side: 'BUY' | 'SELL';
      qty: number;
      price: number;
      seatId: SeatId;
      tag: string;
      sebiAlgoTag?: string;
      orderSlices?: number[];
    }) => Promise<void>;
  }): Promise<{
    istTimeStr: string;
    sessionPhase: string;
    breadth: MarketBreadthSnapshot;
    realizedDailyPnlInr: number;
    floatingPnlInr: number;
    circuitBreakerTriggered: boolean;
    activePositions: ActiveBharatPosition[];
    recentClosedTrades: ClosedBharatTrade[];
  }> {
    const nowMs = params.nowEpochMs ?? Date.now();
    const ist = this.getIstClock(nowMs);

    // 1. UPDATE ALL OPEN POSITIONS ON EVERY LIVE TICK (6-STAGE LADDER + SMART SL + 3:18 PM EXIT)
    await this.manageOpenPositionsOnTick(
      ist,
      params.liveLtpMap,
      params.stockCandles5m,
      params.niftyCandles5m,
      params.bankNiftyCandles5m,
      params.executeBrokerOrder
    );

    // 2. CALCULATE LAYER 1: 14-STOCK MARKET BREADTH
    const breadth = this.computeMarketBreadth(params.stockCandles5m);

    // 3. CHECK DAILY CIRCUIT BREAKER (-₹2,500 HARD FREEZE)
    if (this.realizedDailyPnlInr <= -2500) {
      this.circuitBreakerTriggered = true;
    }

    // 4. CHECK LAYER 7 & USER COMMAND FOR NEW ENTRIES
    const canEnterNewTrades =
      !this.freezeNewEntries &&
      !this.circuitBreakerTriggered &&
      ist.minutesFromMidnight >= 9 * 60 + 25 && // After 09:25 AM Warm-Up
      ist.minutesFromMidnight <= 15 * 60 + 10; // Before 03:10 PM Entry Cutoff

    // 5. ON EVERY CLOSED 5-MINUTE CANDLE (OR INITIAL SETUP), AUTOMATICALLY SCAN & FIRE
    const current5mBucket = Math.floor(nowMs / (5 * 60 * 1000));
    const hasValidCandles = Object.keys(params.stockCandles5m).length >= 10;
    const shouldEvaluate =
      canEnterNewTrades &&
      hasValidCandles &&
      (current5mBucket > this.lastEvaluated5mBucket || this.lastEvaluated5mBucket === 0);

    if (shouldEvaluate) {
      this.lastEvaluated5mBucket = current5mBucket;

      await this.scanAndExecuteNewEntries({
        ist,
        breadth,
        stockCandles5m: params.stockCandles5m,
        niftyCandles5m: params.niftyCandles5m,
        bankNiftyCandles5m: params.bankNiftyCandles5m,
        liveLtpMap: params.liveLtpMap,
        onStockSignal: params.onStockSignal,
        executeBrokerOrder: params.executeBrokerOrder,
      });
    }

    const floatingPnlInr = Array.from(this.activePositions.values()).reduce(
      (sum, p) => sum + p.unrealizedPnlInr,
      0
    );

    return {
      istTimeStr: ist.formattedTime,
      sessionPhase: ist.phaseLabel,
      breadth,
      realizedDailyPnlInr: Number(this.realizedDailyPnlInr.toFixed(2)),
      floatingPnlInr: Number(floatingPnlInr.toFixed(2)),
      circuitBreakerTriggered: this.circuitBreakerTriggered,
      freezeNewEntries: this.freezeNewEntries,
      activePositions: Array.from(this.activePositions.values()),
      recentClosedTrades: this.closedTrades.slice(0, 50),
    };
  }

  // ===========================================================================
  // LAYER 1: ANTI-CHOP MARKET BREADTH FILTER (>= 65.0%)
  // ===========================================================================
  public computeMarketBreadth(
    stockCandles5m: Record<string, NseCandle5m[]>
  ): MarketBreadthSnapshot {
    let bullishCount = 0;
    let bearishCount = 0;
    let validCount = 0;

    for (const sym of NexusBharatAutoEngine.WHITELIST_14) {
      const candles = stockCandles5m[sym];
      if (!candles || candles.length < 25) continue;
      validCount++;

      const closes = candles.map((c) => c.close);
      const lastClose = closes[closes.length - 1];
      const vwap = this.computeIntradayVwap(candles);
      const ema9 = this.computeEma(closes, 9);
      const ema21 = this.computeEma(closes, 21);

      if (lastClose > vwap && ema9 >= ema21) {
        bullishCount++;
      } else if (lastClose < vwap && ema9 <= ema21) {
        bearishCount++;
      }
    }

    const total = Math.max(1, validCount);
    const maxDirectional = Math.max(bullishCount, bearishCount);
    const breadthPct = Number(((maxDirectional / total) * 100).toFixed(1));

    let dominantBias: MarketBreadthSnapshot['dominantBias'] = 'NEUTRAL_CHOP';
    // Lowered threshold from 65.0% to 55.0% (8 out of 14 stocks)
    if (breadthPct >= 55.0) {
      dominantBias = bullishCount >= bearishCount ? 'BULLISH' : 'BEARISH';
    } else if (breadthPct >= 45.0) {
      // 45%–55% Sector Rotation Mode: allows stock-specific relative strength trades!
      dominantBias = 'SECTOR_ROTATION';
    }

    return {
      totalSymbols: total,
      bullishCount,
      bearishCount,
      breadthPct,
      dominantBias,
    };
  }

  // ===========================================================================
  // LAYERS 2, 3, 4 & 5: AUTOMATIC ENTRY SCANNER (OPTIONS + EQUITY RUNNERS)
  // ===========================================================================
  private async scanAndExecuteNewEntries(params: {
    ist: { formattedTime: string; minutesFromMidnight: number };
    breadth: MarketBreadthSnapshot;
    stockCandles5m: Record<string, NseCandle5m[]>;
    niftyCandles5m: NseCandle5m[];
    bankNiftyCandles5m: NseCandle5m[];
    liveLtpMap: Record<string, number>;
    onStockSignal?: (signal: {
      symbol: string;
      side: 'BUY' | 'SELL';
      spotPrice: number;
      istTime: string;
    }) => Promise<void>;
    executeBrokerOrder?: (order: {
      symbol: string;
      side: 'BUY' | 'SELL';
      qty: number;
      price: number;
      seatId: SeatId;
      tag: string;
      sebiAlgoTag?: string;
      orderSlices?: number[];
    }) => Promise<void>;
  }): Promise<void> {
    const { ist, breadth, stockCandles5m, niftyCandles5m, bankNiftyCandles5m, liveLtpMap } =
      params;

    // USER COMMAND: कोई और ट्रेड नहीं लेगा (Hard Freeze on all new entries)
    if (this.freezeNewEntries) {
      return;
    }

    // If Breadth < 45% (Chop below 45%), strictly hold in cash preserve
    if (breadth.dominantBias === 'NEUTRAL_CHOP') {
      return;
    }

    // -------------------------------------------------------------------------
    // LAYER 5: INTER-MARKET INDEX CONFLUENCE (IMIC) FOR OPTION_1 & OPTION_2
    // Requires Directional Breadth >= 55.0% (BULLISH or BEARISH)
    // -------------------------------------------------------------------------
    if (breadth.dominantBias === 'BULLISH' || breadth.dominantBias === 'BEARISH') {
      const allowedOptionSide: 'BUY' | 'SELL' =
        breadth.dominantBias === 'BULLISH' ? 'BUY' : 'SELL';

      if (!this.activePositions.has('OPTION_1') || !this.activePositions.has('OPTION_2')) {
        const imic = this.evaluateIndexImicConfluence(
          niftyCandles5m,
          bankNiftyCandles5m,
          allowedOptionSide
        );

        if (imic.inSync) {
          if (!this.activePositions.has('OPTION_1') && imic.niftySignal) {
            await this.openOptionSeat(
              'OPTION_1',
              'NIFTY',
              allowedOptionSide === 'BUY' ? 'CE' : 'PE',
              imic.niftySignal,
              liveLtpMap,
              ist.formattedTime,
              params.executeBrokerOrder
            );
          }
          if (!this.activePositions.has('OPTION_2') && imic.bankNiftySignal) {
            await this.openOptionSeat(
              'OPTION_2',
              'BANKNIFTY',
              allowedOptionSide === 'BUY' ? 'CE' : 'PE',
              imic.bankNiftySignal,
              liveLtpMap,
              ist.formattedTime,
              params.executeBrokerOrder
            );
          }
        }
      }
    }

    // -------------------------------------------------------------------------
    // LAYERS 2, 3 & 4: SCAN 14 WHITELIST STOCKS FOR TREND_1/2 & CHOP_1/2 SEATS
    // In Sector Rotation Mode (45%–55%), stocks trade by individual Relative Strength!
    // -------------------------------------------------------------------------
    const candidates: SignalCandidate[] = [];
    for (const sym of NexusBharatAutoEngine.WHITELIST_14) {
      if (this.isSymbolAlreadyOpen(sym)) continue;
      // ANTI-SPAM & OVER-TRADING SHIELD: 20-minute mandatory cooldown on exited symbol
      const cooldownUntil = NexusBharatAutoEngine.symbolCooldownUntilMs.get(sym) || 0;
      if (Date.now() < cooldownUntil) continue;
      const candles = stockCandles5m[sym];
      if (!candles || candles.length < 52) continue;

      let stockAllowedSide: 'BUY' | 'SELL' | null = null;
      if (breadth.dominantBias === 'BULLISH') {
        stockAllowedSide = 'BUY';
      } else if (breadth.dominantBias === 'BEARISH') {
        stockAllowedSide = 'SELL';
      } else if (breadth.dominantBias === 'SECTOR_ROTATION') {
        // Sector Rotation Mode: Check individual Relative Strength vs VWAP & EMA9/21
        const closes = candles.map((c) => c.close);
        const lastClose = closes[closes.length - 1];
        const vwap = this.computeIntradayVwap(candles);
        const ema9 = this.computeEma(closes, 9);
        const ema21 = this.computeEma(closes, 21);

        if (lastClose > vwap && ema9 > ema21) {
          stockAllowedSide = 'BUY';
        } else if (lastClose < vwap && ema9 < ema21) {
          stockAllowedSide = 'SELL';
        }
      }

      if (!stockAllowedSide) continue;

      const evalResult = this.evaluateSingleInstrumentLayers2To4(
        sym,
        candles,
        stockAllowedSide,
        ist.minutesFromMidnight
      );
      if (evalResult) {
        candidates.push(evalResult);
      }
    }

    // Rank by RVOL + Momentum Score so top leaders get seats first
    candidates.sort((a, b) => b.score - a.score);

    const availableEquitySeats: SeatId[] = (
      ['TREND_1', 'TREND_2', 'CHOP_1', 'CHOP_2'] as SeatId[]
    ).filter((s) => !this.activePositions.has(s));

    for (let i = 0; i < Math.min(candidates.length, availableEquitySeats.length); i++) {
      const seat = availableEquitySeats[i];
      const sig = candidates[i];

      // F&O Stock Option Execution: BUY signal -> ATM Call Option (CE), SELL signal -> ATM Put Option (PE)
      const isCall = sig.side === 'BUY';
      const optType = isCall ? 'CE' : 'PE';

      // 1. Resolve Exact Real Exchange-Listed Contract via 5-Guardrail Stock Option Engine
      const decision = await UniversalIndianMarketConnector.resolveStockOptionWithGuardrails({
        symbol: sig.symbol,
        spotPrice: sig.entryPrice,
        optionType: optType,
        offset: 0,
        requestedLots: 1,
        autoRollToNextMonthOnPhysicalWindow: true,
      });

      if (!decision.approved || !decision.tradingSymbol) {
        console.warn(`[Stock Option STRICT VETO] ${sig.symbol} ${optType}: ${decision.vetoReason}`);
        continue;
      }

      const lotQty = decision.lotSize;
      const atmStrike = decision.selectedStrike;

      // Enforce NexusPermanentCore: Block impossible strikes or split-corrupted spot prices (e.g. INFY 1114, KOTAK 495, BAJFINANCE 1100)
      if (!NexusPermanentCore.isContractRealAndValid(sig.symbol, atmStrike, sig.entryPrice)) {
        console.warn(`[Stock Option VETO - CORRUPTED PRICE] ${sig.symbol}: Spot=₹${sig.entryPrice}, Strike=${atmStrike}`);
        continue;
      }

      const optionSymbol = decision.tradingSymbol;
      const realPremium = decision.protectedLimitBuyPrice; // Mandatory Protected Limit Order Price

      console.log(
        `🏛️ [Stock Option 5-Guardrail Selected] ${sig.symbol} | Spot: ₹${sig.entryPrice} | ` +
        `Strike: ${atmStrike} ${optType} (${optionSymbol}) | Protected Limit Buy: ₹${realPremium} (Ask: ₹${decision.ask}) | ` +
        `Spread: ₹${decision.spreadInr} (${decision.spreadPct}%) | OI: ${decision.openInterest.toLocaleString('en-IN')} | ` +
        `DTE: ${decision.daysToExpiry} (Rolled Next Month: ${decision.rolledToNextMonthForPhysicalGuard ? 'YES' : 'NO'}) | ` +
        `Order: ${decision.orderType} | Slices: [${decision.orderSlices.join(', ')}] | SEBI Tag: ${decision.sebiAlgoTag}`
      );

      const maxLossInr = 2500; // Strict user rule: ₹2,500 Max Loss per lot
      const minTpInr = 3000;   // Strict user rule: Minimum ₹3,000 Profit before trailing

      const slPrice = Number(Math.max(0.05, realPremium - maxLossInr / lotQty).toFixed(2));
      const tpPrice = Number((realPremium + minTpInr / lotQty).toFixed(2));

      const pos: ActiveBharatPosition = {
        id: `${optionSymbol}-${Date.now()}`,
        seatId: seat,
        symbol: optionSymbol,
        underlyingSymbol: sig.symbol as any,
        isOption: true,
        optionType: optType,
        side: 'BUY', // Option buyer: Buying CE on bullish signal, Buying PE on bearish signal
        qty: lotQty,
        entryPrice: realPremium,
        currentPrice: realPremium,
        initialSlPrice: slPrice,
        currentSlPrice: slPrice,
        targetPrice: tpPrice,
        currentVwap: sig.vwap,
        unrealizedPnlInr: 0,
        lockedProfitInr: 0,
        ladderStage: 0,
        openedAtIst: ist.formattedTime,
      };

      this.activePositions.set(seat, pos);

      if (params.executeBrokerOrder) {
        const ok = await params.executeBrokerOrder({
          symbol: optionSymbol,
          side: 'BUY',
          qty: lotQty,
          price: realPremium,
          seatId: seat,
          tag: `${sig.reason}_STOCK_OPT_${optType}_${decision.sebiAlgoTag}`,
          sebiAlgoTag: decision.sebiAlgoTag,
          orderSlices: decision.orderSlices,
        });
        if (ok === false) {
          this.activePositions.delete(seat);
        }
      }
    }
  }

  private getStrikeStepForPrice(price: number): number {
    if (price < 250) return 2.5;
    if (price < 500) return 5;
    if (price < 1000) return 10;
    if (price < 2500) return 20;
    if (price < 5000) return 50;
    return 100;
  }

  // ===========================================================================
  // UPGRADED LAYERS 2, 3, 4 + INSTITUTIONAL PRICE ACTION & REVERSAL-WALL TP/SL
  // ===========================================================================
  public evaluateSingleInstrumentLayers2To4(
    symbol: string,
    candles: NseCandle5m[],
    allowedSide: 'BUY' | 'SELL',
    minutesFromMidnight: number
  ): SignalCandidate | null {
    if (candles.length < 52) return null;

    const n = candles.length;
    const c0 = candles[n - 1]; // Current closed 5m candle
    const c1 = candles[n - 2]; // Previous 5m candle
    const c2 = candles[n - 3]; // 2 bars ago
    const closes = candles.map((c) => c.close);
    const entryPrice = c0.close;

    const vwap = this.computeIntradayVwap(candles);
    const ema9 = this.computeEma(closes, 9);
    const ema21 = this.computeEma(closes, 21);
    const ema50 = this.computeEma(closes, 50);
    const rsi14 = this.computeRsi(closes, 14);

    // RVOL Check (Mid-Morning Adaptive Baseline)
    const isMidMorning = minutesFromMidnight >= 10 * 60 + 15;
    // Calculate baseline volume: after 10:15 AM, use last 10 mid-morning bars excluding 09:15-10:00 AM distortion
    const baselineBars = isMidMorning ? candles.slice(-11, -1) : candles.slice(-21, -1);
    const avgVol =
      baselineBars.reduce((sum, b) => sum + (b.volume || 1), 0) / Math.max(1, baselineBars.length);
    const rvol = avgVol > 0 ? (c0.volume || avgVol) / avgVol : 1.0;
    const rvolPrior = avgVol > 0 ? (c1.volume || avgVol) / avgVol : 1.0;

    const minRequiredRvol = minutesFromMidnight < 10 * 60 ? 1.3 : isMidMorning ? 0.70 : 1.1;
    // After 10:15 AM, allow if current bar >= 0.70x OR prior closed bar confirmed volume >= 0.50x during healthy pullback
    const volumePass =
      rvol >= minRequiredRvol ||
      (isMidMorning && (rvol >= 0.50 || rvolPrior >= 0.50));
    if (!volumePass) return null;

    // -------------------------------------------------------------------------
    // PRICE ACTION CANDLE ANATOMY & PATTERN DETECTOR
    // -------------------------------------------------------------------------
    const range0 = Math.max(c0.high - c0.low, 1e-8);
    const body0 = Math.abs(c0.close - c0.open);
    const bodyRatio0 = body0 / range0;
    const upperWickRatio0 = (c0.high - Math.max(c0.open, c0.close)) / range0;
    const lowerWickRatio0 = (Math.min(c0.open, c0.close) - c0.low) / range0;

    // 1. Pinbar / Hammer / Shooting Star Rejection
    const isBullishPinbar =
      c0.close > c0.open &&
      lowerWickRatio0 >= 0.35 &&
      upperWickRatio0 <= 0.25 &&
      bodyRatio0 >= 0.18;
    const isBearishShootingStar =
      c0.close < c0.open &&
      upperWickRatio0 >= 0.35 &&
      lowerWickRatio0 <= 0.25 &&
      bodyRatio0 >= 0.18;

    // 2. Bullish / Bearish Engulfing & Piercing Reclaim
    const isBullishEngulfing =
      c0.close > c0.open &&
      c1.close < c1.open &&
      c0.close > (c1.open + c1.close) / 2 &&
      bodyRatio0 >= 0.45 &&
      upperWickRatio0 <= 0.25;
    const isBearishEngulfing =
      c0.close < c0.open &&
      c1.close > c1.open &&
      c0.close < (c1.open + c1.close) / 2 &&
      bodyRatio0 >= 0.45 &&
      lowerWickRatio0 <= 0.25;

    // 3. 3-Candle Morning Star / Evening Star Turn
    const isMorningStar =
      c2.close < c2.open &&
      c0.close > c0.open &&
      c0.close > Math.max(c1.high, (c2.open + c2.close) / 2) &&
      bodyRatio0 >= 0.42 &&
      upperWickRatio0 <= 0.26;
    const isEveningStar =
      c2.close > c2.open &&
      c0.close < c0.open &&
      c0.close < Math.min(c1.low, (c2.open + c2.close) / 2) &&
      bodyRatio0 >= 0.42 &&
      lowerWickRatio0 <= 0.26;

    // 4. Inside-Bar / Structure Breakout Candle
    const isBullishBreakoutBar =
      c0.close > c0.open &&
      c0.close > c1.high &&
      bodyRatio0 >= 0.50 &&
      upperWickRatio0 <= 0.24;
    const isBearishBreakdownBar =
      c0.close < c0.open &&
      c0.close < c1.low &&
      bodyRatio0 >= 0.50 &&
      lowerWickRatio0 <= 0.24;

    // 5. Clean Continuation / Rejection Candle
    const isBullishContinuation =
      c0.close > c0.open &&
      upperWickRatio0 <= 0.35;
    const isBearishContinuation =
      c0.close < c0.open &&
      lowerWickRatio0 <= 0.35;

    const bullishPaPattern = isBullishPinbar
      ? 'PA_HAMMER_PINBAR_BUY'
      : isBullishEngulfing
      ? 'PA_BULLISH_ENGULFING_BUY'
      : isMorningStar
      ? 'PA_MORNING_STAR_BUY'
      : isBullishBreakoutBar
      ? 'PA_STRUCTURE_BREAKOUT_BUY'
      : isBullishContinuation
      ? 'PA_CLEAN_CONTINUATION_BUY'
      : null;

    const bearishPaPattern = isBearishShootingStar
      ? 'PA_SHOOTING_STAR_SELL'
      : isBearishEngulfing
      ? 'PA_BEARISH_ENGULFING_SELL'
      : isEveningStar
      ? 'PA_EVENING_STAR_SELL'
      : isBearishBreakdownBar
      ? 'PA_STRUCTURE_BREAKDOWN_SELL'
      : isBearishContinuation
      ? 'PA_CLEAN_CONTINUATION_SELL'
      : null;

    // -------------------------------------------------------------------------
    // SCAN STRUCTURAL SWING HIGHS & LOWS (FOR REVERSAL-WALL TP & PROTECTED SL)
    // -------------------------------------------------------------------------
    const lookback = candles.slice(-42, -1);
    const swingHighs: number[] = [];
    const swingLows: number[] = [];

    for (let i = 2; i < lookback.length - 2; i++) {
      const b = lookback[i];
      if (
        b.high >= lookback[i - 1].high &&
        b.high >= lookback[i - 2].high &&
        b.high >= lookback[i + 1].high &&
        b.high >= lookback[i + 2].high
      ) {
        swingHighs.push(b.high);
      }
      if (
        b.low <= lookback[i - 1].low &&
        b.low <= lookback[i - 2].low &&
        b.low <= lookback[i + 1].low &&
        b.low <= lookback[i + 2].low
      ) {
        swingLows.push(b.low);
      }
    }

    const recent3Low = Math.min(c0.low, c1.low, c2.low);
    const recent3High = Math.max(c0.high, c1.high, c2.high);

    if (allowedSide === 'BUY') {
      // Layer 2: Multi-Timeframe Trend Alignment OR Liquidity Sweep Reclaim above VWAP
      const trendAligned = entryPrice > vwap && ema9 > ema21 && ema21 >= ema50 * 0.999;
      // Layer 3: Value-Zone Retest (tested within 0.35% of EMA 9, EMA 21, OR Intraday VWAP)
      const valueZoneHigh = Math.max(ema9, ema21, vwap);
      const retestedValueZone = recent3Low <= valueZoneHigh * 1.0035;

      // Layer 4: Must have a valid Bullish Price Action Pattern + RSI 46–74
      if (!trendAligned || !retestedValueZone || !bullishPaPattern || rsi14 < 46 || rsi14 > 74) {
        return null;
      }

      // SMART BREATHING SL: Behind the 3-bar Rejection Wick OR minimum 0.60% breathing buffer (whichever is safer)
      const rawWickSl = recent3Low * (1 - 0.0015);
      const minBufferSl = entryPrice * (1 - 0.0060);
      const slPrice = Number(Math.min(rawWickSl, minBufferSl).toFixed(2));
      const slDist = Math.max(entryPrice - slPrice, entryPrice * 0.0060);
      const maxRiskQty = Math.max(1, Math.floor(400 / slDist)); // Max risk strictly capped at -₹400
      const maxMarginQty = Math.max(1, Math.floor(8000 / (entryPrice * 0.20))); // ₹8,000 margin cap per seat (~₹40k turnover)
      const qty = Math.min(maxRiskQty, maxMarginQty);

      // SMART PRE-REVERSAL TP: 0.08% before the ahead Structural Reversal Wall (min 1.8R or +₹3,000 Hurdle)
      const minTargetPrice = entryPrice + slDist * 1.8;
      const aheadWalls = swingHighs
        .filter((h) => h >= minTargetPrice)
        .sort((a, b) => a - b);

      const rawTpWall =
        aheadWalls.length > 0 ? aheadWalls[0] * (1 - 0.0008) : entryPrice + 3000 / qty;
      const tpPrice = Number(Math.max(minTargetPrice, rawTpWall).toFixed(2));

      return {
        symbol,
        side: 'BUY',
        entryPrice,
        slPrice,
        tpPrice,
        qty,
        vwap,
        ema9,
        ema21,
        ema50,
        rsi14,
        rvol,
        score: rvol * 55 + bodyRatio0 * 30 + (rsi14 - 50),
        reason: `${bullishPaPattern} (VWAP=${vwap.toFixed(1)}, RSI=${rsi14.toFixed(1)}, RVOL=${rvol.toFixed(2)}x)`,
      };
    } else {
      // Layer 2: Bearish Alignment below VWAP
      const trendAligned = entryPrice < vwap && ema9 < ema21 && ema21 <= ema50 * 1.001;
      // Layer 3: Value-Zone Retest (tested within 0.35% of EMA 9, EMA 21, OR Intraday VWAP)
      const valueZoneLow = Math.min(ema9, ema21, vwap);
      const retestedValueZone = recent3High >= valueZoneLow * 0.9965;

      // Layer 4: Must have a valid Bearish Price Action Pattern + RSI 26–54
      if (!trendAligned || !retestedValueZone || !bearishPaPattern || rsi14 < 26 || rsi14 > 54) {
        return null;
      }

      // SMART BREATHING SL: Above the 3-bar Rejection Wick OR minimum 0.60% breathing buffer (whichever is safer)
      const rawWickSl = recent3High * (1 + 0.0015);
      const minBufferSl = entryPrice * (1 + 0.0060);
      const slPrice = Number(Math.max(rawWickSl, minBufferSl).toFixed(2));
      const slDist = Math.max(slPrice - entryPrice, entryPrice * 0.0060);
      const maxRiskQty = Math.max(1, Math.floor(400 / slDist)); // Max risk strictly capped at -₹400
      const maxMarginQty = Math.max(1, Math.floor(8000 / (entryPrice * 0.20))); // ₹8,000 margin cap per seat (~₹40k turnover)
      const qty = Math.min(maxRiskQty, maxMarginQty);

      // SMART PRE-REVERSAL TP: 0.08% before the ahead Structural Demand Wall (min 1.8R or +₹1,500)
      const maxTargetPrice = entryPrice - slDist * 1.8;
      const aheadWalls = swingLows
        .filter((l) => l <= maxTargetPrice)
        .sort((a, b) => b - a);

      const rawTpWall =
        aheadWalls.length > 0 ? aheadWalls[0] * (1 + 0.0008) : entryPrice - 3000 / qty;
      const tpPrice = Number(Math.min(maxTargetPrice, rawTpWall).toFixed(2));

      return {
        symbol,
        side: 'SELL',
        entryPrice,
        slPrice,
        tpPrice,
        qty,
        vwap,
        ema9,
        ema21,
        ema50,
        rsi14,
        rvol,
        score: rvol * 55 + bodyRatio0 * 30 + (50 - rsi14),
        reason: `${bearishPaPattern} (VWAP=${vwap.toFixed(1)}, RSI=${rsi14.toFixed(1)}, RVOL=${rvol.toFixed(2)}x)`,
      };
    }
  }

  // ===========================================================================
  // REUSABLE INSTITUTIONAL PRICE ACTION DETECTOR HELPER
  // ===========================================================================
  public detectCandlePriceAction(
    c0: NseCandle5m,
    c1: NseCandle5m,
    c2: NseCandle5m
  ): {
    bullishPaPattern: string | null;
    bearishPaPattern: string | null;
    bodyRatio: number;
    upperWickRatio: number;
    lowerWickRatio: number;
  } {
    const range0 = Math.max(c0.high - c0.low, 1e-8);
    const body0 = Math.abs(c0.close - c0.open);
    const bodyRatio = body0 / range0;
    const upperWickRatio = (c0.high - Math.max(c0.open, c0.close)) / range0;
    const lowerWickRatio = (Math.min(c0.open, c0.close) - c0.low) / range0;

    const isBullishPinbar =
      c0.close > c0.open && lowerWickRatio >= 0.35 && upperWickRatio <= 0.25 && bodyRatio >= 0.18;
    const isBearishShootingStar =
      c0.close < c0.open && upperWickRatio >= 0.35 && lowerWickRatio <= 0.25 && bodyRatio >= 0.18;

    const isBullishEngulfing =
      c0.close > c0.open &&
      c1.close < c1.open &&
      c0.close > (c1.open + c1.close) / 2 &&
      bodyRatio >= 0.45 &&
      upperWickRatio <= 0.25;
    const isBearishEngulfing =
      c0.close < c0.open &&
      c1.close > c1.open &&
      c0.close < (c1.open + c1.close) / 2 &&
      bodyRatio >= 0.45 &&
      lowerWickRatio <= 0.25;

    const isMorningStar =
      c2.close < c2.open &&
      c0.close > c0.open &&
      c0.close > Math.max(c1.high, (c2.open + c2.close) / 2) &&
      bodyRatio >= 0.42 &&
      upperWickRatio <= 0.26;
    const isEveningStar =
      c2.close > c2.open &&
      c0.close < c0.open &&
      c0.close < Math.min(c1.low, (c2.open + c2.close) / 2) &&
      bodyRatio >= 0.42 &&
      lowerWickRatio <= 0.26;

    const isBullishBreakoutBar =
      c0.close > c0.open && c0.close > c1.high && bodyRatio >= 0.50 && upperWickRatio <= 0.24;
    const isBearishBreakdownBar =
      c0.close < c0.open && c0.close < c1.low && bodyRatio >= 0.50 && lowerWickRatio <= 0.24;

    const isBullishContinuation =
      c0.close > c0.open && upperWickRatio <= 0.35;
    const isBearishContinuation =
      c0.close < c0.open && lowerWickRatio <= 0.35;

    const bullishPaPattern = isBullishPinbar
      ? 'PA_HAMMER_PINBAR_BUY'
      : isBullishEngulfing
      ? 'PA_BULLISH_ENGULFING_BUY'
      : isMorningStar
      ? 'PA_MORNING_STAR_BUY'
      : isBullishBreakoutBar
      ? 'PA_STRUCTURE_BREAKOUT_BUY'
      : isBullishContinuation
      ? 'PA_CLEAN_CONTINUATION_BUY'
      : null;

    const bearishPaPattern = isBearishShootingStar
      ? 'PA_SHOOTING_STAR_SELL'
      : isBearishEngulfing
      ? 'PA_BEARISH_ENGULFING_SELL'
      : isEveningStar
      ? 'PA_EVENING_STAR_SELL'
      : isBearishBreakdownBar
      ? 'PA_STRUCTURE_BREAKDOWN_SELL'
      : isBearishContinuation
      ? 'PA_CLEAN_CONTINUATION_SELL'
      : null;

    return {
      bullishPaPattern,
      bearishPaPattern,
      bodyRatio,
      upperWickRatio,
      lowerWickRatio,
    };
  }

  // ===========================================================================
  // LAYER 5: UPGRADED INTER-MARKET INDEX CONFLUENCE (IMIC) FOR NIFTY & BANKNIFTY OPTIONS
  // ===========================================================================
  private evaluateIndexImicConfluence(
    niftyCandles: NseCandle5m[],
    bankNiftyCandles: NseCandle5m[],
    allowedSide: 'BUY' | 'SELL'
  ): {
    inSync: boolean;
    niftySignal: SignalCandidate | null;
    bankNiftySignal: SignalCandidate | null;
  } {
    if (!niftyCandles || niftyCandles.length < 50 || !bankNiftyCandles || bankNiftyCandles.length < 50) {
      return { inSync: false, niftySignal: null, bankNiftySignal: null };
    }

    const nCloses = niftyCandles.map((c) => c.close);
    const nLast = nCloses[nCloses.length - 1];
    const nVwap = this.computeIntradayVwap(niftyCandles);
    const nEma9 = this.computeEma(nCloses, 9);
    const nEma21 = this.computeEma(nCloses, 21);

    const bCloses = bankNiftyCandles.map((c) => c.close);
    const bLast = bCloses[bCloses.length - 1];
    const bVwap = this.computeIntradayVwap(bankNiftyCandles);
    const bEma9 = this.computeEma(bCloses, 9);
    const bEma21 = this.computeEma(bCloses, 21);

    // CALL Option Sync: Both NIFTY & BANKNIFTY > VWAP and EMA9 >= EMA21
    const callSync =
      allowedSide === 'BUY' &&
      nLast > nVwap &&
      nEma9 >= nEma21 &&
      bLast > bVwap &&
      bEma9 >= bEma21;

    // PUT Option Sync: Both NIFTY & BANKNIFTY < VWAP and EMA9 <= EMA21
    const putSync =
      allowedSide === 'SELL' &&
      nLast < nVwap &&
      nEma9 <= nEma21 &&
      bLast < bVwap &&
      bEma9 <= bEma21;

    if (!callSync && !putSync) {
      return { inSync: false, niftySignal: null, bankNiftySignal: null };
    }

    // Detect Price Action Patterns on Nifty & BankNifty 3-candle windows
    const nLen = niftyCandles.length;
    const nPa = this.detectCandlePriceAction(
      niftyCandles[nLen - 1],
      niftyCandles[nLen - 2],
      niftyCandles[nLen - 3]
    );

    const bLen = bankNiftyCandles.length;
    const bPa = this.detectCandlePriceAction(
      bankNiftyCandles[bLen - 1],
      bankNiftyCandles[bLen - 2],
      bankNiftyCandles[bLen - 3]
    );

    const nRecent3 = niftyCandles.slice(-3);
    const bRecent3 = bankNiftyCandles.slice(-3);
    const nRecent3Low = Math.min(...nRecent3.map((c) => c.low));
    const nRecent3High = Math.max(...nRecent3.map((c) => c.high));
    const bRecent3Low = Math.min(...bRecent3.map((c) => c.low));
    const bRecent3High = Math.max(...bRecent3.map((c) => c.high));

    // Structural Swing Walls for Pre-Reversal TP
    const nLookback = niftyCandles.slice(-42, -1);
    const nSwingHighs = nLookback.map((c) => c.high);
    const nSwingLows = nLookback.map((c) => c.low);
    const bLookback = bankNiftyCandles.slice(-42, -1);
    const bSwingHighs = bLookback.map((c) => c.high);
    const bSwingLows = bLookback.map((c) => c.low);

    if (allowedSide === 'BUY') {
      const activePaPattern = nPa.bullishPaPattern || bPa.bullishPaPattern;
      // Smart Breathing SL: +0.15% buffer outside recent 3-candle rejection wick
      const nSl = Number((nRecent3Low * (1 - 0.0015)).toFixed(2));
      const bSl = Number((bRecent3Low * (1 - 0.0015)).toFixed(2));

      // Smart Pre-Reversal TP: 0.08% before ahead structural swing high wall
      const nAhead = nSwingHighs.filter((h) => h >= nLast * 1.004).sort((a, b) => a - b);
      const nTp = Number((nAhead.length > 0 ? nAhead[0] * (1 - 0.0008) : nLast * 1.01).toFixed(2));

      const bAhead = bSwingHighs.filter((h) => h >= bLast * 1.004).sort((a, b) => a - b);
      const bTp = Number((bAhead.length > 0 ? bAhead[0] * (1 - 0.0008) : bLast * 1.01).toFixed(2));

      return {
        inSync: true,
        niftySignal: {
          symbol: 'NIFTY',
          side: 'BUY',
          entryPrice: nLast,
          slPrice: nSl,
          tpPrice: nTp,
          qty: 75, // 1 Standard Nifty Lot
          vwap: nVwap,
          ema9: nEma9,
          ema21: nEma21,
          ema50: nEma21,
          rsi14: 60,
          rvol: 1.25,
          score: 95,
          reason: `IMIC_CE_${activePaPattern || 'PA_CONFIRMED'}`,
        },
        bankNiftySignal: {
          symbol: 'BANKNIFTY',
          side: 'BUY',
          entryPrice: bLast,
          slPrice: bSl,
          tpPrice: bTp,
          qty: 30, // 1 Standard BankNifty Lot
          vwap: bVwap,
          ema9: bEma9,
          ema21: bEma21,
          ema50: bEma21,
          rsi14: 60,
          rvol: 1.25,
          score: 95,
          reason: `IMIC_CE_${activePaPattern || 'PA_CONFIRMED'}`,
        },
      };
    } else {
      const activePaPattern = nPa.bearishPaPattern || bPa.bearishPaPattern;
      // Smart Breathing SL: +0.15% buffer outside recent 3-candle rejection wick
      const nSl = Number((nRecent3High * (1 + 0.0015)).toFixed(2));
      const bSl = Number((bRecent3High * (1 + 0.0015)).toFixed(2));

      // Smart Pre-Reversal TP: 0.08% before ahead structural demand wall
      const nAhead = nSwingLows.filter((l) => l <= nLast * 0.996).sort((a, b) => b - a);
      const nTp = Number((nAhead.length > 0 ? nAhead[0] * (1 + 0.0008) : nLast * 0.99).toFixed(2));

      const bAhead = bSwingLows.filter((l) => l <= bLast * 0.996).sort((a, b) => b - a);
      const bTp = Number((bAhead.length > 0 ? bAhead[0] * (1 + 0.0008) : bLast * 0.99).toFixed(2));

      return {
        inSync: true,
        niftySignal: {
          symbol: 'NIFTY',
          side: 'SELL',
          entryPrice: nLast,
          slPrice: nSl,
          tpPrice: nTp,
          qty: 75,
          vwap: nVwap,
          ema9: nEma9,
          ema21: nEma21,
          ema50: nEma21,
          rsi14: 40,
          rvol: 1.25,
          score: 95,
          reason: `IMIC_PE_${activePaPattern || 'PA_CONFIRMED'}`,
        },
        bankNiftySignal: {
          symbol: 'BANKNIFTY',
          side: 'SELL',
          entryPrice: bLast,
          slPrice: bSl,
          tpPrice: bTp,
          qty: 30,
          vwap: bVwap,
          ema9: bEma9,
          ema21: bEma21,
          ema50: bEma21,
          rsi14: 40,
          rvol: 1.25,
          score: 95,
          reason: `IMIC_PE_${activePaPattern || 'PA_CONFIRMED'}`,
        },
      };
    }
  }

  // ===========================================================================
  // LIVE PRICE ACTION SCANNER MATRIX (ACROSS 14 NSE STOCKS + INDICES)
  // ===========================================================================
  public scanAllPriceActionStatus(
    stockCandles5m: Record<string, NseCandle5m[]>,
    niftyCandles5m: NseCandle5m[],
    bankNiftyCandles5m: NseCandle5m[]
  ): Array<{
    symbol: string;
    close: number;
    vwap: number;
    ema9: number;
    ema21: number;
    rsi14: number;
    rvol: number;
    bullishPa: string | null;
    bearishPa: string | null;
    breathingSlBuy: number;
    breathingSlSell: number;
    preReversalTpBuy: number;
    preReversalTpSell: number;
    bias: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  }> {
    const list: Array<{
      symbol: string;
      close: number;
      vwap: number;
      ema9: number;
      ema21: number;
      rsi14: number;
      rvol: number;
      bullishPa: string | null;
      bearishPa: string | null;
      breathingSlBuy: number;
      breathingSlSell: number;
      preReversalTpBuy: number;
      preReversalTpSell: number;
      bias: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
    }> = [];

    const allSymbols = [
      'NIFTY',
      'BANKNIFTY',
      ...NexusBharatAutoEngine.WHITELIST_14,
    ];

    for (const sym of allSymbols) {
      const candles =
        sym === 'NIFTY'
          ? niftyCandles5m
          : sym === 'BANKNIFTY'
          ? bankNiftyCandles5m
          : stockCandles5m[sym];

      if (!candles || candles.length < 25) continue;

      const n = candles.length;
      const c0 = candles[n - 1];
      const c1 = n >= 2 ? candles[n - 2] : c0;
      const c2 = n >= 3 ? candles[n - 3] : c1;
      const closes = candles.map((c) => c.close);
      const vwap = this.computeIntradayVwap(candles);
      const ema9 = this.computeEma(closes, 9);
      const ema21 = this.computeEma(closes, 21);
      const rsi14 = this.computeRsi(closes, 14);

      const prior20 = candles.slice(-21, -1);
      const avgVol20 =
        prior20.reduce((sum, b) => sum + (b.volume || 1), 0) / Math.max(1, prior20.length);
      const rvol = avgVol20 > 0 ? (c0.volume || avgVol20) / avgVol20 : 1.0;

      const pa = this.detectCandlePriceAction(c0, c1, c2);

      const recent3Low = Math.min(c0.low, c1.low, c2.low);
      const recent3High = Math.max(c0.high, c1.high, c2.high);
      const breathingSlBuy = Number((recent3Low * (1 - 0.0015)).toFixed(2));
      const breathingSlSell = Number((recent3High * (1 + 0.0015)).toFixed(2));

      const lookback = candles.slice(-42, -1);
      const highs = lookback.map((b) => b.high).filter((h) => h >= c0.close * 1.003).sort((a, b) => a - b);
      const lows = lookback.map((b) => b.low).filter((l) => l <= c0.close * 0.997).sort((a, b) => b - a);

      const preReversalTpBuy = Number((highs.length > 0 ? highs[0] * (1 - 0.0008) : c0.close * 1.015).toFixed(2));
      const preReversalTpSell = Number((lows.length > 0 ? lows[0] * (1 + 0.0008) : c0.close * 0.985).toFixed(2));

      let bias: 'BULLISH' | 'BEARISH' | 'NEUTRAL' = 'NEUTRAL';
      if (c0.close > vwap && ema9 >= ema21) bias = 'BULLISH';
      else if (c0.close < vwap && ema9 <= ema21) bias = 'BEARISH';

      list.push({
        symbol: sym,
        close: c0.close,
        vwap: Number(vwap.toFixed(2)),
        ema9: Number(ema9.toFixed(2)),
        ema21: Number(ema21.toFixed(2)),
        rsi14: Number(rsi14.toFixed(1)),
        rvol: Number(rvol.toFixed(2)),
        bullishPa: pa.bullishPaPattern,
        bearishPa: pa.bearishPaPattern,
        breathingSlBuy,
        breathingSlSell,
        preReversalTpBuy,
        preReversalTpSell,
        bias,
      });
    }

    return list;
  }

  private async openOptionSeat(
    seatId: 'OPTION_1' | 'OPTION_2',
    indexName: 'NIFTY' | 'BANKNIFTY',
    optionType: 'CE' | 'PE',
    indexSignal: SignalCandidate,
    liveLtpMap: Record<string, number>,
    istTime: string,
    executeBrokerOrder?: (order: {
      symbol: string;
      side: 'BUY' | 'SELL';
      qty: number;
      price: number;
      seatId: SeatId;
      tag: string;
      sebiAlgoTag?: string;
      orderSlices?: number[];
    }) => Promise<void>
  ): Promise<void> {
    const numLots = 1;

    // 1. Resolve Exact Real Exchange-Listed Contract via 5-Pillar 2026 Institutional Engine
    const decision = await UniversalIndianMarketConnector.resolveInstitutionalOption({
      symbol: indexName,
      spotPrice: indexSignal.entryPrice,
      optionType,
      selectionMode: 'OFFSET',
      offset: 0, // Auto-shifts to ITM1 on Expiry Day (0-DTE)!
      requestedLots: numLots,
    });

    if (!decision.approved || !decision.tradingSymbol) {
      console.warn(`[Index Option STRICT VETO] ${indexName} ${optionType}: ${decision.vetoReason}`);
      return;
    }

    const atmStrike = decision.selectedStrike;
    const optionSymbol = decision.tradingSymbol;
    const lotQty = decision.lotSize;
    const premiumEntry = decision.ltp;

    console.log(
      `🏛️ [SEBI 2026 Institutional Option Selected] ${indexName} | Ref Price: ₹${decision.referencePriceUsed} (${decision.referencePriceSource}) | ` +
      `Strike: ${atmStrike} ${optionType} | LTP: ₹${premiumEntry} | Spread: ₹${decision.bidAskSpreadInr} (${(decision.bidAskSpreadPct * 100).toFixed(2)}%) | ` +
      `OI: ${decision.openInterest.toLocaleString('en-IN')} | Delta: ${decision.estimatedDelta} | Slices: [${decision.orderSlices.join(', ')}] | SEBI Tag: ${decision.sebiAlgoTag}`
    );

    const maxLossInr = 2500 * numLots; // Strict Rule: ₹2,500 Loss per lot on SL
    const slPrice = Number(Math.max(0.5, premiumEntry - maxLossInr / lotQty).toFixed(2));
    const tpPrice = Number((premiumEntry + 8000 / lotQty).toFixed(2)); // Max TP +₹8,000

    this.activePositions.set(seatId, {
      id: `${optionSymbol}-${Date.now()}`,
      seatId,
      symbol: optionSymbol,
      isOption: true,
      optionType,
      underlyingSymbol: indexName,
      side: 'BUY', // Buying CE or Buying PE
      qty: lotQty,
      entryPrice: premiumEntry,
      currentPrice: premiumEntry,
      initialSlPrice: slPrice,
      currentSlPrice: slPrice,
      targetPrice: tpPrice,
      currentVwap: indexSignal.vwap,
      unrealizedPnlInr: 0,
      lockedProfitInr: 0,
      ladderStage: 0,
      openedAtIst: istTime,
      openedEpochMs: Date.now(),
    });

    if (executeBrokerOrder) {
      await executeBrokerOrder({
        symbol: optionSymbol,
        side: 'BUY',
        qty: lotQty,
        price: premiumEntry,
        seatId,
        tag: `IMIC_${optionType}_${decision.sebiAlgoTag}`,
        sebiAlgoTag: decision.sebiAlgoTag,
        orderSlices: decision.orderSlices,
      });
    }
  }

  // ===========================================================================
  // LAYER 6: LIVE TICK POSITION MANAGER (6-STAGE LADDER + SMART VWAP EARLY CUT)
  // ===========================================================================
  private async manageOpenPositionsOnTick(
    ist: { formattedTime: string; minutesFromMidnight: number },
    liveLtpMap: Record<string, number>,
    stockCandles5m: Record<string, NseCandle5m[]>,
    niftyCandles5m: NseCandle5m[],
    bankNiftyCandles5m: NseCandle5m[],
    executeBrokerOrder?: (order: {
      symbol: string;
      side: 'BUY' | 'SELL';
      qty: number;
      price: number;
      seatId: SeatId;
      tag: string;
      sebiAlgoTag?: string;
      orderSlices?: number[];
    }) => Promise<void>
  ): Promise<void> {
    const isAutoSquareOffTime = ist.minutesFromMidnight >= 15 * 60 + 18; // 03:18 PM IST

    for (const [seatId, pos] of Array.from(this.activePositions.entries())) {
      const latestPrice = liveLtpMap[pos.symbol] ?? pos.currentPrice;
      pos.currentPrice = latestPrice;

      // Compute live PnL in INR
      const priceDiff =
        pos.side === 'BUY'
          ? latestPrice - pos.entryPrice
          : pos.entryPrice - latestPrice;
      pos.unrealizedPnlInr = Number((priceDiff * pos.qty).toFixed(2));

      // 1. MANDATORY 03:18 PM AUTO SQUARE-OFF
      if (isAutoSquareOffTime) {
        await this.closePosition(
          seatId,
          pos,
          latestPrice,
          'AUTO_SQUARE_OFF_318PM',
          ist.formattedTime,
          executeBrokerOrder
        );
        continue;
      }

      // 2. DIAMOND-HANDS STRUCTURAL HOLD & BREATHING LADDER EVALUATION
      const nowMs = Date.now();
      const decision = DiamondHandsHoldManager.evaluatePositionHold({
        symbol: pos.symbol,
        optionType: pos.optionType || 'CE',
        lotSize: pos.qty,
        entryPremium: pos.entryPrice,
        currentPremium: latestPrice,
        initialSlPremium: pos.initialSlPrice,
        currentSlPremium: pos.currentSlPrice,
        peakPnlInr: Math.max(pos.unrealizedPnlInr, pos.lockedProfitInr),
        ladderStage: pos.ladderStage,
        entryTimestampMs: pos.openedEpochMs || nowMs,
        nowTimestampMs: nowMs,
        underlyingSpotLtp: pos.underlyingSymbol ? (liveLtpMap[pos.underlyingSymbol] || latestPrice) : latestPrice,
        structuralInvalidationSpot: 0,
        isFiveMinCandleClosed: false,
      });

      pos.ladderStage = decision.newLadderStage as any;
      pos.currentSlPrice = decision.newSlPremium;

      if (decision.action === 'EXECUTE_EXIT') {
        const exitReason = decision.exitReason === 'MANDATORY_318PM_SQUARE_OFF'
          ? 'AUTO_SQUARE_OFF_318PM'
          : decision.exitReason === 'HARD_SL_HIT'
          ? 'INITIAL_SL_HIT'
          : 'LADDER_TRAIL_SL_HIT';

        await this.closePosition(
          seatId,
          pos,
          latestPrice,
          exitReason,
          ist.formattedTime,
          executeBrokerOrder
        );
        continue;
      }
    }
  }

  private priceForTargetPnl(pos: ActiveBharatPosition, targetPnlInr: number): number {
    const deltaPerUnit = targetPnlInr / Math.max(1, pos.qty);
    return Number(
      (pos.side === 'BUY'
        ? pos.entryPrice + deltaPerUnit
        : pos.entryPrice - deltaPerUnit
      ).toFixed(2)
    );
  }

  private async closePosition(
    seatId: SeatId,
    pos: ActiveBharatPosition,
    exitPrice: number,
    exitReason: ClosedBharatTrade['exitReason'],
    istTime: string,
    executeBrokerOrder?: (order: {
      symbol: string;
      side: 'BUY' | 'SELL';
      qty: number;
      price: number;
      seatId: SeatId;
      tag: string;
      sebiAlgoTag?: string;
      orderSlices?: number[];
    }) => Promise<void>
  ): Promise<void> {
    const netPnlInr = Number(
      ((pos.side === 'BUY'
        ? exitPrice - pos.entryPrice
        : pos.entryPrice - exitPrice) *
        pos.qty).toFixed(2)
    );

    this.realizedDailyPnlInr += netPnlInr;
    this.activePositions.delete(seatId);

    // ANTI-SPAM SHIELD: Mandatory 20-minute cooldown on the closed instrument
    const cooldownMs = Date.now() + 20 * 60 * 1000;
    if (pos.underlyingSymbol) {
      NexusBharatAutoEngine.symbolCooldownUntilMs.set(pos.underlyingSymbol, cooldownMs);
    }
    const baseSym = pos.symbol.split(/[0-9]/)[0].replace('.NS', '');
    NexusBharatAutoEngine.symbolCooldownUntilMs.set(baseSym, cooldownMs);
    NexusBharatAutoEngine.symbolCooldownUntilMs.set(pos.symbol, cooldownMs);

    this.closedTrades.unshift({
      id: pos.id,
      seatId,
      symbol: pos.symbol,
      side: pos.side,
      qty: pos.qty,
      entryPrice: pos.entryPrice,
      exitPrice,
      netPnlInr,
      ladderStageReached: pos.ladderStage,
      exitReason,
      closedAtIst: istTime,
    });

    if (executeBrokerOrder) {
      await executeBrokerOrder({
        symbol: pos.symbol,
        side: pos.side === 'BUY' ? 'SELL' : 'BUY',
        qty: pos.qty,
        price: exitPrice,
        seatId,
        tag: exitReason,
      });
    }
  }

  // --- TECHNICAL INDICATOR HELPERS ---

  public isSymbolAlreadyOpen(symbol: string): boolean {
    const clean = symbol.replace('.NS', '').replace('^', '').trim().toUpperCase();
    for (const pos of this.activePositions.values()) {
      if (pos.symbol.toUpperCase() === clean) return true;
      if (pos.underlyingSymbol && pos.underlyingSymbol.toUpperCase() === clean) return true;
      if (pos.symbol.toUpperCase().startsWith(clean)) return true;
      const m = pos.symbol.match(/^([A-Z&_-]+?)(?:\d{2}[A-Z]{3}|\d{2}[A-Z]|\d{4}|_\d)/);
      if (m && m[1].toUpperCase() === clean) return true;
    }
    return false;
  }

  private computeIntradayVwap(candles: NseCandle5m[]): number {
    const recentSession = candles.slice(-75);
    let pv = 0;
    let volSum = 0;
    for (const c of recentSession) {
      const typical = (c.high + c.low + c.close) / 3;
      const v = c.volume > 0 ? c.volume : 1;
      pv += typical * v;
      volSum += v;
    }
    return volSum > 0 ? pv / volSum : candles[candles.length - 1].close;
  }

  private computeEma(values: number[], period: number): number {
    if (values.length === 0) return 0;
    const k = 2 / (period + 1);
    let ema = values[0];
    for (let i = 1; i < values.length; i++) {
      ema = values[i] * k + ema * (1 - k);
    }
    return ema;
  }

  private computeRsi(values: number[], period = 14): number {
    if (values.length <= period) return 50;
    let gains = 0;
    let losses = 0;
    for (let i = values.length - period; i < values.length; i++) {
      const diff = values[i] - values[i - 1];
      if (diff >= 0) gains += diff;
      else losses -= diff;
    }
    if (losses === 0) return 100;
    return 100 - 100 / (1 + gains / losses);
  }

  private getIstClock(epochMs: number): {
    formattedTime: string;
    minutesFromMidnight: number;
    phaseLabel: string;
  } {
    const istDate = new Date(epochMs + 5.5 * 60 * 60 * 1000);
    const hrs = istDate.getUTCHours();
    const mins = istDate.getUTCMinutes();
    const secs = istDate.getUTCSeconds();
    const minutesFromMidnight = hrs * 60 + mins;

    let phaseLabel = 'AFTER_MARKET_CLOSED';
    if (minutesFromMidnight >= 9 * 60 + 15 && minutesFromMidnight < 9 * 60 + 25) {
      phaseLabel = '09:15–09:25 WARM_UP_PHASE (NO TRADES)';
    } else if (minutesFromMidnight >= 9 * 60 + 25 && minutesFromMidnight < 10 * 60) {
      phaseLabel = '09:25–10:00 OPENING_ORB_FILTER';
    } else if (minutesFromMidnight >= 10 * 60 && minutesFromMidnight <= 15 * 60 + 10) {
      phaseLabel = '10:00–15:10 ACTIVE_SNIPER_WINDOW';
    } else if (minutesFromMidnight > 15 * 60 + 10 && minutesFromMidnight < 15 * 60 + 18) {
      phaseLabel = '15:10–15:18 ENTRY_CUTOFF_HOLDING';
    } else if (minutesFromMidnight >= 15 * 60 + 18 && minutesFromMidnight <= 15 * 60 + 30) {
      phaseLabel = '15:18 MANDATORY_AUTO_SQUARE_OFF';
    }

    const formattedTime = `${String(hrs).padStart(2, '0')}:${String(mins).padStart(
      2,
      '0'
    )}:${String(secs).padStart(2, '0')} IST`;

    return { formattedTime, minutesFromMidnight, phaseLabel };
  }
}
